import os
from dotenv import load_dotenv
load_dotenv()
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_URI = os.getenv("NEO4J_URI")
from neo4j import GraphDatabase
uri = NEO4J_URI
username = NEO4J_USERNAME
password = NEO4J_PASSWORD
driver = GraphDatabase.driver(uri, auth=(username, password))
try:
   driver.verify_connectivity()
   print("Connection successful!")
except Exception as e:
   print(f"Failed to connect to Neo4j: {e}")