import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

class ERPGraphDB:
    def __init__(self):
        uri = os.getenv("NEO4J_URI") or f"neo4j://{os.getenv('NEO4J_HOST', 'localhost')}:{os.getenv('NEO4J_PORT', '7687')}"
        user = os.getenv("NEO4J_USERNAME")
        password = os.getenv("NEO4J_PASSWORD")
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def ingesta_datos_erp(self):
       
        query = """
        MERGE (prov:Proveedor {nombre: 'TechCorp', pais: 'México'})
        MERGE (prod:Producto {nombre: 'Servidor Rack 1U', SKU: 'SRV-001'})
        MERGE (prov)-[r:SUMINISTRA {costo_unitario: 1500}]->(prod)
        RETURN prov.nombre, prod.nombre
        """
        with self.driver.session() as session:
            session.run(query)
            print("Datos ERP (Nodos y Relaciones) ingresados exitosamente en Neo4j.")

    def consultar_inventario(self):
     
        query = """
        MATCH (prov:Proveedor)-[r:SUMINISTRA]->(prod:Producto)
        RETURN prov.nombre AS Proveedor, prod.nombre AS Producto, r.costo_unitario AS Costo
        """
        with self.driver.session() as session:
            resultados = session.run(query)
            print("\n--- Resultados de la Consulta Cypher ---")
            for record in resultados:
                print(f"El proveedor {record['Proveedor']} suministra '{record['Producto']}' a un costo de ${record['Costo']}")

if __name__ == "__main__":
    erp_db = ERPGraphDB()
    erp_db.ingesta_datos_erp()
    erp_db.consultar_inventario()
    erp_db.close()