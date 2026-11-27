"""Carga el programa de órdenes de producción de PostgreSQL a Neo4j.

Autor: Diego Luna Saucedo - 184814 · Issue #300

Lee las vistas y tablas creadas por 01_esquema_programacion.sql y construye
el grafo descrito en 04_grafo_programacion.cypher. Después ejecuta las
consultas de análisis y muestra sus resultados.

Variables de entorno (con valores por defecto para GitHub Actions):
    PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE
    NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

Uso:
    python cargar_grafo.py               # carga y muestra las consultas
    python cargar_grafo.py --etapa-id 2  # etapa para la consulta de retraso
"""

from __future__ import annotations

import argparse
import os
from decimal import Decimal
from pathlib import Path

import psycopg2
import psycopg2.extras
from neo4j import GraphDatabase

CYPHER_FILE = Path(__file__).with_name("04_grafo_programacion.cypher")

SQL_CENTROS = """
    SELECT codigo, nombre, capacidad_horas_dia
    FROM centro_trabajo
"""

SQL_ORDENES = """
    SELECT o.folio, o.cantidad, o.estatus, o.fecha_inicio, o.fecha_fin,
           fc.fecha_compromiso, o.costo_planificado
    FROM orden_produccion o
    LEFT JOIN orden_fecha_compromiso fc ON fc.orden_produccion_id = o.orden_produccion_id
    WHERE o.estatus IN ('PLANIFICADA', 'LIBERADA')
"""

SQL_ETAPAS = """
    SELECT p.orden_produccion_etapa_id AS id, p.folio, p.secuencia, p.etapa,
           p.centro_trabajo AS centro, p.estatus_etapa AS estatus,
           e.dias_espera, p.fecha_inicio, p.fecha_fin
    FROM vw_programa_ordenes p
    JOIN orden_produccion_etapa e ON e.orden_produccion_etapa_id = p.orden_produccion_etapa_id
    WHERE p.estatus_orden IN ('PLANIFICADA', 'LIBERADA')
"""

SQL_CARGA = """
    SELECT c.orden_produccion_etapa_id AS etapa_id, c.fecha, c.horas
    FROM orden_etapa_carga_dia c
    JOIN orden_produccion_etapa e USING (orden_produccion_etapa_id)
    JOIN orden_produccion o USING (orden_produccion_id)
    WHERE o.estatus IN ('PLANIFICADA', 'LIBERADA')
"""


def leer_bloques_cypher(ruta: Path = CYPHER_FILE) -> dict[str, str]:
    """Separa el archivo .cypher en bloques con nombre (líneas "// @nombre")."""
    bloques: dict[str, list[str]] = {}
    actual: str | None = None
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        if linea.startswith("// @"):
            actual = linea[4:].strip()
            bloques[actual] = []
        elif actual is not None and not linea.lstrip().startswith("//"):
            bloques[actual].append(linea)
    return {nombre: "\n".join(lineas).strip().rstrip(";") for nombre, lineas in bloques.items()}


def _a_neo4j(valor):
    """Convierte tipos de PostgreSQL a tipos que acepta el driver de Neo4j."""
    if isinstance(valor, Decimal):
        return float(valor)
    if hasattr(valor, "isoformat"):
        return valor.isoformat()
    return valor


def _filas(cursor, sql: str) -> list[dict]:
    cursor.execute(sql)
    return [{k: _a_neo4j(v) for k, v in fila.items()} for fila in cursor.fetchall()]


def conectar_postgres():
    return psycopg2.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=int(os.getenv("PGPORT", "5432")),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", "postgres"),
        dbname=os.getenv("PGDATABASE", "erp_rutas"),
    )


def conectar_neo4j():
    return GraphDatabase.driver(
        os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "password")),
    )


def leer_programa(conn) -> dict[str, list[dict]]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        return {
            "centros": _filas(cur, SQL_CENTROS),
            "ordenes": _filas(cur, SQL_ORDENES),
            "etapas": _filas(cur, SQL_ETAPAS),
            "carga": _filas(cur, SQL_CARGA),
        }


def cargar_grafo(driver, programa: dict[str, list[dict]]) -> dict[str, int]:
    """Borra el grafo anterior de este módulo y lo vuelve a construir."""
    q = leer_bloques_cypher()
    with driver.session() as s:
        for indice in ("indice_orden", "indice_etapa", "indice_centro", "indice_dia"):
            s.run(q[indice]).consume()
        s.run(q["limpiar"]).consume()
        s.run(q["cargar_centros"], filas=programa["centros"]).consume()
        s.run(q["cargar_ordenes"], filas=programa["ordenes"]).consume()
        s.run(q["cargar_etapas"], filas=programa["etapas"]).consume()
        s.run(q["cargar_secuencia"]).consume()
        s.run(q["cargar_carga"], filas=programa["carga"]).consume()
        conteo = s.run(
            "MATCH (n {fuente: 'rutas_184814'}) "
            "RETURN labels(n)[0] AS etiqueta, count(*) AS total"
        )
        return {r["etiqueta"]: r["total"] for r in conteo}


def consultar(driver, nombre: str, **parametros) -> list[dict]:
    q = leer_bloques_cypher()
    with driver.session() as s:
        return [r.data() for r in s.run(q[nombre], **parametros)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--etapa-id", type=int, default=None,
                        help="Etapa para la consulta de propagación de retraso")
    args = parser.parse_args()

    with conectar_postgres() as conn:
        programa = leer_programa(conn)

    driver = conectar_neo4j()
    try:
        conteo = cargar_grafo(driver, programa)
        print("Nodos cargados:", conteo)

        etapa_id = args.etapa_id
        if etapa_id is None:
            primera = min(programa["etapas"], key=lambda e: (e["folio"], e["secuencia"]))
            etapa_id = primera["id"]

        for nombre, params in (
            ("propagacion_retraso", {"etapa_id": etapa_id}),
            ("impacto_en_otras_ordenes", {"etapa_id": etapa_id}),
            ("conflictos_centro_dia", {}),
            ("duracion_acumulada", {}),
        ):
            print(f"\n== {nombre} {params or ''}")
            for fila in consultar(driver, nombre, **params):
                print("  ", {k: str(v) for k, v in fila.items()})
    finally:
        driver.close()


if __name__ == "__main__":
    main()
