"""Fase 1 - Deduplicación y clasificación estructural del Item Master.

Agente: SKU Sentinel & Data Steward (matrícula 175805).

Al dar de alta un SKU se compara su estructura (categoría + marca + modelo +
capacidad + tipo, ya normalizados) contra el catálogo vigente. Si coincide con un
artículo existente, el alta se bloquea y se sugiere el SKU que ya existe. Esto
protege la regla de clave irrepetible sin depender solo del texto libre.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

CAMPOS_ESTRUCTURALES = ("marca", "modelo", "capacidad", "tipo")

# Palabras que permiten clasificar una descripción cuando falta la categoría.
PALABRAS_CATEGORIA = {
    "Motherboard": ("tarjeta madre", "motherboard", "b650", "b550"),
    "GPU": ("tarjeta de video", "rtx", "radeon", "gpu"),
    "CPU": ("procesador", "ryzen", "intel core"),
    "RAM": ("ram", "memoria", "ddr4", "ddr5"),
    "SSD": ("ssd", "nvme"),
    "PSU": ("fuente", "psu"),
}

SINONIMOS = {"memoria": "ram"}
PALABRAS_VACIAS = {"de", "con", "para", "el", "la", "y"}


def normalizar_texto(valor: Optional[str]) -> str:
    """Minúsculas y espacios colapsados."""
    return re.sub(r"\s+", " ", (valor or "").strip()).casefold()


def normalizar_capacidad(valor: Optional[str]) -> str:
    """'16 gb' -> '16GB'."""
    return re.sub(r"\s+", "", (valor or "")).upper()


def atributos_normalizados(item: dict) -> dict:
    attrs = item.get("atributosTecnicos") or {}
    return {
        "marca": normalizar_texto(attrs.get("marca")),
        "modelo": normalizar_texto(attrs.get("modelo")),
        "capacidad": normalizar_capacidad(attrs.get("capacidad")),
        "tipo": normalizar_texto(attrs.get("tipo")),
    }


def atributos_completos(item: dict) -> bool:
    return all(atributos_normalizados(item)[c] for c in CAMPOS_ESTRUCTURALES)


def clave_estructural(item: dict) -> tuple:
    """Clave de equivalencia: dos artículos con la misma clave son el mismo producto."""
    attrs = atributos_normalizados(item)
    return (normalizar_texto(item.get("Category")),) + tuple(attrs[c] for c in CAMPOS_ESTRUCTURALES)


def tokens_descripcion(descripcion: str) -> set:
    """Conjunto de palabras clave de una descripción, sin importar el orden."""
    texto = normalizar_texto(descripcion)
    texto = re.sub(r"(\d+)\s*(gb|tb|w)\b", r"\1\2", texto)
    palabras = re.findall(r"[a-z0-9+]+", texto)
    return {SINONIMOS.get(p, p) for p in palabras if p not in PALABRAS_VACIAS}


def similitud_descripcion(a: str, b: str) -> float:
    """Índice de Jaccard entre las palabras clave de dos descripciones."""
    ta, tb = tokens_descripcion(a), tokens_descripcion(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def clasificar_categoria(descripcion: str) -> Optional[str]:
    """Sugiere la categoría de un artículo a partir de su descripción."""
    texto = " " + normalizar_texto(descripcion) + " "
    palabras = set(re.findall(r"[a-z0-9]+", texto))
    for categoria, claves in PALABRAS_CATEGORIA.items():
        for clave in claves:
            if " " in clave:
                if clave in texto:
                    return categoria
            elif clave in palabras:
                return categoria
    return None


@dataclass
class ResultadoAlta:
    codigo: str
    decision: str = "APROBADO"          # APROBADO | BLOQUEADO
    motivos: list = field(default_factory=list)
    advertencias: list = field(default_factory=list)
    sku_existente: Optional[str] = None


def evaluar_alta(nuevo: dict, catalogo: list, umbral_similitud: float = 0.8) -> ResultadoAlta:
    """Decide si un SKU nuevo puede darse de alta en el catálogo maestro."""
    resultado = ResultadoAlta(codigo=nuevo.get("ItemCode", "?"))

    # 1) Clave irrepetible: el ItemCode no puede repetirse.
    for existente in catalogo:
        if existente["ItemCode"] == nuevo.get("ItemCode"):
            resultado.decision = "BLOQUEADO"
            resultado.sku_existente = existente["ItemCode"]
            resultado.motivos.append(f"El ItemCode {existente['ItemCode']} ya existe en el catálogo")
            return resultado

    # 2) Categoría faltante: se sugiere a partir de la descripción.
    if not nuevo.get("Category"):
        sugerida = clasificar_categoria(nuevo.get("Description", ""))
        if sugerida:
            nuevo = {**nuevo, "Category": sugerida}
            resultado.advertencias.append(f"Category vacía; se sugiere '{sugerida}'")

    # 3) Equivalencia estructural por atributos técnicos.
    if atributos_completos(nuevo):
        clave_nueva = clave_estructural(nuevo)
        for existente in catalogo:
            if atributos_completos(existente) and clave_estructural(existente) == clave_nueva:
                resultado.decision = "BLOQUEADO"
                resultado.sku_existente = existente["ItemCode"]
                resultado.motivos.append(
                    f"Duplicado estructural de {existente['ItemCode']} "
                    f"(misma categoría, marca, modelo, capacidad y tipo). Usar el SKU existente."
                )
                break
    else:
        resultado.advertencias.append(
            "atributosTecnicos incompletos: la comparación estructural no es confiable"
        )

    # 4) Similitud de texto libre: solo advierte, no bloquea.
    for existente in catalogo:
        if existente.get("Category") != nuevo.get("Category"):
            continue
        similitud = similitud_descripcion(nuevo.get("Description", ""), existente["Description"])
        if similitud >= umbral_similitud:
            resultado.advertencias.append(
                f"Descripción {similitud:.0%} similar a {existente['ItemCode']} "
                f"('{existente['Description']}')"
            )
    return resultado
