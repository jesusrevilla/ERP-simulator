import os
from neo4j import GraphDatabase

HOST = os.getenv("NEO4J_HOST", "localhost")
PORT = os.getenv("NEO4J_PORT", "7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

URI = f"bolt://{HOST}:{PORT}"

def construir_y_verificar_grafo(tx):
    # 1. Verifica cuantos nodos cargo previamente el script del profesor (src.neo4j_load)
    conteo_base = tx.run("MATCH (n) RETURN count(n) AS total").single()["total"]
    print(f"Nodos cargados por src.neo4j_load: {conteo_base}")

    # 2. Crea un grafo simple de ejemplo para la entrega (Matricula 184838)
    query_grafo = """
    MERGE (cli:ClienteAR {id: 'CLI-184838', nombre: 'Ensambles del Bajio SA', limite_credito: 150000})
    MERGE (fac:FacturaAR {folio: 'FAC-9001', monto: 45000, estatus: 'PENDIENTE'})
    MERGE (prov:ProveedorAP {id: 'PROV-184838', nombre: 'Componentes SLP'})
    MERGE (oc:OrdenCompraAP {folio: 'OC-5010', total: 28000, estatus: 'APROBADA'})

    MERGE (cli)-[:TIENE_FACTURA {dias_credito: 30}]->(fac)
    MERGE (prov)-[:SURTE_ORDEN {tiempo_entrega: 3}]->(oc)
    """
    tx.run(query_grafo)

    # 3. Consulta el grafo simple creado para dejar evidencia en los logs de GitHub Actions
    registros = tx.run("""
        MATCH (c:ClienteAR)-[r:TIENE_FACTURA]->(f:FacturaAR)
        RETURN c.nombre AS cliente, f.folio AS factura, f.monto AS monto, r.dias_credito AS plazo
    """)

    print("=== GRAFO SIMPLE GENERADO EXITOSAMENTE (184838) ===")
    for row in registros:
        print(f"Cliente: {row['cliente']} -> Factura: {row['factura']} (${row['monto']}) | Plazo: {row['plazo']} dias")

def main():
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    try:
        driver.verify_connectivity()
        with driver.session() as session:
            session.execute_write(construir_y_verificar_grafo)
    finally:
        driver.close()

if __name__ == "__main__":
    main()