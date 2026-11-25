"""Agente IA de Costeo Estándar Multinivel y Optimización de Mermas BOM (LLM + Neo4j).

Resuelve:
- Costeo estándar acumulado multinivel (Cost Roll-Up, RN-11) por producto terminado y subensamble.
- Validación de factor de merma/scrap en rango [0, 1) (RN-03) y detección de mermas anómalas.
- Consolidación aplanada con redondeo discreto únicamente al acumulado final (PU09).
- Análisis de variaciones de costo y recomendaciones de optimización mediante LLM.
"""

from __future__ import annotations

import json
import math
import os
import urllib.request
from typing import Any, Dict, List, Optional


CYPHER_COST_ROLLUP = """
MATCH p = (pt:Articulo {sku: $parent_sku})-[rels:CONSUME*1..6]->(mp:Articulo {tipo_item: 'MP'})
WITH mp,
     reduce(cant = 1.0, r IN rels | cant * (r.cantidad / (1.0 - r.merma))) AS req_bruto_rama,
     mp.costo_estandar AS costo_unitario
RETURN mp.sku AS sku_mp,
       sum(req_bruto_rama) AS consumo_total_sin_redondeo,
       costo_unitario,
       sum(req_bruto_rama) * costo_unitario AS costo_total_componente
ORDER BY costo_total_componente DESC
"""

CYPHER_SAVE_COST_ANALYSIS = """
MERGE (pt:Articulo {sku: $parent_sku})
MERGE (an:AnalisisCosteoBOM {analisis_id: $analisis_id})
SET an.costo_unitario_estandar = $costo_unitario,
    an.costo_total_lote = $costo_total_lote,
    an.componente_mas_costoso = $top_driver,
    an.recomendacion_llm = $recomendacion_llm
MERGE (an)-[:EVALUA_COSTO_DE]->(pt)
RETURN an.analisis_id AS analisis_id
"""


class CostingValidationError(ValueError):
    """Error en parámetros de costo, cantidad base o merma."""


class CostingLLMOptimizer:
    """Adaptador LLM para diagnóstico de drivers de costo y reducción de merma en BOM."""

    def __init__(self, provider: Optional[str] = None) -> None:
        self.provider = provider or os.getenv("LLM_PROVIDER", "local")

    def analizar_costos(self, reporte: Dict[str, Any]) -> Dict[str, Any]:
        prompt = (
            "Analiza el costeo estándar multinivel y factores de merma del BOM. "
            "Responde JSON con: estado_costo (OPTIMO|ALERTA_MERMA|SOBRECOSTO), "
            "sugerencias (lista), resumen.\n"
            f"Reporte: {json.dumps(reporte, ensure_ascii=False)}"
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

        alertas_merma = reporte.get("alertas_merma", [])
        top_driver = reporte.get("top_driver", {})
        estado = "ALERTA_MERMA" if alertas_merma else "OPTIMO"
        sugerencias = []
        if alertas_merma:
            for a in alertas_merma:
                sugerencias.append(
                    f"Revisar proceso de ensamble para {a['child_sku']} (merma={a['merma']*100:.1f}% > umbral)."
                )
        if top_driver:
            sugerencias.append(
                f"Negociar compra por volumen para {top_driver['sku']} "
                f"(representa {top_driver['participacion_pct']}% del costo total)."
            )
        return {
            "modelo": "costing-llm-sim-v1",
            "estado_costo": estado,
            "sugerencias": sugerencias,
            "resumen": (
                f"Costo unitario estándar de {reporte['parent_sku']}: ${reporte['costo_unitario']:.2f}. "
                f"Alertas de merma detectadas: {len(alertas_merma)}."
            ),
        }


class BOMCostingScrapAgent:
    """Agente experto + LLM de costeo estándar multinivel y control de merma."""

    def __init__(
        self,
        items_catalog: Dict[str, Dict[str, Any]],
        bom_headers: Dict[str, Dict[str, Any]],
        bom_lines: Dict[str, List[Dict[str, Any]]],
        neo4j_driver: Any = None,
        umbral_merma_alerta: float = 0.08,
        llm: Optional[CostingLLMOptimizer] = None,
    ) -> None:
        self.items = items_catalog
        self.headers = bom_headers
        self.lines = bom_lines
        self.driver = neo4j_driver
        self.umbral_merma = umbral_merma_alerta
        self.llm = llm or CostingLLMOptimizer()

    def _acumular_materias_primas(
        self, sku: str, factor_padre: float, alertas_merma: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        item = self.items.get(sku)
        if not item:
            raise CostingValidationError(f"Artículo '{sku}' no existe en catálogo maestro.")
        if item["tipo_item"] == "MP" or sku not in self.headers:
            return {sku: factor_padre}

        header = self.headers[sku]
        cant_base = float(header.get("cantidad_base", 1.0))
        if cant_base <= 0:
            raise CostingValidationError(f"Cantidad base inválida para '{sku}': {cant_base}.")

        acumulado: Dict[str, float] = {}
        for line in self.lines.get(sku, []):
            qty = float(line["cantidad"])
            merma = float(line.get("scrap_merma", 0.0))
            if qty <= 0:
                raise CostingValidationError(f"RN-03: Cantidad <= 0 en {sku} -> {line['child_sku']}.")
            if merma < 0.0 or merma >= 1.0:
                raise CostingValidationError(
                    f"RN-03: Factor de merma fuera de rango [0, 1) en {line['child_sku']}: {merma}."
                )
            if merma > self.umbral_merma:
                alertas_merma.append(
                    {"parent_sku": sku, "child_sku": line["child_sku"], "merma": merma}
                )

            proporcion = factor_padre * (qty / (cant_base * (1.0 - merma)))
            sub_acum = self._acumular_materias_primas(line["child_sku"], proporcion, alertas_merma)
            for mp_sku, mp_qty in sub_acum.items():
                acumulado[mp_sku] = acumulado.get(mp_sku, 0.0) + mp_qty
        return acumulado

    def calcular_costeo_lote(
        self, analisis_id: str, parent_sku: str, cantidad_lote: float = 1.0
    ) -> Dict[str, Any]:
        if cantidad_lote <= 0:
            raise CostingValidationError("La cantidad de lote debe ser > 0.")

        alertas_merma: List[Dict[str, Any]] = []
        raw_mp = self._acumular_materias_primas(parent_sku, float(cantidad_lote), alertas_merma)

        desglose: List[Dict[str, Any]] = []
        costo_total_lote = 0.0
        for mp_sku, raw_qty in raw_mp.items():
            mp_info = self.items[mp_sku]
            es_discreto = mp_info.get("es_discreto", True)
            # PU09: Redondeo techo aplicado únicamente al acumulado final de todas las ramas
            qty_final = float(math.ceil(raw_qty)) if es_discreto else round(raw_qty, 4)
            costo_unit = float(mp_info.get("costo_estandar", 0.0))
            costo_comp = round(qty_final * costo_unit, 2)
            costo_total_lote = round(costo_total_lote + costo_comp, 2)
            desglose.append(
                {
                    "sku": mp_sku,
                    "cantidad_sin_redondeo": round(raw_qty, 6),
                    "cantidad_final": qty_final,
                    "costo_unitario": costo_unit,
                    "costo_total": costo_comp,
                }
            )

        desglose.sort(key=lambda x: x["costo_total"], reverse=True)
        top_driver = None
        if desglose and costo_total_lote > 0:
            top = desglose[0]
            top_driver = {
                "sku": top["sku"],
                "costo_total": top["costo_total"],
                "participacion_pct": round((top["costo_total"] / costo_total_lote) * 100.0, 2),
            }

        reporte = {
            "analisis_id": analisis_id,
            "parent_sku": parent_sku,
            "cantidad_lote": float(cantidad_lote),
            "costo_total_lote": costo_total_lote,
            "costo_unitario": round(costo_total_lote / float(cantidad_lote), 2),
            "desglose_mp": desglose,
            "alertas_merma": alertas_merma,
            "top_driver": top_driver,
        }
        analisis_llm = self.llm.analizar_costos(reporte)
        reporte["analisis_llm"] = analisis_llm

        if self.driver is not None:
            self.driver.execute_query(CYPHER_COST_ROLLUP, parent_sku=parent_sku)
            self.driver.execute_query(
                CYPHER_SAVE_COST_ANALYSIS,
                parent_sku=parent_sku,
                analisis_id=analisis_id,
                costo_unitario=reporte["costo_unitario"],
                costo_total_lote=reporte["costo_total_lote"],
                top_driver=top_driver["sku"] if top_driver else "",
                recomendacion_llm=analisis_llm["resumen"],
            )
        return reporte
