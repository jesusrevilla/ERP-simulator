import os

from dotenv import load_dotenv
from neo4j import GraphDatabase
from neo4j.time import DateTime

load_dotenv()

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD")),
)


def titulo(texto):
    print(f"\n=== {texto} ===")


titulo("1. Conexión")
try:
    driver.verify_connectivity()
    print("Connection successful!")
except Exception as e:
    print(f"Failed to connect to Neo4j: {e}")
    raise SystemExit(1)

titulo("2. Tamaño del grafo")
nodos, _, _ = driver.execute_query("MATCH (n) RETURN count(n) AS nodos", database_="neo4j")
rels, _, _ = driver.execute_query("MATCH ()-[r]->() RETURN count(r) AS relaciones", database_="neo4j")
print(nodos[0].data())
print(rels[0].data())

titulo("3. Equipo con más victorias en la FIFA World Cup")
query = """
MATCH (t:Team)-[:WON]->(m:Match)-[:PART_OF]->(:Tournament {name: "FIFA World Cup"})
RETURN t.name AS Team, COUNT(m) AS MatchesWon
ORDER BY MatchesWon DESC
LIMIT 1
"""
records, summary, keys = driver.execute_query(query, database_="neo4j")
for record in records:
    print(record.data())

titulo("4. Consulta con parámetros (UEFA Euro, top 3)")
query = """
MATCH (t:Team)-[:WON]->(m:Match)-[:PART_OF]->(:Tournament {name: $tournament})
RETURN t.name AS Team, COUNT(m) AS MatchesWon
ORDER BY MatchesWon DESC
LIMIT $limit
"""
records, summary, keys = driver.execute_query(
    query, database_="neo4j", tournament="UEFA Euro", limit=3,
)
for record in records:
    print(record.data())


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
        database_="neo4j",
        coach_name=coach_name,
        team_name=team_name,
        start_date=start_date,
        end_date=end_date,
    )
    summary = result.summary
    print(f"Added new coach: {coach_name} for existing team {team_name} starting from {start_date}")
    print(f"Nodes created: {summary.counters.nodes_created}")
    print(f"Relationships created: {summary.counters.relationships_created}")


titulo("5. Escritura con CREATE (nuevo entrenador)")
add_new_coach(
    driver=driver,
    coach_name="Lionel Scaloni",
    team_name="Argentina",
    start_date=DateTime(2018, 6, 1),
    end_date=None,
)

titulo("6. Verificación del entrenador creado")
records, _, _ = driver.execute_query(
    """
    MATCH (c:Coach)-[r:COACHES]->(t:Team)
    RETURN c.name AS Coach, t.name AS Team, r.start_date AS Start
    """,
    database_="neo4j",
)
for record in records:
    print(record.data())


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


titulo("7. Transacción con sesión (goleadores de la FIFA World Cup)")
with driver.session() as session:
    result = session.execute_read(top_goal_scorers, "FIFA World Cup", 5)
    for record in result:
        print(record)

driver.close()
