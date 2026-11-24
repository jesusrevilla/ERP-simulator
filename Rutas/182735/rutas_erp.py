"""Reglas de negocio del trazado de rutas en ERP (Rutas.md).

Cada función indica el nodo del diagrama que implementa (B1, C2, E1a, ...).
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date, timedelta
from math import ceil

MINUTOS_POR_DIA = 480


class ReglaDeRutaError(ValueError):
    """Se violó una regla de negocio del trazado de rutas."""


@dataclass
class Etapa:
    secuencia: int
    codigo: str
    materiales: dict[str, float]
    run_time_min: float
    dias_espera: int = 0


@dataclass
class Ruta:
    codigo: str
    etapas: list[Etapa] = field(default_factory=list)

    @property
    def total_run_time(self) -> float:
        return sum(e.run_time_min for e in self.etapas)

    def agregar_etapa(self, etapa: Etapa) -> None:
        if any(e.secuencia == etapa.secuencia for e in self.etapas):
            raise ReglaDeRutaError(f"La secuencia {etapa.secuencia} ya existe en la ruta")
        self.etapas.append(etapa)
        self.etapas.sort(key=lambda e: e.secuencia)

    def buscar_etapa(self, secuencia: int) -> Etapa | None:
        return next((e for e in self.etapas if e.secuencia == secuencia), None)


@dataclass
class Linea:
    secuencia: int | None
    material: str
    planificada: float
    costo_unitario: float
    despachada: float = 0.0


@dataclass
class EtapaOrden:
    secuencia: int
    codigo: str
    almacen: str
    fecha_inicio: date
    fecha_fin: date


@dataclass
class Orden:
    folio: str
    material: str
    cantidad: float
    almacen: str
    fecha_inicio: date
    fecha_fin: date
    ruta: Ruta
    etapas: list[EtapaOrden]
    lineas: list[Linea]
    estatus: str = "PLANIFICADA"

    @property
    def costo_planificado(self) -> float:
        return sum(l.planificada * l.costo_unitario for l in self.lineas)

    @property
    def costo_real(self) -> float:
        return sum(l.despachada * l.costo_unitario for l in self.lineas)


class Inventario:
    def __init__(self, existencias: dict[tuple[str, str], float]):
        self.existencias = dict(existencias)

    def cantidad(self, material: str, almacen: str) -> float:
        return self.existencias.get((material, almacen), 0.0)

    def descontar(self, material: str, almacen: str, cantidad: float) -> None:
        if self.cantidad(material, almacen) < cantidad:
            raise ReglaDeRutaError(f"Existencia insuficiente de {material} en {almacen}")
        self.existencias[(material, almacen)] -= cantidad


# --- 2. Reglas de negocio -------------------------------------------------

def validar_secuencia(etapas: list[Etapa]) -> None:
    """C1: la secuencia usa números enteros y correlativos."""
    secuencias = [e.secuencia for e in etapas]
    if any(not isinstance(s, int) or isinstance(s, bool) for s in secuencias):
        raise ReglaDeRutaError("La secuencia debe usar números enteros")
    if sorted(secuencias) != list(range(1, len(secuencias) + 1)):
        raise ReglaDeRutaError("La secuencia debe ser correlativa, empezando en 1")


def insertar_etapa(ruta: Ruta, etapa: Etapa) -> None:
    """D3: al insertar una secuencia intermedia se reenumeran las siguientes."""
    if etapa.secuencia < 1 or etapa.secuencia > len(ruta.etapas) + 1:
        raise ReglaDeRutaError("La secuencia a insertar queda fuera del rango de la ruta")
    for existente in ruta.etapas:
        if existente.secuencia >= etapa.secuencia:
            existente.secuencia += 1
    ruta.agregar_etapa(etapa)


def programar_fechas(fecha_inicio: date, etapas: list[Etapa]) -> list[tuple[date, date]]:
    """B3 y B4: fechas por Run Time (jornada de MINUTOS_POR_DIA) y días de espera."""
    fechas = []
    inicio = fecha_inicio
    for etapa in sorted(etapas, key=lambda e: e.secuencia):
        dias = max(1, ceil(etapa.run_time_min / MINUTOS_POR_DIA))
        fin = inicio + timedelta(days=dias - 1)
        fechas.append((inicio, fin))
        inicio = fin + timedelta(days=1 + etapa.dias_espera)
    return fechas


def crear_orden(
    ruta: Ruta,
    folio: str,
    material: str,
    cantidad: float,
    almacen: str,
    fecha_inicio: date,
    fecha_fin: date,
    costos: dict[str, float],
) -> Orden:
    """C1 y C2; F3: la orden recibe una copia de la ruta."""
    validar_secuencia(ruta.etapas)
    ruta_copia = deepcopy(ruta)
    fechas = programar_fechas(fecha_inicio, ruta_copia.etapas)
    if fechas[-1][1] > fecha_fin:
        raise ReglaDeRutaError("Las fechas de las etapas exceden el horizonte de la orden")
    etapas = [
        EtapaOrden(e.secuencia, e.codigo, almacen, ini, fin)
        for e, (ini, fin) in zip(ruta_copia.etapas, fechas)
    ]
    lineas = [
        Linea(e.secuencia, mat, qty * cantidad, costos[mat])
        for e in ruta_copia.etapas
        for mat, qty in e.materiales.items()
    ]
    return Orden(folio, material, cantidad, almacen, fecha_inicio, fecha_fin, ruta_copia, etapas, lineas)


def liberar_orden(orden: Orden) -> None:
    """E1: crear y liberar una orden."""
    orden.estatus = "LIBERADA"


# --- 4. Despacho de inventario (Issue for Production) -----------------------

def lineas_para_despacho(orden: Orden, secuencia: int) -> list[Linea]:
    """E1a: el filtro de una etapa solo muestra sus propias líneas."""
    return [l for l in orden.lineas if l.secuencia == secuencia]


def _etapa(orden: Orden, secuencia: int) -> EtapaOrden:
    etapa = next((e for e in orden.etapas if e.secuencia == secuencia), None)
    if etapa is None:
        raise ReglaDeRutaError(f"La etapa {secuencia} no pertenece a la orden")
    return etapa


def _etapa_despachada(orden: Orden, secuencia: int) -> bool:
    return all(l.despachada >= l.planificada for l in lineas_para_despacho(orden, secuencia))


def emitir_para_produccion(
    orden: Orden, inventario: Inventario, secuencia: int, material: str, cantidad: float
) -> None:
    """C3 y E1b: exige despacho previo completo y descuenta el inventario."""
    if orden.estatus != "LIBERADA":
        raise ReglaDeRutaError("La orden no está liberada")
    etapa = _etapa(orden, secuencia)
    if not all(_etapa_despachada(orden, e.secuencia) for e in orden.etapas if e.secuencia < secuencia):
        raise ReglaDeRutaError("Falta completar el despacho de una etapa anterior")
    linea = next((l for l in lineas_para_despacho(orden, secuencia) if l.material == material), None)
    if linea is None:
        raise ReglaDeRutaError(f"{material} no pertenece a la etapa {secuencia}")
    if linea.despachada + cantidad > linea.planificada:
        raise ReglaDeRutaError("No se puede despachar más de lo planificado")
    inventario.descontar(material, etapa.almacen, cantidad)
    linea.despachada += cantidad


def cambiar_almacen(orden: Orden, secuencia: int, nuevo_almacen: str) -> None:
    """E2: el almacén solo cambia después de completar la Etapa 1."""
    if secuencia < 2 or not _etapa_despachada(orden, 1):
        raise ReglaDeRutaError("El almacén solo puede cambiar después de completar la Etapa 1")
    _etapa(orden, secuencia).almacen = nuevo_almacen


def auditar_costos(orden: Orden) -> dict[str, float]:
    """E1c: compara el costo planificado contra el real."""
    return {
        "planificado": orden.costo_planificado,
        "real": orden.costo_real,
        "diferencia": orden.costo_real - orden.costo_planificado,
    }


def finalizar_orden(orden: Orden) -> dict[str, float]:
    if not all(_etapa_despachada(orden, e.secuencia) for e in orden.etapas):
        raise ReglaDeRutaError("No se puede finalizar con despachos pendientes")
    orden.estatus = "CERRADA"
    return auditar_costos(orden)


# --- 5. Integridad de los datos -------------------------------------------

def lineas_huerfanas(orden: Orden) -> list[Linea]:
    """F1: líneas sin etapa o con una etapa que no existe."""
    validas = {e.secuencia for e in orden.etapas}
    return [l for l in orden.lineas if l.secuencia is None or l.secuencia not in validas]


def borrar_etapa(orden: Orden, secuencia: int) -> None:
    """F2: no se borra una etapa con movimientos en una orden Liberada."""
    _etapa(orden, secuencia)
    movimientos = any(l.despachada > 0 for l in lineas_para_despacho(orden, secuencia))
    if orden.estatus == "LIBERADA" and movimientos:
        raise ReglaDeRutaError("No se puede borrar una etapa con movimientos en una orden liberada")
    orden.etapas = [e for e in orden.etapas if e.secuencia != secuencia]
    orden.lineas = [l for l in orden.lineas if l.secuencia != secuencia]
