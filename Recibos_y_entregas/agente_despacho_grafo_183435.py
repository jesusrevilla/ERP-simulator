#!/usr/bin/env python3

import json
import os
from pathlib import Path

from neo4j import GraphDatabase

EVENTS_FILE = Path(__file__).with_name("eventos.json")


def load_outbound_events(path=EVENTS_FILE):
    with path.open(encoding="utf-8") as file:
        document = json.load(file)

    machines = document["isa_95_hierarchy"]["manufacturing_lines"]
    outbound = next(line for line in machines if line["line_id"] == "LINE-OUTBOUND-01")
    activities = outbound["machines"][0]["sequence_activities"]

    events = []
    for activity in activities:
        for message in activity.get("messages", []):
            events.append(
                {
                    "step_code": activity["step_code"],
                    "action": activity["action"],
                    "msg_id": message["msg_id"],
                    "payload": message.get("payload", {}),
                }
            )
    return events


def evaluate_dispatch(events):
    by_step = {event["step_code"]: event for event in events}
    validations = by_step.get("GW_RN01_RN02", {}).get("payload", {})
    picking = by_step.get("RF-06", {}).get("payload", {})
    rf07 = by_step.get("RF-07", {})
    rf08 = by_step.get("RF-08", {})
    decisions = []

    validations_ok = (
        validations.get("check_stock_negative") == "PASSED"
        and validations.get("check_lot_expired") == "PASSED"
    )
    picking_ok = bool(picking.get("item_id")) and int(picking.get("reserved_qty", 0)) > 0

    rf07_payload = rf07.get("payload", {})
    docs_confirmed = all(
        rf07_payload.get(field) == "GENERATED"
        for field in ("packing_list_status", "label_status", "waybill_status")
    )

    if not validations_ok:
        decision, rule, reason, action = (
            "NO_CERRAR",
            "RN-01/RN-02",
            "No están aprobadas las validaciones de stock y lote.",
            "Resolver las validaciones previas antes de generar documentos.",
        )
    elif not picking_ok:
        decision, rule, reason, action = (
            "NO_CERRAR",
            "RF-06/DI-01",
            "No se encontró una reserva de picking válida.",
            "Confirmar el picking y su cantidad reservada.",
        )
    elif not rf07_payload.get("package_id") or not rf07_payload.get("carrier"):
        decision, rule, reason, action = (
            "NO_CERRAR",
            "RF-07",
            "Falta el identificador de bulto o el transportista.",
            "Completar los datos de expedición.",
        )
    elif not docs_confirmed:
        decision, rule, reason, action = (
            "NO_CERRAR",
            "RF-07",
            "El evento solicita emitir documentos, pero no confirma la lista, etiqueta y guía generadas.",
            "Esperar la respuesta de ShippingService con los tres estados en GENERATED.",
        )
    else:
        decision, rule, reason, action = (
            "LISTO_PARA_CONFIRMAR",
            "RF-07",
            "La lista de empaque, etiqueta y guía están confirmadas.",
            "Esperar confirmación física de salida para RF-08.",
        )

    decisions.append(
        {
            **rf07,
            "decision": decision,
            "rule_id": rule,
            "reason": reason,
            "suggested_action": action,
        }
    )

    rf08_payload = rf08.get("payload", {})
    inventory_confirmed = rf08_payload.get("inventory_status") == "DEDUCTED"
    accounting_confirmed = rf08_payload.get("accounting_entry_status") == "Posted"

    if decision != "LISTO_PARA_CONFIRMAR":
        close_decision, close_rule, close_reason, close_action = (
            "NO_CERRAR",
            "RF-07",
            "RF-07 todavía no está completo; el ejemplo no permite cerrar la salida.",
            "Completar y verificar los documentos antes de confirmar el despacho.",
        )
    elif rf08_payload.get("transaction_type") != "ACID_COMMIT":
        close_decision, close_rule, close_reason, close_action = (
            "NO_CERRAR",
            "DI-02",
            "El mensaje no acredita una transacción ACID confirmada.",
            "No cerrar; ejecutar la operación transaccional y revisar su resultado.",
        )
    elif inventory_confirmed and accounting_confirmed:
        close_decision, close_rule, close_reason, close_action = (
            "CONTINUAR",
            "DI-02",
            "El inventario y el asiento aparecen confirmados juntos.",
            "Cerrar el despacho.",
        )
    elif rf08_payload.get("transaction_status") == "ROLLED_BACK":
        close_decision, close_rule, close_reason, close_action = (
            "REVERTIR",
            "DI-02",
            "La transacción reportó rollback; no debe quedar efecto parcial.",
            "Verificar por operation_id que inventario y asiento estén revertidos.",
        )
    else:
        close_decision, close_rule, close_reason, close_action = (
            "REQUIERE_REVISION",
            "DI-02",
            "No se confirma el descuento de inventario junto con el asiento.",
            "Consultar el estado de la transacción antes de reintentar; evitar duplicar la salida.",
        )

    decisions.append(
        {
            **rf08,
            "decision": close_decision,
            "rule_id": close_rule,
            "reason": close_reason,
            "suggested_action": close_action,
        }
    )
    return decisions


def persist_graph(driver, run_id, events):
    graph_events = [
        {
            "step_code": event["step_code"],
            "msg_id": event["msg_id"],
            "action": event["action"],
            "operation": event.get("payload", {}).get("operation", "VALIDATION"),
        }
        for event in events
    ]

    with driver.session() as session:
        session.run(
            """
            UNWIND $events AS event
            MERGE (step:DispatchStep {run_id: $run_id, msg_id: event.msg_id})
            SET step.step_code = event.step_code,
                step.action = event.action,
                step.operation = event.operation
            """,
            run_id=run_id,
            events=graph_events,
        )

        session.run(
            """
            UNWIND range(0, size($events) - 2) AS idx
            MATCH (first:DispatchStep {run_id: $run_id, msg_id: $events[idx].msg_id})
            MATCH (second:DispatchStep {run_id: $run_id, msg_id: $events[idx + 1].msg_id})
            MERGE (first)-[:NEXT]->(second)
            """,
            run_id=run_id,
            events=graph_events,
        )

        session.run(
            """
            MATCH (close:DispatchStep {run_id: $run_id, step_code: 'RF-08'})
            MATCH (docs:DispatchStep {run_id: $run_id, step_code: 'RF-07'})
            MERGE (close)-[:DEPENDS_ON]->(docs)
            """,
            run_id=run_id,
        )


def persist_decisions(driver, run_id, decisions):
    with driver.session() as session:
        for result in decisions:
            session.run(
                """
                MATCH (step:DispatchStep {run_id: $run_id, msg_id: $msg_id})
                SET step.decision = $decision,
                    step.rule_id = $rule_id,
                    step.reason = $reason,
                    step.suggested_action = $suggested_action
                """,
                run_id=run_id,
                msg_id=result["msg_id"],
                decision=result["decision"],
                rule_id=result["rule_id"],
                reason=result["reason"],
                suggested_action=result["suggested_action"],
            )


def main():
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    username = os.getenv("NEO4J_USERNAME", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    run_id = os.getenv("GITHUB_RUN_ID", "local-run")

    events = load_outbound_events()
    decisions = evaluate_dispatch(events)

    with GraphDatabase.driver(uri, auth=(username, password)) as driver:
        driver.verify_connectivity()
        persist_graph(driver, run_id, events)
        persist_decisions(driver, run_id, decisions)

    print("Grafo Outbound guardado en el servicio Neo4j temporal.")
    for result in decisions:
        print(
            f"{result['step_code']} | {result['msg_id']} | "
            f"{result['decision']} | {result['rule_id']} | {result['reason']}"
        )
        print(f"Acción sugerida: {result['suggested_action']}")


if __name__ == "__main__":
    main()