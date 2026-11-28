"""
Agente 3 - Pedidos, stock y picking (184661)

"""

import json
import os
import sys
import time
from datetime import date


def validar_salida(stock_disponible, cantidad_solicitada, lote_despachable):
    if not lote_despachable:
        return {"decision": "RECHAZAR", "motivo": "Lote vencido o bloqueado"}
    if stock_disponible < cantidad_solicitada:
        return {"decision": "RECHAZAR", "motivo": "Stock insuficiente"}
    return {"decision": "RESERVAR"}


def leer_eventos(ruta):
    with open(ruta, encoding="utf-8") as archivo:
        datos = json.load(archivo)
    mensajes = []
    for linea in datos["isa_95_hierarchy"]["manufacturing_lines"]:
        for maquina in linea["machines"]:
            for paso in maquina["sequence_activities"]:
                for mensaje in paso["messages"]:
                    mensaje["step_code"] = paso["step_code"]
                    mensajes.append(mensaje)
    return mensajes


def conectar():
    from neo4j import GraphDatabase

    uri = f"bolt://{os.getenv('NEO4J_HOST', 'localhost')}:{os.getenv('NEO4J_PORT', '7687')}"
    driver = GraphDatabase.driver(uri, auth=(os.getenv("NEO4J_USER", "neo4j"),
                                             os.getenv("NEO4J_PASSWORD", "password")))
    for intento in range(30):  # Neo4j tarda unos segundos en arrancar
        try:
            driver.verify_connectivity()
            return driver
        except Exception:
            print("Esperando a Neo4j...")
            time.sleep(3)
    raise SystemExit("No se pudo conectar a Neo4j")


def respuesta(mensaje, decision, **datos):
    return {"msg_id": mensaje["msg_id"], "step_code": mensaje["step_code"],
            "decision": decision, **datos}


def main():
    mensajes = leer_eventos(sys.argv[1])
    driver = conectar()
    db = driver.execute_query
    db("MATCH (n) WHERE n:Pedido OR n:Lote OR n:Articulo DETACH DELETE n")

    pedido, lote, decision, stock = None, None, None, 0
    for m in mensajes:
        p = m["payload"]
        tipo = p.get("operation") or m["step_code"]  # MSG-OUT-002 no trae "operation"

        if tipo == "CAPTURE_TRACEABILITY":  # RF-02: lote que entró al almacén
            lote = p
            db("MERGE (l:Lote {id: $id}) SET l.caducidad = date($caducidad)",
               id=p["batch_id"], caducidad=p["expiry_date"])
            continue

        if tipo == "PROCESS_SALES_ORDER":  # RF-05: llega el pedido
            pedido = p
            pedido["fecha"] = date.fromisoformat(m["timestamp"][:10].replace("/", "-"))
            db("MERGE (pe:Pedido {id: $id}) SET pe.cantidad = $cantidad, pe.estado = 'RECIBIDO'",
               id=p["sales_order_id"], cantidad=p["requested_qty"])
            r = respuesta(m, "CONTINUAR")

        elif tipo == "GW_RN01_RN02":  # RN-02 lote vigente, RN-01 stock suficiente
            stock = p["available_stock"]
            vigente = lote is not None and date.fromisoformat(lote["expiry_date"]) >= pedido["fecha"]
            resultado = validar_salida(p["available_stock"], pedido["requested_qty"], vigente)
            decision = resultado["decision"]
            if decision == "RESERVAR":
                db("""MATCH (pe:Pedido {id: $pedido}), (l:Lote {id: $lote})
                      SET pe.estado = 'VALIDADO' MERGE (pe)-[:SURTE_DE]->(l)""",
                   pedido=pedido["sales_order_id"], lote=lote["batch_id"])
                r = respuesta(m, "RESERVAR")
            else:
                regla = "RN-02" if "Lote" in resultado["motivo"] else "RN-01"
                r = respuesta(m, "RECHAZAR", regla_fallida=regla, motivo=resultado["motivo"],
                              accion_sugerida="Dejar el pedido pendiente y revisar stock o lote")

        elif tipo == "ROW_LEVEL_LOCK_ALLOCATION":  # RF-06: reserva con bloqueo (DI-01)
            if decision != "RESERVAR":
                r = respuesta(m, "RECHAZAR", motivo="Reserva sin validación aprobada")
            else:
                # El primer SET bloquea el nodo del artículo: otro pedido tiene que esperar.
                records, _, _ = db("""
                    MATCH (pe:Pedido {id: $pedido})
                    MERGE (a:Articulo {id: $articulo})
                    ON CREATE SET a.stock = $stock, a.reservado = 0
                    SET a.reservado = a.reservado
                    WITH pe, a WHERE a.stock - a.reservado >= $cantidad
                    SET a.reservado = a.reservado + $cantidad, pe.estado = 'RESERVADO'
                    MERGE (pe)-[:RESERVA {cantidad: $cantidad}]->(a)
                    RETURN a.stock - a.reservado AS restante""",
                    pedido=pedido["sales_order_id"], articulo=p["item_id"],
                    stock=stock, cantidad=p["reserved_qty"])
                if records:
                    r = respuesta(m, "RESERVADO", restante=records[0]["restante"])
                else:
                    r = respuesta(m, "RECHAZAR", regla_fallida="RN-01", motivo="Stock insuficiente")
        else:
            continue  # eventos de otros agentes

        print(json.dumps(r, ensure_ascii=False))

    print("\nGrafo en Neo4j:")
    records, _, _ = db("MATCH (a)-[r]->(b) RETURN a.id AS a, type(r) AS r, b.id AS b")
    for x in records:
        print(f"({x['a']})-[:{x['r']}]->({x['b']})")
    driver.close()


if __name__ == "__main__":
    main()
