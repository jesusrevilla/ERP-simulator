"""
Agente de procedimientos transaccionales (184661)


"""

import json
import os
import time

PRODUCTOS = {"ERP-001": 10, "ERP-002": 0}           

DOCUMENTOS = {                                        
    "C-001": [("ERP-001", 8)],
    "V-001": [("ERP-001", 3)],
    "V-002": [("ERP-001", 3), ("ERP-002", 2)],       
}

OPERACIONES = [
    {"msg_id": "OP-1", "operation": "CONFIRMAR_COMPRA", "documento": "C-001"},
    {"msg_id": "OP-2", "operation": "CONFIRMAR_VENTA", "documento": "V-001"},
    {"msg_id": "OP-3", "operation": "CONFIRMAR_VENTA", "documento": "V-002"},
    {"msg_id": "OP-4", "operation": "CONFIRMAR_VENTA", "documento": "V-001"},
]


class Rechazo(Exception):
    def __init__(self, regla, motivo):
        super().__init__(motivo)
        self.regla, self.motivo = regla, motivo


def conectar():
    from neo4j import GraphDatabase

    uri = f"bolt://{os.getenv('NEO4J_HOST', 'localhost')}:{os.getenv('NEO4J_PORT', '7687')}"
    driver = GraphDatabase.driver(uri, auth=(os.getenv("NEO4J_USER", "neo4j"),
                                             os.getenv("NEO4J_PASSWORD", "password")))
    for intento in range(30): 
        try:
            driver.verify_connectivity()
            return driver
        except Exception:
            print("Esperando a Neo4j...")
            time.sleep(3)
    raise SystemExit("No se pudo conectar a Neo4j")


def preparar_grafo(driver):
    driver.execute_query("MATCH (n) WHERE n:Producto OR n:Documento DETACH DELETE n")
    for sku, stock in PRODUCTOS.items():
        driver.execute_query("CREATE (:Producto {sku: $sku, stock: $stock})", sku=sku, stock=stock)
    for doc, renglones in DOCUMENTOS.items():
        driver.execute_query("CREATE (:Documento {id: $id, estado: 'Borrador'})", id=doc)
        for sku, cantidad in renglones:
            driver.execute_query("""
                MATCH (d:Documento {id: $id}), (p:Producto {sku: $sku})
                CREATE (d)-[:INCLUYE {cantidad: $cantidad}]->(p)""",
                id=doc, sku=sku, cantidad=cantidad)


def confirmar(tx, operacion):
    """Todo lo que pasa aquí se guarda junto o no se guarda nada."""
    doc = operacion["documento"]
    es_venta = operacion["operation"] == "CONFIRMAR_VENTA"

    estado = tx.run("MATCH (d:Documento {id: $id}) RETURN d.estado AS estado", id=doc).single()
    if estado is None or estado["estado"] != "Borrador":
        raise Rechazo("ESTADO_DOCUMENTO", "El documento no existe o ya fue confirmado")

    renglones = tx.run("""MATCH (:Documento {id: $id})-[i:INCLUYE]->(p:Producto)
                          RETURN p.sku AS sku, i.cantidad AS cantidad""", id=doc).data()
    for r in renglones:
        if es_venta:
            ok = tx.run("""MATCH (p:Producto {sku: $sku}) WHERE p.stock >= $cantidad
                           SET p.stock = p.stock - $cantidad RETURN p.stock""", **r).single()
            if ok is None:
                raise Rechazo("STOCK_NO_NEGATIVO", f"No hay existencias suficientes de {r['sku']}")
        else:
            tx.run("MATCH (p:Producto {sku: $sku}) SET p.stock = p.stock + $cantidad", **r)

    tx.run("MATCH (d:Documento {id: $id}) SET d.estado = 'Confirmada'", id=doc)


def atender(driver, operacion):
    if operacion["operation"] not in ("CONFIRMAR_COMPRA", "CONFIRMAR_VENTA"):
        return {"msg_id": operacion["msg_id"], "decision": "REVISAR",
                "motivo": "Operación no soportada"}

    with driver.session() as sesion:
        tx = sesion.begin_transaction()           
        try:
            confirmar(tx, operacion)
            tx.commit()                            
            resultado = {"decision": "CONFIRMADA", "transaccion": "COMMIT"}
        except Rechazo as error:
            tx.rollback()                          
            resultado = {"decision": "RECHAZAR", "transaccion": "ROLLBACK",
                         "regla_fallida": error.regla, "motivo": error.motivo}

    # Verificación: se vuelve a leer lo que quedó guardado
    records, _, _ = driver.execute_query("MATCH (p:Producto) RETURN p.sku AS sku, p.stock AS stock")
    stock = {x["sku"]: x["stock"] for x in records}
    return {"msg_id": operacion["msg_id"], "operacion": operacion["operation"],
            "documento": operacion["documento"], **resultado, "stock_guardado": stock}


def main():
    driver = conectar()
    preparar_grafo(driver)
    for operacion in OPERACIONES:
        print(json.dumps(atender(driver, operacion), ensure_ascii=False))

    print("\nGrafo en Neo4j:")
    records, _, _ = driver.execute_query("""
        MATCH (d:Documento)-[i:INCLUYE]->(p:Producto)
        RETURN d.id AS doc, d.estado AS estado, i.cantidad AS cantidad, p.sku AS sku""")
    for x in records:
        print(f"(Documento {x['doc']} {x['estado']})-[:INCLUYE {{cantidad: {x['cantidad']}}}]->(Producto {x['sku']})")
    driver.close()


if __name__ == "__main__":
    main()
