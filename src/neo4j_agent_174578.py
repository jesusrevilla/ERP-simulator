import importlib.util
import json
import os
import sys
from datetime import datetime, timedelta
from importlib.machinery import SourceFileLoader

from src.neo4j_load import get_driver
from src.neo4j_shortages import shortages

def _find(name, env_var):
    if os.getenv(env_var):
        return os.getenv(env_var)
    for folder in ("LeadTime", "Lead Time", "."):
        path = os.path.join(folder, name)
        if os.path.exists(path):
            return path
    for root, _, files in os.walk("."):
        if ".git" not in root and name in files:
            return os.path.join(root, name)
    raise FileNotFoundError(f"No se encontró {name} en el repositorio")


LEAD_TIME_JSON = _find("173030Lead_Time_Materiales_Productos_Internos.json", "LEAD_TIME_JSON")
ORCHESTRATOR_FILE = _find("Algoritmo_LeadTime_LLM_Orchestrator", "ORCHESTRATOR_FILE")
OUT_DIR = os.getenv("GRAPH_AGENT_OUT", "graph-agent")

CONTEXT_FILE = os.path.join(OUT_DIR, "contexto_mrp.json")
AGENT_FILE = os.path.join(OUT_DIR, "reporte_agente.md")
RESOLVE_FILE = os.path.join(OUT_DIR, "resolucion.json")


def _read_shortages(driver):
    with driver.session() as session:
        rows = session.execute_read(shortages)
        codes = {
            r["name"]: r["code"]
            for r in session.run(
                "MATCH (m:Material) RETURN m.name AS name, m.code AS code"
            ).data()
        }
    for r in rows:
        r["code"] = codes.get(r["material"])
    return rows


def _write_json(path, data):
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def _read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_context():
    lead_time = _read_json(LEAD_TIME_JSON)
    driver = get_driver()
    rows = _read_shortages(driver)
    driver.close()

    lista = [
        {
            "codigo": r["code"],
            "material": r["material"],
            "stock_inicial": r["stock"],
            "cantidad_requerida": r["required"],
            "faltante": max(r["shortage"], 0),
        }
        for r in rows
    ]
    faltantes = [m for m in lista if m["faltante"] > 0]

    if faltantes:
        critico = max(faltantes, key=lambda m: m["faltante"])
        abastecimiento = dict(lead_time["abastecimiento"])
        abastecimiento.update(
            material_critico=critico["material"],
            codigo=critico["codigo"],
            faltante=critico["faltante"],
        )
    else:
        abastecimiento = {"faltante": 0, "lead_time_horas": 0}

    context = {
        "empresa": lead_time.get("empresa", "TechAssembly S.A."),
        "producto": lead_time.get("producto", {}).get("nombre", "Gaming PC"),
        "cantidad_orden": int(os.getenv("ORDER_QUANTITY", "30")),
        "fuente": "Neo4j (src/neo4j_shortages.py) + " + LEAD_TIME_JSON,
        "lista_materiales_y_mrp": lista,
        "abastecimiento": abastecimiento,
        "produccion_interna": lead_time["produccion_interna"],
        "lead_time_total_orden": lead_time["lead_time_total_orden"],
    }
    _write_json(CONTEXT_FILE, context)

    print(f"Contexto MRP generado desde el grafo -> {CONTEXT_FILE}")
    for m in lista:
        estado = f"FALTANTE {m['faltante']}" if m["faltante"] else "OK"
        print(f"  {m['codigo']:<8}{m['material']:<22} stock={m['stock_inicial']:<5} "
              f"req={m['cantidad_requerida']:<5} {estado}")


def run_agent():
    context = _read_json(CONTEXT_FILE)

    if not os.getenv("OPENAI_API_KEY"):
        msg = ("Agente IA omitido: no hay secreto OPENAI_API_KEY configurado. "
               "El grafo se resuelve igual con las reglas MRP.")
        print(msg)
        with open(AGENT_FILE, "w", encoding="utf-8") as f:
            f.write(f"> {msg}\n")
        return


    loader = SourceFileLoader("leadtime_orchestrator", ORCHESTRATOR_FILE)
    spec = importlib.util.spec_from_loader(loader.name, loader)
    orchestrator = importlib.util.module_from_spec(spec)
    loader.exec_module(orchestrator)


    orchestrator.cargar_json_mrp = lambda: json.dumps(context, ensure_ascii=False)

    result = orchestrator.LeadTime_LLM_Orchestrator()
    text = getattr(result, "raw", None) or str(result)

    with open(AGENT_FILE, "w", encoding="utf-8") as f:
        f.write(text)
    print("--- RESULTADO DEL AGENTE IA ---")
    print(text)


def resolve():
    context = _read_json(CONTEXT_FILE)
    agent_text = open(AGENT_FILE, encoding="utf-8").read() if os.path.exists(AGENT_FILE) else ""
    lead_hours = float(context["abastecimiento"].get("lead_time_horas", 0) or 0)
    run_id = os.getenv("GITHUB_RUN_ID", "local")

    driver = get_driver()
    before = _read_shortages(driver)
    to_buy = [r for r in before if r["shortage"] > 0]

    ordered_at = datetime.now().replace(microsecond=0)
    received_at = ordered_at + timedelta(hours=lead_hours)

    with driver.session() as session:
        for r in to_buy:
            session.run(
                """
                MATCH (m:Material {code: $code})
                MERGE (po:PurchaseOrder {id: $po_id})
                SET po.material_code = $code,
                    po.quantity      = $qty,
                    po.status        = 'RECEIVED',
                    po.lead_time_horas = $lead,
                    po.ordered_at    = datetime($ordered),
                    po.received_at   = datetime($received)
                MERGE (po)-[:REPLENISHES]->(m)
                SET m.stock = m.stock + $qty
                WITH po, m
                MATCH (so:SalesOrder)-[:FOR]->(:Product)-[:REQUIRES]->(m)
                MERGE (po)-[:FOR_ORDER]->(so)
                """,
                code=r["code"], qty=r["shortage"], lead=lead_hours,
                po_id=f"PO-{r['code']}-{run_id}",
                ordered=ordered_at.isoformat(), received=received_at.isoformat(),
            )


        session.run(
            """
            MERGE (a:AgentReport {id: $id})
            SET a.agent = 'LeadTime_LLM_Orchestrator',
                a.created_at = datetime(),
                a.lead_time_total_horas = $total,
                a.text = $text
            WITH a
            MATCH (so:SalesOrder)
            MERGE (a)-[:ANALYZED]->(so)
            """,
            id=f"AR-{run_id}", text=agent_text[:20000],
            total=float(context["lead_time_total_orden"].get("horas", 0)),
        )

    after = _read_shortages(driver)
    driver.close()

    pending = [r for r in after if r["shortage"] > 0]
    _write_json(RESOLVE_FILE, {
        "antes": before,
        "despues": after,
        "ordenes_compra": [
            {"id": f"PO-{r['code']}-{run_id}", "codigo": r["code"],
             "material": r["material"], "cantidad": r["shortage"]}
            for r in to_buy
        ],
        "lead_time_horas": lead_hours,
    })

    print(f"Órdenes de compra creadas en el grafo: {len(to_buy)}")
    for r in to_buy:
        print(f"  PO-{r['code']}-{run_id}: {r['shortage']} x {r['material']}")

    if pending:
        print("ERROR: el grafo sigue con faltantes:", pending)
        sys.exit(1)
    print("Grafo resuelto: ningún material con faltante.")


def report():
    context = _read_json(CONTEXT_FILE)
    res = _read_json(RESOLVE_FILE)
    agent_text = open(AGENT_FILE, encoding="utf-8").read() if os.path.exists(AGENT_FILE) else ""
    after = {r["code"]: r for r in res["despues"]}

    lines = [f"## Grafo resuelto – {context['cantidad_orden']} x {context['producto']}", ""]
    lines += ["```mermaid", "graph LR",
              f'  SO["SalesOrder<br/>{context["cantidad_orden"]} pzs"] -->|FOR| P["{context["producto"]}"]']
    for r in res["antes"]:
        c = r["code"]
        lines.append(f'  P -->|REQUIRES| {c}["{r["material"]}<br/>stock {after[c]["stock"]} / req {r["required"]}"]')
    for po in res["ordenes_compra"]:
        n = po["id"].replace("-", "_")
        lines.append(f'  {n}(["{po["id"]}<br/>{po["cantidad"]} pzs · {res["lead_time_horas"]} h"]) -->|REPLENISHES| {po["codigo"]}')
        lines.append(f"  style {po['codigo']} fill:#d4edda,stroke:#27ae60")
    lines += ["  AR{{Agente IA}} -->|ANALYZED| SO", "```", ""]

    lines += ["| Material | Requerido | Stock antes | Faltante | Stock después |",
              "|---|---:|---:|---:|---:|"]
    for r in res["antes"]:
        lines.append(f"| {r['material']} | {r['required']} | {r['stock']} | "
                     f"{max(r['shortage'], 0)} | {after[r['code']]['stock']} |")

    lt = context["lead_time_total_orden"]
    lines += ["", f"**Lead time abastecimiento:** {res['lead_time_horas']} h · "
              f"**Producción:** {context['produccion_interna'].get('lead_time_horas')} h · "
              f"**Total orden:** {lt.get('horas')} h", ""]
    lines += ["### Análisis del agente IA", "", agent_text or "_Sin salida_", ""]

    text = "\n".join(lines)
    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(text + "\n")
    with open(os.path.join(OUT_DIR, "reporte_final.md"), "w", encoding="utf-8") as f:
        f.write(text)
    print(text)


STAGES = {"context": build_context, "agent": run_agent, "resolve": resolve, "report": report}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in STAGES:
        sys.exit(f"Uso: python -m src.neo4j_agent_resolve [{'|'.join(STAGES)}]")
    STAGES[sys.argv[1]]()
