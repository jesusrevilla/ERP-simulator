"""
Suite de Pruebas Automatizadas (Base de Datos #305 + Agente IA #306)
Matrícula: 178084
"""

from pathlib import Path
import sys
import psycopg2
import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
BD_DIR = ROOT_DIR / "Recibos_y_entregas" / "178084_cuarentena_rtv"
IA_DIR = ROOT_DIR / "Inventario" / "178084_agente_atp_fefo"

sys.path.insert(0, str(BD_DIR))
sys.path.insert(0, str(IA_DIR))

import db_pipeline_178084 as db_pipe
from agente_atp_fefo_178084 import InventoryFEFOAgent


@pytest.fixture(scope="module")
def entorno_limpio():
    """Inicializa PostgreSQL, Neo4j y MongoDB con los datos semilla del proyecto."""
    db_pipe.load_postgres()
    db_pipe.sync_neo4j()
    db_pipe.seed_mongodb_inspections()
    yield


# ============================================================================
# PRUEBAS DE BASE DE DATOS (#305 - Recibos y Entregas: Cuarentena, Lotes y RTV)
# ============================================================================

def test_carga_poliglota_postgres_neo4j_mongo(entorno_limpio):
    """Verifica que las 3 bases de datos contengan los registros esperados tras el pipeline."""
    # 1. PostgreSQL: 3 devoluciones RTV creadas automáticamente por sp_dictaminar_lote
    conn = db_pipe.get_postgres_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM devoluciones_rtv_178084")
            total_rtv = cur.fetchone()[0]
            assert total_rtv == 3
    finally:
        conn.close()

    # 2. Neo4j: nodos sincronizados con etiqueta proyecto='178084'
    driver = db_pipe.get_neo4j_driver()
    try:
        with driver.session() as session:
            rec = session.run(
                "MATCH (l:Lote {proyecto: '178084'}) RETURN count(l) AS total"
            ).single()
            assert rec["total"] == 8
    finally:
        driver.close()

    # 3. MongoDB: 8 bitácoras de inspección de calidad
    client, db = db_pipe.get_mongo_db()
    try:
        total_docs = db["inspecciones_calidad_178084"].count_documents({})
        assert total_docs == 8
    finally:
        client.close()


def test_bloqueo_entrega_lote_en_cuarentena(entorno_limpio):
    """El trigger debe impedir despachar un lote que sigue en CUARENTENA (LOT-SSD-Q01)."""
    conn = db_pipe.get_postgres_conn()
    try:
        with conn.cursor() as cur:
            with pytest.raises(psycopg2.Error, match="CUARENTENA"):
                cur.execute(
                    """
                    INSERT INTO entregas_178084
                        (folio_entrega, cliente, lote_id, articulo_id, cantidad_entregada)
                    VALUES ('ENT-ERR-Q01', 'Cliente Test', 7, 3, 5)
                    """
                )
        conn.rollback()
    finally:
        conn.close()


def test_bloqueo_entrega_lote_vencido(entorno_limpio):
    """El trigger debe impedir despachar un lote cuya fecha de caducidad ya expiró."""
    conn = db_pipe.get_postgres_conn()
    try:
        with conn.cursor() as cur:
            with pytest.raises(psycopg2.Error, match="vencido"):
                cur.execute(
                    """
                    INSERT INTO entregas_178084
                        (folio_entrega, cliente, lote_id, articulo_id, cantidad_entregada)
                    VALUES ('ENT-ERR-EXP', 'Cliente Test', 5, 2, 2)
                    """
                )
        conn.rollback()
    finally:
        conn.close()


def test_bloqueo_entrega_stock_insuficiente(entorno_limpio):
    """El trigger debe impedir entregas que superen el stock_disponible del artículo."""
    conn = db_pipe.get_postgres_conn()
    try:
        with conn.cursor() as cur:
            with pytest.raises(psycopg2.Error, match="stock disponible insuficiente"):
                cur.execute(
                    """
                    INSERT INTO entregas_178084
                        (folio_entrega, cliente, lote_id, articulo_id, cantidad_entregada)
                    VALUES ('ENT-ERR-STK', 'Cliente Test', 6, 3, 999)
                    """
                )
        conn.rollback()
    finally:
        conn.close()


def test_trigger_cuarentena_y_sp_dictaminar_lote(entorno_limpio):
    """Valida flujo completo: ingreso a cuarentena -> dictamen parcial -> liberación + RTV."""
    conn = db_pipe.get_postgres_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT stock_disponible, stock_cuarentena FROM articulos_178084 WHERE articulo_id = 4"
            )
            disp_antes, cuar_antes = cur.fetchone()

            # 1. Insertar lote nuevo -> debe sumar solo a stock_cuarentena
            cur.execute(
                """
                INSERT INTO lotes_inspeccion_178084
                    (numero_lote, recepcion_id, articulo_id, cantidad_recibida, fecha_caducidad)
                VALUES ('LOT-TEST-99', 1, 4, 20, CURRENT_DATE + INTERVAL '60 days')
                RETURNING lote_id
                """
            )
            nuevo_lote_id = cur.fetchone()[0]

            cur.execute(
                "SELECT stock_disponible, stock_cuarentena FROM articulos_178084 WHERE articulo_id = 4"
            )
            disp_mid, cuar_mid = cur.fetchone()
            assert disp_mid == disp_antes
            assert cuar_mid == cuar_antes + 20

            # 2. Dictaminar 14 aprobadas y 6 rechazadas -> libera 14 y genera RTV por 6
            cur.execute(
                "CALL sp_dictaminar_lote(%s, 14, 6, 'Prueba automatizada de rechazo')",
                (nuevo_lote_id,),
            )

            cur.execute(
                "SELECT stock_disponible, stock_cuarentena FROM articulos_178084 WHERE articulo_id = 4"
            )
            disp_despues, cuar_despues = cur.fetchone()
            assert disp_despues == disp_antes + 14
            assert cuar_despues == cuar_antes

            cur.execute(
                "SELECT folio_rtv, cantidad_devuelta FROM devoluciones_rtv_178084 WHERE lote_id = %s",
                (nuevo_lote_id,),
            )
            rtv = cur.fetchone()
            assert rtv == ("RTV-LOT-TEST-99", 6)

        # Revertir prueba de mutación para no alterar los datos base de las pruebas del agente
        conn.rollback()
    finally:
        conn.close()


# ============================================================================
# PRUEBAS DEL AGENTE DE IA (#306 - InventoryFEFOAgent: ATP, FEFO y Neo4j)
# ============================================================================

def test_agente_evaluacion_atp_fefo_y_proveedor_neo4j(entorno_limpio):
    """Valida las decisiones ATP, priorización FEFO, selección de proveedor y registro MongoDB."""
    agente = InventoryFEFOAgent(dias_alerta_fefo=30, tasa_minima_proveedor=80.0)
    reporte = agente.ejecutar(guardar_en_mongo=True)

    assert reporte["agente"] == "InventoryFEFOAgent"
    assert "mongo_document_id" in reporte

    por_sku = {e["sku"]: e for e in reporte["evaluaciones"]}

    # 1. SKU-BAT02: Backorder crítico (ATP = -5), recomienda PROV-01 (100% cumplimiento)
    bat = por_sku["SKU-BAT02"]
    assert bat["decision_atp"]["severidad"] == "CRITICO"
    assert bat["decision_atp"]["estado_atp"] == "QUIEBRE_BACKORDER"
    assert bat["decision_atp"]["atp"] == -5
    assert bat["decision_atp"]["cantidad_reabastecer"] == 35
    assert bat["decision_atp"]["proveedor_recomendado"]["codigo"] == "PROV-01"
    # Lote vencido detectado y excluido del despacho FEFO; LOT-BAT-01 priorizado primero
    acciones_fefo_bat = {a["numero_lote"]: a["accion"] for a in bat["alertas_fefo"]}
    assert acciones_fefo_bat["LOT-BAT-EXP"] == "BLOQUEAR_LOTE_VENCIDO"
    assert acciones_fefo_bat["LOT-BAT-01"] == "PRIORIZAR_DESPACHO_FEFO"
    assert [l["numero_lote"] for l in bat["plan_despacho_fefo"]] == ["LOT-BAT-01", "LOT-BAT-00"]

    # 2. SKU-SSD03: ATP bajo mínimo (5 < 15), pero con 25 en cuarentena -> escalamiento a Calidad
    ssd = por_sku["SKU-SSD03"]
    assert ssd["decision_atp"]["severidad"] == "ADVERTENCIA"
    assert ssd["decision_atp"]["estado_atp"] == "BAJO_MINIMO_CON_CUARENTENA"
    assert ssd["decision_atp"]["cantidad_reabastecer"] == 0

    # 3. SKU-PT01: ATP saludable (45 >= 20) con priorización FEFO LOT-PT-01 antes de LOT-PT-02
    pt = por_sku["SKU-PT01"]
    assert pt["decision_atp"]["estado_atp"] == "SALUDABLE"
    assert [l["numero_lote"] for l in pt["plan_despacho_fefo"]] == ["LOT-PT-01", "LOT-PT-02"]

    # 4. Verificar que la decisión quedó registrada en MongoDB
    client, db = db_pipe.get_mongo_db()
    try:
        count = db["decisiones_agente_178084"].count_documents({"proyecto": "178084"})
        assert count >= 1
    finally:
        client.close()