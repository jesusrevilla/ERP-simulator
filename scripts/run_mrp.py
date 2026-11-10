from neo4j import GraphDatabase

def create_bom(tx):
    tx.run("MERGE (p:Producto {nombre: 'Gaming PC'})")
    componentes = ["CPU Ryzen 7", "Motherboard B650", "RAM 16GB DDR5", "SSD 1TB NVMe", "Power Supply 750W", "Graphics Card RTX"]
    for comp in componentes:
        tx.run("""
            MATCH (p:Producto {nombre: 'Gaming PC'})
            MERGE (c:Componente {nombre: $nombre})
            MERGE (p)-[:REQUIERE {cantidad: 1}]->(c)
        """, nombre=comp)

def main():
    driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "mrp_password"))
    with driver.session() as session:
        session.execute_write(create_bom)
        print("Neo4j: OK")
    driver.close()

if __name__ == "__main__":
    main()