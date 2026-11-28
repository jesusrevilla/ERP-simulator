import math
import os
import pytest
import psycopg2
from neo4j import GraphDatabase

PG_CONFIG = {
    "host": os.getenv("PGHOST", "localhost"),
    "port": int(os.getenv("PGPORT", "5432")),
    "dbname": os.getenv("PGDATABASE", "erp_bom"),
    "user": os.getenv("PGUSER", "erp_user"),
    "password": os.getenv("PGPASSWORD", "erp_pass"),
}

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "erp_neo4j_pass")

FECHA_PRUEBA_PG = "2026-11-10 08:00:00+00"
FECHA_PRUEBA_NEO4J = "2026-11-10T08:00:00Z"


@pytest.fixture()
def pg_conn():
    conn = psycopg2.connect(**PG_CONFIG)
    yield conn
    conn.rollback()
    conn.close()


@pytest.fixture(scope="module")
def neo4j_driver():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    driver.verify_connectivity()
    yield driver
    driver.close()


def _agent_reference_pc001(demanda: float = 1.0):
    """Cálculo de referencia equivalente a BOMGraphExplosionAgent para PC001 (RN08 + PU09)."""
    gpu_exacta = 1.0 * demanda
    torn_exacta = (0.4 + 0.4) * demanda
    gpu_final = float(math.ceil(gpu_exacta))
    torn_final = float(math.ceil(torn_exacta))
    return {
        "GPU001": (round(gpu_exacta, 4), gpu_final, round(gpu_final * 500.0, 2)),
        "TORN-M3": (round(torn_exacta, 4), torn_final, round(torn_final * 0.10, 2)),
    }


def _neo4j_explode(driver, parent_sku: str, demanda: float = 1.0):
    cypher = """
    WITH $demanda AS demanda, datetime($fecha) AS fecha_demanda
    MATCH p = (root:BOMItem {sku: $sku, activo: true})-[:BOM_REQUIRES*1..10]->(mp:BOMItem {tipo_item: 'MP', activo: true})
    WHERE ALL(r IN relationships(p) WHERE r.estado = 'ACTIVO'
          AND r.fecha_inicio <= fecha_demanda
          AND (r.fecha_fin IS NULL OR fecha_demanda < r.fecha_fin))
      AND ALL(n IN nodes(p) WHERE n.activo = true)
    WITH mp, demanda,
         reduce(acc = 1.0, r IN relationships(p) |
           acc * ((r.cantidad * r.factor_uom) / (r.cantidad_base * (1.0 - r.scrap_merma)))
         ) AS factor_ruta
    WITH mp, demanda, sum(factor_ruta) AS factor_total
    WITH mp, (factor_total * demanda) AS bruta_exacta
    WITH mp, bruta_exacta,
         CASE WHEN mp.es_discreto THEN ceil(bruta_exacta) ELSE round(bruta_exacta, 4) END AS cantidad_final
    RETURN mp.sku AS mp_sku,
           round(bruta_exacta, 4) AS bruta,
           toFloat(cantidad_final) AS final,
           round(cantidad_final * mp.costo, 2) AS costo
    ORDER BY mp_sku
    """
    records, _, _ = driver.execute_query(
        cypher, sku=parent_sku, demanda=float(demanda), fecha=FECHA_PRUEBA_NEO4J
    )
    return {
        r["mp_sku"]: (round(float(r["bruta"]), 4), round(float(r["final"]), 4), round(float(r["costo"]), 2))
        for r in records
    }


def test_parity_pc001_agent_pg_neo4j(pg_conn, neo4j_driver):
    """Valida PU09 (0.4 + 0.4 = 0.8 -> ceil = 1) y paridad Agente == PostgreSQL == Neo4j."""
    expected_agent = _agent_reference_pc001(1.0)

    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT mp_sku, cantidad_bruta_exacta, cantidad_requerida_final, costo_total_estimado "
            "FROM fn_explode_bom_summarized('PC001', 1.0, %s);",
            (FECHA_PRUEBA_PG,),
        )
        pg_res = {
            row[0]: (round(float(row[1]), 4), round(float(row[2]), 4), round(float(row[3]), 2))
            for row in cur.fetchall()
        }

    neo_res = _neo4j_explode(neo4j_driver, "PC001", 1.0)

    assert pg_res == expected_agent
    assert neo_res == expected_agent


def test_parity_pc_pro_scrap_and_uom(pg_conn, neo4j_driver):
    """Valida RN08 (merma 20% y 25%), conversión UOM (G -> KG) y redondeo continuo vs discreto."""
    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT mp_sku, cantidad_bruta_exacta, cantidad_requerida_final, costo_total_estimado "
            "FROM fn_explode_bom_summarized('PC-PRO', 1.0, %s);",
            (FECHA_PRUEBA_PG,),
        )
        pg_res = {
            row[0]: (round(float(row[1]), 4), round(float(row[2]), 4), round(float(row[3]), 2))
            for row in cur.fetchall()
        }

    neo_res = _neo4j_explode(neo4j_driver, "PC-PRO", 1.0)

    assert pg_res == neo_res
    assert pg_res["PASTA-TER"] == (0.0125, 0.0125, 1.5)
    assert pg_res["TORN-M3"] == (9.0, 9.0, 0.9)
    assert pg_res["GPU001"] == (2.0, 2.0, 1000.0)


def test_cost_rollup_parity_pg_neo4j(pg_conn, neo4j_driver):
    """Valida que el Cost Roll-up multinivel coincida entre PostgreSQL y Neo4j."""
    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT parent_sku, costo_exacto_sin_ceil, costo_estandar_rollup "
            "FROM fn_bom_cost_rollup(%s);",
            (FECHA_PRUEBA_PG,),
        )
        pg_rollup = {
            row[0]: (round(float(row[1]), 4), round(float(row[2]), 2))
            for row in cur.fetchall()
        }

    cypher_rollup = """
    WITH datetime($fecha) AS fecha_demanda
    MATCH p = (root:BOMItem)-[:BOM_REQUIRES*1..10]->(mp:BOMItem {tipo_item: 'MP', activo: true})
    WHERE root.tipo_item IN ['PT', 'SE'] AND root.activo = true
      AND ALL(r IN relationships(p) WHERE r.estado = 'ACTIVO'
          AND r.fecha_inicio <= fecha_demanda
          AND (r.fecha_fin IS NULL OR fecha_demanda < r.fecha_fin))
    WITH root, mp,
         reduce(acc = 1.0, r IN relationships(p) |
           acc * ((r.cantidad * r.factor_uom) / (r.cantidad_base * (1.0 - r.scrap_merma)))
         ) AS factor_ruta
    WITH root, mp, sum(factor_ruta) AS bruta_mp
    WITH root, mp, bruta_mp,
         CASE WHEN mp.es_discreto THEN ceil(bruta_mp) ELSE round(bruta_mp, 4) END AS cant_final_mp
    WITH root.sku AS parent_sku,
         sum(bruta_mp * mp.costo) AS suma_exacta,
         sum(cant_final_mp * mp.costo) AS suma_rollup
    RETURN parent_sku, round(suma_exacta, 4) AS exacta, round(suma_rollup, 2) AS rollup
    """
    records, _, _ = neo4j_driver.execute_query(cypher_rollup, fecha=FECHA_PRUEBA_NEO4J)
    neo_rollup = {
        r["parent_sku"]: (round(float(r["exacta"]), 4), round(float(r["rollup"]), 2))
        for r in records
    }

    assert pg_rollup == neo_rollup
    assert pg_rollup["PC001"] == (500.08, 500.10)
    assert pg_rollup["PC-PRO"] == (1002.4, 1002.40)


def test_mrp_run_persistence_and_audit_trigger(pg_conn):
    """Valida persistencia atómica de EVT-MRP-201, payload BOM.Exploded y trigger en auditoria_bom."""
    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT run_id, estado_ejecucion, costo_total_estimado, payload_evento "
            "FROM fn_ejecutar_corrida_mrp('PC001', 1.0, %s, 'EVT-MRP-201-TEST');",
            (FECHA_PRUEBA_PG,),
        )
        run_id, estado, costo, payload = cur.fetchone()

        assert estado == "BOM.Exploded"
        assert float(costo) == 500.10
        assert payload["evento"] == "BOM.Exploded"
        assert len(payload["materiales_aplanados"]) == 2
        assert len(payload["versiones_resueltas"]) == 2

        cur.execute(
            "SELECT COUNT(*) FROM auditoria_bom "
            "WHERE entidad_afectada = 'mrp_explosion_runs' AND registro_id = %s;",
            (str(run_id),),
        )
        assert cur.fetchone()[0] >= 2  # INSERT + UPDATE registrados por trigger


def test_rejection_without_active_version_pu08(pg_conn):
    """Valida PU08: rechazo BOM.ExplosionRejected si solo hay BORRADOR o fecha fuera de vigencia."""
    with pg_conn.cursor() as cur:
        with pytest.raises(psycopg2.Error, match="BOM.ExplosionRejected"):
            cur.execute("SELECT * FROM fn_explode_bom_summarized('PT-SIN-VIG', 1.0, %s);", (FECHA_PRUEBA_PG,))
    pg_conn.rollback()

    with pg_conn.cursor() as cur:
        with pytest.raises(psycopg2.Error, match="BOM.ExplosionRejected"):
            cur.execute("SELECT * FROM fn_explode_bom_summarized('PC001', 1.0, '2025-06-01 00:00:00+00');")
    pg_conn.rollback()


def test_validation_rules_mp_parent_and_invalid_demand(pg_conn):
    """Valida RN01/RN-15 (MP no puede tener BOM) y demanda <= 0."""
    with pg_conn.cursor() as cur:
        with pytest.raises(psycopg2.Error, match="BOM.ValidationFailed"):
            cur.execute("SELECT * FROM fn_explode_bom_summarized('GPU001', 1.0, %s);", (FECHA_PRUEBA_PG,))
    pg_conn.rollback()

    with pg_conn.cursor() as cur:
        with pytest.raises(psycopg2.Error, match="BOM.ValidationFailed"):
            cur.execute("SELECT * FROM fn_explode_bom_summarized('PC001', 0, %s);", (FECHA_PRUEBA_PG,))
    pg_conn.rollback()


def test_where_used_financial_sensitivity_neo4j(neo4j_driver):
    """Valida análisis de impacto financiero (+15% en GPU001) sobre Knowledge Graph."""
    cypher = """
    WITH 'GPU001' AS mp_objetivo, 0.15 AS incremento_pct, datetime($fecha) AS fecha_demanda
    MATCH p = (pt:BOMItem {tipo_item: 'PT', activo: true})-[:BOM_REQUIRES*1..10]->(mp:BOMItem {sku: mp_objetivo})
    WHERE ALL(r IN relationships(p) WHERE r.estado = 'ACTIVO'
          AND r.fecha_inicio <= fecha_demanda
          AND (r.fecha_fin IS NULL OR fecha_demanda < r.fecha_fin))
    WITH pt, mp, incremento_pct,
         reduce(acc = 1.0, r IN relationships(p) |
           acc * ((r.cantidad * r.factor_uom) / (r.cantidad_base * (1.0 - r.scrap_merma)))
         ) AS factor_ruta
    WITH pt, mp, incremento_pct, sum(factor_ruta) AS bruta_mp
    WITH pt, mp, incremento_pct,
         CASE WHEN mp.es_discreto THEN ceil(bruta_mp) ELSE round(bruta_mp, 4) END AS cant_final
    RETURN pt.sku AS pt, round(cant_final * mp.costo * incremento_pct, 2) AS impacto
    """
    records, _, _ = neo4j_driver.execute_query(cypher, fecha=FECHA_PRUEBA_NEO4J)
    impacto = {r["pt"]: round(float(r["impacto"]), 2) for r in records}
    assert impacto == {"PC-PRO": 150.0, "PC001": 75.0}
