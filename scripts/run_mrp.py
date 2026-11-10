from neo4j import GraphDatabase

def create_bom(tx):
    tx.run("MERGE (p:Producto {nombre: 'Gaming PC'})")
    
    # Diccionario con la cantidad exacta por cada computadora
    componentes = {
        "CPU Ryzen 7": 1, 
        "Motherboard B650": 1, 
        "RAM 16GB DDR5": 2, 
        "SSD 1TB NVMe": 1, 
        "Power Supply 750W": 1, 
        "Graphics Card RTX": 1
    }
    
    for nombre, cantidad in componentes.items():
        tx.run("""
            MATCH (p:Producto {nombre: 'Gaming PC'})
            MERGE (c:Componente {nombre: $nombre})
            MERGE (p)-[:REQUIERE {cantidad: $cantidad}]->(c)
        """, nombre=nombre, cantidad=cantidad)

def main():
    driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "mrp_password"))
    with driver.session() as session:
        # Primero borramos todo para asegurar que no queden relaciones viejas
        session.run("MATCH (n) DETACH DELETE n")
        # Luego creamos la receta nueva
        session.execute_write(create_bom)
        print("Neo4j: Receta de BOM creada correctamente (2 RAMs por PC).")
    driver.close()

if __name__ == "__main__":
    main()