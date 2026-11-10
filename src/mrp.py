from neo4j import GraphDatabase

def calculate_mrp(product, quantity):
    """Se conecta a Neo4j, busca las piezas necesarias y las multiplica por el pedido."""
    driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "mrp_password"))
    requirements = {}
    
    with driver.session() as session:
        query = """
        MATCH (p:Producto {nombre: $producto})-[r:REQUIERE]->(c:Componente)
        RETURN c.nombre AS componente, r.cantidad AS cantidad_unitaria
        """
        records = session.run(query, producto=product)
        
        for record in records:
            requirements[record["componente"]] = record["cantidad_unitaria"] * quantity
            
    driver.close()
    return requirements