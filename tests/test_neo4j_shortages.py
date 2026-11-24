import pytest
from src.neo4j_load import get_driver, get_pg
from src.neo4j_shortages import shortages


def shortages_postgres():
    try:
        conn = get_pg()
    except Exception:
        pytest.skip("PostgreSQL no disponible")
    cur = conn.cursor()
    cur.execute("""
        SELECT m.name,
               SUM(bom.quantity_required * so.quantity) - i.stock AS shortage
        FROM sales_orders so
        JOIN bill_of_materials bom ON bom.product_id = so.product_id
        JOIN materials m ON m.id = bom.material_id
        JOIN inventory i ON i.material_id = m.id
        GROUP BY m.name, i.stock
    """)
    result = {name: shortage for name, shortage in cur.fetchall()}
    cur.close()
    conn.close()
    return result


def shortages_neo4j():
    try:
        driver = get_driver()
    except Exception:
        pytest.skip("Neo4j no disponible")
    with driver.session() as session:
        rows = session.execute_read(shortages)
    driver.close()
    return {r["material"]: r["shortage"] for r in rows}


def test_neo4j_matches_postgres():
    assert shortages_neo4j() == shortages_postgres()