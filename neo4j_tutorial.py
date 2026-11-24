import os
from dotenv import load_dotenv
from neo4j import GraphDatabase
from neo4j.time import DateTime
from datetime import datetime

# 1. Cargar las credenciales
load_dotenv()
URI = os.getenv("NEO4J_URI")
AUTH = (os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD"))

# 2. Funciones Cypher para crear y leer Nodos/Relaciones
def create_team_and_coach(tx, team_name, coach_name, start_date, end_date):
    query = """
    MERGE (t:Team {name: $team_name})
    MERGE (c:Coach {name: $coach_name})
    MERGE (c)-[r:COACHES]->(t)
    SET r.start_date = $start_date, r.end_date = $end_date
    """
    tx.run(query, team_name=team_name, coach_name=coach_name, start_date=start_date, end_date=end_date)

def get_coaches_data(tx):
    query = """
    MATCH (c:Coach)-[r:COACHES]->(t:Team)
    RETURN c.name AS coach_name, t.name AS team_name, r.start_date AS start_date
    """
    return [record for record in tx.run(query)]

# 3. Bloque principal de ejecución
if __name__ == "__main__":
    # Creamos el driver usando 'with' para que englobe toda la operación
    with GraphDatabase.driver(URI, auth=AUTH) as driver:
        
        # Verificamos conectividad
        driver.verify_connectivity()
        print("Conexión exitosa a Neo4j AuraDB.")
        
        # Abrimos la sesión usando el driver que sigue activo
        with driver.session() as session:
            start = DateTime.from_native(datetime(2023, 1, 1))
            end = DateTime.from_native(datetime(2024, 1, 1))
            
            # Transacciones de escritura
            session.execute_write(create_team_and_coach, "Real Madrid", "Carlo Ancelotti", start, end)
            session.execute_write(create_team_and_coach, "Manchester City", "Pep Guardiola", start, end)
            print("Nodos y relaciones creados con éxito.")
            
            # Transacciones de lectura
            results = session.execute_read(get_coaches_data)
            print("\n--- Resultados del Grafo ---")
            for row in results:
                print(f"[{row['coach_name']}] entrena a [{row['team_name']}] desde el {row['start_date']}")