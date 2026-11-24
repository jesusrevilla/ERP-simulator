"""Fase 2 - Validación de reglas de integridad del maestro de artículos.

Reglas de negocio (ListPrice >= StandardCost, UnitOfMeasure válida, SafetyStock > 0
en críticos) y validación de atributos técnicos como un problema de satisfacción
de restricciones (CSP): consistencia de nodo + AC-3.

Las restricciones por categoría son reglas de ejemplo para esta demostración.
"""
from __future__ import annotations

from collections import deque
from typing import Callable, Optional

from fase1_deduplicacion import normalizar_capacidad

TIPOS_ITEM_VALIDOS = {"Componente", "Producto Terminado", "Materia Prima"}
UNIDADES_VALIDAS = {"PZA", "KG", "LT", "M", "CAJA"}

# Dominios de las variables (tipo, capacidad) por categoría.
DOMINIOS = {
    "RAM": {"tipo": {"DDR4", "DDR5"}, "capacidad": {"8GB", "16GB", "32GB", "64GB"}},
    "SSD": {"tipo": {"NVMe", "SATA"}, "capacidad": {"256GB", "512GB", "1TB", "2TB", "4TB"}},
    "CPU": {"tipo": {"AM4", "AM5"}, "capacidad": {"6N", "8N", "12N", "16N"}},
    "Motherboard": {"tipo": {"B550", "B650", "X670"}, "capacidad": {"ATX", "mATX", "ITX"}},
    "PSU": {"tipo": {"80+ Bronze", "80+ Gold"}, "capacidad": {"650W", "750W", "850W"}},
    "GPU": {"tipo": {"GDDR6", "GDDR6X"}, "capacidad": {"8GB", "12GB", "16GB"}},
}

# Restricción binaria entre tipo y capacidad: True si la combinación es válida.
RESTRICCIONES_TIPO_CAPACIDAD: dict = {
    "RAM": lambda tipo, cap: not (tipo == "DDR4" and cap == "64GB"),
    "SSD": lambda tipo, cap: not (tipo == "SATA" and cap == "4TB"),
}


def _canonico(valor: Optional[str], dominio: set) -> Optional[str]:
    """Devuelve el valor del dominio que coincide sin importar mayúsculas."""
    if valor is None:
        return None
    buscado = normalizar_capacidad(str(valor))
    for candidato in dominio:
        if normalizar_capacidad(candidato) == buscado:
            return candidato
    return None


def ac3(dominios: dict, arcos: dict) -> bool:
    """Algoritmo AC-3. Poda los dominios en sitio.

    dominios: {variable: conjunto de valores}
    arcos: {(xi, xj): predicado(vi, vj)} con True si el par es compatible.
    Devuelve False si algún dominio queda vacío (CSP inconsistente).
    """
    cola = deque(arcos.keys())
    while cola:
        xi, xj = cola.popleft()
        if _revisar(dominios, arcos, xi, xj):
            if not dominios[xi]:
                return False
            for (xk, xl) in arcos:
                if xl == xi and xk != xj:
                    cola.append((xk, xl))
    return True


def _revisar(dominios: dict, arcos: dict, xi: str, xj: str) -> bool:
    """Elimina de D(xi) los valores sin apoyo en D(xj). True si hubo cambios."""
    predicado: Callable = arcos[(xi, xj)]
    cambio = False
    for vi in list(dominios[xi]):
        if not any(predicado(vi, vj) for vj in dominios[xj]):
            dominios[xi].discard(vi)
            cambio = True
    return cambio


def validar_atributos_csp(item: dict) -> tuple:
    """Valida tipo y capacidad con consistencia de nodo + AC-3.

    Devuelve (errores, dominios_finales).
    """
    errores: list = []
    categoria = item.get("Category")
    attrs = item.get("atributosTecnicos") or {}

    for campo in ("marca", "modelo"):
        if not str(attrs.get(campo) or "").strip():
            errores.append(f"atributosTecnicos.{campo} es obligatorio")

    if categoria not in DOMINIOS:
        return errores, {}

    base = DOMINIOS[categoria]
    dominios = {}
    # Consistencia de nodo: cada valor asignado debe pertenecer a su dominio.
    for variable in ("tipo", "capacidad"):
        valor = attrs.get(variable)
        if valor in (None, ""):
            dominios[variable] = set(base[variable])
            continue
        canonico = _canonico(valor, base[variable])
        if canonico is None:
            errores.append(
                f"{variable} '{valor}' fuera del dominio de {categoria}: {sorted(base[variable])}"
            )
            return errores, dominios
        dominios[variable] = {canonico}

    # Consistencia de arco entre tipo y capacidad.
    permitido = RESTRICCIONES_TIPO_CAPACIDAD.get(categoria, lambda t, c: True)
    arcos = {
        ("tipo", "capacidad"): lambda t, c: permitido(t, c),
        ("capacidad", "tipo"): lambda c, t: permitido(t, c),
    }
    if not ac3(dominios, arcos):
        errores.append(
            f"Combinación inválida en {categoria}: tipo '{attrs.get('tipo')}' "
            f"con capacidad '{attrs.get('capacidad')}' (AC-3 vació un dominio)"
        )
    return errores, dominios


def validar_integridad(item: dict) -> list:
    """Devuelve la lista de violaciones de integridad (vacía si el artículo es válido)."""
    errores: list = []

    if item.get("ItemType") not in TIPOS_ITEM_VALIDOS:
        errores.append(f"ItemType '{item.get('ItemType')}' no es válido: {sorted(TIPOS_ITEM_VALIDOS)}")

    if item.get("UnitOfMeasure") not in UNIDADES_VALIDAS:
        errores.append(
            f"UnitOfMeasure '{item.get('UnitOfMeasure')}' no es válida: {sorted(UNIDADES_VALIDAS)}"
        )

    precio, costo = item.get("ListPrice"), item.get("StandardCost")
    if not isinstance(precio, (int, float)) or not isinstance(costo, (int, float)) or precio < 0 or costo < 0:
        errores.append("ListPrice y StandardCost deben ser números no negativos")
    elif precio < costo:
        errores.append(f"ListPrice ({precio}) menor que StandardCost ({costo})")

    safety = item.get("SafetyStock")
    if not isinstance(safety, (int, float)) or safety < 0:
        errores.append("SafetyStock debe ser un número no negativo")
    elif item.get("EsCritico") and safety <= 0:
        errores.append("SafetyStock debe ser mayor que 0 en componentes críticos")

    errores_csp, _ = validar_atributos_csp(item)
    errores.extend(errores_csp)
    return errores
