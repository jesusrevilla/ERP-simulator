import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

try:
    driver.verify_connectivity()
    print("Connection successful!")
except Exception as e:
    print(f"Failed to connect to Neo4j: {e}")

# Consulta 1: equipo con más victorias en el Mundial
query = """
MATCH (t:Team)-[:WON]->(m:Match)-[:PART_OF]->(:Tournament {name: "FIFA World Cup"})
RETURN t.name AS Team, COUNT(m) AS MatchesWon
ORDER BY MatchesWon DESC
LIMIT 1
"""
records, summary, keys = driver.execute_query(query, database_=DATABASE)
print("\nConsulta 1: equipo con más victorias en el Mundial")
for record in records:
    print(record.data())

# Consulta 2: con parámetros (Eurocopa, top 3)
query = """
MATCH (t:Team)-[:WON]->(m:Match)-[:PART_OF]->(:Tournament {name: $tournament})
RETURN t.name AS Team, COUNT(m) AS MatchesWon
ORDER BY MatchesWon DESC
LIMIT $limit
"""
records, summary, keys = driver.execute_query(
    query, database_=DATABASE, tournament="UEFA Euro", limit=3
)
print("\nConsulta 2: top 3 de la Eurocopa")
for record in records:
    print(record.data())

# Escritura: agregar un entrenador
from neo4j.time import DateTime


def add_new_coach(driver, coach_name, team_name, start_date, end_date):
    query = """
    MATCH (t:Team {name: $team_name})
    CREATE (c:Coach {name: $coach_name})
    CREATE (c)-[r:COACHES]->(t)
    SET r.start_date = $start_date
    SET r.end_date = $end_date
    """
    result = driver.execute_query(
        query,
        database_=DATABASE,
        coach_name=coach_name,
        team_name=team_name,
        start_date=start_date,
        end_date=end_date,
    )
    summary = result.summary
    print(f"Added new coach: {coach_name} for existing team {team_name} starting from {start_date}")
    print(f"Nodes created: {summary.counters.nodes_created}")
    print(f"Relationships created: {summary.counters.relationships_created}")


print("\nEscritura: agregar entrenador")
add_new_coach(
    driver=driver,
    coach_name="Lionel Scaloni",
    team_name="Argentina",
    start_date=DateTime(2018, 6, 1),
    end_date=None,
)


# Transacciones: top goleadores con sesión
def top_goal_scorers(tx, tournament, limit):
    query = """
    MATCH (p:Player)-[s:SCORED_IN]->(m:Match)-[:PART_OF]->(t:Tournament)
    WHERE t.name = $tournament
    RETURN p.name AS Player, COUNT(s) AS Goals
    ORDER BY Goals DESC
    LIMIT $limit
    """
    result = tx.run(query, tournament=tournament, limit=limit)
    return [record.data() for record in result]


print("\nTransacciones: top 5 goleadores del Mundial")
with driver.session(database=DATABASE) as session:
    result = session.execute_read(top_goal_scorers, "FIFA World Cup", 5)
    for record in result:
        print(record)

driver.close()