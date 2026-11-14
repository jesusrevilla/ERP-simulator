"""Ejercicios del tutorial: consultas Cypher de partidos de fútbol."""

import os
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv(Path(__file__).with_name(".env"))


def mostrar(titulo, registros):
    print(f"\n--- {titulo} ---")
    if not registros:
        print("No se encontraron registros. ¿Importaste los CSV del tutorial?")
    for registro in registros:
        print(registro.data())


def top_goleadores(tx, torneo, limite):
    resultado = tx.run(
        """
        MATCH (p:Player)-[s:SCORED_IN]->(m:Match)-[:PART_OF]->(t:Tournament)
        WHERE t.name = $torneo
        RETURN p.name AS Jugador, COUNT(s) AS Goles
        ORDER BY Goles DESC
        LIMIT $limite
        """,
        torneo=torneo,
        limite=limite,
    )
    return list(resultado)


def main():
    uri = os.getenv("NEO4J_URI")
    usuario = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")
    base = os.getenv("NEO4J_DATABASE", "neo4j")
    if not all((uri, usuario, password)):
        raise RuntimeError("Crea .env con NEO4J_URI, NEO4J_USERNAME y NEO4J_PASSWORD")

    with GraphDatabase.driver(uri, auth=(usuario, password)) as driver:
        driver.verify_connectivity()

        # ¿Cuál equipo ganó más partidos de la Copa Mundial?
        registros, _, _ = driver.execute_query(
            """
            MATCH (t:Team)-[:WON]->(m:Match)-[:PART_OF]->
                  (:Tournament {name: 'FIFA World Cup'})
            RETURN t.name AS Equipo, COUNT(m) AS PartidosGanados
            ORDER BY PartidosGanados DESC
            LIMIT 1
            """,
            database_=base,
        )
        mostrar("Equipo con más victorias mundialistas", registros)

        # Parámetros reutilizables: torneo y número de resultados.
        registros, _, _ = driver.execute_query(
            """
            MATCH (t:Team)-[:WON]->(m:Match)-[:PART_OF]->
                  (:Tournament {name: $torneo})
            RETURN t.name AS Equipo, COUNT(m) AS PartidosGanados
            ORDER BY PartidosGanados DESC
            LIMIT $limite
            """,
            torneo="UEFA Euro",
            limite=3,
            database_=base,
        )
        mostrar("Tres equipos con más victorias en la Eurocopa", registros)

        # Session + execute_read: consultar goleadores del Mundial.
        with driver.session(database=base) as session:
            goleadores = session.execute_read(top_goleadores, "FIFA World Cup", 5)
        mostrar("Cinco máximos goleadores mundialistas", goleadores)

        # Escritura con MERGE para evitar duplicar al mismo entrenador.
        resultado = driver.execute_query(
            """
            MATCH (t:Team {name: $equipo})
            MERGE (c:Coach {name: $entrenador})
            MERGE (c)-[r:COACHES]->(t)
            SET r.start_date = date($fecha_inicio)
            RETURN c.name AS Entrenador, t.name AS Equipo
            """,
            entrenador="Lionel Scaloni",
            equipo="Argentina",
            fecha_inicio="2018-06-01",
            database_=base,
        )
        mostrar("Relación entrenador-equipo", resultado.records)

    print("\nEjercicios terminados.")


if __name__ == "__main__":
    main()
