"""Comprobar la conexión de Python con una instancia de Neo4j AuraDB."""

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
        raise RuntimeError("Faltan datos de Neo4j en el archivo .env")

    with GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD)) as driver:
        driver.verify_connectivity()
        print("Conexión correcta con Neo4j AuraDB")


if __name__ == "__main__":
    main()
