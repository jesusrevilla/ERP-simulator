"""
Algoritmo de Orquestación Compra-a-Pago (Procure-to-Pay-Orchestrator)
Proyecto ERP-Simulator - agentes derivados de los requerimientos de MRP, Recibos y A/P.

Uso:
    python procure_to_pay_orchestrator.py          # corre la simulación local (no requiere API key)
    python procure_to_pay_orchestrator.py --crew   # además corre el crew de CrewAI (requiere LLM configurado)
"""
import copy
import math
import sys
from datetime import datetime

# ---------------------------------------------------------------------------
# 1. Motor determinista: la lógica real de cada agente
# ---------------------------------------------------------------------------

class ReglaNegocioError(Exception):
    """Se lanza cuando una regla de negocio (RN) bloquea la operación."""


def agente_proveedores(estado, oc):
    """RN-01: solo se emiten órdenes a proveedores con estatus aprobado."""
    prov = estado["proveedores"].get(oc["proveedor"])
    if prov is None or prov["estatus"] != "aprobado":
        raise ReglaNegocioError(f"RN-01: proveedor '{oc['proveedor']}' no existe o no está aprobado")
    if oc["sku"] not in estado["items"] or not estado["items"][oc["sku"]]["activo"]:
        raise ReglaNegocioError(f"Item Master: SKU '{oc['sku']}' inexistente o inactivo")
    return prov


def agente_ordenes_compra(estado, necesidad_neta, sku, proveedor):
    """RN-02: la cantidad respeta MOQ y múltiplo del proveedor."""
    prov = estado["proveedores"][proveedor]
    if necesidad_neta <= 0:
        raise ReglaNegocioError("No hay necesidad neta que comprar")
    cantidad = max(necesidad_neta, prov["moq"])
    cantidad = math.ceil(cantidad / prov["multiplo"]) * prov["multiplo"]
    oc = {"id": f"OC-{len(estado['ordenes']) + 1:03d}", "sku": sku, "proveedor": proveedor,
          "cantidad": cantidad, "precio": prov["precios"][sku], "recibido": 0, "estatus": "abierta"}
    agente_proveedores(estado, oc)
    estado["ordenes"][oc["id"]] = oc          # compromiso de pago enviado a A/P
    return oc


def agente_recibos(estado, oc_id, cantidad, danada=0, autoriza_gerente=False):
    """Recibe mercancía contra una OC: sin recibir de más, proveedor activo, inventario al aprobar."""
    oc = estado["ordenes"][oc_id]
    agente_proveedores(estado, oc)                                  # proveedor activo
    pendiente = oc["cantidad"] - oc["recibido"]
    if cantidad > pendiente and not autoriza_gerente:
        raise ReglaNegocioError(f"No recibir de más: llegaron {cantidad}, pendiente {pendiente}")
    buenas = cantidad - danada
    oc["recibido"] += cantidad
    oc["estatus"] = "recibida" if oc["recibido"] >= oc["cantidad"] else "parcial"
    estado["inventario"][oc["sku"]] = estado["inventario"].get(oc["sku"], 0) + buenas
    estado["movimientos"].append(("ENTRADA", oc["sku"], buenas))
    return {"oc": oc_id, "aceptadas": buenas, "danadas": danada}


def agente_conciliacion_ap(estado, oc_id, factura, tolerancia=0.02):
    """Conciliación de 3 vías (orden - recepción - factura). RN-03, RN-04, RF-05."""
    oc = estado["ordenes"][oc_id]
    if factura["cantidad"] > oc["recibido"]:                         # RN-04
        return {"factura": factura["id"], "estado": "retenida",
                "motivo": f"RN-04: factura {factura['cantidad']} > recibido {oc['recibido']}"}
    variacion = (factura["precio"] - oc["precio"]) / oc["precio"]
    if abs(variacion) > tolerancia:                                  # RN-03
        return {"factura": factura["id"], "estado": "retenida",
                "motivo": f"RN-03: variación de precio {variacion:.1%} fuera de tolerancia {tolerancia:.0%}"}
    ajuste = (factura["precio"] - oc["precio"]) * factura["cantidad"]   # RF-05
    estado["costo_inventario"][oc["sku"]] = estado["costo_inventario"].get(oc["sku"], 0) + round(ajuste, 2)
    return {"factura": factura["id"], "estado": "programada_para_pago",
            "monto": round(factura["precio"] * factura["cantidad"], 2), "ajuste_costo": round(ajuste, 2)}


def agente_integridad(estado, operacion, *args, usuario="sistema", **kwargs):
    """Envoltorio ACID: snapshot -> operación -> commit o rollback, con bitácora."""
    snapshot = copy.deepcopy({k: v for k, v in estado.items() if k != "bitacora"})
    entrada = {"fecha": datetime.now().isoformat(timespec="seconds"), "usuario": usuario,
               "operacion": operacion.__name__, "antes": snapshot["inventario"].copy()}
    try:
        resultado = operacion(estado, *args, **kwargs)
        entrada.update(resultado="COMMIT", despues=estado["inventario"].copy())
        return resultado
    except ReglaNegocioError as e:
        for k, v in snapshot.items():                                # ROLLBACK
            estado[k] = v
        entrada.update(resultado=f"ROLLBACK ({e})", despues=estado["inventario"].copy())
        return {"error": str(e)}
    finally:
        estado["bitacora"].append(entrada)


def verificar_integridad(estado):
    """Entradas - Salidas = Stock actual."""
    for sku, stock in estado["inventario"].items():
        neto = sum(c if t == "ENTRADA" else -c for t, s, c in estado["movimientos"] if s == sku)
        assert neto == stock, f"Descuadre en {sku}: movimientos={neto}, stock={stock}"


def estado_inicial():
    return {
        "items": {"SKU-100": {"activo": True}},
        "proveedores": {
            "PROV-A": {"estatus": "aprobado", "moq": 100, "multiplo": 50, "precios": {"SKU-100": 10.0}},
            "PROV-B": {"estatus": "bloqueado", "moq": 10, "multiplo": 1, "precios": {"SKU-100": 9.0}},
        },
        "ordenes": {}, "inventario": {}, "costo_inventario": {}, "movimientos": [], "bitacora": [],
    }


def simulacion_local():
    e = estado_inicial()
    print("1) OC con necesidad neta 120 (MOQ 100, múltiplo 50):")
    r = agente_integridad(e, agente_ordenes_compra, 120, "SKU-100", "PROV-A", usuario="planificador")
    print("  ", r)
    print("2) OC a proveedor bloqueado:")
    print("  ", agente_integridad(e, agente_ordenes_compra, 50, "SKU-100", "PROV-B"))
    print("3) Recibo de más (200 vs 150) sin autorización:")
    print("  ", agente_integridad(e, agente_recibos, "OC-001", 200))
    print("4) Recibo de 150 con 10 dañadas:")
    print("  ", agente_integridad(e, agente_recibos, "OC-001", 150, 10, usuario="almacen"))
    print("5) Factura por 150 a precio 10.10 (1% de variación):")
    print("  ", agente_integridad(e, agente_conciliacion_ap, "OC-001",
                                  {"id": "F-1", "cantidad": 150, "precio": 10.10}, usuario="cxp"))
    print("6) Factura por 200 (más de lo recibido):")
    print("  ", agente_integridad(e, agente_conciliacion_ap, "OC-001",
                                  {"id": "F-2", "cantidad": 200, "precio": 10.0}))
    verificar_integridad(e)
    print("\nInventario:", e["inventario"], "| Ajuste de costo:", e["costo_inventario"])
    print("Bitácora:")
    for b in e["bitacora"]:
        print("  ", b["fecha"], b["usuario"], b["operacion"], "->", b["resultado"])


# ---------------------------------------------------------------------------
# 2. Orquestación con CrewAI (misma estructura que BOM-Manufacturing-Orchestrator)
# ---------------------------------------------------------------------------

def Procure_to_Pay_Orchestrator():
    from crewai import Agent, Task, Crew, Process

    agente_prov = Agent(
        role="Agente de proveedores y datos maestros",
        goal="Aprobar solo proveedores con estatus aprobado y SKU activos en el Item Master.",
        backstory="Aplica RN-01: bloquea cualquier orden a proveedores suspendidos o dados de baja.",
        allow_delegation=False)
    agente_oc = Agent(
        role="Agente de órdenes de compra",
        goal="Convertir necesidades netas del MRP en órdenes de compra válidas.",
        backstory="Aplica RN-02: cantidad = max(necesidad, MOQ) redondeada al múltiplo del proveedor.",
        allow_delegation=False)
    agente_rec = Agent(
        role="Agente de recibos y entregas",
        goal="Registrar la llegada de mercancía contra la OC y actualizar el inventario.",
        backstory="No acepta más de lo pedido sin autorización del gerente; descuenta piezas dañadas.",
        allow_delegation=False)
    agente_ap = Agent(
        role="Agente de conciliación de cuentas por pagar",
        goal="Conciliar orden, recepción y factura antes de programar el pago.",
        backstory="Aplica RN-03 y RN-04: cantidad y precio dentro de tolerancia, nunca más de lo recibido.",
        allow_delegation=False)
    agente_int = Agent(
        role="Agente de integridad transaccional y auditoría",
        goal="Garantizar ACID y la bitácora; verificar Entradas - Salidas = Stock.",
        backstory="Abre transacción, aplica rollback ante fallos y registra usuario, fecha y valores.",
        allow_delegation=False)

    tareas = [
        Task(description="Abre la transacción y bloquea los registros de la OC, el SKU y el proveedor.",
             expected_output="Transacción abierta.", agent=agente_int),
        Task(description="Valida que el proveedor esté aprobado y el SKU activo.",
             expected_output="Validación aprobada o rechazo con mensaje.", agent=agente_prov),
        Task(description="Genera la OC con la necesidad neta respetando MOQ y múltiplo.",
             expected_output="Orden de compra abierta enviada a A/P como compromiso.", agent=agente_oc),
        Task(description="Registra el recibo contra la OC, sin recibir de más, y actualiza el inventario.",
             expected_output="Recibo aprobado e inventario actualizado.", agent=agente_rec),
        Task(description="Concilia OC, recibo y factura (tolerancia de precio, factura <= recibido).",
             expected_output="Factura programada para pago o retenida con motivo.", agent=agente_ap),
        Task(description="Si todo fue exitoso haz Commit y guarda bitácora; si no, Rollback en cascada.",
             expected_output="Transacción cerrada y auditoría registrada.", agent=agente_int),
    ]
    crew = Crew(agents=[agente_prov, agente_oc, agente_rec, agente_ap, agente_int],
                tasks=tareas, process=Process.sequential)
    return crew.kickoff()


if __name__ == "__main__":
    simulacion_local()
    if "--crew" in sys.argv:
        print(Procure_to_Pay_Orchestrator())
