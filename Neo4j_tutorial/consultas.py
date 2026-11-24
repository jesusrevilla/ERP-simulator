import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()
driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD")),
)

query = """
MATCH (t:Team)-[:WON]->(m:Match)-[:PART_OF]->(:Tournament {name: "FIFA World Cup"})
RETURN t.name AS Team, COUNT(m) AS MatchesWon
ORDER BY MatchesWon DESC
LIMIT 1
"""
records, summary, keys = driver.execute_query(query, database_="neo4j")
for record in records:
    print(record.data())
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
        database_="neo4j",
        coach_name=coach_name,
        team_name=team_name,
        start_date=start_date,
        end_date=end_date,
    )
    summary = result.summary
    print(f"Added new coach: {coach_name} for existing team {team_name}")
    print(f"Nodes created: {summary.counters.nodes_created}")
    print(f"Relationships created: {summary.counters.relationships_created}")

add_new_coach(driver, "Lionel Scaloni", "Argentina", DateTime(2018, 6, 1), None)

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

with driver.session(database="neo4j") as session:
    result = session.execute_read(top_goal_scorers, "FIFA World Cup", 5)
    for record in result:
        print(record)

driver.close()