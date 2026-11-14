import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

# Cargar variables del archivo .env
load_dotenv()

URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "SuperPassword123")


class Neo4jTutorial:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def reset_database(self):
        """Elimina todos los nodos y relaciones para empezar limpio."""
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
            print("✔ Base de datos reiniciada.")

    def create_graph(self):
        """Crea nodos de Personas, Proyectos y sus relaciones."""
        query = """
        CREATE (dev:Developer {name: 'Pedro', role: 'Full Stack'})
        CREATE (proj:Project {name: 'Graph Management System', status: 'Active'})
        CREATE (tech:Technology {name: 'Neo4j', type: 'Graph Database'})
        CREATE (dev)-[:WORKS_ON {role: 'Lead'}]->(proj)
        CREATE (proj)-[:USES]->(tech)
        """
        with self.driver.session() as session:
            session.run(query)
            print("✔ Grafo de prueba generado correctamente.")

    def query_graph(self):
        """Consulta el grafo para verificar las relaciones."""
        query = """
        MATCH (d:Developer)-[r:WORKS_ON]->(p:Project)-[:USES]->(t:Technology)
        RETURN d.name AS developer, p.name AS project, t.name AS technology
        """
        with self.driver.session() as session:
            results = session.run(query)
            print("\n--- Resultados de la Consulta Cypher ---")
            for record in results:
                print(f"Desarrollador: {record['developer']} | "
                      f"Proyecto: {record['project']} | "
                      f"Tecnología: {record['technology']}")


if __name__ == "__main__":
    app = Neo4jTutorial(URI, USER, PASSWORD)
    try:
        app.reset_database()
        app.create_graph()
        app.query_graph()
    finally:
        app.close()
