from src.neo4j_load import get_driver


def shortages(tx):
    query = """
    MATCH (so:SalesOrder)-[:FOR]->(:Product)-[r:REQUIRES]->(m:Material)
    WITH m, sum(r.qty * so.quantity) AS required
    RETURN m.name AS material, m.stock AS stock, required,
           required - m.stock AS shortage
    ORDER BY material
    """
    return [rec.data() for rec in tx.run(query)]


def what_if(driver, product_code, quantity):
    query = """
    MATCH (:Product {code: $code})-[r:REQUIRES]->(m:Material)
    RETURN m.name AS material, m.stock AS stock,
           r.qty * $quantity AS required,
           r.qty * $quantity - m.stock AS shortage
    ORDER BY material
    """
    records, _, _ = driver.execute_query(
        query, code=product_code, quantity=quantity, database_="neo4j"
    )
    return [r.data() for r in records]


if __name__ == "__main__":
    driver = get_driver()

    print("Faltantes de la orden de venta actual:")
    with driver.session() as session:
        for row in session.execute_read(shortages):
            if row["shortage"] > 0:
                print(f"{row['material']}: shortage={row['shortage']}")
            else:
                print(f"{row['material']}: stock OK")

    print("\nWhat-if: 100 Gaming PC")
    for row in what_if(driver, "PC001", 100):
        print(row)

    driver.close()