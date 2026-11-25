"""Agente IA de Ingeniería de Cambios (ECO) y Versionado BOM (LLM + Neo4j).

Resuelve:
- Validación de matriz de transición de estados (BORRADOR, ACTIVO, INACTIVO, OBSOLETO).
- Bloqueo de traslape temporal entre versiones ACTIVAS de un mismo producto padre (RN-08).
- Protección contra edición directa de BOMs activos o comprometidos en producción (RN-14).
- Clonación automática hacia nueva versión en BORRADOR (RN-09).
- Análisis de impacto y dictamen técnico asistido por LLM (OpenAI/Gemini o motor local).
"""

from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


VALID_TRANSITIONS: Dict[str, set] = {
    "BORRADOR": {"ACTIVO"},
    "ACTIVO": {"INACTIVO", "OBSOLETO"},
    "INACTIVO": {"ACTIVO", "OBSOLETO"},
    "OBSOLETO": set(),
}

CYPHER_CHECK_OVERLAP = """
MATCH (p:Producto {sku: $parent_sku})-[:TIENE_VERSION]->(v:BOMVersion)
WHERE v.estado = 'ACTIVO'
  AND v.version <> $version
  AND v.fecha_inicio < coalesce($fecha_fin, '9999-12-31T23:59:59')
  AND coalesce(v.fecha_fin, '9999-12-31T23:59:59') > $fecha_inicio
RETURN v.version AS version_conflictiva,
       v.fecha_inicio AS fecha_inicio,
       v.fecha_fin AS fecha_fin
"""

CYPHER_REGISTER_ECO = """
MERGE (p:Producto {sku: $parent_sku})
MERGE (v:BOMVersion {bom_id: $bom_id})
SET v.version = $version,
    v.estado = $estado,
    v.fecha_inicio = $fecha_inicio,
    v.fecha_fin = $fecha_fin
MERGE (p)-[:TIENE_VERSION]->(v)
MERGE (eco:OrdenCambioECO {eco_id: $eco_id})
SET eco.motivo = $motivo,
    eco.dictamen_llm = $dictamen_llm,
    eco.fecha = $fecha_eco
MERGE (eco)-[:MODIFICA]->(v)
RETURN eco.eco_id AS eco_id, v.version AS version
"""


class ECOBusinessError(Exception):
    """Error de regla de negocio en ciclo de vida o ECO de BOM."""


@dataclass
class BOMVersion:
    bom_id: str
    parent_sku: str
    version: str
    estado: str
    fecha_inicio: str
    fecha_fin: Optional[str]
    componentes: List[Dict[str, Any]]
    tiene_ordenes_produccion: bool = False


class ECOLLMAnalyzer:
    """Adaptador LLM especializado en evaluación de Órdenes de Cambio de Ingeniería (ECO)."""

    def __init__(self, provider: Optional[str] = None) -> None:
        self.provider = provider or os.getenv("LLM_PROVIDER", "local")

    def evaluar_eco(self, contexto: Dict[str, Any]) -> Dict[str, Any]:
        prompt = (
            "Evalúa la siguiente Orden de Cambio de Ingeniería (ECO) sobre un BOM ERP. "
            "Responde JSON con: decision (APROBAR|RECHAZAR|REVISAR), riesgo (BAJO|MEDIO|ALTO), resumen.\n"
            f"Contexto: {json.dumps(contexto, ensure_ascii=False)}"
        )

        api_key = os.getenv("OPENAI_API_KEY")
        if self.provider == "openai" and api_key:
            return self._call_openai(prompt, api_key)

        # Fallback determinista offline para pruebas reproducibles sin API externa
        conflictos = contexto.get("conflictos", [])
        ordenes_activas = contexto.get("ordenes_produccion_abiertas", False)
        delta_componentes = len(contexto.get("componentes_nuevos", [])) - len(
            contexto.get("componentes_anteriores", [])
        )

        if conflictos:
            return {
                "modelo": "eco-llm-sim-v1",
                "decision": "RECHAZAR",
                "riesgo": "ALTO",
                "resumen": (
                    f"Se detectó traslape de vigencia con versión activa: {conflictos[0]['version_conflictiva']}. "
                    "Cerrar la vigencia previa antes de activar."
                ),
            }
        if ordenes_activas and contexto.get("accion") == "EDITAR_DIRECTO":
            return {
                "modelo": "eco-llm-sim-v1",
                "decision": "RECHAZAR",
                "riesgo": "ALTO",
                "resumen": "El BOM tiene órdenes de producción vinculadas; clonar a nueva versión BORRADOR.",
            }
        riesgo = "MEDIO" if delta_componentes != 0 else "BAJO"
        return {
            "modelo": "eco-llm-sim-v1",
            "decision": "APROBAR",
            "riesgo": riesgo,
            "resumen": (
                f"ECO válido para {contexto.get('parent_sku')} ({contexto.get('version')}). "
                f"Cambio neto de líneas: {delta_componentes:+d}. Motivo: {contexto.get('motivo', '')}."
            ),
        }

    @staticmethod
    def _call_openai(prompt: str, api_key: str) -> Dict[str, Any]:
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


class BOMECOLifecycleAgent:
    """Agente experto + LLM para versionado, clonación y ECOs de BOM sobre Neo4j."""

    def __init__(self, neo4j_driver: Any = None, llm: Optional[ECOLLMAnalyzer] = None) -> None:
        self.driver = neo4j_driver
        self.llm = llm or ECOLLMAnalyzer()
        self.versiones: Dict[str, BOMVersion] = {}

    def registrar_version(self, version: BOMVersion) -> BOMVersion:
        if version.bom_id in self.versiones:
            raise ECOBusinessError(f"BOM '{version.bom_id}' ya existe.")
        for existing in self.versiones.values():
            if existing.parent_sku == version.parent_sku and existing.version == version.version:
                raise ECOBusinessError(
                    f"RN-06: La versión '{version.version}' ya existe para '{version.parent_sku}'."
                )
        if version.estado == "ACTIVO":
            conflictos = self.detectar_traslapes(
                version.parent_sku, version.version, version.fecha_inicio, version.fecha_fin
            )
            if conflictos:
                raise ECOBusinessError(
                    f"RN-08: Traslape de vigencia activa con {conflictos[0]['version_conflictiva']}."
                )
        self.versiones[version.bom_id] = version
        return version

    def detectar_traslapes(
        self, parent_sku: str, version: str, fecha_inicio: str, fecha_fin: Optional[str]
    ) -> List[Dict[str, Any]]:
        ini = datetime.fromisoformat(fecha_inicio)
        fin = datetime.fromisoformat(fecha_fin) if fecha_fin else datetime.max
        if fin <= ini:
            raise ECOBusinessError("fecha_fin debe ser posterior a fecha_inicio.")

        conflictos: List[Dict[str, Any]] = []
        for v in self.versiones.values():
            if v.parent_sku != parent_sku or v.estado != "ACTIVO" or v.version == version:
                continue
            v_ini = datetime.fromisoformat(v.fecha_inicio)
            v_fin = datetime.fromisoformat(v.fecha_fin) if v.fecha_fin else datetime.max
            if ini < v_fin and fin > v_ini:
                conflictos.append(
                    {
                        "version_conflictiva": v.version,
                        "fecha_inicio": v.fecha_inicio,
                        "fecha_fin": v.fecha_fin,
                    }
                )
        if self.driver is not None:
            records, _, _ = self.driver.execute_query(
                CYPHER_CHECK_OVERLAP,
                parent_sku=parent_sku,
                version=version,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
            )
            for rec in records:
                conflictos.append(rec.data())
        return conflictos

    def editar_componentes(self, bom_id: str, nuevos_componentes: List[Dict[str, Any]]) -> BOMVersion:
        bom = self.versiones.get(bom_id)
        if not bom:
            raise ECOBusinessError(f"BOM '{bom_id}' no encontrado.")
        if bom.estado == "ACTIVO" or bom.tiene_ordenes_produccion:
            raise ECOBusinessError(
                f"RN-14: El BOM '{bom_id}' ({bom.estado}) es inmutable; debe clonarse a BORRADOR."
            )
        bom.componentes = [dict(c) for c in nuevos_componentes]
        return bom

    def clonar_version(
        self, bom_origen_id: str, nuevo_bom_id: str, nueva_version: str, fecha_clonacion: str
    ) -> BOMVersion:
        origen = self.versiones.get(bom_origen_id)
        if not origen:
            raise ECOBusinessError(f"BOM origen '{bom_origen_id}' no existe.")
        clon = BOMVersion(
            bom_id=nuevo_bom_id,
            parent_sku=origen.parent_sku,
            version=nueva_version,
            estado="BORRADOR",
            fecha_inicio=fecha_clonacion,
            fecha_fin=None,
            componentes=[dict(c) for c in origen.componentes],
            tiene_ordenes_produccion=False,
        )
        return self.registrar_version(clon)

    def procesar_eco_y_transicionar(
        self, eco_id: str, bom_id: str, nuevo_estado: str, motivo: str
    ) -> Dict[str, Any]:
        bom = self.versiones.get(bom_id)
        if not bom:
            raise ECOBusinessError(f"BOM '{bom_id}' no existe.")
        if nuevo_estado not in VALID_TRANSITIONS.get(bom.estado, set()):
            raise ECOBusinessError(
                f"RN-07: Transición inválida {bom.estado} -> {nuevo_estado}."
            )

        conflictos: List[Dict[str, Any]] = []
        if nuevo_estado == "ACTIVO":
            conflictos = self.detectar_traslapes(
                bom.parent_sku, bom.version, bom.fecha_inicio, bom.fecha_fin
            )

        dictamen = self.llm.evaluar_eco(
            {
                "eco_id": eco_id,
                "parent_sku": bom.parent_sku,
                "version": bom.version,
                "estado_actual": bom.estado,
                "nuevo_estado": nuevo_estado,
                "motivo": motivo,
                "conflictos": conflictos,
                "ordenes_produccion_abiertas": bom.tiene_ordenes_produccion,
                "componentes_nuevos": bom.componentes,
                "componentes_anteriores": bom.componentes,
            }
        )

        if dictamen["decision"] == "RECHAZAR":
            raise ECOBusinessError(f"ECO rechazado por agente LLM: {dictamen['resumen']}")

        bom.estado = nuevo_estado
        if self.driver is not None:
            self.driver.execute_query(
                CYPHER_REGISTER_ECO,
                parent_sku=bom.parent_sku,
                bom_id=bom.bom_id,
                version=bom.version,
                estado=bom.estado,
                fecha_inicio=bom.fecha_inicio,
                fecha_fin=bom.fecha_fin,
                eco_id=eco_id,
                motivo=motivo,
                dictamen_llm=dictamen["resumen"],
                fecha_eco=datetime.now(timezone.utc).isoformat(),
            )
        return {"eco_id": eco_id, "bom_id": bom.bom_id, "estado": bom.estado, "dictamen_llm": dictamen}
