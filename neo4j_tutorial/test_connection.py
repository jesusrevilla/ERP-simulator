import os
from neo4j import GraphDatabase

uri = os.getenv("NEO4J_URI")
username = os.getenv("NEO4J_USERNAME")
password = os.getenv("NEO4J_PASSWORD")

if not uri or not username or not password:
    raise ValueError("Faltan las credenciales de Neo4j.")

driver = GraphDatabase.driver(
    uri,
    auth=(username, password)
)

try:
    driver.verify_connectivity()
    print("Conexion exitosa con Neo4j Aura.")

    with driver.session() as session:
        result = session.run("RETURN 'Neo4j funciona correctamente' AS message")
        print(result.single()["message"])

finally:
    driver.close()
