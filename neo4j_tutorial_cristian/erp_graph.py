"""Tutorial Neo4j para TechAssembly: BOM, faltantes MRP y eventos ISA-95.

Ejemplo autónomo que añade nodos con prefijo CG; no borra nodos ajenos.
Modo de prueba local sin servidor: python -m neo4j_tutorial_cristian.erp_graph --offline
"""

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from src.mrp import BOM


CATALOG_PATH = (
    Path(__file__).resolve().parents[1]
    / "Inventario"
    / "eventos_CristianGodinez_ISA95.json"
)

MATERIALS = {
    "CPU Ryzen 7": ("CPU001", 50),
    "Motherboard B650": ("MB001", 45),
    "RAM 16GB DDR5": ("RAM001", 200),
    "SSD 1TB NVMe": ("SSD001", 75),
    "Power Supply 750W": ("PSU001", 40),
    "Graphics Card RTX": ("GPU001", 20),
}


def materials_for_product():
    rows = []
    for name, units in BOM["Gaming PC"].items():
        code, stock = MATERIALS[name]
        rows.append({"code": code, "name": name, "units": units, "stock": stock})
    return rows


def calculate_shortages(quantity):
    if type(quantity) is not int or quantity <= 0:
        raise ValueError("La cantidad de equipos debe ser un entero positivo")
    result = []
    for row in materials_for_product():
        required = row["units"] * quantity
        result.append(
            {
                "material": row["name"],
                "required": required,
                "stock": row["stock"],
                "shortage": max(0, required - row["stock"]),
            }
        )
    return sorted(result, key=lambda row: row["material"])


def load_events(path=CATALOG_PATH):
    catalog = json.loads(Path(path).read_text(encoding="utf-8"))
    events = catalog.get("events")
    if catalog.get("example_data") is not True or not isinstance(events, list) or not events:
        raise ValueError("Se esperaba un catálogo de eventos de simulación no vacío")
    ids = set()
    previous_timestamp = None
    previous_stock = 0
    for event in events:
        event_id = event["event_id"]
        if event_id in ids:
            raise ValueError(f"Evento repetido: {event_id}")
        ids.add(event_id)
        timestamp = datetime.fromisoformat(event["timestamp_utc"].replace("Z", "+00:00"))
        if timestamp.tzinfo is None or timestamp.utcoffset().total_seconds() != 0:
            raise ValueError("Los eventos deben registrar tiempo UTC")
        if previous_timestamp is not None and timestamp <= previous_timestamp:
            raise ValueError("Los eventos deben tener timestamps únicos ascendentes")
        before, after, delta = (
            event["stock_before"], event["stock_after"], event["stock_delta"]
        )
        if type(delta) is not int or before != previous_stock or after != before + delta or after < 0:
            raise ValueError(f"Secuencia de stock inconsistente en {event_id}")
        if event["origin_isa95_level"] != 4 or event["destination_isa95_level"] != 3:
            raise ValueError("Jerarquía ISA-95 distinta a ERP nivel 4 y MES nivel 3")
        if event["product_sku"] != catalog["product"]["sku"]:
            raise ValueError("Los eventos deben referir el artículo de la simulación")
        previous_stock = after
        previous_timestamp = timestamp
    return catalog


PRODUCT_CYPHER = """
MERGE (p:CGProduct {code: $code})
SET p.name = $name, p.example = true
"""

MATERIALS_CYPHER = """
UNWIND $rows AS row
MATCH (p:CGProduct {code: $product_code})
MERGE (m:CGMaterial {code: row.code})
SET m.name = row.name, m.stock = row.stock, m.example = true
MERGE (p)-[r:CG_REQUIRES]->(m)
SET r.units = row.units
"""

EVENTS_CYPHER = """
UNWIND $events AS event
MERGE (p:CGProduct {code: event.product_sku})
ON CREATE SET p.name = $event_product_name, p.example = true
MERGE (e:CGEvent {id: event.event_id})
SET e.type = event.event_type,
    e.timestamp = datetime(event.timestamp_utc),
    e.stock_delta = event.stock_delta,
    e.stock_before = event.stock_before,
    e.stock_after = event.stock_after,
    e.document_id = event.document_id,
    e.business_rule = event.business_rule,
    e.example = true
MERGE (e)-[:CG_AFFECTS]->(p)
"""

SHORTAGE_CYPHER = """
MATCH (p:CGProduct {code: $product_code})-[r:CG_REQUIRES]->(m:CGMaterial)
WITH m, (r.units * $quantity) AS required
RETURN m.name AS material, m.stock AS stock, required,
       CASE WHEN required > m.stock THEN required - m.stock ELSE 0 END AS shortage
ORDER BY material
"""


def load_graph(driver, catalog, database="neo4j"):
    for cypher in (
        "CREATE CONSTRAINT cg_product_code IF NOT EXISTS FOR (p:CGProduct) REQUIRE p.code IS UNIQUE",
        "CREATE CONSTRAINT cg_material_code IF NOT EXISTS FOR (m:CGMaterial) REQUIRE m.code IS UNIQUE",
        "CREATE CONSTRAINT cg_event_id IF NOT EXISTS FOR (e:CGEvent) REQUIRE e.id IS UNIQUE",
    ):
        driver.execute_query(cypher, database_=database)
    driver.execute_query(
        PRODUCT_CYPHER, code="PC001", name="Gaming PC", database_=database
    )
    driver.execute_query(
        MATERIALS_CYPHER,
        rows=materials_for_product(),
        product_code="PC001",
        database_=database,
    )
    driver.execute_query(
        EVENTS_CYPHER,
        events=catalog["events"],
        event_product_name=catalog["product"]["name"],
        database_=database,
    )


def query_shortages(driver, quantity, database="neo4j"):
    if type(quantity) is not int or quantity <= 0:
        raise ValueError("La cantidad debe ser positiva")
    records, _, _ = driver.execute_query(
        SHORTAGE_CYPHER,
        product_code="PC001",
        quantity=quantity,
        database_=database,
    )
    return [row.data() for row in records]


def main():
    parser = argparse.ArgumentParser(description="Tutorial Neo4j para MRP TechAssembly")
    parser.add_argument("--quantity", type=int, default=30)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    catalog = load_events()
    expected = calculate_shortages(args.quantity)
    print(f"Eventos ISA-95 simulados validados: {len(catalog['events'])}")
    if args.offline:
        for row in expected:
            print(f"{row['material']}: requerido={row['required']}, stock={row['stock']}, faltante={row['shortage']}")
        return

    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USERNAME", os.getenv("NEO4J_USER", "neo4j"))
    password = os.getenv("NEO4J_PASSWORD")
    if not password:
        raise ValueError("Configura NEO4J_PASSWORD como variable de entorno")
    database = os.getenv("NEO4J_DATABASE", "neo4j")
    from neo4j import GraphDatabase

    with GraphDatabase.driver(uri, auth=(user, password)) as driver:
        driver.verify_connectivity()
        load_graph(driver, catalog, database=database)
        actual = query_shortages(driver, args.quantity, database=database)
    if actual != expected:
        raise AssertionError(f"Neo4j y el cálculo MRP difieren: {actual!r} != {expected!r}")
    for row in actual:
        print(f"{row['material']}: requerido={row['required']}, stock={row['stock']}, faltante={row['shortage']}")
    print("Carga MERGE y consultas Cypher: OK")


if __name__ == "__main__":
    main()
