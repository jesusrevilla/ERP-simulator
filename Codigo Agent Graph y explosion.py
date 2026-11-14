import math
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from collections import defaultdict


class BOMGraphExplosionAgent:
    """
    Agente de Razonamiento Estructural y Explosión Multinivel (DAG + DFS + DP).
    Cumple con RN01-RN08 (181914) y RN-01 a RN-15 (BOM_Requirements).
    """

    def __init__(self, items_master: Dict[str, dict], bom_headers: List[dict], bom_details: List[dict]):
        """
        :param items_master: {sku: {'tipo_item': 'PT'|'SE'|'MP', 'uom_base': str, 'es_discreto': bool, 'activo': bool, 'costo': float}}
        :param bom_headers: Lista de cabeceras BOM (bom_cabecera)
        :param bom_details: Lista de líneas de componentes (bom_detalle)
        """
        self.items = items_master
        self.headers = bom_headers
        self.details = bom_details
        self._memo_explosion: Dict[Tuple[str, str], Dict[str, float]] = {}

    def _build_adjacency_graph(self, include_drafts: bool = True) -> Dict[str, List[str]]:
        """Construye la lista de adyacencia G=(V,E) para validación estructural."""
        adj = defaultdict(list)
        valid_states = {'ACTIVO', 'BORRADOR'} if include_drafts else {'ACTIVO'}
        header_map = {h['bom_id']: h for h in self.headers if h['estado'] in valid_states}

        for line in self.details:
            header = header_map.get(line['bom_id'])
            if header:
                adj[header['parent_sku']].append(line['component_sku'])
        return adj

    def validar_grafo_aciclico_dag(self, proposed_parent: str = None, proposed_child: str = None) -> Tuple[bool, str]:
        """
        Algoritmo DFS con coloración de 3 estados (0=No visitado, 1=En visita/Pila, 2=Completado).
        Detecta autorreferencias (A -> A) y ciclos indirectos (A -> B -> C -> A).
        """
        adj = self._build_adjacency_graph(include_drafts=True)
        if proposed_parent and proposed_child:
            if proposed_parent == proposed_child:
                return False, f"Error DAG (RN03): Autorreferencia directa detectada ({proposed_parent} -> {proposed_child})."
            adj[proposed_parent].append(proposed_child)

        estado_nodo = defaultdict(int)  # 0: Blanco, 1: Gris (en pila), 2: Negro (procesado)

        def dfs(nodo: str, ruta: List[str]) -> Optional[List[str]]:
            estado_nodo[nodo] = 1
            for vecino in adj.get(nodo, []):
                if estado_nodo[vecino] == 1:
                    return ruta + [vecino]
                if estado_nodo[vecino] == 0:
                    ciclo = dfs(vecino, ruta + [vecino])
                    if ciclo:
                        return ciclo
            estado_nodo[nodo] = 2
            return None

        for sku in list(adj.keys()):
            if estado_nodo[sku] == 0:
                ciclo_detectado = dfs(sku, [sku])
                if ciclo_detectado:
                    return False, f"Error DAG (RN03/RN-13): Ciclo estructural detectado -> {' -> '.join(ciclo_detectado)}"

        return True, "Estructura válida: Grafo Acíclico Dirigido (DAG) verificado."

    def seleccionar_version_vigente(self, parent_sku: str, fecha_demanda: datetime) -> dict:
        """
        Selecciona la única versión ACTIVA vigente en [fecha_inicio, fecha_fin) (RN06, RN07, PU08).
        """
        item = self.items.get(parent_sku)
        if not item or not item['activo']:
            raise ValueError(f"Artículo '{parent_sku}' inexistente o inactivo en catálogo maestro.")
        if item['tipo_item'] == 'MP':
            raise ValueError(f"Materia Prima '{parent_sku}' no puede tener BOM (RN01/RN-15).")

        candidatas = []
        for h in self.headers:
            if h['parent_sku'] == parent_sku and h['estado'] == 'ACTIVO':
                inicio = datetime.fromisoformat(h['fecha_inicio'])
                fin = datetime.fromisoformat(h['fecha_fin']) if h['fecha_fin'] else datetime.max
                if inicio <= fecha_demanda < fin:
                    candidatas.append(h)

        if not candidatas:
            raise LookupError(f"BOM.ExplosionRejected: No existe versión ACTIVA para '{parent_sku}' en {fecha_demanda.isoformat()}.")
        if len(candidatas) > 1:
            raise RuntimeError(f"BOM.ConcurrencyConflict: Traslape de vigencias activas para '{parent_sku}'.")

        return candidatas[0]

    def _explotar_recursivo(self, sku: str, fecha_demanda: datetime, visitados: set) -> Dict[str, float]:
        """
        Recorrido Top-Down con memoización para calcular requerimientos unitarios de Materias Primas (MP).
        """
        if sku in visitados:
            raise RecursionError(f"Ciclo infinito detectado durante explosión en SKU '{sku}'.")

        item = self.items[sku]
        # Caso base: hoja del árbol (Materia Prima)
        if item['tipo_item'] == 'MP':
            return {sku: 1.0}

        cache_key = (sku, fecha_demanda.isoformat())
        if cache_key in self._memo_explosion:
            return self._memo_explosion[cache_key]

        header = self.seleccionar_version_vigente(sku, fecha_demanda)
        lineas = [d for d in self.details if d['bom_id'] == header['bom_id']]
        if not lineas:
            raise ValueError(f"BOM '{header['version_codigo']}' de '{sku}' no tiene componentes (RN01).")

        requerimientos_mp = defaultdict(float)
        visitados.add(sku)

        for linea in lineas:
            comp_sku = linea['component_sku']
            scrap = linea.get('scrap_merma', 0.0)
            if not (0.0 <= scrap < 1.0):
                raise ValueError(f"Merma inválida ({scrap}) en componente '{comp_sku}' (RN08).")

            # Fórmula RN08: cantidad_teorica / (base * (1 - merma))
            factor_consumo = linea['cantidad'] / (header['cantidad_base'] * (1.0 - scrap))

            sub_explosion = self._explotar_recursivo(comp_sku, fecha_demanda, visitados)
            for mp_sku, cant_sub in sub_explosion.items():
                requerimientos_mp[mp_sku] += factor_consumo * cant_sub

        visitados.remove(sku)
        resultado = dict(requerimientos_mp)
        self._memo_explosion[cache_key] = resultado
        return resultado

    def explotar_bom(self, parent_sku: str, cantidad_demanda: float, fecha_demanda: str) -> dict:
        """
        Ejecuta la explosión completa, acumula ramas compartidas y redondea hacia arriba
        al final para artículos discretos (RN08, PU09).
        """
        if cantidad_demanda <= 0:
            raise ValueError("La cantidad de demanda debe ser mayor a cero.")

        dt_demanda = datetime.fromisoformat(fecha_demanda)
        es_dag, msg = self.validar_grafo_aciclico_dag()
        if not es_dag:
            raise ValueError(msg)

        consumo_unitario_mp = self._explotar_recursivo(parent_sku, dt_demanda, set())
        materiales_consolidados = []

        for mp_sku, cant_unitaria in consumo_unitario_mp.items():
            bruta_exacta = cant_unitaria * cantidad_demanda
            meta_item = self.items[mp_sku]
            # Redondeo hacia arriba (ceil) solo al final de la acumulación (PU09)
            cantidad_final = math.ceil(bruta_exacta) if meta_item['es_discreto'] else round(bruta_exacta, 4)

            materiales_consolidados.append({
                "sku": mp_sku,
                "uom": meta_item['uom_base'],
                "cantidad_bruta_exacta": round(bruta_exacta, 4),
                "cantidad_requerida_final": cantidad_final,
                "costo_total_estimado": round(cantidad_final * meta_item['costo'], 2)
            })

        return {
            "evento": "BOM.Exploded",
            "producto_padre": parent_sku,
            "demanda": cantidad_demanda,
            "fecha_demanda": fecha_demanda,
            "materiales_aplanados": materiales_consolidados
        }


# ==========================================
# EJEMPLO DE EJECUCIÓN (Basado en JSON y PDF)
# ==========================================
if __name__ == "__main__":
    catalogo = {
        "PC001": {"tipo_item": "PT", "uom_base": "PCS", "es_discreto": True, "activo": True, "costo": 0.0},
        "SE-COOL": {"tipo_item": "SE", "uom_base": "PCS", "es_discreto": True, "activo": True, "costo": 0.0},
        "GPU001": {"tipo_item": "MP", "uom_base": "PCS", "es_discreto": True, "activo": True, "costo": 500.0},
        "TORN-M3": {"tipo_item": "MP", "uom_base": "PCS", "es_discreto": True, "activo": True, "costo": 0.10},
    }
    cabeceras = [
        {"bom_id": 1, "parent_sku": "PC001", "version_codigo": "v1.0", "cantidad_base": 1.0,
         "estado": "ACTIVO", "fecha_inicio": "2026-01-01T00:00:00", "fecha_fin": None},
        {"bom_id": 2, "parent_sku": "SE-COOL", "version_codigo": "v1.0", "cantidad_base": 1.0,
         "estado": "ACTIVO", "fecha_inicio": "2026-01-01T00:00:00", "fecha_fin": None},
    ]
    detalles = [
        {"bom_id": 1, "component_sku": "GPU001", "cantidad": 1.0, "scrap_merma": 0.0},
        {"bom_id": 1, "component_sku": "SE-COOL", "cantidad": 1.0, "scrap_merma": 0.0},
        {"bom_id": 1, "component_sku": "TORN-M3", "cantidad": 0.4, "scrap_merma": 0.0},   # Rama 1: 0.4
        {"bom_id": 2, "component_sku": "TORN-M3", "cantidad": 0.4, "scrap_merma": 0.0},   # Rama 2: 0.4 (Suma 0.8 -> ceil = 1)
    ]

    agente_bom = BOMGraphExplosionAgent(catalogo, cabeceras, detalles)
    print(agente_bom.explotar_bom("PC001", cantidad_demanda=1, fecha_demanda="2026-11-10T08:00:00"))