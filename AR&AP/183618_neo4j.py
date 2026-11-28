import os
from neo4j import GraphDatabase

# 1. Obtener las credenciales del entorno
host = os.getenv('NEO4J_HOST', 'localhost')
port = os.getenv('NEO4J_PORT', '7687')
user = os.getenv('NEO4J_USER', 'neo4j')
password = os.getenv('NEO4J_PASSWORD', 'password')

URI = f"bolt://{host}:{port}"

def create_arap_graph(tx):
    # Limpiar la base de datos por si hay ejecuciones previas
    tx.run("MATCH (n) DETACH DELETE n")
    
    # Crear un grafo del módulo AR&AP (Cliente -> adeuda -> Factura)
    query = """
    CREATE (c:Cliente {nombre: 'Tech Corp', rfc: 'TECH001'})
    CREATE (f1:Factura {folio: 'INV-994812', monto: 150000.0, estado: 'Pendiente'})
    CREATE (f2:Factura {folio: 'INV-994813', monto: 45000.0, estado: 'Pagada'})
    CREATE (c)-[:ADEUDA]->(f1)
    CREATE (c)-[:ADEUDA]->(f2)
    """
    tx.run(query)
    print("Grafo de AR&AP (Clientes y Facturas) creado exitosamente en Neo4j.")

if __name__ == "__main__":
    print(f"Conectando a Neo4j en {URI}...")
    driver = GraphDatabase.driver(URI, auth=(user, password))
    
    with driver.session() as session:
        session.execute_write(create_arap_graph)
    
    driver.close()