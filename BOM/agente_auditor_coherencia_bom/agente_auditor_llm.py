"""Agente IA Auditor de Coherencia Estructural, UOM y Reglas de Catálogo BOM (LLM + Neo4j).

Resuelve:
- Bloqueo de Materias Primas (MP) configuradas como SKU padre (RN-01, RN-15).
- Detección de componentes hijos duplicados en una misma versión BOM (RN-02).
- Validación de compatibilidad dimensional de Unidades de Medida (UOM) (RN-04).
- Verificación de subensambles (SE) con estructura BOM propia (RN-05).
- Emisión de dictamen de auditoría QA y acciones correctivas asistidas por LLM.
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Any, Dict, List, Optional


UOM_DIMENSION: Dict[str, str] = {
    "PZA": "CONTEO",
    "UN": "CONTEO",
    "CAJA": "CONTEO",
    "KG": "MASA",
    "G": "MASA",
    "L": "VOLUMEN",
    "ML": "VOLUMEN",
    "M": "LONGITUD",
    "CM": "LONGITUD",
}

CYPHER_AUDIT_MP_PARENTS = """
MATCH (mp:Articulo {tipo_item: 'MP'})-[:TIENE_BOM]->(b:BOMVersion)
RETURN mp.sku AS sku_invalido, b.version AS version
"""

CYPHER_REGISTER_AUDIT = """
MERGE (b:BOMVersion {bom_id: $bom_id})
MERGE (aud:AuditoriaBOM {auditoria_id: $auditoria_id})
SET aud.aprobado = $aprobado,
    aud.total_hallazgos = $total_hallazgos,
    aud.dictamen_llm = $dictamen_llm
MERGE (aud)-[:AUDITA]->(b)
RETURN aud.auditoria_id AS auditoria_id
"""


class AuditorLLMReviewer:
    """Adaptador LLM que redacta dictámenes QA y remediación para hallazgos de BOM."""

    def __init__(self, provider: Optional[str] = None) -> None:
        self.provider = provider or os.getenv("LLM_PROVIDER", "local")

    def dictaminar(self, auditoria: Dict[str, Any]) -> Dict[str, Any]:
        prompt = (
            "Actúa como auditor QA de ingeniería BOM ERP. Responde JSON con: "
            "veredicto (APROBADO|RECHAZADO), severidad (NINGUNA|ALTA|CRITICA), "
            "plan_remediacion (lista), resumen.\n"
            f"Auditoría: {json.dumps(auditoria, ensure_ascii=False)}"
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

        hallazgos = auditoria.get("hallazgos", [])
        if not hallazgos:
            return {
                "modelo": "auditor-llm-sim-v1",
                "veredicto": "APROBADO",
                "severidad": "NINGUNA",
                "plan_remediacion": [],
                "resumen": f"BOM '{auditoria['bom_id']}' cumple todas las reglas estructurales y UOM.",
            }

        reglas = {h["regla"] for h in hallazgos}
        severidad = "CRITICA" if ({"RN-15", "RN-01", "RN-05"} & reglas) else "ALTA"
        plan = [f"[{h['regla']}] {h['accion_correctiva']}" for h in hallazgos]
        return {
            "modelo": "auditor-llm-sim-v1",
            "veredicto": "RECHAZADO",
            "severidad": severidad,
            "plan_remediacion": plan,
            "resumen": f"Se detectaron {len(hallazgos)} incumplimiento(s) normativo(s) en '{auditoria['bom_id']}'.",
        }


class BOMCoherenceAuditorAgent:
    """Agente IA auditor de integridad referencial, tipología (PT/SE/MP) y UOM."""

    def __init__(
        self,
        items_catalog: Dict[str, Dict[str, Any]],
        boms_index: Dict[str, Dict[str, Any]],
        neo4j_driver: Any = None,
        llm: Optional[AuditorLLMReviewer] = None,
    ) -> None:
        self.items = items_catalog
        self.boms = boms_index
        self.driver = neo4j_driver
        self.llm = llm or AuditorLLMReviewer()

    def auditar_bom(self, auditoria_id: str, bom: Dict[str, Any]) -> Dict[str, Any]:
        hallazgos: List[Dict[str, str]] = []
        parent_sku = bom.get("parent_sku", "")
        parent_item = self.items.get(parent_sku)

        if not parent_item:
            hallazgos.append(
                {
                    "regla": "RN-01",
                    "detalle": f"SKU padre '{parent_sku}' no existe en el catálogo maestro.",
                    "accion_correctiva": f"Dar de alta '{parent_sku}' como PT o SE antes de crear el BOM.",
                }
            )
        elif parent_item["tipo_item"] == "MP":
            hallazgos.append(
                {
                    "regla": "RN-15",
                    "detalle": f"'{parent_sku}' es Materia Prima (MP) y no puede encabezar un BOM.",
                    "accion_correctiva": "Reasignar un SKU de tipo PT o SE como padre del BOM.",
                }
            )

        vistos = set()
        for linea in bom.get("lineas", []):
            child_sku = linea.get("child_sku", "")
            if child_sku in vistos:
                hallazgos.append(
                    {
                        "regla": "RN-02",
                        "detalle": f"Componente '{child_sku}' duplicado en la misma versión BOM.",
                        "accion_correctiva": f"Consolidar las líneas repetidas de '{child_sku}' en un solo registro.",
                    }
                )
            vistos.add(child_sku)

            child_item = self.items.get(child_sku)
            if not child_item or not child_item.get("activo", True):
                hallazgos.append(
                    {
                        "regla": "RN-02",
                        "detalle": f"Componente hijo '{child_sku}' inexistente o inactivo.",
                        "accion_correctiva": f"Activar o reemplazar '{child_sku}' por un SKU vigente.",
                    }
                )
                continue

            if float(linea.get("cantidad", 0)) <= 0:
                hallazgos.append(
                    {
                        "regla": "RN-03",
                        "detalle": f"Cantidad no positiva para '{child_sku}'.",
                        "accion_correctiva": f"Capturar cantidad > 0 para '{child_sku}'.",
                    }
                )

            uom_linea = linea.get("uom", child_item.get("uom_base", "PZA")).upper()
            uom_base = child_item.get("uom_base", "PZA").upper()
            dim_linea = UOM_DIMENSION.get(uom_linea)
            dim_base = UOM_DIMENSION.get(uom_base)
            if not dim_linea or dim_linea != dim_base:
                hallazgos.append(
                    {
                        "regla": "RN-04",
                        "detalle": (
                            f"UOM incompatible en '{child_sku}': línea={uom_linea} ({dim_linea}) "
                            f"vs base={uom_base} ({dim_base})."
                        ),
                        "accion_correctiva": f"Convertir la línea de '{child_sku}' a unidad compatible con {uom_base}.",
                    }
                )

            if child_item["tipo_item"] == "SE":
                sub_bom = self.boms.get(child_sku)
                if not sub_bom or sub_bom.get("estado") not in ("ACTIVO", "BORRADOR"):
                    hallazgos.append(
                        {
                            "regla": "RN-05",
                            "detalle": f"Subensamble '{child_sku}' carece de BOM propio ACTIVO o BORRADOR.",
                            "accion_correctiva": f"Registrar y vincular una receta BOM válida para '{child_sku}'.",
                        }
                    )

        aprobado = len(hallazgos) == 0
        resultado = {
            "auditoria_id": auditoria_id,
            "bom_id": bom["bom_id"],
            "parent_sku": parent_sku,
            "aprobado": aprobado,
            "total_hallazgos": len(hallazgos),
            "hallazgos": hallazgos,
        }
        dictamen = self.llm.dictaminar(resultado)
        resultado["dictamen_llm"] = dictamen

        if self.driver is not None:
            self.driver.execute_query(CYPHER_AUDIT_MP_PARENTS)
            self.driver.execute_query(
                CYPHER_REGISTER_AUDIT,
                bom_id=bom["bom_id"],
                auditoria_id=auditoria_id,
                aprobado=aprobado,
                total_hallazgos=len(hallazgos),
                dictamen_llm=dictamen["resumen"],
            )
        return resultado
