"""Pruebas del motor de programación y costeo planificado (184814 · Issue #300).

Requieren PostgreSQL. Las pruebas de Neo4j se omiten si no hay servidor.
Cada prueba corre dentro de una transacción que se deshace al final, así que
no dejan cambios en la base de prueba.

    pytest Rutas/184814-ProgramacionCosteo -v
"""

from __future__ import annotations

import os
from datetime import date
from decimal import Decimal
from pathlib import Path

import psycopg2
import pytest

AQUI = Path(__file__).parent
SCRIPTS = [
    AQUI.parent / "Scheme.sql",
    AQUI / "01_esquema_programacion.sql",
    AQUI / "02_datos_semilla.sql",
]
BD_PRUEBA = "rutas_184814_test"


def _params(dbname: str) -> dict:
    return dict(
        host=os.getenv("PGHOST", "localhost"),
        port=int(os.getenv("PGPORT", "5432")),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", "postgres"),
        dbname=dbname,
        client_encoding="UTF8",
    )


@pytest.fixture(scope="session")
def bd():
    """Crea una base limpia y carga Scheme.sql + los scripts de 184814."""
    try:
        admin = psycopg2.connect(**_params(os.getenv("PGDATABASE_ADMIN", "postgres")))
    except psycopg2.OperationalError as exc:
        pytest.skip(f"PostgreSQL no disponible: {exc}")
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute(f"DROP DATABASE IF EXISTS {BD_PRUEBA}")
        cur.execute(f"CREATE DATABASE {BD_PRUEBA} ENCODING 'UTF8' TEMPLATE template0")
    admin.close()

    conn = psycopg2.connect(**_params(BD_PRUEBA))
    conn.autocommit = True
    with conn.cursor() as cur:
        for script in SCRIPTS:
            cur.execute(script.read_text(encoding="utf-8"))
    conn.close()
    return _params(BD_PRUEBA)


@pytest.fixture
def cur(bd):
    conn = psycopg2.connect(**bd)
    cursor = conn.cursor()
    yield cursor
    conn.rollback()
    conn.close()


def _uno(cur, sql, params=None):
    cur.execute(sql, params)
    return cur.fetchone()


def _orden_id(cur, folio):
    return _uno(cur, "SELECT orden_produccion_id FROM orden_produccion WHERE folio = %s", (folio,))[0]


def _etapas(cur, folio):
    cur.execute(
        "SELECT secuencia, fecha_inicio, fecha_fin, estatus_etapa FROM vw_programa_ordenes "
        "WHERE folio = %s ORDER BY secuencia",
        (folio,),
    )
    return cur.fetchall()


# ---------------------------------------------------------------------
# Programación de fechas
# ---------------------------------------------------------------------

def test_fechas_de_30_gaming_pc(cur):
    """45.5 h, 30.3 h y 30.3 h a 8 h/día → 6, 4 y 4 días laborables."""
    assert [(s, i, f) for s, i, f, _ in _etapas(cur, "OP-2026-001")] == [
        (1, date(2026, 12, 1), date(2026, 12, 8)),
        (2, date(2026, 12, 9), date(2026, 12, 14)),
        (3, date(2026, 12, 16), date(2026, 12, 21)),
    ]
    assert _uno(cur, "SELECT fecha_fin FROM orden_produccion WHERE folio = 'OP-2026-001'")[0] \
        == date(2026, 12, 21)


def test_la_espera_retrasa_el_inicio_de_la_etapa(cur):
    """La etapa 3 tiene 1 día de espera: la 2 termina el 14 y la 3 inicia el 16."""
    etapas = _etapas(cur, "OP-2026-001")
    assert (etapas[2][1] - etapas[1][2]).days == 2


def test_ninguna_etapa_se_programa_en_dia_no_laborable(cur):
    cur.execute("SELECT count(*) FROM orden_etapa_carga_dia WHERE NOT fn_es_laborable(fecha)")
    assert cur.fetchone()[0] == 0
    cur.execute("SELECT count(*) FROM vw_programa_ordenes WHERE NOT fn_es_laborable(fecha_inicio)")
    assert cur.fetchone()[0] == 0


def test_se_salta_navidad_y_el_fin_de_semana(cur):
    """OP-2026-003, etapa 2: 24 de diciembre y luego 28 (25 festivo, 26-27 fin de semana)."""
    cur.execute(
        "SELECT c.fecha FROM orden_etapa_carga_dia c "
        "JOIN vw_programa_ordenes p USING (orden_produccion_etapa_id) "
        "WHERE p.folio = 'OP-2026-003' AND p.secuencia = 2 ORDER BY c.fecha"
    )
    assert [f for (f,) in cur.fetchall()] == [date(2026, 12, 24), date(2026, 12, 28)]


def test_las_etapas_quedan_dentro_del_horizonte_de_la_orden(cur):
    cur.execute(
        "SELECT count(*) FROM orden_produccion_etapa e "
        "JOIN orden_produccion o USING (orden_produccion_id) "
        "WHERE e.fecha_inicio < o.fecha_inicio OR e.fecha_fin > o.fecha_fin"
    )
    assert cur.fetchone()[0] == 0


def test_holgura_negativa_cuando_no_se_cumple_el_compromiso(cur):
    assert _uno(cur, "SELECT DISTINCT holgura_dias FROM vw_programa_ordenes "
                     "WHERE folio = 'OP-2026-001'")[0] == -3


def test_orden_liberada_requiere_motivo(cur):
    with pytest.raises(psycopg2.errors.RaiseException, match="motivo"):
        cur.execute("SELECT * FROM fn_programar_orden(%s)", (_orden_id(cur, "OP-2026-001"),))


def test_orden_cancelada_no_se_programa(cur):
    oid = _orden_id(cur, "OP-2026-002")
    cur.execute("UPDATE orden_produccion SET estatus = 'CANCELADA' WHERE orden_produccion_id = %s", (oid,))
    with pytest.raises(psycopg2.errors.RaiseException, match="CANCELADA"):
        cur.execute("SELECT * FROM fn_programar_orden(%s)", (oid,))


def test_retraso_recorre_las_etapas_siguientes(cur):
    cur.execute(
        "SELECT orden_produccion_etapa_id FROM vw_programa_ordenes "
        "WHERE folio = 'OP-2026-001' AND secuencia = 2"
    )
    etapa_id = cur.fetchone()[0]
    cur.execute("SELECT fecha_fin_nueva FROM fn_registrar_retraso(%s, 2, 'Falla en estación')",
                (etapa_id,))
    assert cur.fetchone()[0] == date(2026, 12, 23)
    etapas = _etapas(cur, "OP-2026-001")
    assert etapas[1][2:] == (date(2026, 12, 16), "EN_PROCESO")
    assert etapas[2][1:3] == (date(2026, 12, 18), date(2026, 12, 23))


# ---------------------------------------------------------------------
# Costeo planificado
# ---------------------------------------------------------------------

def test_costo_planificado_es_la_suma_de_sus_componentes(cur):
    """Material 690,000 + recurso 8,025 + centro 19,110 = 717,135."""
    oid = _orden_id(cur, "OP-2026-001")
    cur.execute("SELECT * FROM fn_calcular_costo_planificado(%s)", (oid,))
    material, recurso, centro, total = cur.fetchone()
    assert material == Decimal("690000")
    assert recurso == Decimal("8025")
    assert centro == Decimal("19110")
    assert total == material + recurso + centro
    assert _uno(cur, "SELECT costo_planificado FROM orden_produccion WHERE orden_produccion_id = %s",
                (oid,))[0] == total


def test_desviacion_por_cpu_mas_caro(cur):
    """30 CPU a 5,350 en vez de 5,200 → desviación de 4,500 (1.30 %)."""
    cur.execute("SELECT desviacion, desviacion_pct FROM vw_desviacion_costos "
                "WHERE nivel = 'ETAPA' AND folio = 'OP-2026-001' AND secuencia = 1")
    assert cur.fetchone() == (Decimal("4500.00"), Decimal("1.30"))


# ---------------------------------------------------------------------
# Carga por centro de trabajo
# ---------------------------------------------------------------------

def test_detecta_centro_sobreprogramado(cur):
    cur.execute("SELECT horas_programadas, sobrecargado, ordenes FROM vw_carga_centro_dia "
                "WHERE centro_trabajo = 'CT-ENS' AND fecha = '2026-12-03'")
    assert cur.fetchone() == (Decimal("16.00"), True, "OP-2026-001, OP-2026-002")


# ---------------------------------------------------------------------
# Reenumeración y bitácora
# ---------------------------------------------------------------------

def _hoja_borrador(cur) -> int:
    cur.execute(
        "INSERT INTO hoja_ruta (numero, descripcion, vigente_desde, creado_por) "
        "SELECT 'HR-PRUEBA', 'Hoja de prueba', DATE '2026-11-01', usuario_id "
        "FROM usuario WHERE correo = 'procesos@techassembly.mx' RETURNING hoja_ruta_id"
    )
    hoja = cur.fetchone()[0]
    cur.execute(
        "INSERT INTO hoja_ruta_operacion (hoja_ruta_id, secuencia, etapa_ruta_id, centro_trabajo_id, "
        "tiempo_ejecucion_min) SELECT %s, s, 1, 1, 10 FROM generate_series(1, 3) s",
        (hoja,),
    )
    return hoja


def test_reenumerar_abre_hueco_para_operacion_intermedia(cur):
    hoja = _hoja_borrador(cur)
    cur.execute("SELECT fn_reenumerar_secuencia(%s, 2)", (hoja,))
    assert cur.fetchone()[0] == 2
    cur.execute(
        "INSERT INTO hoja_ruta_operacion (hoja_ruta_id, secuencia, etapa_ruta_id, centro_trabajo_id, "
        "tiempo_ejecucion_min) VALUES (%s, 2, 2, 2, 5)",
        (hoja,),
    )
    cur.execute("SELECT secuencia FROM hoja_ruta_operacion WHERE hoja_ruta_id = %s ORDER BY 1", (hoja,))
    assert [s for (s,) in cur.fetchall()] == [1, 2, 3, 4]
    # tr_actualizar_tiempo_total (Scheme.sql) sigue funcionando
    assert _uno(cur, "SELECT tiempo_total_min FROM hoja_ruta WHERE hoja_ruta_id = %s", (hoja,))[0] \
        == Decimal("35")


def test_no_se_reenumera_una_hoja_liberada(cur):
    hoja = _uno(cur, "SELECT hoja_ruta_id FROM hoja_ruta WHERE numero = 'HR-GPC-001'")[0]
    with pytest.raises(psycopg2.errors.RaiseException, match="LIBERADA"):
        cur.execute("SELECT fn_reenumerar_secuencia(%s, 2)", (hoja,))


def test_cada_programacion_queda_en_la_bitacora(cur):
    cur.execute("SELECT count(*) FROM orden_programacion_log WHERE tipo = 'PROGRAMACION'")
    assert cur.fetchone()[0] == 3


def test_la_bitacora_no_se_puede_modificar(cur):
    with pytest.raises(psycopg2.errors.RaiseException, match="bitácora"):
        cur.execute("UPDATE orden_programacion_log SET motivo = 'cambio'")


def test_la_bitacora_no_se_puede_borrar(cur):
    with pytest.raises(psycopg2.errors.RaiseException, match="bitácora"):
        cur.execute("DELETE FROM orden_programacion_log")


# ---------------------------------------------------------------------
# Grafo en Neo4j
# ---------------------------------------------------------------------

@pytest.fixture(scope="module")
def grafo(bd):
    neo4j = pytest.importorskip("neo4j")
    import cargar_grafo as cg  # noqa: E402  (mismo directorio)

    driver = neo4j.GraphDatabase.driver(
        os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "password")),
    )
    try:
        driver.verify_connectivity()
    except Exception as exc:  # noqa: BLE001
        driver.close()
        pytest.skip(f"Neo4j no disponible: {exc}")

    conn = psycopg2.connect(**bd)
    programa = cg.leer_programa(conn)
    conn.close()
    conteo = cg.cargar_grafo(driver, programa)
    yield cg, driver, programa, conteo
    driver.close()


def test_grafo_tiene_ordenes_etapas_y_centros(grafo):
    _, _, _, conteo = grafo
    assert conteo["Orden"] == 3
    assert conteo["EtapaOrden"] == 9
    assert conteo["CentroTrabajo"] == 3
    assert conteo["Dia"] > 0


def test_grafo_propagacion_de_retraso(grafo):
    cg, driver, programa, _ = grafo
    etapa_1 = next(e["id"] for e in programa["etapas"]
                   if e["folio"] == "OP-2026-001" and e["secuencia"] == 1)
    filas = cg.consultar(driver, "propagacion_retraso", etapa_id=etapa_1)
    assert filas == [{"folio": "OP-2026-001", "etapas_afectadas": [2, 3]}]


def test_grafo_impacto_en_otras_ordenes(grafo):
    cg, driver, programa, _ = grafo
    etapa_1 = next(e["id"] for e in programa["etapas"]
                   if e["folio"] == "OP-2026-001" and e["secuencia"] == 1)
    filas = cg.consultar(driver, "impacto_en_otras_ordenes", etapa_id=etapa_1)
    assert {f["orden_en_riesgo"] for f in filas} >= {"OP-2026-002"}


def test_grafo_conflictos_centro_dia(grafo):
    cg, driver, _, _ = grafo
    filas = cg.consultar(driver, "conflictos_centro_dia")
    claves = {(f["centro_trabajo"], str(f["fecha"])) for f in filas}
    assert ("CT-ENS", "2026-12-03") in claves
    assert all(set(f["ordenes"]) == {"OP-2026-001", "OP-2026-002"} for f in filas)


def test_grafo_duracion_acumulada(grafo):
    cg, driver, _, _ = grafo
    filas = {f["folio"]: f for f in cg.consultar(driver, "duracion_acumulada")}
    assert filas["OP-2026-001"]["dias_laborables"] == 14
    assert filas["OP-2026-001"]["dias_espera"] == 1
    assert filas["OP-2026-001"]["dias_naturales"] == 21
