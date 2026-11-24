
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

def maximos_goleadores(tx, torneo, limite):
    query = """
    MATCH (p:Player)-[s:SCORED_IN]->(m:Match)-[:PART_OF]->(t:Tournament)
    WHERE t.name = $torneo
    RETURN p.name AS Jugador, COUNT(s) AS Goles
    ORDER BY Goles DESC
    LIMIT $limite
    """

    resultado = tx.run(
        query,
        torneo=torneo,
        limite=limite
    )

    return [registro.data() for registro in resultado]

try:
    with driver.session() as session:
        resultados = session.execute_read(
            maximos_goleadores,
            "FIFA World Cup",
            5
        )

        print("Máximos goleadores de los mundiales:")

        for jugador in resultados:
            print(jugador)

except Exception as e:
    print("Error:", e)

finally:
    driver.close()
