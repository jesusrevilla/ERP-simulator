import os

from neo4j import GraphDatabase


MATERIALS = [
    {"code": "CPU001", "name": "CPU Ryzen 7", "quantity": 1},
    {"code": "MB001", "name": "Motherboard B650", "quantity": 1},
    {"code": "RAM001", "name": "RAM 16GB DDR5", "quantity": 2},
    {"code": "SSD001", "name": "SSD 1TB NVMe", "quantity": 1},
    {"code": "PSU001", "name": "Power Supply 750W", "quantity": 1},
    {"code": "GPU001", "name": "Graphics Card RTX", "quantity": 1},
]

def create_indexes(driver):
    queries = [
        """
        CREATE INDEX product_code_index IF NOT EXISTS
        FOR (product:Product)
        ON (product.code)
        """,
        """
        CREATE INDEX material_code_index IF NOT EXISTS
        FOR (material:Material)
        ON (material.code)
        """,
    ]

    for query in queries:
        driver.execute_query(query, database_="neo4j")

    print("Índices verificados para Product.code y Material.code.")

def _create_and_remove_example(tx):
    result = tx.run(
        """
        CREATE (example:TutorialExample {name: $name})
        RETURN example.name AS name
        """,
        name="Ejemplo CREATE",
    )

    record = result.single()

    tx.run(
        """
        MATCH (example:TutorialExample {name: $name})
        DELETE example
        """,
        name=record["name"],
    ).consume()

    return record["name"]


def demonstrate_create(driver):
    with driver.session(database="neo4j") as session:
        example_name = session.execute_write(_create_and_remove_example)

    print(f"CREATE creó el nodo de ejemplo: {example_name}")
    print("La transacción lo eliminó para no dejar datos de prueba.")

def _write_bom_graph(tx, product_code, product_name, materials):
    query = """
    MERGE (product:Product {code: $product_code})
    SET product.name = $product_name
    WITH product
    UNWIND $materials AS item
    MERGE (material:Material {code: item.code})
    SET material.name = item.name
    MERGE (product)-[requires:REQUIRES]->(material)
    SET requires.quantity = item.quantity
    RETURN count(material) AS components
    """

    result = tx.run(
        query,
        product_code=product_code,
        product_name=product_name,
        materials=materials,
    )

    record = result.single()
    summary = result.consume()

    return (
        record["components"],
        summary.counters.nodes_created,
        summary.counters.relationships_created,
    )


def create_bom_graph(driver):
    with driver.session(database="neo4j") as session:
        return session.execute_write(
            _write_bom_graph,
            "PC001",
            "Gaming PC",
            MATERIALS,
        )


def _read_required_materials(tx, product_code, order_quantity):
    query = """
    MATCH (product:Product {code: $product_code})
          -[requires:REQUIRES]->
          (material:Material)
    RETURN material.name AS material,
           requires.quantity * $order_quantity AS required
    ORDER BY material
    """

    result = tx.run(
        query,
        product_code=product_code,
        order_quantity=order_quantity,
    )

    return [record.data() for record in result]


def get_required_materials(driver, product_code, order_quantity):
    with driver.session(database="neo4j") as session:
        return session.execute_read(
            _read_required_materials,
            product_code,
            order_quantity,
        )


def main():
    host = os.getenv("NEO4J_HOST", "localhost")
    port = os.getenv("NEO4J_PORT", "7687")
    username = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    order_quantity = int(os.getenv("ORDER_QUANTITY", "30"))

    uri = f"bolt://{host}:{port}"

    with GraphDatabase.driver(uri, auth=(username, password)) as driver:
        driver.verify_connectivity()
        print("Conexión con Neo4j correcta.")

        create_indexes(driver)
        demonstrate_create(driver)

        component_count, nodes_created, relationships_created = create_bom_graph(driver)
        print(f"Componentes relacionados: {component_count}")
        print(f"Nodos creados: {nodes_created}")
        print(f"Relaciones creadas: {relationships_created}")

        requirements = get_required_materials(
            driver,
            product_code="PC001",
            order_quantity=order_quantity,
        )

        print(f"\nMateriales necesarios para {order_quantity} Gaming PC:")
        for item in requirements:
            print(f"{item['material']}: {item['required']}")


if __name__ == "__main__":
    main()