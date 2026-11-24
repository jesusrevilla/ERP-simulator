"""Fase 3 - Recomendación de sustitutos y segmentación ABC.

Cuando un componente se agota, el agente recorre el grafo de compatibilidad
(:Item)-[:COMPATIBLE_WITH]->(:Item) para encontrar un reemplazo de la misma
categoría, con existencias y compatible con la misma Motherboard.

Se implementan dos recorridos:
  * BFS (anchura): el sustituto con menos saltos en el grafo.
  * Greedy Best-First Search: expande primero el nodo más parecido al original
    según una heurística h(n).
"""
from __future__ import annotations

import heapq
import itertools
import re
from collections import deque
from dataclasses import dataclass
from typing import Optional


@dataclass
class Sustituto:
    codigo: str
    saltos: int
    algoritmo: str
    nodos_explorados: int


def construir_grafo(items: list, aristas: list) -> dict:
    """Grafo no dirigido {ItemCode: {vecinos}} a partir de las relaciones COMPATIBLE_WITH."""
    grafo = {item["ItemCode"]: set() for item in items}
    for a, b in aristas:
        if a in grafo and b in grafo:
            grafo[a].add(b)
            grafo[b].add(a)
    return grafo


def _valor_capacidad(texto: Optional[str]) -> float:
    """'16GB' -> 16, '2TB' -> 2000, '750W' -> 750, '8N' -> 8."""
    if not texto:
        return 0.0
    m = re.match(r"\s*(\d+(?:\.\d+)?)\s*(TB|GB|W|N)?", str(texto).upper())
    if not m:
        return 0.0
    valor = float(m.group(1))
    return valor * 1000 if m.group(2) == "TB" else valor


def heuristica(origen: dict, nodo: dict) -> float:
    """h(n): qué tan distinto es un nodo del artículo agotado (0 = idéntico)."""
    h = 0.0
    if nodo.get("Category") != origen.get("Category"):
        h += 2.0
    if nodo.get("SubstituteGroup") != origen.get("SubstituteGroup"):
        h += 1.0
    cap_o = _valor_capacidad((origen.get("atributosTecnicos") or {}).get("capacidad"))
    cap_n = _valor_capacidad((nodo.get("atributosTecnicos") or {}).get("capacidad"))
    if max(cap_o, cap_n) > 0:
        h += abs(cap_o - cap_n) / max(cap_o, cap_n)
    precio_o, precio_n = origen.get("ListPrice", 0), nodo.get("ListPrice", 0)
    if max(precio_o, precio_n) > 0:
        h += abs(precio_o - precio_n) / max(precio_o, precio_n)
    return h


def _placas(grafo: dict, items: dict, codigo: str) -> set:
    return {v for v in grafo.get(codigo, ()) if items[v].get("Category") == "Motherboard"}


def es_sustituto(grafo: dict, items: dict, origen: str, candidato: str) -> bool:
    """Misma categoría, con existencias y compatible con una Motherboard del original."""
    if candidato == origen or items[origen].get("Category") == "Motherboard":
        return False
    c, o = items[candidato], items[origen]
    if c.get("Category") != o.get("Category") or c.get("StockDisponible", 0) <= 0:
        return False
    return bool(_placas(grafo, items, origen) & _placas(grafo, items, candidato))


def bfs_sustituto(grafo: dict, items: dict, codigo: str) -> Optional[Sustituto]:
    """Búsqueda en anchura: nivel por nivel; desempata con la heurística."""
    visitados = {codigo}
    frontera = deque([codigo])
    saltos = 0
    while frontera:
        saltos += 1
        siguiente: deque = deque()
        candidatos = []
        for nodo in sorted(frontera):
            for vecino in sorted(grafo.get(nodo, ())):
                if vecino in visitados:
                    continue
                visitados.add(vecino)
                siguiente.append(vecino)
                if es_sustituto(grafo, items, codigo, vecino):
                    candidatos.append(vecino)
        if candidatos:
            mejor = min(candidatos, key=lambda c: (heuristica(items[codigo], items[c]), c))
            return Sustituto(mejor, saltos, "BFS", len(visitados))
        frontera = siguiente
    return None


def greedy_sustituto(grafo: dict, items: dict, codigo: str) -> Optional[Sustituto]:
    """Búsqueda voraz: siempre expande el nodo con menor h(n)."""
    origen = items[codigo]
    desempate = itertools.count()
    heap = [(heuristica(origen, origen), next(desempate), codigo, 0)]
    visitados: set = set()
    while heap:
        _, _, nodo, saltos = heapq.heappop(heap)
        if nodo in visitados:
            continue
        visitados.add(nodo)
        if es_sustituto(grafo, items, codigo, nodo):
            return Sustituto(nodo, saltos, "Greedy", len(visitados))
        for vecino in sorted(grafo.get(nodo, ())):
            if vecino not in visitados:
                heapq.heappush(heap, (heuristica(origen, items[vecino]), next(desempate), vecino, saltos + 1))
    return None


def segmentacion_abc(items: list, corte_a: float = 0.80, corte_b: float = 0.95) -> dict:
    """Clasifica por valor de consumo anual (DemandaAnual x StandardCost).

    A: los artículos que acumulan hasta el 80 % del valor; B: hasta 95 %; C: el resto.
    """
    valores = sorted(
        ((i["ItemCode"], i.get("DemandaAnual", 0) * i.get("StandardCost", 0)) for i in items),
        key=lambda par: (-par[1], par[0]),
    )
    total = sum(v for _, v in valores)
    clases: dict = {}
    acumulado = 0.0
    for codigo, valor in valores:
        proporcion_previa = acumulado / total if total else 1.0
        if proporcion_previa < corte_a:
            clases[codigo] = "A"
        elif proporcion_previa < corte_b:
            clases[codigo] = "B"
        else:
            clases[codigo] = "C"
        acumulado += valor
    return clases
