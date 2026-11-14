import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_URI = os.getenv("NEO4J_URI")

print(f"Conectando a: {NEO4J_URI} con usuario: {NEO4J_USER}")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

try:
    driver.verify_connectivity()
    print("¡Conexión exitosa a Neo4j Aura! 🎉")
except Exception as e:
    print(f"Fallo al conectar a Neo4j: {e}")
finally:
    driver.close()