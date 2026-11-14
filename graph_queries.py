import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

# Cargar variables de entorno
load_dotenv()
URI = os.getenv("NEO4J_URI")
AUTH = (os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD"))

def main():
    # Conectar a la base de datos
    with GraphDatabase.driver(URI, auth=AUTH) as driver:
        try:
            driver.verify_connectivity()
            print("Conexión exitosa a Neo4j Aura DB!")
        except Exception as e:
            print(f"Error de conexión: {e}")
            return

        # Ejecutar operaciones con una sesión
        with driver.session() as session:
            # 1. Borrar datos previos (opcional, para mantener limpio el grafo en las pruebas)
            session.run("MATCH (n) DETACH DELETE n")

            # 2. Insertar nodos (CREATE)
            print("Insertando datos...")
            session.run("CREATE (p:Persona {nombre: 'Leo', rol: 'Ingeniero de Procesos'})")
            session.run("CREATE (p:Persona {nombre: 'Alice', rol: 'Desarrolladora'})")

            # 3. Consultar los nodos (MATCH)
            print("\nConsultando el grafo:")
            resultado = session.run("MATCH (p:Persona) RETURN p.nombre AS nombre, p.rol AS rol")
            
            for registro in resultado:
                print(f"- {registro['nombre']} ({registro['rol']})")

if __name__ == "__main__":
    main()