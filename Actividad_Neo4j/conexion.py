import os
from neo4j import GraphDatabase

# Hardcoded credentials to bypass .env issues
URI = "neo4j+ssc://7a3a1081.databases.neo4j.io"
USERNAME = "7a3a1081"
PASSWORD = "2ze9f9yhcFfvqo0sU9A7x5b-kmNAFww8sKiuOEindy4"

def main():
    print(f"Intentando conectar a: {URI}...")
    try:
        with GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD)) as driver:
            driver.verify_connectivity()
            print("¡Conexión correcta con Neo4j AuraDB!")
    except Exception as e:
        print(f"Error de conexión: {e}")

if __name__ == "__main__":
    main()