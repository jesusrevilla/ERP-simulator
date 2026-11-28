"""
Pipeline de Base de Datos Políglota (PostgreSQL + Neo4j + MongoDB)
Matrícula: 178084 | Issue #305 (Recibos y Entregas - Cuarentena, Lotes y RTV)
"""

from datetime import datetime, timezone
from pathlib import Path
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from neo4j import GraphDatabase
from pymongo import MongoClient

BASE_DIR = Path(__file__).resolve().parent
PROYECTO_TAG = "178084"


def get_postgres_conn():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "erpdb"),
        user=os.getenv("POSTGRES_USER", "erp"),
        password=os.getenv("POSTGRES_PASSWORD", "erp"),
    )


def get_neo4j_driver():
    host = os.getenv("NEO4J_HOST", "localhost")
    port = os.getenv("NEO4J_PORT", "7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    uri = f"bolt://{host}:{port}"
    return GraphDatabase.driver(uri, auth=(user, password))


def get_mongo_db():
    host = os.getenv("MONGO_HOST", "localhost")
    port = int(os.getenv("MONGO_PORT", "27017"))
    client = MongoClient(f"mongodb://{host}:{port}/", serverSelectionTimeoutMS=5000)
    db_name = os.getenv("MONGO_DB", "erpdb")
    return client, client[db_name]


def load_postgres():
    """Ejecuta el DDL y los datos semilla en PostgreSQL."""
    schema_sql = (BASE_DIR / "schema_178084.sql").read_text(encoding="utf-8")
    seed_sql = (BASE_DIR / "seed_178084.sql").read_text(encoding="utf-8")

    conn = get_postgres_conn()
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(schema_sql)
            cur.execute(seed_sql)
    finally:
        conn.close()


def sync_neo4j():
    """Sincroniza proveedores, recepciones, lotes, artículos, RTV y entregas a Neo4j."""
    conn = get_postgres_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM proveedores_178084")
            proveedores = cur.fetchall()

            cur.execute("SELECT * FROM articulos_178084")
            articulos = cur.fetchall()

            cur.execute(
                """
                SELECT r.*, p.codigo AS proveedor_codigo
                  FROM recepciones_178084 r
                  JOIN proveedores_178084 p ON p.proveedor_id = r.proveedor_id
                """
            )
            recepciones = cur.fetchall()

            cur.execute(
                """
                SELECT l.*, r.folio_recepcion, a.sku
                  FROM lotes_inspeccion_178084 l
                  JOIN recepciones_178084 r ON r.recepcion_id = l.recepcion_id
                  JOIN articulos_178084 a   ON a.articulo_id = l.articulo_id
                """
            )
            lotes = cur.fetchall()

            cur.execute(
                """
                SELECT rtv.*, l.numero_lote
                  FROM devoluciones_rtv_178084 rtv
                  JOIN lotes_inspeccion_178084 l ON l.lote_id = rtv.lote_id
                """
            )
            rtvs = cur.fetchall()

            cur.execute(
                """
                SELECT e.*, l.numero_lote
                  FROM entregas_178084 e
                  JOIN lotes_inspeccion_178084 l ON l.lote_id = e.lote_id
                """
            )
            entregas = cur.fetchall()
    finally:
        conn.close()

    driver = get_neo4j_driver()
    try:
        with driver.session() as session:
            # Limpieza aislada únicamente de los nodos de este proyecto
            session.run(
                "MATCH (n {proyecto: $tag}) DETACH DELETE n",
                tag=PROYECTO_TAG,
            )

            for p in proveedores:
                session.run(
                    """
                    CREATE (:Proveedor {
                        proyecto: $tag,
                        proveedor_id: $proveedor_id,
                        codigo: $codigo,
                        nombre: $nombre,
                        activo: $activo
                    })
                    """,
                    tag=PROYECTO_TAG,
                    proveedor_id=p["proveedor_id"],
                    codigo=p["codigo"],
                    nombre=p["nombre"],
                    activo=p["activo"],
                )

            for a in articulos:
                session.run(
                    """
                    CREATE (:Articulo {
                        proyecto: $tag,
                        articulo_id: $articulo_id,
                        sku: $sku,
                        nombre: $nombre
                    })
                    """,
                    tag=PROYECTO_TAG,
                    articulo_id=a["articulo_id"],
                    sku=a["sku"],
                    nombre=a["nombre"],
                )

            for r in recepciones:
                session.run(
                    """
                    MATCH (p:Proveedor {proyecto: $tag, codigo: $proveedor_codigo})
                    CREATE (rec:Recepcion {
                        proyecto: $tag,
                        folio_recepcion: $folio_recepcion,
                        folio_oc: $folio_oc,
                        almacen: $almacen,
                        fecha_recepcion: $fecha_recepcion,
                        estatus: $estatus
                    })
                    CREATE (p)-[:SUMINISTRO]->(rec)
                    """,
                    tag=PROYECTO_TAG,
                    proveedor_codigo=r["proveedor_codigo"],
                    folio_recepcion=r["folio_recepcion"],
                    folio_oc=r["folio_oc"],
                    almacen=r["almacen"],
                    fecha_recepcion=r["fecha_recepcion"].isoformat(),
                    estatus=r["estatus"],
                )

            for l in lotes:
                session.run(
                    """
                    MATCH (rec:Recepcion {proyecto: $tag, folio_recepcion: $folio_recepcion})
                    MATCH (a:Articulo {proyecto: $tag, sku: $sku})
                    CREATE (lote:Lote {
                        proyecto: $tag,
                        numero_lote: $numero_lote,
                        cantidad_recibida: $cantidad_recibida,
                        cantidad_aprobada: $cantidad_aprobada,
                        cantidad_rechazada: $cantidad_rechazada,
                        fecha_caducidad: $fecha_caducidad,
                        estatus_lote: $estatus_lote
                    })
                    CREATE (rec)-[:CONTIENE]->(lote)
                    CREATE (lote)-[:ES_ARTICULO]->(a)
                    """,
                    tag=PROYECTO_TAG,
                    folio_recepcion=l["folio_recepcion"],
                    sku=l["sku"],
                    numero_lote=l["numero_lote"],
                    cantidad_recibida=l["cantidad_recibida"],
                    cantidad_aprobada=l["cantidad_aprobada"],
                    cantidad_rechazada=l["cantidad_rechazada"],
                    fecha_caducidad=l["fecha_caducidad"].isoformat(),
                    estatus_lote=l["estatus_lote"],
                )

            for rtv in rtvs:
                session.run(
                    """
                    MATCH (lote:Lote {proyecto: $tag, numero_lote: $numero_lote})
                    CREATE (dev:DevolucionRTV {
                        proyecto: $tag,
                        folio_rtv: $folio_rtv,
                        cantidad_devuelta: $cantidad_devuelta,
                        motivo: $motivo
                    })
                    CREATE (lote)-[:DEVUELTO_EN]->(dev)
                    """,
                    tag=PROYECTO_TAG,
                    numero_lote=rtv["numero_lote"],
                    folio_rtv=rtv["folio_rtv"],
                    cantidad_devuelta=rtv["cantidad_devuelta"],
                    motivo=rtv["motivo"],
                )

            for e in entregas:
                session.run(
                    """
                    MATCH (lote:Lote {proyecto: $tag, numero_lote: $numero_lote})
                    CREATE (ent:Entrega {
                        proyecto: $tag,
                        folio_entrega: $folio_entrega,
                        cliente: $cliente,
                        cantidad_entregada: $cantidad_entregada,
                        fecha_entrega: $fecha_entrega,
                        estatus: $estatus
                    })
                    CREATE (lote)-[:DESPACHADO_EN]->(ent)
                    """,
                    tag=PROYECTO_TAG,
                    numero_lote=e["numero_lote"],
                    folio_entrega=e["folio_entrega"],
                    cliente=e["cliente"],
                    cantidad_entregada=e["cantidad_entregada"],
                    fecha_entrega=e["fecha_entrega"].isoformat(),
                    estatus=e["estatus"],
                )
    finally:
        driver.close()


def seed_mongodb_inspections():
    """Registra la bitácora JSON de inspecciones de calidad en MongoDB."""
    conn = get_postgres_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    l.numero_lote,
                    a.sku,
                    a.nombre AS articulo,
                    p.codigo AS proveedor_codigo,
                    p.nombre AS proveedor,
                    r.folio_recepcion,
                    l.cantidad_recibida,
                    l.cantidad_aprobada,
                    l.cantidad_rechazada,
                    l.fecha_caducidad,
                    l.estatus_lote,
                    rtv.folio_rtv,
                    rtv.motivo AS motivo_rtv
                FROM lotes_inspeccion_178084 l
                JOIN recepciones_178084 r ON r.recepcion_id = l.recepcion_id
                JOIN proveedores_178084 p ON p.proveedor_id = r.proveedor_id
                JOIN articulos_178084 a   ON a.articulo_id = l.articulo_id
                LEFT JOIN devoluciones_rtv_178084 rtv ON rtv.lote_id = l.lote_id
                ORDER BY l.lote_id
                """
            )
            lotes = cur.fetchall()
    finally:
        conn.close()

    client, db = get_mongo_db()
    try:
        col = db["inspecciones_calidad_178084"]
        col.delete_many({})

        documentos = []
        for l in lotes:
            en_cuarentena = l["estatus_lote"] == "CUARENTENA"
            tiene_rechazo = l["cantidad_rechazada"] > 0

            doc = {
                "proyecto": PROYECTO_TAG,
                "numero_lote": l["numero_lote"],
                "folio_recepcion": l["folio_recepcion"],
                "sku": l["sku"],
                "articulo": l["articulo"],
                "proveedor": {
                    "codigo": l["proveedor_codigo"],
                    "nombre": l["proveedor"],
                },
                "resultado": "PENDIENTE"
                if en_cuarentena
                else ("APROBADO_PARCIAL" if tiene_rechazo else "APROBADO_TOTAL"),
                "cantidades": {
                    "recibida": l["cantidad_recibida"],
                    "aprobada": l["cantidad_aprobada"],
                    "rechazada": l["cantidad_rechazada"],
                },
                "checklist_calidad": {
                    "integridad_empaque": not tiene_rechazo,
                    "etiquetado_lote": True,
                    "certificado_proveedor": True,
                },
                "fecha_caducidad": l["fecha_caducidad"].isoformat(),
                "folio_rtv": l["folio_rtv"],
                "observaciones": l["motivo_rtv"]
                or ("Pendiente de inspección física" if en_cuarentena else "Sin incidencias"),
                "fecha_registro": datetime.now(timezone.utc).isoformat(),
            }
            documentos.append(doc)

        if documentos:
            col.insert_many(documentos)
        return len(documentos)
    finally:
        client.close()


def run_pipeline():
    print("=== [178084] Iniciando pipeline de Base de Datos (PostgreSQL + Neo4j + MongoDB) ===")
    load_postgres()
    print("[OK] PostgreSQL: esquema, triggers, procedimiento y datos semilla cargados.")

    sync_neo4j()
    print("[OK] Neo4j: grafo de trazabilidad (Proveedor -> Recepción -> Lote -> RTV/Entrega) sincronizado.")

    total_docs = seed_mongodb_inspections()
    print(f"[OK] MongoDB: {total_docs} bitácoras de inspección registradas en 'inspecciones_calidad_178084'.")

    # Mostrar resumen de consultas clave para evidencias
    conn = get_postgres_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM vw_inventario_atp_178084")
            print("\n--- Vista PostgreSQL: vw_inventario_atp_178084 ---")
            for row in cur.fetchall():
                print(dict(row))

            cur.execute("SELECT * FROM vw_ranking_proveedores_178084")
            print("\n--- Vista PostgreSQL: vw_ranking_proveedores_178084 ---")
            for row in cur.fetchall():
                print(dict(row))
    finally:
        conn.close()

    driver = get_neo4j_driver()
    try:
        with driver.session() as session:
            res = session.run(
                """
                MATCH (p:Proveedor {proyecto: $tag})-[:SUMINISTRO]->(:Recepcion)-[:CONTIENE]->(l:Lote)
                OPTIONAL MATCH (l)-[:DEVUELTO_EN]->(rtv:DevolucionRTV)
                RETURN p.codigo AS codigo, p.nombre AS proveedor,
                       sum(l.cantidad_aprobada) AS aprobadas,
                       sum(l.cantidad_rechazada) AS rechazadas,
                       count(DISTINCT rtv) AS total_rtv
                ORDER BY rechazadas ASC, aprobadas DESC
                """,
                tag=PROYECTO_TAG,
            )
            print("\n--- Consulta Neo4j (Cypher): Confiabilidad de Proveedores ---")
            for record in res:
                print(dict(record))
    finally:
        driver.close()


if __name__ == "__main__":
    run_pipeline()