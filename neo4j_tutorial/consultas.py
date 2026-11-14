
import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

URI = os.getenv("NEO4J_URI")
USERNAME = os.getenv("NEO4J_USERNAME")
PASSWORD = os.getenv("NEO4J_PASSWORD")

driver = GraphDatabase.driver(
    URI,
    auth=(USERNAME, PASSWORD)
)

try:
    driver.verify_connectivity()
    print("Conexión exitosa con Neo4j\n")

    # Consulta 1: equipo con más partidos ganados en mundiales
    query = """
    MATCH (t:Team)-[:WON]->(m:Match)-[:PART_OF]->(:Tournament {name: "FIFA World Cup"})
    RETURN t.name AS Equipo, COUNT(m) AS PartidosGanados
    ORDER BY PartidosGanados DESC
    LIMIT 1
    """

    records, summary, keys = driver.execute_query(
        query
    )

    print("Equipo con más partidos ganados en mundiales:")
    for record in records:
        print(record.data())

    # Consulta 2: equipos con más partidos ganados en la Euro
    query = """
    MATCH (t:Team)-[:WON]->(m:Match)-[:PART_OF]->(:Tournament {name: $tournament})
    RETURN t.name AS Equipo, COUNT(m) AS PartidosGanados
    ORDER BY PartidosGanados DESC
    LIMIT $limite
    """

    records, summary, keys = driver.execute_query(
        query,
        tournament="UEFA Euro",
        limite=3
    )

    print("\nEquipos con más partidos ganados en la Euro:")
    for record in records:
        print(record.data())

except Exception as e:
    print("Ocurrió un error:", e)

finally:
    driver.close()
