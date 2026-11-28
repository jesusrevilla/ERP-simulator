import os
from neo4j import GraphDatabase

uri = f"bolt://{os.getenv('NEO4J_HOST', 'localhost')}:{os.getenv('NEO4J_PORT', '7687')}"
user = os.getenv('NEO4J_USER', 'neo4j')
password = os.getenv('NEO4J_PASSWORD', 'password')
order_quantity = int(os.getenv('ORDER_QUANTITY', '30'))

def create_ar_ap_graph(tx, qty):
    total_receivable = qty * 1800.00  
    total_payable = qty * 1150.00

    query = """
    // 1. Cuentas por Cobrar (AR): Cliente, Orden de Venta y Factura
    MERGE (c:Customer {name: 'Cliente Mayorista AR'})
    MERGE (so:SalesOrder {id: 'SO-AR-001', quantity: $qty})
    MERGE (inv:AR_Invoice {id: 'INV-AR-01', total: $total_ar, status: 'PENDING'})
    
    MERGE (c)-[:PLACED]->(so)
    MERGE (so)-[:BILLED_AS]->(inv)

    // 2. Cuentas por Pagar (AP): Proveedor, Orden de Compra y Factura
    MERGE (s:Supplier {name: 'Proveedor Hardware AP'})
    MERGE (po:PurchaseOrder {id: 'PO-AP-001', total: $total_ap})
    MERGE (bill:AP_Bill {id: 'BILL-AP-01', total: $total_ap, status: 'UNPAID'})
    
    MERGE (po)-[:ISSUED_TO]->(s)
    MERGE (s)-[:INVOICED_AS]->(bill)

    // 3. Trazabilidad Operativa-Financiera
    MERGE (so)-[:TRIGGERS_PROCUREMENT]->(po)
    """
    tx.run(query, qty=qty, total_ar=total_receivable, total_ap=total_payable)

if __name__ == "__main__":
    driver = GraphDatabase.driver(uri, auth=(user, password))
    with driver.session() as session:
        session.execute_write(create_ar_ap_graph, order_quantity)
        print(f"¡Grafo AR & AP generado exitosamente en Neo4j para {order_quantity} PCs!")
    driver.close()
