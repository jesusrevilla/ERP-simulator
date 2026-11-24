import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

NEO4J_HOST = os.getenv("NEO4J_HOST", "localhost")
NEO4J_PORT = os.getenv("NEO4J_PORT", "7687")
NEO4J_URI = os.getenv("NEO4J_URI", f"bolt://{NEO4J_HOST}:{NEO4J_PORT}")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
ORDER_QUANTITY = int(os.getenv("ORDER_QUANTITY", "30"))


def create_erp_graph(driver):
    query = '''
    MERGE (p:Product {sku: "PC-GAMING-PRO", name: "Gaming PC Pro"})
    MERGE (s1:Supplier {id: "SUP-01", name: "TechComponents MX", country: "Mexico"})
    MERGE (s2:Supplier {id: "SUP-02", name: "GlobalSilicon", country: "Taiwan"})

    MERGE (c1:Component {sku: "CPU-R7", name: "Ryzen 7 7800X3D", stock: 25, unit_cost: 350.0})
    MERGE (c2:Component {sku: "GPU-4070", name: "NVIDIA RTX 4070", stock: 18, unit_cost: 550.0})
    MERGE (c3:Component {sku: "RAM-32GB", name: "DDR5 32GB Kit", stock: 50, unit_cost: 110.0})
    MERGE (c4:Component {sku: "SSD-1TB", name: "NVMe SSD 1TB", stock: 40, unit_cost: 80.0})

    MERGE (p)-[:REQUIRES {qty_per_unit: 1}]->(c1)
    MERGE (p)-[:REQUIRES {qty_per_unit: 1}]->(c2)
    MERGE (p)-[:REQUIRES {qty_per_unit: 1}]->(c3)
    MERGE (p)-[:REQUIRES {qty_per_unit: 2}]->(c4)

    MERGE (s1)-[:SUPPLIES {lead_time_days: 3}]->(c3)
    MERGE (s1)-[:SUPPLIES {lead_time_days: 4}]->(c4)
    MERGE (s2)-[:SUPPLIES {lead_time_days: 12}]->(c1)
    MERGE (s2)-[:SUPPLIES {lead_time_days: 15}]->(c2)
    '''
    driver.execute_query(query)
    print("Grafo BOM de Gaming PC cargado en Neo4j.")


def analyze_shortages(driver, order_qty):
    query = '''
    MATCH (s:Supplier)-[sup:SUPPLIES]->(c:Component)<-[r:REQUIRES]-(p:Product {sku: "PC-GAMING-PRO"})
    WITH c, s, sup, r, (r.qty_per_unit * $order_qty) AS required_qty
    WHERE c.stock < required_qty
    RETURN c.sku AS SKU,
           c.name AS Componente,
           c.stock AS Stock_Actual,
           required_qty AS Requerido,
           (required_qty - c.stock) AS Faltante,
           s.name AS Proveedor,
           sup.lead_time_days AS Dias_Entrega
    ORDER BY Faltante DESC
    '''
    records, _, _ = driver.execute_query(query, order_qty=order_qty)

    print(f"\n--- Analisis de Faltantes (MRP) para {order_qty} Gaming PCs ---")
    if not records:
        print("Stock suficiente para cubrir la orden.")
    else:
        for row in records:
            data = row.data()
            print(
                f"- {data['Componente']} ({data['SKU']}): "
                f"Stock={data['Stock_Actual']}, Requerido={data['Requerido']}, "
                f"Faltante={data['Faltante']} | Proveedor: {data['Proveedor']} ({data['Dias_Entrega']} dias)"
            )


def main():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        driver.verify_connectivity()
        print("Conexion exitosa a Neo4j.")
        create_erp_graph(driver)
        analyze_shortages(driver, ORDER_QUANTITY)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
