"""Ejercicios del tutorial de Neo4j: consultas Cypher sobre el grafo de
partidos de fútbol internacional (1872-2024), usando el driver oficial de
Python (neo4j) sobre una instancia de Neo4j AuraDB.

Requiere que ya se haya corrido `ingest_football_data.py` sobre la misma
instancia (ver README.md de esta carpeta).

Uso:
    python consultas.py
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv(Path(__file__).with_name(".env"))


def mostrar(titulo, registros):
    print(f"\n--- {titulo} ---")
    if not registros:
        print("Sin resultados (¿corriste ingest_football_data.py?)")
        return
    for registro in registros:
        print(registro.data() if hasattr(registro, "data") else registro)


def equipo_mas_ganador(driver, database, torneo, limite=1):
    """MATCH + RETURN + COUNT + ORDER BY + LIMIT: equipo(s) con más
    victorias dentro de un torneo dado (consulta parametrizada)."""
    query = """
    MATCH (t:Team)-[:WON]->(m:Match)-[:PART_OF]->(:Tournament {name: $torneo})
    RETURN t.name AS Equipo, COUNT(m) AS PartidosGanados
    ORDER BY PartidosGanados DESC
    LIMIT $limite
    """
    registros, _, _ = driver.execute_query(
        query, database_=database, torneo=torneo, limite=limite
    )
    return registros


def top_goleadores(tx, torneo, limite):
    """Función de transacción para usar con session.execute_read():
    los jugadores que más goles anotaron en un torneo."""
    query = """
    MATCH (p:Player)-[s:SCORED_IN]->(m:Match)-[:PART_OF]->(t:Tournament)
    WHERE t.name = $torneo
    RETURN p.name AS Jugador, COUNT(s) AS Goles
    ORDER BY Goles DESC
    LIMIT $limite
    """
    resultado = tx.run(query, torneo=torneo, limite=limite)
    return [registro.data() for registro in resultado]


def registrar_entrenador(driver, database, entrenador, equipo, fecha_inicio):
    """CREATE + MERGE: agrega un nodo Coach y su relación COACHES con un
    equipo existente, sin duplicar si ya existía (MERGE en vez de CREATE
    para el nodo y la relación, igual que recomienda el tutorial)."""
    query = """
    MATCH (t:Team {name: $equipo})
    MERGE (c:Coach {name: $entrenador})
    MERGE (c)-[r:COACHES]->(t)
    SET r.start_date = date($fecha_inicio)
    RETURN c.name AS Entrenador, t.name AS Equipo, r.start_date AS Desde
    """
    resultado = driver.execute_query(
        query,
        database_=database,
        entrenador=entrenador,
        equipo=equipo,
        fecha_inicio=fecha_inicio,
    )
    return resultado


def main():
    uri = os.getenv("NEO4J_URI")
    usuario = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")
    base = os.getenv("NEO4J_DATABASE", "neo4j")

    if not all((uri, usuario, password)):
        raise RuntimeError(
            "Crea un archivo .env (a partir de .env.example) con "
            "NEO4J_URI, NEO4J_USERNAME y NEO4J_PASSWORD."
        )

    driver = GraphDatabase.driver(uri, auth=(usuario, password))
    try:
        driver.verify_connectivity()

        # 1) ¿Qué equipo ganó más partidos de la Copa Mundial?
        registros = equipo_mas_ganador(driver, base, "FIFA World Cup", limite=1)
        mostrar("Equipo con más victorias en la FIFA World Cup", registros)

        # 2) Misma consulta, pero parametrizada para otro torneo y top 3.
        registros = equipo_mas_ganador(driver, base, "UEFA Euro", limite=3)
        mostrar("Top 3 equipos con más victorias en la UEFA Euro", registros)

        # 3) Transacción de lectura explícita con session.execute_read().
        with driver.session(database=base) as session:
            goleadores = session.execute_read(
                top_goleadores, "FIFA World Cup", 5
            )
        mostrar("Top 5 goleadores históricos de la FIFA World Cup", goleadores)

        # 4) Escritura: registrar un entrenador con MERGE (no duplica si
        #    ya existe el mismo Coach/relación).
        resultado = registrar_entrenador(
            driver,
            base,
            entrenador="Lionel Scaloni",
            equipo="Argentina",
            fecha_inicio="2018-06-01",
        )
        mostrar("Entrenador registrado (MERGE)", resultado.records)
        print(
            f"Nodos creados: {resultado.summary.counters.nodes_created}, "
            f"relaciones creadas: {resultado.summary.counters.relationships_created}"
        )

    finally:
        driver.close()

    print("\nConsultas completadas.")


if __name__ == "__main__":
    main()
