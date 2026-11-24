import os
import psycopg2
from neo4j import GraphDatabase


def get_pg():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        database=os.getenv("POSTGRES_DB", "erpdb"),
        user=os.getenv("POSTGRES_USER", "erp"),
        password=os.getenv("POSTGRES_PASSWORD", "erp"),
    )


def get_driver():
    uri = os.getenv("NEO4J_URI")
    if not uri:
        host = os.getenv("NEO4J_HOST", "localhost")
        port = os.getenv("NEO4J_PORT", "7687")
        uri = f"bolt://{host}:{port}"

    driver = GraphDatabase.driver(
        uri,
        auth=(
            os.getenv("NEO4J_USER", os.getenv("NEO4J_USERNAME", "neo4j")),
            os.getenv("NEO4J_PASSWORD", "password"),
        ),
    )
    driver.verify_connectivity()
    return driver


def extract():
    conn = get_pg()
    cur = conn.cursor()

    cur.execute("SELECT id, code, name FROM products")
    products = [{"id": r[0], "code": r[1], "name": r[2]} for r in cur.fetchall()]

    cur.execute("""
        SELECT m.id, m.code, m.name, COALESCE(i.stock, 0)
        FROM materials m
        LEFT JOIN inventory i ON i.material_id = m.id
    """)
    materials = [
        {"id": r[0], "code": r[1], "name": r[2], "stock": r[3]}
        for r in cur.fetchall()
    ]

    cur.execute(
        "SELECT product_id, material_id, quantity_required FROM bill_of_materials"
    )
    bom = [
        {"product_id": r[0], "material_id": r[1], "qty": r[2]}
        for r in cur.fetchall()
    ]

    cur.execute("SELECT id, product_id, quantity, order_date FROM sales_orders")
    orders = [
        {
            "id": r[0],
            "product_id": r[1],
            "quantity": r[2],
            "order_date": r[3].isoformat(),
        }
        for r in cur.fetchall()
    ]

    cur.close()
    conn.close()
    return products, materials, bom, orders


def create_constraints(session):
    for label in ("Product", "Material", "SalesOrder"):
        session.run(
            f"CREATE CONSTRAINT {label.lower()}_id IF NOT EXISTS "
            f"FOR (n:{label}) REQUIRE n.id IS UNIQUE"
        )
    session.run(
        "CREATE INDEX material_code IF NOT EXISTS FOR (m:Material) ON (m.code)"
    )
    session.run(
        "CREATE INDEX product_code IF NOT EXISTS FOR (p:Product) ON (p.code)"
    )


def load_graph(tx, products, materials, bom, orders):
    tx.run("""
        UNWIND $rows AS row
        MERGE (p:Product {id: row.id})
        SET p.code = row.code, p.name = row.name
    """, rows=products)

    tx.run("""
        UNWIND $rows AS row
        MERGE (m:Material {id: row.id})
        SET m.code = row.code, m.name = row.name, m.stock = row.stock
    """, rows=materials)

    tx.run("""
        UNWIND $rows AS row
        MATCH (p:Product {id: row.product_id})
        MATCH (m:Material {id: row.material_id})
        MERGE (p)-[r:REQUIRES]->(m)
        SET r.qty = row.qty
    """, rows=bom)

    tx.run("""
        UNWIND $rows AS row
        MATCH (p:Product {id: row.product_id})
        MERGE (so:SalesOrder {id: row.id})
        SET so.quantity = row.quantity, so.order_date = datetime(row.order_date)
        MERGE (so)-[:FOR]->(p)
    """, rows=orders)


if __name__ == "__main__":
    data = extract()
    driver = get_driver()
    with driver.session() as session:
        create_constraints(session)
        session.execute_write(load_graph, *data)
    driver.close()
    print("Graph loaded (products, materials, bom, orders):", [len(d) for d in data])