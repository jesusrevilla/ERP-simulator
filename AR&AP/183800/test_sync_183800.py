"""
test_sync_183800.py                                         Matrícula 183800

Pruebas del sincronizador PostgreSQL -> Neo4j (sync_postgres_neo4j.py).

Tres niveles (los dos últimos se omiten solos si no hay base de datos):
  1. Unitarias: no necesitan bases de datos.
  2. Con PostgreSQL real: crean un esquema temporal "test_183800" con las tablas
     del equipo + datos de prueba y lo borran al terminar.
  3. Con PostgreSQL y Neo4j reales: corren el sincronizador dos veces y
     comprueban que la segunda no crea nada (idempotencia).

Cómo ejecutarlas (desde la raíz del repositorio):
    pytest "AR&AP/183800" -v

Variables de entorno: POSTGRES_HOST/PORT/DB/USER/PASSWORD y
NEO4J_URI (o NEO4J_HOST/PORT), NEO4J_USER, NEO4J_PASSWORD.

Aviso: el nivel 3 escribe datos de prueba en el Neo4j al que se conecte.
Úsalo con una base de desarrollo. No borra nada que no haya creado la prueba.
"""
import json
import re
from datetime import datetime
from pathlib import Path

import pytest

import sync_postgres_neo4j as sync

CARPETA = Path(__file__).resolve().parent
AR_AP = CARPETA.parent
ESQUEMA_PRUEBA = "test_183800"
FUENTE_PRUEBA = "TEST183800"


# ======================================================================
# 1. Unitarias (sin bases de datos)
# ======================================================================
def _escribir_json(tmp_path, nombre, contenido):
    ruta = tmp_path / nombre
    ruta.write_text(json.dumps(contenido), encoding="utf-8")
    return ruta


def test_tres_formatos_de_eventos_se_normalizan(tmp_path):
    ruta = _escribir_json(tmp_path, "eventos.json", {"fuentes": [
        {"matricula": "111", "contenido": {"events": [{
            "eventId": "EVT-01", "timestamp": "2025-11-10T20:00:03-06:00", "eventType": "FacturaClienteCreada",
            "isa95": {"level": 4, "enterprise": "ERP", "site": "MX01", "area": "AR", "workCenter": "Ventas"},
            "actor": "Ventas", "document": {"folio": "FC-2001", "base": "PV-1001"}, "data": {"total": 1160.0}}]}},
        {"matricula": "222", "contenido": {"messages": [{
            "messageId": "MSG-003", "timestamp": "2026-11-04T11:30:00-06:00", "isa95Level": 3, "process": "AP",
            "eventType": "APInvoicePosted",
            "hierarchy": {"enterprise": "E", "site": "S1", "area": "ENS", "line": "L1"},
            "payload": {"apInvoiceId": "APINV-1", "purchaseOrderId": "PO-1", "goodsReceiptId": "GR-1"}}]}},
        {"matricula": "333", "contenido": {"empresa": "TECH", "eventos": [{
            "id": 7, "area": "Logística", "proceso": "AR", "evento": "Se entregan las computadoras",
            "control": "Comparar", "riesgo": "Cobrar antes", "timestamp": "2026-11-10 10:40:00"}]}},
    ]})
    a, b, c = sync.normalizar_eventos(ruta)

    assert (a["eventId"], a["folio"], a["folio_base"], a["nivel"], a["proceso"]) == \
           ("111-EVT-01", "FC-2001", "PV-1001", 4, "AR")
    assert a["area_clave"] == "ERP/MX01/AR/Ventas" and a["nivel_inferido"] is False

    assert (b["eventId"], b["nivel"], b["proceso"]) == ("222-MSG-003", 3, "AP")
    assert b["folio"] == "APINV-1"  # la factura tiene prioridad sobre la OC y la recepción
    assert b["area_clave"] == "E/S1/ENS/L1" and b["area_nombre"] == "L1"

    assert c["eventId"] == "333-7" and c["folio"] is None
    assert c["timestamp"] == "2026-11-10T10:40:00-06:00"  # sin zona -> UTC-06:00
    assert c["nivel"] == 4 and c["nivel_inferido"] is True
    assert c["area_clave"] == "TECH/Logística"


def test_archivo_real_de_eventos_tiene_estructura_valida():
    eventos = sync.normalizar_eventos(AR_AP / "Eventos_ISA95.json")
    assert eventos, "Eventos_ISA95.json no produjo eventos"
    ids = [e["eventId"] for e in eventos]
    assert len(ids) == len(set(ids)), "eventId repetido: rompería el constraint de unicidad"
    for e in eventos:
        assert 0 <= e["nivel"] <= 4
        assert datetime.fromisoformat(e["timestamp"]).tzinfo is not None
        assert e["proceso"] and e["area_clave"] and e["tipo"]
        json.loads(e["datos"])  # los datos anidados se guardan como JSON válido


@pytest.mark.parametrize("entrada, esperado", [
    ("2026-11-10 09:00:00", "2026-11-10T09:00:00-06:00"),
    ("2025-11-10T20:00:01-06:00", "2025-11-10T20:00:01-06:00"),
    ("2025-11-10T20:00:01Z", "2025-11-10T20:00:01Z"),
    ("2025-11-10T20:00:01+01:00", "2025-11-10T20:00:01+01:00"),
])
def test_marcas_de_tiempo_quedan_en_iso8601_con_zona(entrada, esperado):
    assert sync._iso(entrada) == esperado


def test_cadena_siguiente_por_fuente_y_proceso():
    def ev(i, fuente, proceso, ts):
        return {"eventId": i, "fuente": fuente, "proceso": proceso, "timestamp": ts}
    eventos = [  # a propósito desordenados
        ev("A3", "F1", "AR", "2025-01-01T10:00:03-06:00"),
        ev("A1", "F1", "AR", "2025-01-01T10:00:01-06:00"),
        ev("A2", "F1", "AR", "2025-01-01T10:00:02-06:00"),
        ev("P2", "F1", "AP", "2025-01-01T10:00:05-06:00"),
        ev("P1", "F1", "AP", "2025-01-01T10:00:04-06:00"),
        ev("X1", "F2", "AR", "2025-01-01T09:00:00-06:00"),
        ev("X2", "F2", "AR", "2025-01-01T09:00:00-06:00"),  # empate: gana el orden por eventId
    ]
    pares = sync.pares_siguiente(eventos)
    assert sorted(pares["F1"]) == [("A1", "A2"), ("A2", "A3"), ("P1", "P2")]
    assert pares["F2"] == [("X1", "X2")]


def test_pasos_del_proceso_con_compuertas_y_ciclos(tmp_path):
    ruta = _escribir_json(tmp_path, "pasos.json", [
        {"id": "P1", "tipo": "tarea", "nombre": "Uno", "siguiente": "G"},
        {"id": "G", "tipo": "compuerta", "nombre": "Decide",
         "ramas": [{"condicion": "No", "siguiente": "P1"}, {"condicion": "Sí", "siguiente": "F"}]},
        {"id": "F", "tipo": "fin", "nombre": "Fin"},
    ])
    pasos, aristas = sync.normalizar_pasos(ruta)
    assert [p["id"] for p in pasos] == ["P1", "G", "F"]
    assert {(a["de"], a["a"], a["condicion"]) for a in aristas} == \
           {("P1", "G", None), ("G", "P1", "No"), ("G", "F", "Sí")}


def test_archivo_real_de_pasos_no_tiene_transiciones_rotas():
    pasos, aristas = sync.normalizar_pasos(AR_AP / "eventos_ap.json")
    ids = {p["id"] for p in pasos}
    assert aristas and all(a["de"] in ids and a["a"] in ids for a in aristas)


def test_limpiar_convierte_tipos_de_postgres():
    from datetime import date
    from decimal import Decimal
    assert sync._limpiar(Decimal("1160.00")) == 1160.0
    assert sync._limpiar(date(2025, 11, 10)) == "2025-11-10"
    assert sync._limpiar(datetime(2025, 11, 10, 20, 0, 3)) == "2025-11-10T20:00:03"
    assert sync._limpiar(None) is None and sync._limpiar("x") == "x"


def test_consultas_sql_estan_completas_y_son_seguras():
    consultas = sync.cargar_consultas()
    esperadas = set(sync.MAESTROS) | set(sync.DOCUMENTOS) | set(sync.LINEAS) | \
        {"cobro_aplicaciones", "pago_aplicaciones"}
    assert set(consultas) == esperadas
    for nombre, sql in consultas.items():
        assert sql.upper().startswith("SELECT"), nombre
        sin_parametro = sql.replace("%(desde)s", "")
        assert "%" not in sin_parametro, f"{nombre}: un % suelto rompe psycopg2"
        assert ";" not in sql, nombre
        if nombre in sync.MAESTROS:
            assert "%(desde)s" not in sql, f"{nombre}: los catálogos se leen completos"
        else:
            assert "%(desde)s" in sql, f"{nombre}: falta el filtro incremental"
    assert ">=" in consultas["facturas_cliente"]


def test_toda_escritura_en_neo4j_es_merge_y_nunca_borra_la_base():
    prohibidas = re.compile(r"\b(CREATE|DETACH|DROP|REMOVE)\b", re.IGNORECASE)
    for cypher in sync.todas_las_sentencias_de_escritura():
        assert not prohibidas.search(cypher), cypher
        if cypher is sync.CYPHER_EVENTOS_SIGUIENTE_OBSOLETAS:
            continue
        assert "DELETE" not in cypher.upper(), cypher
    # Lo único que se elimina: relaciones :SIGUIENTE obsoletas de una fuente.
    obsoleta = sync.CYPHER_EVENTOS_SIGUIENTE_OBSOLETAS
    assert "[r:SIGUIENTE]" in obsoleta and "$fuente" in obsoleta and "DELETE r" in obsoleta
    # Todo lo que crea nodos o relaciones lo hace con MERGE
    for cypher in sync.todas_las_sentencias_de_escritura():
        if cypher in (sync.CYPHER_EVENTOS_SIGUIENTE_OBSOLETAS, sync.CYPHER_EVENTOS_HUERFANOS):
            continue
        assert "MERGE" in cypher, cypher


def test_schema_cypher_es_idempotente_y_cubre_el_diseno():
    sentencias = sync.leer_sentencias_cypher()
    assert len(sentencias) >= 19
    for s in sentencias:
        assert re.match(r"CREATE (CONSTRAINT|INDEX)\b", s), s
        assert "IF NOT EXISTS" in s, s
        assert not re.search(r"\bDROP\b", s, re.IGNORECASE)
    texto = " ".join(sentencias)
    for requerido in ("(n:Cliente) REQUIRE n.rfc IS UNIQUE", "(n:Proveedor) REQUIRE n.rfc IS UNIQUE",
                      "(n:EventoISA95) REQUIRE n.eventId IS UNIQUE", "(n:Documento) ON (n.folio)"):
        assert requerido in texto, requerido
    for etiqueta, _ in sync.DOCUMENTOS.values():  # folio único en cada tipo de documento
        assert f"(n:{etiqueta}) REQUIRE n.folio IS UNIQUE" in texto, etiqueta


def test_relaciones_del_diseno_estan_definidas():
    tipos = {rel for _, _, rel, _, _ in sync.RELACIONES}
    assert {"GENERA_PEDIDO", "FACTURADO_EN", "PAGA", "RECIBE_OC", "SURTIDA_EN",
            "CONCILIADA_EN", "LIQUIDA"} <= tipos


def test_catalogo_de_consultas_cypher_se_lee_completo():
    import ejecutar_consultas as ec
    consultas = ec.leer_consultas()
    assert [n for n, _, _ in consultas] == [f"Q{i}" for i in range(1, 14)]
    for numero, titulo, cypher in consultas:
        assert titulo and cypher, numero
        assert cypher.split()[0] in ("MATCH", "UNWIND"), numero  # son solo lecturas
        assert "//" not in cypher and ";" not in cypher, numero
        assert not re.search(r"\b(CREATE|MERGE|DELETE|SET|REMOVE|DROP)\b", cypher, re.IGNORECASE), \
            f"{numero}: el catálogo debe ser de solo lectura"


class _Resumen:
    nodes_created = relationships_created = properties_set = relationships_deleted = 0


class _SesionFalsa:
    """Registra lo que se enviaría a Neo4j, sin base de datos."""

    def __init__(self):
        self.llamadas = []

    def execute_write(self, trabajo):
        sesion = self

        class Tx:
            def run(self, cypher, **params):
                sesion.llamadas.append((cypher, params))

                class R:
                    def consume(self_):
                        class S:
                            counters = _Resumen()
                        return S()
                return R()
        return trabajo(Tx())


def test_cargar_grafo_da_forma_a_propiedades_y_omite_enlaces_vacios():
    datos = {
        "clientes": [{"id": 1, "codigo": "C001", "rfc": "RFC1", "razon_social": "Alfa"}],
        "facturas_cliente": [
            {"id": 1, "folio": "FC-1", "cliente_rfc": "RFC1", "pedido_folio": "PV-1", "total": 10.0},
            {"id": 2, "folio": "FC-2", "cliente_rfc": "RFC1", "pedido_folio": None, "total": 5.0},
        ],
    }
    sesion = _SesionFalsa()
    sync.cargar_grafo(sesion, datos, sync.Contadores())

    docs = [(c, p) for c, p in sesion.llamadas if "MERGE (n:FacturaCliente" in c]
    assert len(docs) == 1
    props = docs[0][1]["rows"][0]["props"]
    assert props["proceso"] == "AR" and props["tipo_documento"] == "FacturaCliente"
    assert "cliente_rfc" not in props and "pedido_folio" not in props  # son relaciones, no propiedades

    facturado = [p for c, p in sesion.llamadas if "[r:FACTURADO_EN]" in c]
    assert [f["folio"] for f in facturado[0]["rows"]] == ["FC-1"]  # FC-2 no tiene pedido: se omite


# ======================================================================
# 2. Con PostgreSQL real
# ======================================================================
def _sentencias_sql(texto: str):
    """Separa un script SQL en sentencias, respetando comillas y comentarios --."""
    actual, comilla, i = [], False, 0
    while i < len(texto):
        c = texto[i]
        if not comilla and texto.startswith("--", i):
            i = texto.find("\n", i)
            i = len(texto) if i == -1 else i
            continue
        if c == "'":
            comilla = not comilla
        if c == ";" and not comilla:
            sentencia = "".join(actual).strip()
            if sentencia:
                yield sentencia
            actual = []
        else:
            actual.append(c)
        i += 1
    resto = "".join(actual).strip()
    if resto:
        yield resto


@pytest.fixture(scope="module")
def pg_conn():
    import psycopg2
    try:
        conn = sync.conectar_postgres()
    except Exception as e:  # sin PostgreSQL: se omiten estas pruebas
        pytest.skip(f"No hay PostgreSQL disponible ({str(e).splitlines()[0]})")
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(f"DROP SCHEMA IF EXISTS {ESQUEMA_PRUEBA} CASCADE")
    cur.execute(f"CREATE SCHEMA {ESQUEMA_PRUEBA}")
    cur.execute(f"SET search_path TO {ESQUEMA_PRUEBA}")
    for archivo in ("Tablas-Alexis.sql", "tablas.sql", "azul_ventas.sql",
                    "miriam_contabilidad.sql", "183800/seed_arap_183800.sql"):
        for sentencia in _sentencias_sql((AR_AP / archivo).read_text(encoding="utf-8")):
            try:
                cur.execute(sentencia)
            except psycopg2.errors.DuplicateTable:
                pass  # azul_ventas.sql repite el nombre de 2 índices de tablas.sql; no afecta
    yield conn
    cur.execute("SET search_path TO public")
    cur.execute(f"DROP SCHEMA IF EXISTS {ESQUEMA_PRUEBA} CASCADE")
    conn.close()


def test_extraccion_completa_trae_todos_los_registros(pg_conn):
    datos = sync.extraer(pg_conn, sync.DESDE_SIEMPRE)
    cuentas = {k: len(v) for k, v in datos.items()}
    assert cuentas == {
        "clientes": 2, "proveedores": 2, "cuentas_contables": 7,
        "pedidos_venta": 3, "pedido_lineas": 3, "facturas_cliente": 4, "cobros": 3, "cobro_aplicaciones": 3,
        "ordenes_compra": 3, "oc_lineas": 3, "recepciones": 3, "facturas_proveedor": 2,
        "pagos": 1, "pago_aplicaciones": 1,
    }


def test_extraccion_incremental_solo_trae_documentos_nuevos(pg_conn):
    datos = sync.extraer(pg_conn, "2025-11-01T00:00:00")
    assert [f["folio"] for f in datos["pedidos_venta"]] == ["PV-1001"]
    assert [f["folio"] for f in datos["facturas_cliente"]] == ["FC-2001"]
    assert sorted(f["folio"] for f in datos["cobros"]) == ["CB-3001", "CB-3002"]
    assert [f["folio"] for f in datos["ordenes_compra"]] == ["OC-4001"]
    assert [f["folio"] for f in datos["pagos"]] == ["PP-7001"]
    assert len(datos["clientes"]) == 2 and len(datos["proveedores"]) == 2  # catálogos completos
    assert sync.marca_de_agua(datos, None) == "2025-11-30T10:00:00"
    assert sync.extraer(pg_conn, "2026-01-01T00:00:00")["facturas_cliente"] == []


def test_extraccion_trae_las_claves_para_armar_relaciones(pg_conn):
    datos = sync.extraer(pg_conn, sync.DESDE_SIEMPRE)
    fc = {f["folio"]: f for f in datos["facturas_cliente"]}
    assert fc["FC-2001"]["pedido_folio"] == "PV-1001" and fc["FC-2001"]["cliente_rfc"] == "CAL010101AA1"
    assert fc["FC-2004"]["pedido_folio"] is None  # factura sin pedido: solo se enlaza al cliente
    fp = {f["folio"]: f for f in datos["facturas_proveedor"]}
    assert fp["FP-6001"]["recepcion_folio"] == "RM-5001" and fp["FP-6001"]["oc_folio"] == "OC-4001"
    assert {(a["cobro_folio"], a["factura_folio"]) for a in datos["cobro_aplicaciones"]} >= {("CB-3001", "FC-2001")}
    assert all(isinstance(f["total"], float) for f in datos["facturas_cliente"])  # Decimal -> float


def test_aplicaciones_cuadran_con_los_saldos(pg_conn):
    """Calidad de datos: total - saldo debe ser igual a lo aplicado por cobros/pagos."""
    datos = sync.extraer(pg_conn, sync.DESDE_SIEMPRE)
    for facturas, aplicaciones in (("facturas_cliente", "cobro_aplicaciones"),
                                   ("facturas_proveedor", "pago_aplicaciones")):
        aplicado = {}
        for a in datos[aplicaciones]:
            aplicado[a["factura_folio"]] = aplicado.get(a["factura_folio"], 0) + a["monto_aplicado"]
        for f in datos[facturas]:
            assert round(f["total"] - f["saldo"], 2) == round(aplicado.get(f["folio"], 0), 2), f["folio"]


# ======================================================================
# 3. Con PostgreSQL y Neo4j reales
# ======================================================================
@pytest.fixture(scope="module")
def neo4j_driver():
    try:
        driver = sync.conectar_neo4j()
        driver.verify_connectivity()
    except Exception as e:
        pytest.skip(f"No hay Neo4j disponible ({str(e).splitlines()[0]})")
    yield driver
    driver.close()


@pytest.fixture
def eventos_de_prueba(tmp_path):
    """Un archivo de eventos propio: uno con documento real, uno huérfano y uno intermedio."""
    ruta = tmp_path / f"{FUENTE_PRUEBA}.json"
    ruta.write_text(json.dumps({"events": [
        {"eventId": "E1", "timestamp": "2025-11-10T20:00:03-06:00", "eventType": "FacturaClienteCreada",
         "isa95": {"level": 4, "enterprise": "T", "site": "S", "area": "AR", "workCenter": "Ventas"},
         "document": {"folio": "FC-2001", "base": "PV-1001"}, "data": {}},
        {"eventId": "E2", "timestamp": "2025-11-10T20:00:04-06:00", "eventType": "CobroAplicado",
         "isa95": {"level": 4, "enterprise": "T", "site": "S", "area": "AR", "workCenter": "Cobranza"},
         "document": {"folio": "CB-3001", "base": "FC-2001"}, "data": {}},
        {"eventId": "E3", "timestamp": "2025-11-10T20:00:05-06:00", "eventType": "EventoSinDocumento",
         "isa95": {"level": 4, "enterprise": "T", "site": "S", "area": "AR", "workCenter": "Cobranza"},
         "document": {"folio": "FC-NO-EXISTE-183800", "base": None}, "data": {}},
    ]}), encoding="utf-8")
    return ruta


def _consulta(driver, cypher, **params):
    with driver.session() as sesion:
        return [dict(r) for r in sesion.run(cypher, **params)]


def test_sincronizacion_es_idempotente(pg_conn, neo4j_driver, tmp_path, eventos_de_prueba):
    try:
        primera = sync.sincronizar(pg_conn, neo4j_driver, ruta_eventos=eventos_de_prueba,
                                   ruta_pasos=AR_AP / "eventos_ap.json", ruta_estado=None, log=lambda *a: None)
        segunda = sync.sincronizar(pg_conn, neo4j_driver, ruta_eventos=eventos_de_prueba,
                                   ruta_pasos=AR_AP / "eventos_ap.json", ruta_estado=None, log=lambda *a: None)
        assert segunda["creados"]["nodos_creados"] == 0
        assert segunda["creados"]["relaciones_creadas"] == 0
        assert segunda["creados"]["relaciones_borradas"] == 0
        assert segunda["grafo"]["nodos"] == primera["grafo"]["nodos"]
        assert segunda["grafo"]["relaciones"] == primera["grafo"]["relaciones"]
    finally:
        _consulta(neo4j_driver, "MATCH (e:EventoISA95 {fuente: $f}) DETACH DELETE e", f=FUENTE_PRUEBA)


def test_documentos_eventos_y_huerfanos_en_el_grafo(pg_conn, neo4j_driver, eventos_de_prueba):
    try:
        sync.sincronizar(pg_conn, neo4j_driver, ruta_eventos=eventos_de_prueba,
                         ruta_pasos=None, ruta_estado=None, log=lambda *a: None)
        # ciclo de venta completo: pedido -> factura <- cobro
        ciclo = _consulta(neo4j_driver, """
            MATCH (:Cliente {rfc: 'CAL010101AA1'})-[:GENERA_PEDIDO]->(:PedidoVenta {folio: 'PV-1001'})
                  -[:FACTURADO_EN]->(f:FacturaCliente {folio: 'FC-2001'})<-[p:PAGA]-(c:Cobro)
            RETURN c.folio AS cobro, p.monto_aplicado AS monto ORDER BY cobro""")
        assert [(r["cobro"], r["monto"]) for r in ciclo] == [("CB-3001", 500.0), ("CB-3002", 660.0)]

        # ciclo de compra completo: OC -> recepción -> factura <- pago
        compra = _consulta(neo4j_driver, """
            MATCH (:Proveedor)-[:RECIBE_OC]->(:OrdenCompra {folio: 'OC-4001'})-[:SURTIDA_EN]->
                  (:Recepcion {folio: 'RM-5001'})-[:CONCILIADA_EN]->(:FacturaProveedor {folio: 'FP-6001'})
                  <-[:LIQUIDA]-(p:Pago) RETURN p.folio AS pago""")
        assert [r["pago"] for r in compra] == ["PP-7001"]

        # el evento con documento real se enlaza; el del folio inexistente queda huérfano
        enlazado = _consulta(neo4j_driver, """
            MATCH (e:EventoISA95 {eventId: $id})-[:REGISTRADO_EN]->(d:Documento) RETURN d.folio AS folio""",
                             id=f"{FUENTE_PRUEBA}-E1")
        assert [r["folio"] for r in enlazado] == ["FC-2001"]
        estado = {r["id"]: r["h"] for r in _consulta(neo4j_driver, """
            MATCH (e:EventoISA95 {fuente: $f}) RETURN e.eventId AS id, e.huerfano AS h""", f=FUENTE_PRUEBA)}
        assert estado == {f"{FUENTE_PRUEBA}-E1": False, f"{FUENTE_PRUEBA}-E2": False, f"{FUENTE_PRUEBA}-E3": True}

        # los eventos de la fuente quedan encadenados en orden cronológico
        cadena = _consulta(neo4j_driver, """
            MATCH (a:EventoISA95 {fuente: $f})-[:SIGUIENTE]->(b) RETURN a.idOriginal AS de, b.idOriginal AS a
            ORDER BY de""", f=FUENTE_PRUEBA)
        assert [(r["de"], r["a"]) for r in cadena] == [("E1", "E2"), ("E2", "E3")]
    finally:
        _consulta(neo4j_driver, "MATCH (e:EventoISA95 {fuente: $f}) DETACH DELETE e", f=FUENTE_PRUEBA)
