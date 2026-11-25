"""Agente IA de Implosión (Where-Used) y Análisis de Impacto por Desabasto BOM (LLM + Neo4j).

Resuelve:
- Consulta inversa multinivel (Where-Used / Implosión) desde materia prima hacia subensambles y PT (RF-03.3, RN-12).
- Cálculo del radio de afectación ante desabasto o incremento de precio de un componente.
- Análisis de mitigación y plan de sustitución asistido por LLM (OpenAI o motor experto local).
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Any, Dict, List, Optional


CYPHER_WHERE_USED = """
MATCH p = (padre:Articulo)-[rels:REQUIRES*1..6]->(comp:Articulo {sku: $component_sku})
WHERE ($incluir_inactivos = true OR ALL(r IN rels WHERE r.estado = 'ACTIVO'))
RETURN padre.sku AS sku_afectado,
       padre.tipo_item AS tipo_item,
       length(p) AS profundidad,
       reduce(qty = 1.0, r IN rels | qty * r.cantidad) AS consumo_unitario_total,
       [n IN nodes(p) | n.sku] AS ruta_ensamble
ORDER BY profundidad ASC, sku_afectado ASC
"""

CYPHER_REGISTER_MITIGATION = """
MERGE (c:Articulo {sku: $component_sku})
MERGE (al:AlertaDesabasto {alerta_id: $alerta_id})
SET al.nivel_riesgo = $nivel_riesgo,
    al.productos_terminados_afectados = $pt_afectados,
    al.plan_llm = $plan_llm
MERGE (al)-[:ORIGINA_EN]->(c)
RETURN al.alerta_id AS alerta_id
"""


class WhereUsedLLMPlanner:
    """Adaptador LLM que genera recomendaciones de mitigación ante desabasto de componentes BOM."""

    def __init__(self, provider: Optional[str] = None) -> None:
        self.provider = provider or os.getenv("LLM_PROVIDER", "local")

    def plan_mitigacion(self, impacto: Dict[str, Any]) -> Dict[str, Any]:
        prompt = (
            "Analiza el impacto de desabasto en un BOM multinivel y devuelve JSON con: "
            "nivel_riesgo (BAJO|MEDIO|CRITICO), acciones (lista de strings), resumen.\n"
            f"Impacto: {json.dumps(impacto, ensure_ascii=False)}"
        )
        api_key = os.getenv("OPENAI_API_KEY")
        if self.provider == "openai" and api_key:
            req = urllib.request.Request(
                "https://api.openai.com/v1/chat/completions",
                data=json.dumps(
                    {
                        "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                        "messages": [{"role": "user", "content": prompt}],
                        "response_format": {"type": "json_object"},
                    }
                ).encode("utf-8"),
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            content = json.loads(body["choices"][0]["message"]["content"])
            content["modelo"] = body.get("model", "openai")
            return content

        pts = impacto.get("productos_terminados", [])
        ses = impacto.get("subensambles", [])
        deficit = impacto.get("deficit_unidades", 0)
        riesgo = "CRITICO" if len(pts) >= 1 and deficit > 0 else ("MEDIO" if ses else "BAJO")
        acciones = [
            f"Priorizar compra urgente de {deficit} unidades de {impacto['component_sku']}.",
            f"Evaluar sustituto homologado vía ECO para {len(pts)} producto(s) terminado(s): {', '.join(pts) or 'ninguno'}.",
        ]
        if ses:
            acciones.append(f"Reprogramar ensamble de subensambles intermedios: {', '.join(ses)}.")
        return {
            "modelo": "whereused-llm-sim-v1",
            "nivel_riesgo": riesgo,
            "acciones": acciones,
            "resumen": f"Componente {impacto['component_sku']} impacta {len(pts)} PT y {len(ses)} SE.",
        }


class BOMWhereUsedImpactAgent:
    """Agente IA de implosión inversa (Where-Used) sobre estructuras BOM multinivel."""

    def __init__(
        self,
        items_catalog: Dict[str, Dict[str, Any]],
        bom_edges: List[Dict[str, Any]],
        neo4j_driver: Any = None,
        llm: Optional[WhereUsedLLMPlanner] = None,
    ) -> None:
        self.items = items_catalog
        self.edges = bom_edges
        self.driver = neo4j_driver
        self.llm = llm or WhereUsedLLMPlanner()

    def implosion_where_used(
        self, component_sku: str, incluir_inactivos: bool = False
    ) -> List[Dict[str, Any]]:
        """Encuentra todos los usos directos (profundidad 1) e indirectos (profundidad >= 2)."""
        resultados: List[Dict[str, Any]] = []

        # Construcción inversa: hijo -> lista de padres
        padres_por_hijo: Dict[str, List[Dict[str, Any]]] = {}
        for edge in self.edges:
            if not incluir_inactivos and edge.get("estado", "ACTIVO") != "ACTIVO":
                continue
            padres_por_hijo.setdefault(edge["child_sku"], []).append(edge)

        def dfs_inverso(actual: str, acum_qty: float, ruta_inversa: List[str], prof: int) -> None:
            for edge in padres_por_hijo.get(actual, []):
                padre = edge["parent_sku"]
                if padre in ruta_inversa:
                    continue
                nueva_qty = round(acum_qty * float(edge["cantidad"]), 4)
                nueva_ruta = [padre] + ruta_inversa
                resultados.append(
                    {
                        "sku_afectado": padre,
                        "tipo_item": self.items.get(padre, {}).get("tipo_item", "DESCONOCIDO"),
                        "profundidad": prof,
                        "consumo_unitario_total": nueva_qty,
                        "ruta_ensamble": nueva_ruta,
                    }
                )
                dfs_inverso(padre, nueva_qty, nueva_ruta, prof + 1)

        dfs_inverso(component_sku, 1.0, [component_sku], 1)

        if self.driver is not None:
            self.driver.execute_query(
                CYPHER_WHERE_USED,
                component_sku=component_sku,
                incluir_inactivos=incluir_inactivos,
            )

        resultados.sort(key=lambda r: (r["profundidad"], r["sku_afectado"]))
        return resultados

    def analizar_impacto_desabasto(
        self,
        alerta_id: str,
        component_sku: str,
        stock_actual: float,
        demanda_componente: float,
        incluir_inactivos: bool = False,
    ) -> Dict[str, Any]:
        usos = self.implosion_where_used(component_sku, incluir_inactivos=incluir_inactivos)
        pts = sorted({u["sku_afectado"] for u in usos if u["tipo_item"] == "PT"})
        ses = sorted({u["sku_afectado"] for u in usos if u["tipo_item"] == "SE"})
        deficit = max(0.0, round(demanda_componente - stock_actual, 4))

        impacto = {
            "alerta_id": alerta_id,
            "component_sku": component_sku,
            "stock_actual": stock_actual,
            "demanda_componente": demanda_componente,
            "deficit_unidades": deficit,
            "productos_terminados": pts,
            "subensambles": ses,
            "usos_detallados": usos,
        }
        plan = self.llm.plan_mitigacion(impacto)
        impacto["recomendacion_llm"] = plan

        if self.driver is not None:
            self.driver.execute_query(
                CYPHER_REGISTER_MITIGATION,
                component_sku=component_sku,
                alerta_id=alerta_id,
                nivel_riesgo=plan["nivel_riesgo"],
                pt_afectados=pts,
                plan_llm=plan["resumen"],
            )
        return impacto
