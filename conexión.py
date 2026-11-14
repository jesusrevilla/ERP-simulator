import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

class Neo4jConnection:
    def __init__(self):

        uri = os.getenv("NEO4J_URI")
        user = os.getenv("NEO4J_USERNAME")
        password = os.getenv("NEO4J_PASSWORD")
        
        if not uri:
            host = os.getenv("NEO4J_HOST", "localhost")
            port = os.getenv("NEO4J_PORT", "7687")
            uri = f"neo4j://{host}:{port}"

        try:
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
            self.driver.verify_connectivity()
            print("Conexión a Neo4j establecida con éxito.")
        except Exception as e:
            print(f"Error al conectar con Neo4j: {e}")

    def close(self):
        if self.driver:
            self.driver.close()
            print("Conexión a Neo4j cerrada.")

# Bloque de prueba
if __name__ == "__main__":
    db_conn = Neo4jConnection()
    
    db_conn.close()