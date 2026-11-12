"""Comprueba la conexión de Python con una instancia de Neo4j AuraDB.

Uso:
    python conexion.py
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv(Path(__file__).with_name(".env"))

URI = os.getenv("NEO4J_URI")
USERNAME = os.getenv("NEO4J_USERNAME")
PASSWORD = os.getenv("NEO4J_PASSWORD")


def main():
    if not all((URI, USERNAME, PASSWORD)):
        raise RuntimeError(
            "Faltan credenciales. Copia .env.example a .env y llena "
            "NEO4J_URI, NEO4J_USERNAME y NEO4J_PASSWORD con los datos "
            "de tu instancia de AuraDB."
        )

    driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD))
    try:
        driver.verify_connectivity()
        print("Conexión correcta con Neo4j AuraDB")
    except Exception as exc:
        print(f"No se pudo conectar a Neo4j: {exc}")
    finally:
        driver.close()


if __name__ == "__main__":
    main()
