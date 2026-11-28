import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()
URI = os.getenv("NEO4J_URI")
AUTH = (os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD"))
def main():
    with GraphDatabase.driver(URI, auth=AUTH) as driver:
        try:
            driver.verify_connectivity()
            print("Conexión exitosa")
        except Exception as e:
            print(f"Error de conexión: {e}")
            return
        with driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
            print("Insertando datos...")
            session.run("CREATE (p:Persona {nombre: 'Chui', rol: 'Healer'})")
            session.run("CREATE (p:Persona {nombre: 'Rivera', rol: 'Tanque'})")
            session.run("CREATE (p:Persona {nombre: 'Ale', rol: 'DPS'})")
            print("\nConsultando el grafo:")
            resultado = session.run("MATCH (p:Persona) RETURN p.nombre AS nombre, p.rol AS rol")
            for registro in resultado:
                print(f"- {registro['nombre']} ({registro['rol']})")

if __name__ == "__main__":
    main()
