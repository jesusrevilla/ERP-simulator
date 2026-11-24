"""Grafo del Maestro de Artículos (Item Master) en Neo4j - Matrícula 177622.

Crea un grafo con los artículos de la Gaming PC, sus almacenes, su stock,
la lista de materiales y las relaciones de compatibilidad y sustitución.
Después ejecuta consultas Cypher que sirven de base a los agentes propuestos
en item/item_master_agents_177622.json:

  * Agente #3 Warehouse Transfer Planner  -> stock por almacén y rutas
  * Agente #4 SKU Data Steward / Substitute Recommender -> sustitutos (BFS)

La carga es idempotente (MERGE) y usa etiquetas propias (IMItem,
IMWarehouse, IMCategory) para no chocar con los nodos de otros compañeros.
"""
import os

from neo4j import GraphDatabase

ORDER_QUANTITY = int(os.getenv("ORDER_QUANTITY", "30"))
PRODUCTION_WAREHOUSE = "ALM-PROD"

# --------------------------------------------------------------------------
# Datos maestros (mismos códigos que sql/seeds.sql)
# --------------------------------------------------------------------------
CATEGORIES = ["Producto Terminado", "CPU", "Motherboard", "RAM",
              "Almacenamiento", "Fuente de Poder", "Tarjeta de Video"]

ITEMS = [
    # code, name, item_type, uom, standard_cost, list_price, safety_stock, category
    ("PC001", "Gaming PC", "Producto Terminado", "PZA", 28500, 34999, 5, "Producto Terminado"),
    ("CPU001", "CPU Ryzen 7", "Materia Prima", "PZA", 6200, 7400, 10, "CPU"),
    ("MB001", "Motherboard B650", "Materia Prima", "PZA", 3900, 4600, 10, "Motherboard"),
    ("RAM001", "RAM 16GB DDR5", "Materia Prima", "PZA", 1100, 1350, 20, "RAM"),
    ("RAM002", "RAM 16GB DDR5 6000MHz", "Materia Prima", "PZA", 1250, 1500, 10, "RAM"),
    ("SSD001", "SSD 1TB NVMe", "Materia Prima", "PZA", 1300, 1600, 10, "Almacenamiento"),
    ("SSD002", "SSD 1TB NVMe Gen4", "Materia Prima", "PZA", 1450, 1800, 5, "Almacenamiento"),
    ("PSU001", "Power Supply 750W", "Materia Prima", "PZA", 1700, 2100, 10, "Fuente de Poder"),
    ("PSU002", "Power Supply 850W", "Materia Prima", "PZA", 2000, 2400, 5, "Fuente de Poder"),
    ("GPU001", "Graphics Card RTX", "Materia Prima", "PZA", 11500, 13900, 5, "Tarjeta de Video"),
]

BOM = [  # producto, componente, cantidad (igual que src/mrp.py)
    ("PC001", "CPU001", 1), ("PC001", "MB001", 1), ("PC001", "RAM001", 2),
    ("PC001", "SSD001", 1), ("PC001", "PSU001", 1), ("PC001", "GPU001", 1),
]

WAREHOUSES = [  # code, name, active
    ("ALM-PROD", "Almacén de Producción", True),
    ("ALM-MP", "Almacén de Materia Prima", True),
    ("ALM-CEDIS", "CEDIS San Luis Potosí", True),
    ("ALM-OLD", "Almacén Temporal (inactivo)", False),
]

STOCK = [  # item, almacén, cantidad
    ("CPU001", "ALM-PROD", 20), ("CPU001", "ALM-MP", 25),
    ("MB001", "ALM-PROD", 35), ("MB001", "ALM-MP", 10),
    ("RAM001", "ALM-PROD", 30), ("RAM001", "ALM-CEDIS", 40),
    ("RAM002", "ALM-MP", 30),
    ("SSD001", "ALM-PROD", 12), ("SSD001", "ALM-OLD", 8),
    ("SSD002", "ALM-MP", 25),
    ("PSU001", "ALM-PROD", 40),
    ("PSU002", "ALM-CEDIS", 15),
    ("GPU001", "ALM-PROD", 18), ("GPU001", "ALM-CEDIS", 4),
]

ROUTES = [  # origen, destino, horas, costo
    ("ALM-MP", "ALM-PROD", 2, 150), ("ALM-CEDIS", "ALM-MP", 4, 300),
    ("ALM-CEDIS", "ALM-PROD", 8, 500), ("ALM-OLD", "ALM-MP", 3, 200),
]

COMPATIBLE = [  # componente -> componente con el que es compatible
    ("CPU001", "MB001"), ("RAM001", "MB001"), ("RAM002", "MB001"),
    ("SSD001", "MB001"), ("SSD002", "MB001"),
    ("GPU001", "PSU001"), ("GPU001", "PSU002"),
]

SUBSTITUTES = [  # sustituto -> artículo original
    ("RAM002", "RAM001"), ("SSD002", "SSD001"), ("PSU002", "PSU001"),
]


# --------------------------------------------------------------------------
# Conexión
# --------------------------------------------------------------------------
def get_driver():
    uri = os.getenv("NEO4J_URI") or "bolt://{}:{}".format(
        os.getenv("NEO4J_HOST", "localhost"), os.getenv("NEO4J_PORT", "7687"))
    driver = GraphDatabase.driver(
        uri, auth=(os.getenv("NEO4J_USER", "neo4j"),
                   os.getenv("NEO4J_PASSWORD", "password")))
    driver.verify_connectivity()
    return driver


# --------------------------------------------------------------------------
# Creación del grafo
# --------------------------------------------------------------------------
def create_constraints(driver):
    for label, prop in (("IMItem", "code"), ("IMWarehouse", "code"),
                        ("IMCategory", "name")):
        driver.execute_query(
            f"CREATE CONSTRAINT {label.lower()}_{prop} IF NOT EXISTS "
            f"FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE")


def load_graph(tx):
    tx.run("UNWIND $rows AS name MERGE (:IMCategory {name: name})",
           rows=CATEGORIES)

    tx.run("""
        UNWIND $rows AS r
        MERGE (i:IMItem {code: r[0]})
        SET i.name = r[1], i.item_type = r[2], i.uom = r[3],
            i.standard_cost = r[4], i.list_price = r[5], i.safety_stock = r[6]
        WITH i, r
        MATCH (c:IMCategory {name: r[7]})
        MERGE (i)-[:IN_CATEGORY]->(c)
    """, rows=[list(x) for x in ITEMS])

    tx.run("""
        UNWIND $rows AS r
        MERGE (w:IMWarehouse {code: r[0]})
        SET w.name = r[1], w.active = r[2]
    """, rows=[list(x) for x in WAREHOUSES])

    tx.run("""
        UNWIND $rows AS r
        MATCH (i:IMItem {code: r[0]}), (w:IMWarehouse {code: r[1]})
        MERGE (i)-[s:STOCKED_IN]->(w)
        SET s.qty = r[2]
    """, rows=[list(x) for x in STOCK])

    tx.run("""
        UNWIND $rows AS r
        MATCH (p:IMItem {code: r[0]}), (c:IMItem {code: r[1]})
        MERGE (p)-[b:HAS_COMPONENT]->(c)
        SET b.qty = r[2]
    """, rows=[list(x) for x in BOM])

    tx.run("""
        UNWIND $rows AS r
        MATCH (a:IMWarehouse {code: r[0]}), (b:IMWarehouse {code: r[1]})
        MERGE (a)-[t:ROUTE_TO]->(b)
        SET t.hours = r[2], t.cost = r[3]
    """, rows=[list(x) for x in ROUTES])

    tx.run("""
        UNWIND $rows AS r
        MATCH (a:IMItem {code: r[0]}), (b:IMItem {code: r[1]})
        MERGE (a)-[:COMPATIBLE_WITH]->(b)
    """, rows=[list(x) for x in COMPATIBLE])

    tx.run("""
        UNWIND $rows AS r
        MATCH (a:IMItem {code: r[0]}), (b:IMItem {code: r[1]})
        MERGE (a)-[:SUBSTITUTE_FOR]->(b)
    """, rows=[list(x) for x in SUBSTITUTES])


# --------------------------------------------------------------------------
# Consultas
# --------------------------------------------------------------------------
def graph_summary(driver):
    records, _, _ = driver.execute_query("""
        MATCH (n) WHERE any(l IN labels(n) WHERE l STARTS WITH 'IM')
        RETURN labels(n)[0] AS label, count(*) AS total ORDER BY label
    """)
    nodes = {r["label"]: r["total"] for r in records}
    records, _, _ = driver.execute_query("""
        MATCH (a)-[r]->(b)
        WHERE any(l IN labels(a) WHERE l STARTS WITH 'IM')
        RETURN type(r) AS rel, count(*) AS total ORDER BY rel
    """)
    rels = {r["rel"]: r["total"] for r in records}
    return nodes, rels


def stock_vs_safety(driver):
    records, _, _ = driver.execute_query("""
        MATCH (i:IMItem) WHERE i.item_type = 'Materia Prima'
        OPTIONAL MATCH (i)-[s:STOCKED_IN]->(w:IMWarehouse {active: true})
        WITH i, coalesce(sum(s.qty), 0) AS stock
        RETURN i.code AS code, i.name AS name, stock, i.safety_stock AS safety,
               stock < i.safety_stock AS below_safety
        ORDER BY code
    """)
    return [r.data() for r in records]


def shortages_in_production(driver, quantity):
    """Faltantes en el almacén de producción para fabricar `quantity` PCs."""
    records, _, _ = driver.execute_query("""
        MATCH (:IMItem {code: 'PC001'})-[b:HAS_COMPONENT]->(c:IMItem)
        OPTIONAL MATCH (c)-[s:STOCKED_IN]->(:IMWarehouse {code: $wh})
        WITH c, b.qty * $qty AS required, coalesce(s.qty, 0) AS in_prod
        RETURN c.code AS code, c.name AS name, required, in_prod,
               CASE WHEN required > in_prod THEN required - in_prod ELSE 0 END
                 AS shortage
        ORDER BY code
    """, qty=quantity, wh=PRODUCTION_WAREHOUSE)
    return [r.data() for r in records]


def transfer_options(driver, code):
    """Agente #3: almacenes activos con stock del artículo y su ruta más
    corta (en número de traslados) hasta el almacén de producción."""
    records, _, _ = driver.execute_query("""
        MATCH (i:IMItem {code: $code})-[s:STOCKED_IN]->(w:IMWarehouse {active: true})
        WHERE w.code <> $wh AND s.qty > 0
        MATCH (dest:IMWarehouse {code: $wh})
        MATCH path = shortestPath((w)-[:ROUTE_TO*..4]->(dest))
        RETURN w.code AS origin, s.qty AS available,
               [n IN nodes(path) | n.code] AS route,
               reduce(h = 0, r IN relationships(path) | h + r.hours) AS hours,
               reduce(c = 0, r IN relationships(path) | c + r.cost) AS cost
        ORDER BY hours
    """, code=code, wh=PRODUCTION_WAREHOUSE)
    return [r.data() for r in records]


def substitutes_for(driver, code):
    """Agente #4: sustitutos (BFS hasta 2 saltos) compatibles con la
    Motherboard B650 y con stock en algún almacén activo."""
    records, _, _ = driver.execute_query("""
        MATCH (orig:IMItem {code: $code})
        MATCH p = (sub:IMItem)-[:SUBSTITUTE_FOR*1..2]->(orig)
        WHERE sub <> orig
        OPTIONAL MATCH (sub)-[s:STOCKED_IN]->(:IMWarehouse {active: true})
        WITH sub, length(p) AS hops, coalesce(sum(s.qty), 0) AS stock
        WHERE stock > 0
        RETURN sub.code AS code, sub.name AS name, hops, stock,
               exists { (sub)-[:COMPATIBLE_WITH]->(:IMItem {code: 'MB001'}) }
                 AS compatible_mb
        ORDER BY hops, stock DESC
    """, code=code)
    return [r.data() for r in records]


def line(title):
    print("\n" + "=" * 60 + f"\n{title}\n" + "=" * 60)


if __name__ == "__main__":
    driver = get_driver()
    create_constraints(driver)
    with driver.session() as session:
        session.execute_write(load_graph)

    nodes, rels = graph_summary(driver)
    line("GRAFO ITEM MASTER CREADO (177622)")
    print("Nodos:", nodes)
    print("Relaciones:", rels)
    assert nodes.get("IMItem") == len(ITEMS), "No se crearon todos los artículos"
    assert rels.get("STOCKED_IN") == len(STOCK), "Faltan relaciones de stock"

    line("STOCK TOTAL vs SAFETY STOCK (almacenes activos)")
    for r in stock_vs_safety(driver):
        flag = "  <-- DEBAJO DEL SAFETY STOCK" if r["below_safety"] else ""
        print(f"{r['code']:7} {r['name']:24} stock={r['stock']:3} "
              f"safety={r['safety']:3}{flag}")

    line(f"FALTANTES EN {PRODUCTION_WAREHOUSE} PARA {ORDER_QUANTITY} GAMING PCs")
    short = shortages_in_production(driver, ORDER_QUANTITY)
    for r in short:
        print(f"{r['code']:7} requerido={r['required']:3} "
              f"en_produccion={r['in_prod']:3} faltante={r['shortage']}")

    for r in [x for x in short if x["shortage"] > 0]:
        line(f"AGENTE #3 - TRANSFERENCIAS POSIBLES PARA {r['code']} "
             f"(faltan {r['shortage']})")
        options = transfer_options(driver, r["code"])
        for o in options:
            print(f"desde {o['origin']:9} disponible={o['available']:3} "
                  f"ruta={' -> '.join(o['route'])} "
                  f"horas={o['hours']} costo=${o['cost']}")
        covered = sum(o["available"] for o in options)
        if covered < r["shortage"]:
            print(f"Transferencias insuficientes (cubren {covered}). "
                  f"Buscando sustitutos...")
            line(f"AGENTE #4 - SUSTITUTOS PARA {r['code']}")
            subs = substitutes_for(driver, r["code"])
            if not subs:
                print("Sin sustitutos con stock: se requiere compra.")
            for s in subs:
                print(f"{s['code']:7} {s['name']:24} saltos={s['hops']} "
                      f"stock={s['stock']} compatible_B650={s['compatible_mb']}")

    driver.close()
    print("\nGrafo Item Master 177622 OK")
