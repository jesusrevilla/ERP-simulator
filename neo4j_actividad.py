"""
Actividad Neo4j con Python (AuraDB + Cypher)
Aaron Emanuel Gonzalez Diaz - Matrícula 182447

Requisitos:
    pip install neo4j python-dotenv
Archivo .env en la misma carpeta:
    NEO4J_USERNAME="..."
    NEO4J_PASSWORD="..."
    NEO4J_URI="neo4j+s://xxxx.databases.neo4j.io"
Antes de correrlo, la base debe estar poblada con ingest_football_data.py (ver tutorial).
"""
import os

from dotenv import load_dotenv
from neo4j import GraphDatabase
from neo4j.time import DateTime

load_dotenv()
URI = os.getenv("NEO4J_URI") or os.getenv("NEO4J_CONNECTION_URI")
USER = os.getenv("NEO4J_USERNAME")
PASSWORD = os.getenv("NEO4J_PASSWORD")


def conectar():
    """Crea el driver y verifica la conexión."""
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    driver.verify_connectivity()
    print("Connection successful!")
    return driver


def equipo_con_mas_victorias(driver):
    """Consulta fija: equipo con más victorias en la Copa del Mundo."""
    query = """
    MATCH (t:Team)-[:WON]->(m:Match)-[:PART_OF]->(:Tournament {name: "FIFA World Cup"})
    RETURN t.name AS Team, COUNT(m) AS MatchesWon
    ORDER BY MatchesWon DESC
    LIMIT 1
    """
    records, summary, keys = driver.execute_query(query, database_="neo4j")
    return [r.data() for r in records]


def mejores_equipos(driver, torneo, limite):
    """Consulta con parámetros ($tournament, $limit): reutilizable para cualquier torneo."""
    query = """
    MATCH (t:Team)-[:WON]->(m:Match)-[:PART_OF]->(:Tournament {name: $tournament})
    RETURN t.name AS Team, COUNT(m) AS MatchesWon
    ORDER BY MatchesWon DESC
    LIMIT $limit
    """
    records, _, _ = driver.execute_query(query, database_="neo4j", tournament=torneo, limit=limite)
    return [r.data() for r in records]


def goles_en_propia(driver, minuto_min=80, limite=5):
    """Ejemplo de MATCH + WHERE + RETURN + ORDER BY + LIMIT con goles en propia puerta."""
    query = """
    MATCH (p:Player)-[s:SCORED_IN]->(m:Match)-[:PART_OF]->(t:Tournament)
    WHERE t.name = "FIFA World Cup" AND s.minute > $minuto AND s.own_goal = True
    RETURN p.name AS Player, m.date AS MatchDate, s.minute AS GoalMinute
    ORDER BY s.minute DESC
    LIMIT $limite
    """
    records, _, _ = driver.execute_query(query, database_="neo4j", minuto=minuto_min, limite=limite)
    return [r.data() for r in records]


def add_new_coach(driver, coach_name, team_name, start_date, end_date):
    """Escritura con CREATE: nuevo nodo Coach y relación COACHES con un equipo existente."""
    query = """
    MATCH (t:Team {name: $team_name})
    CREATE (c:Coach {name: $coach_name})
    CREATE (c)-[r:COACHES]->(t)
    SET r.start_date = $start_date
    SET r.end_date = $end_date
    """
    result = driver.execute_query(
        query, database_="neo4j", coach_name=coach_name, team_name=team_name,
        start_date=start_date, end_date=end_date)
    summary = result.summary
    print(f"Added new coach: {coach_name} for existing team {team_name} starting from {start_date}")
    print(f"Nodes created: {summary.counters.nodes_created}")
    print(f"Relationships created: {summary.counters.relationships_created}")


def top_goal_scorers(tx, tournament, limit):
    """Función de transacción para usar con session.execute_read."""
    query = """
    MATCH (p:Player)-[s:SCORED_IN]->(m:Match)-[:PART_OF]->(t:Tournament)
    WHERE t.name = $tournament
    RETURN p.name AS Player, COUNT(s) AS Goals
    ORDER BY Goals DESC
    LIMIT $limit
    """
    result = tx.run(query, tournament=tournament, limit=limit)
    return [record.data() for record in result]


def main():
    driver = conectar()
    try:
        print("\n1) Equipo con más victorias en la Copa del Mundo")
        print(equipo_con_mas_victorias(driver))

        print("\n2) Top 3 de la Eurocopa (consulta con parámetros)")
        for fila in mejores_equipos(driver, "UEFA Euro", 3):
            print(fila)

        print("\n3) Goles en propia puerta después del minuto 80 (Copa del Mundo)")
        for fila in goles_en_propia(driver):
            print(fila)

        print("\n4) Agregar entrenador (CREATE)")
        add_new_coach(driver, "Lionel Scaloni", "Argentina", DateTime(2018, 6, 1), None)

        print("\n5) Máximos goleadores de la Copa del Mundo (transacción de lectura)")
        with driver.session() as session:
            for fila in session.execute_read(top_goal_scorers, "FIFA World Cup", 5):
                print(fila)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
