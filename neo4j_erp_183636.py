import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

# Cargar credenciales ocultas
load_dotenv()
URI = os.getenv("NEO4J_URI")
USER = os.getenv("NEO4J_USERNAME")
PASSWORD = os.getenv("NEO4J_PASSWORD")

# Consultas Cypher (Sintaxis gráfica de Neo4j adaptada al ERP)
crear_datos_erp_cypher = """
MERGE (e:Empleado {matricula: '183636', nombre: 'Operador ERP'})
MERGE (p:Producto {sku: 'SERVER-01', nombre: 'Servidor Rack', precio: 5000})
MERGE (o:OrdenCompra {folio: 'ORD-2026-001', estado: 'Procesada'})
MERGE (e)-[:GENERO_ORDEN]->(o)
MERGE (o)-[:CONTIENE_PRODUCTO {cantidad: 3}]->(p)
"""

consultar_datos_erp_cypher = """
MATCH (e:Empleado)-[:GENERO_ORDEN]->(o:OrdenCompra)-[c:CONTIENE_PRODUCTO]->(p:Producto)
RETURN e.matricula AS Empleado, o.folio AS Orden, p.nombre AS Producto, c.cantidad AS Cantidad
"""

def ejecutar_prueba_erp():
    try:
        # Establecer conexión
        driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
        driver.verify_connectivity()
        print("✅ Conexión exitosa a Neo4j AuraDB\n")
        
        with driver.session() as session:
            # Insertar los datos
            session.run(crear_datos_erp_cypher)
            print("✅ Nodos y relaciones del ERP creados correctamente en el grafo.\n")
            
            # Consultar y mostrar los datos
            print("📊 Resultados de la Base de Datos:")
            resultados = session.run(consultar_datos_erp_cypher)
            for registro in resultados:
                print(f"El empleado {registro['Empleado']} generó la orden {registro['Orden']} "
                      f"que incluye {registro['Cantidad']} unidad(es) de '{registro['Producto']}'.")
                
    except Exception as e:
        print(f"❌ Error durante la ejecución: {e}")
    finally:
        driver.close()

if __name__ == "__main__":
    ejecutar_prueba_erp()