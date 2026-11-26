"""Simulación del proceso de gestión de componentes descontinuados en la BOM.

Matrícula: 181914 — Issue #239.

El módulo modela, en memoria y sin dependencias externas, el proceso TO-BE
documentado en esta carpeta:

1. Registro de la descontinuación de un componente (ciclo de vida).
2. Detección automática de las BOM afectadas, incluidas las multinivel.
3. Generación y priorización de la alerta (existencias, órdenes, demanda).
4. Evaluación de sustitutos por el agente inteligente (compatibilidad
   técnica como filtro y puntuación ponderada como ranking).
5. Autorización del responsable técnico.
6. Aplicación de la sustitución mediante una nueva revisión de la BOM,
   con historial y evaluación previa de las órdenes de fabricación.
7. Recálculo del MRP sin recomendaciones ordinarias de compra de
   componentes descontinuados.
8. Cálculo de los KPIs del proceso.

Ejecutar ``python gestor_descontinuados.py`` imprime la evidencia del
escenario hipotético de la tarjeta madre descontinuada.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Catálogos
# ---------------------------------------------------------------------------

ACTIVO = "ACTIVO"
PROXIMO_A_DESCONTINUAR = "PROXIMO_A_DESCONTINUAR"  # NRND / EOL anunciado
DESCONTINUADO = "DESCONTINUADO"
ESTADOS_CICLO_VIDA = (ACTIVO, PROXIMO_A_DESCONTINUAR, DESCONTINUADO)

# Transiciones permitidas del ciclo de vida (RN-01).
TRANSICIONES = {
    ACTIVO: {PROXIMO_A_DESCONTINUAR, DESCONTINUADO},
    PROXIMO_A_DESCONTINUAR: {ACTIVO, DESCONTINUADO},
    DESCONTINUADO: set(),
}

ROL_RESPONSABLE_TECNICO = "RESPONSABLE_TECNICO"
ROL_RESPONSABLE_BOM = "RESPONSABLE_BOM"

# Estados de órdenes de fabricación y su tratamiento (RN-07).
ORDENES_CONGELADAS = {"LIBERADA", "EN_PROCESO"}
ORDENES_REPLANIFICABLES = {"PLANIFICADA"}
ORDENES_CERRADAS = {"TERMINADA", "CANCELADA"}

# Criterios técnicos por categoría: tipo de regla por especificación (RN-05).
#   "igual"  -> el sustituto debe tener exactamente el mismo valor.
#   "minimo" -> el sustituto debe igualar o superar el valor del original.
CRITERIOS_COMPATIBILIDAD = {
    "TARJETA_MADRE": {
        "socket": "igual",
        "tipo_memoria": "igual",
        "form_factor": "igual",
        "pcie_gen": "minimo",
        "ranuras_m2": "minimo",
    },
    "MEMORIA_RAM": {"tipo_memoria": "igual", "capacidad_gb": "igual", "velocidad_mhz": "minimo"},
    "FUENTE_PODER": {"form_factor": "igual", "potencia_w": "minimo", "certificacion_nivel": "minimo"},
    "PROCESADOR": {"socket": "igual", "nucleos": "minimo", "tdp_w": "igual"},
}

# Pesos del modelo de recomendación (suman 1.0).
PESOS = {
    "inventario": 0.25,
    "proveedor": 0.20,
    "costo": 0.20,
    "tiempo_entrega": 0.15,
    "ciclo_vida": 0.10,
    "impacto": 0.10,
}


class ErrorDeProceso(Exception):
    """Violación de una regla de negocio del proceso."""


# ---------------------------------------------------------------------------
# Entidades
# ---------------------------------------------------------------------------


@dataclass
class Componente:
    sku: str
    descripcion: str
    categoria: str
    especificaciones: dict
    costo: float
    tiempo_entrega_dias: int
    existencias: int
    disponible_proveedor: bool
    estado: str = ACTIVO
    uso_stock_autorizado: bool = False
    fecha_descontinuacion: datetime | None = None
    es_fabricado: bool = False


@dataclass
class LineaBOM:
    component_sku: str
    cantidad: float


@dataclass
class BOM:
    bom_id: str
    parent_sku: str
    version: str
    lineas: list[LineaBOM]
    estado: str = "ACTIVO"  # BORRADOR | ACTIVO | OBSOLETO


@dataclass
class OrdenFabricacion:
    codigo: str
    sku: str
    cantidad: int
    estado: str
    bom_id: str


@dataclass
class Alerta:
    sku: str
    fecha_registro: datetime
    fecha_alerta: datetime
    boms_afectadas: list[dict]
    ordenes_afectadas: list[str]
    existencias: int
    demanda_abierta: float
    cobertura: float
    prioridad: str
    estado: str = "ABIERTA"


@dataclass
class Recomendacion:
    sku_original: str
    sku_sustituto: str
    puntuacion: float
    detalle: dict
    justificacion: str


@dataclass
class Autorizacion:
    sku_original: str
    sku_sustituto: str
    usuario: str
    rol: str
    fecha: datetime
    decision: str  # APROBADA | RECHAZADA
    comentario: str = ""


@dataclass
class ERP:
    """Estado mínimo del ERP necesario para el proceso."""

    componentes: dict[str, Componente]
    boms: dict[str, BOM]
    ordenes: list[OrdenFabricacion] = field(default_factory=list)
    alertas: list[Alerta] = field(default_factory=list)
    autorizaciones: list[Autorizacion] = field(default_factory=list)
    historial: list[dict] = field(default_factory=list)
    eventos: list[dict] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------

    def _evento(self, tipo: str, fecha: datetime, **payload) -> None:
        self.eventos.append({"eventType": tipo, "eventTimestamp": fecha.isoformat(), **payload})

    def boms_activas(self) -> list[BOM]:
        return [b for b in self.boms.values() if b.estado == "ACTIVO"]

    def bom_activa_de(self, sku: str) -> BOM | None:
        for bom in self.boms_activas():
            if bom.parent_sku == sku:
                return bom
        return None

    # ------------------------------------------------------------------
    # 1. Ciclo de vida
    # ------------------------------------------------------------------

    def cambiar_estado(self, sku: str, nuevo_estado: str, fecha: datetime,
                       usuario: str, autorizar_uso_stock: bool = True) -> Alerta | None:
        """Cambia el estado de ciclo de vida y, si procede, genera la alerta."""
        if nuevo_estado not in ESTADOS_CICLO_VIDA:
            raise ErrorDeProceso(f"Estado de ciclo de vida inválido: {nuevo_estado}")
        comp = self.componentes[sku]
        if nuevo_estado not in TRANSICIONES[comp.estado]:
            raise ErrorDeProceso(f"Transición no permitida: {comp.estado} -> {nuevo_estado}")
        anterior = comp.estado
        comp.estado = nuevo_estado
        if nuevo_estado == DESCONTINUADO:
            comp.fecha_descontinuacion = fecha
            comp.uso_stock_autorizado = autorizar_uso_stock
            comp.disponible_proveedor = False
        self.historial.append({
            "tipo": "CAMBIO_CICLO_VIDA", "sku": sku, "anterior": anterior,
            "nuevo": nuevo_estado, "usuario": usuario, "fecha": fecha,
        })
        self._evento("Component.LifecycleChanged", fecha, sku=sku, anterior=anterior, nuevo=nuevo_estado)
        if nuevo_estado in (DESCONTINUADO, PROXIMO_A_DESCONTINUAR):
            return self.generar_alerta(sku, fecha)
        return None

    # ------------------------------------------------------------------
    # 2. Detección de BOM afectadas (where-used multinivel)
    # ------------------------------------------------------------------

    def boms_afectadas(self, sku: str) -> list[dict]:
        """Devuelve todas las BOM activas que usan ``sku`` directa o indirectamente.

        Cada resultado incluye el nivel (1 = uso directo) y la ruta desde la
        BOM hasta el componente. Se protege contra ciclos.
        """
        resultado: list[dict] = []
        visitados: set[tuple[str, str]] = set()
        # Pila de (sku buscado, nivel, ruta acumulada desde el componente).
        pendientes = [(sku, 1, [sku])]
        while pendientes:
            buscado, nivel, ruta = pendientes.pop(0)
            for bom in self.boms_activas():
                if not any(l.component_sku == buscado for l in bom.lineas):
                    continue
                clave = (bom.bom_id, buscado)
                if clave in visitados or bom.parent_sku in ruta:
                    continue
                visitados.add(clave)
                nueva_ruta = [bom.parent_sku] + ruta
                resultado.append({
                    "bom_id": bom.bom_id, "parent_sku": bom.parent_sku,
                    "nivel": nivel, "ruta": " > ".join(nueva_ruta),
                })
                pendientes.append((bom.parent_sku, nivel + 1, nueva_ruta))
        return resultado

    def requerimiento_por_unidad(self, padre: str, sku: str) -> float:
        """Cantidad de ``sku`` necesaria para fabricar una unidad de ``padre``."""
        bom = self.bom_activa_de(padre)
        if bom is None:
            return 0.0
        total = 0.0
        for linea in bom.lineas:
            if linea.component_sku == sku:
                total += linea.cantidad
            else:
                total += linea.cantidad * self.requerimiento_por_unidad(linea.component_sku, sku)
        return total

    # ------------------------------------------------------------------
    # 3. Alerta y priorización
    # ------------------------------------------------------------------

    def ordenes_abiertas_afectadas(self, sku: str) -> list[OrdenFabricacion]:
        afectadas = []
        for orden in self.ordenes:
            if orden.estado in ORDENES_CERRADAS:
                continue
            if self.requerimiento_por_unidad(orden.sku, sku) > 0:
                afectadas.append(orden)
        return afectadas

    def generar_alerta(self, sku: str, fecha: datetime) -> Alerta:
        comp = self.componentes[sku]
        boms = self.boms_afectadas(sku)
        ordenes = self.ordenes_abiertas_afectadas(sku)
        demanda = sum(o.cantidad * self.requerimiento_por_unidad(o.sku, sku) for o in ordenes)
        cobertura = 1.0 if demanda == 0 else min(comp.existencias / demanda, 1.0)
        prioridad = self.priorizar(len(boms), len(ordenes), cobertura, comp.estado)
        alerta = Alerta(
            sku=sku,
            fecha_registro=comp.fecha_descontinuacion or fecha,
            fecha_alerta=fecha,
            boms_afectadas=boms,
            ordenes_afectadas=[o.codigo for o in ordenes],
            existencias=comp.existencias,
            demanda_abierta=demanda,
            cobertura=round(cobertura, 4),
            prioridad=prioridad,
        )
        self.alertas.append(alerta)
        self._evento("BOM.DiscontinuedComponentAlert", fecha, sku=sku, prioridad=prioridad,
                     boms=[b["bom_id"] for b in boms], ordenes=alerta.ordenes_afectadas)
        return alerta

    @staticmethod
    def priorizar(num_boms: int, num_ordenes: int, cobertura: float, estado: str) -> str:
        """Prioriza la alerta según el impacto en producción (RN-10)."""
        if num_boms == 0:
            return "BAJA"
        if estado == DESCONTINUADO and num_ordenes > 0 and cobertura < 1.0:
            return "CRITICA"
        if num_ordenes > 0 or (estado == DESCONTINUADO and num_boms >= 3):
            return "ALTA"
        return "MEDIA"

    # ------------------------------------------------------------------
    # 4. Agente de recomendación
    # ------------------------------------------------------------------

    @staticmethod
    def es_compatible(original: Componente, candidato: Componente) -> tuple[bool, list[str]]:
        """Filtro duro de compatibilidad técnica. Devuelve (ok, motivos de rechazo)."""
        if candidato.sku == original.sku:
            return False, ["Es el mismo componente"]
        if candidato.categoria != original.categoria:
            return False, ["Categoría distinta"]
        if candidato.estado == DESCONTINUADO:
            return False, ["El candidato también está descontinuado"]
        motivos = []
        criterios = CRITERIOS_COMPATIBILIDAD.get(original.categoria, {})
        for atributo, regla in criterios.items():
            requerido = original.especificaciones.get(atributo)
            ofrecido = candidato.especificaciones.get(atributo)
            if ofrecido is None:
                motivos.append(f"{atributo}: sin dato")
            elif regla == "igual" and ofrecido != requerido:
                motivos.append(f"{atributo}: {ofrecido} != {requerido}")
            elif regla == "minimo" and ofrecido < requerido:
                motivos.append(f"{atributo}: {ofrecido} < {requerido}")
        return (not motivos), motivos

    def recomendar_sustitutos(self, sku: str, top: int = 3) -> tuple[list[Recomendacion], dict]:
        """Ranking de sustitutos compatibles y motivos de descarte de los demás."""
        original = self.componentes[sku]
        alerta = next((a for a in reversed(self.alertas) if a.sku == sku), None)
        demanda = alerta.demanda_abierta if alerta else 0.0
        faltante = max(demanda - original.existencias, 0)
        num_boms = len(self.boms_afectadas(sku))

        descartados: dict[str, list[str]] = {}
        candidatos = []
        for cand in self.componentes.values():
            if cand.categoria != original.categoria or cand.sku == sku:
                continue
            ok, motivos = self.es_compatible(original, cand)
            if ok:
                candidatos.append(cand)
            else:
                descartados[cand.sku] = motivos

        recomendaciones = []
        for cand in candidatos:
            s_inv = 1.0 if faltante == 0 else min(cand.existencias / faltante, 1.0)
            s_prov = 1.0 if cand.disponible_proveedor else 0.0
            delta = (cand.costo - original.costo) / original.costo
            s_costo = max(0.0, min(1.0, 1.0 - delta))  # +100 % de costo => 0
            s_lt = max(0.0, 1.0 - cand.tiempo_entrega_dias / 30)
            s_ciclo = 1.0 if cand.estado == ACTIVO else 0.3
            # Impacto: diferencias de especificación que obligan a revalidar BOM.
            difs = sum(1 for k, v in original.especificaciones.items()
                       if cand.especificaciones.get(k) != v)
            s_imp = max(0.0, 1.0 - 0.2 * difs)
            detalle = {
                "inventario": round(s_inv, 3), "proveedor": s_prov, "costo": round(s_costo, 3),
                "tiempo_entrega": round(s_lt, 3), "ciclo_vida": s_ciclo, "impacto": round(s_imp, 3),
            }
            puntuacion = round(sum(PESOS[k] * v for k, v in detalle.items()), 4)
            justificacion = (
                f"{cand.sku} cumple los criterios técnicos de {original.categoria}; "
                f"existencias {cand.existencias} para un faltante de {faltante:g}; "
                f"costo {delta:+.1%} vs original; entrega {cand.tiempo_entrega_dias} días; "
                f"estado {cand.estado}; afecta {num_boms} BOM."
            )
            recomendaciones.append(Recomendacion(sku, cand.sku, puntuacion, detalle, justificacion))

        recomendaciones.sort(key=lambda r: r.puntuacion, reverse=True)
        return recomendaciones[:top], descartados

    # ------------------------------------------------------------------
    # 5. Autorización
    # ------------------------------------------------------------------

    def autorizar(self, recomendacion: Recomendacion, usuario: str, rol: str,
                  fecha: datetime, aprobar: bool = True, comentario: str = "") -> Autorizacion:
        if rol != ROL_RESPONSABLE_TECNICO:
            raise ErrorDeProceso("Solo el responsable técnico puede autorizar sustituciones")
        ok, motivos = self.es_compatible(self.componentes[recomendacion.sku_original],
                                         self.componentes[recomendacion.sku_sustituto])
        if aprobar and not ok:
            raise ErrorDeProceso(f"Sustituto incompatible: {motivos}")
        aut = Autorizacion(recomendacion.sku_original, recomendacion.sku_sustituto, usuario, rol,
                           fecha, "APROBADA" if aprobar else "RECHAZADA", comentario)
        self.autorizaciones.append(aut)
        self._evento("BOM.SubstitutionDecision", fecha, original=aut.sku_original,
                     sustituto=aut.sku_sustituto, decision=aut.decision, usuario=usuario)
        return aut

    # ------------------------------------------------------------------
    # 6. Aplicación de la sustitución
    # ------------------------------------------------------------------

    def aplicar_sustitucion(self, autorizacion: Autorizacion, usuario: str, fecha: datetime) -> dict:
        """Crea nuevas revisiones de las BOM con uso directo del componente.

        Las versiones anteriores se marcan OBSOLETO (no se editan, RN-08).
        Las órdenes LIBERADA/EN_PROCESO conservan su versión; las PLANIFICADA
        se replanifican con la nueva revisión (RN-07). Las BOM de niveles
        superiores no se modifican: al explotarse toman la nueva revisión
        vigente del subensamble.
        """
        if autorizacion not in self.autorizaciones or autorizacion.decision != "APROBADA":
            raise ErrorDeProceso("No existe una autorización aprobada para la sustitución")
        original, sustituto = autorizacion.sku_original, autorizacion.sku_sustituto
        directas = [b for b in self.boms_afectadas(original) if b["nivel"] == 1]
        nuevas, ordenes_reasignadas, ordenes_conservadas = [], [], []
        # Evaluación previa de órdenes en todos los niveles (RN-07).
        for orden in self.ordenes_abiertas_afectadas(original):
            if orden.estado in ORDENES_CONGELADAS:
                ordenes_conservadas.append(orden.codigo)
            elif orden.estado in ORDENES_REPLANIFICABLES:
                ordenes_reasignadas.append(orden.codigo)
        for afectada in directas:
            anterior = self.boms[afectada["bom_id"]]
            numero = int(anterior.version.lstrip("v")) + 1
            nueva = BOM(
                bom_id=f"{anterior.parent_sku}-v{numero}",
                parent_sku=anterior.parent_sku,
                version=f"v{numero}",
                lineas=[LineaBOM(sustituto if l.component_sku == original else l.component_sku,
                                 l.cantidad) for l in anterior.lineas],
            )
            anterior.estado = "OBSOLETO"
            self.boms[nueva.bom_id] = nueva
            nuevas.append(nueva.bom_id)
            # Las órdenes planificadas que usan directamente la BOM pasan a la nueva
            # revisión; las de niveles superiores la toman al reexplotar el
            # subensamble. Las congeladas conservan su versión (snapshot).
            for orden in self.ordenes:
                if orden.bom_id == anterior.bom_id and orden.estado in ORDENES_REPLANIFICABLES:
                    orden.bom_id = nueva.bom_id
            self.historial.append({
                "tipo": "SUSTITUCION", "bom_anterior": anterior.bom_id, "bom_nueva": nueva.bom_id,
                "original": original, "sustituto": sustituto, "usuario": usuario,
                "autorizado_por": autorizacion.usuario, "fecha": fecha,
            })
        for alerta in self.alertas:
            if alerta.sku == original:
                alerta.estado = "RESUELTA"
        self._evento("BOM.SubstitutionApplied", fecha, original=original, sustituto=sustituto,
                     boms_nuevas=nuevas)
        return {"boms_nuevas": nuevas, "ordenes_reasignadas": ordenes_reasignadas,
                "ordenes_conservadas": ordenes_conservadas}

    # ------------------------------------------------------------------
    # 7. MRP
    # ------------------------------------------------------------------

    def explotar(self, sku: str, cantidad: float, acumulado: dict | None = None) -> dict:
        """Necesidades brutas de componentes comprados (explosión multinivel)."""
        acumulado = {} if acumulado is None else acumulado
        bom = self.bom_activa_de(sku)
        for linea in bom.lineas if bom else []:
            requerido = cantidad * linea.cantidad
            hijo = self.componentes.get(linea.component_sku)
            if hijo is not None and hijo.es_fabricado:
                self.explotar(hijo.sku, requerido, acumulado)
            else:
                acumulado[linea.component_sku] = acumulado.get(linea.component_sku, 0) + requerido
        return acumulado

    def mrp(self, demanda: dict[str, int], aplicar_reglas: bool = True) -> dict:
        """Calcula recomendaciones de compra.

        Con ``aplicar_reglas=False`` reproduce el comportamiento AS-IS: el MRP
        ignora el ciclo de vida y recomienda comprar componentes descontinuados.
        """
        brutas: dict[str, float] = {}
        for sku, cantidad in demanda.items():
            self.explotar(sku, cantidad, brutas)
        compras, consumo_stock, faltantes_bloqueados = [], {}, {}
        # Política "hasta agotar existencias" (RN-03): si el sustituto reemplazó a
        # un descontinuado con stock autorizado, se consume primero ese stock.
        sustituido_por = {h["sustituto"]: h["original"] for h in self.historial
                          if h["tipo"] == "SUSTITUCION"} if aplicar_reglas else {}
        for sku, requerido in brutas.items():
            comp = self.componentes[sku]
            original = self.componentes.get(sustituido_por.get(sku, ""))
            if original is not None and original.uso_stock_autorizado and original.existencias > 0:
                usado = min(original.existencias, math.ceil(requerido))
                consumo_stock[original.sku] = consumo_stock.get(original.sku, 0) + usado
                requerido -= usado
            neto = max(math.ceil(requerido) - comp.existencias, 0)
            if comp.estado == DESCONTINUADO and aplicar_reglas:
                consumo_stock[sku] = min(comp.existencias, math.ceil(requerido)) if comp.uso_stock_autorizado else 0
                if not comp.uso_stock_autorizado:
                    neto = math.ceil(requerido)
                if neto > 0:
                    faltantes_bloqueados[sku] = neto
                continue
            if neto > 0:
                compras.append({"sku": sku, "cantidad": neto, "estado_componente": comp.estado})
        return {"necesidades_brutas": brutas, "compras": compras,
                "consumo_stock_descontinuado": consumo_stock,
                "faltantes_bloqueados": faltantes_bloqueados}

    # ------------------------------------------------------------------
    # 8. KPIs
    # ------------------------------------------------------------------

    def kpis(self, resultado_mrp: dict, ordenes_retrasadas: list[str]) -> dict:
        alertas = self.alertas
        horas_det = [(a.fecha_alerta - a.fecha_registro).total_seconds() / 3600 for a in alertas]
        horas_sus = []
        for a in alertas:
            aut = next((x for x in self.autorizaciones
                        if x.sku_original == a.sku and x.decision == "APROBADA"), None)
            if aut:
                horas_sus.append((aut.fecha - a.fecha_alerta).total_seconds() / 3600)
        activas = self.boms_activas()
        # Una BOM está afectada si contiene un descontinuado en cualquier nivel.
        con_desc = {b["bom_id"] for c in self.componentes.values() if c.estado == DESCONTINUADO
                    for b in self.boms_afectadas(c.sku)}
        compras = resultado_mrp["compras"]
        # Se evalúa con el estado vigente: una compra emitida antes de conocer la
        # descontinuación también es inválida.
        invalidas = [c for c in compras if self.componentes[c["sku"]].estado == DESCONTINUADO]
        abiertas = [o for o in self.ordenes if o.estado not in ORDENES_CERRADAS]
        requieren = {a.sku for a in alertas if self.componentes[a.sku].estado == DESCONTINUADO
                     and a.boms_afectadas}
        con_sustituto = {x.sku_original for x in self.autorizaciones if x.decision == "APROBADA"}

        def pct(n, d):
            return round(100 * n / d, 2) if d else 0.0

        return {
            "tiempo_deteccion_h": round(sum(horas_det) / len(horas_det), 2) if horas_det else None,
            "tiempo_sustitucion_h": round(sum(horas_sus) / len(horas_sus), 2) if horas_sus else None,
            "boms_afectadas_pct": pct(len(con_desc), len(activas)),
            "recomendaciones_invalidas_pct": pct(len(invalidas), len(compras)),
            "ordenes_afectadas_pct": pct(len(set(ordenes_retrasadas)), len(abiertas)),
            "tasa_sustitucion_exitosa_pct": pct(len(requieren & con_sustituto), len(requieren)),
        }


# ---------------------------------------------------------------------------
# Escenario hipotético
# ---------------------------------------------------------------------------


def utc(texto: str) -> datetime:
    return datetime.fromisoformat(texto).replace(tzinfo=timezone.utc)


def escenario_tarjeta_madre() -> ERP:
    """Construye el escenario: la tarjeta madre MB-B550-PLUS se descontinúa."""

    def mb(sku, desc, socket, mem, ff, pcie, m2, costo, lt, stock, prov=True, estado=ACTIVO):
        return Componente(sku, desc, "TARJETA_MADRE",
                          {"socket": socket, "tipo_memoria": mem, "form_factor": ff,
                           "pcie_gen": pcie, "ranuras_m2": m2},
                          costo, lt, stock, prov, estado)

    componentes = [
        mb("MB-B550-PLUS", "Tarjeta madre B550 ATX (original)", "AM4", "DDR4", "ATX", 4, 2, 2300, 6, 12),
        mb("MB-B550-PRO", "Tarjeta madre B550 PRO ATX", "AM4", "DDR4", "ATX", 4, 2, 2450, 5, 40),
        mb("MB-X570-ELITE", "Tarjeta madre X570 ATX", "AM4", "DDR4", "ATX", 4, 3, 3600, 7, 10),
        mb("MB-B550-LEGACY", "Tarjeta madre B550 ATX (EOL anunciado)", "AM4", "DDR4", "ATX", 4, 2,
           2200, 10, 60, estado=PROXIMO_A_DESCONTINUAR),
        mb("MB-A520M-LITE", "Tarjeta madre A520 mATX", "AM4", "DDR4", "mATX", 3, 1, 1500, 4, 80),
        mb("MB-B650-AURA", "Tarjeta madre B650 ATX (AM5)", "AM5", "DDR5", "ATX", 4, 2, 3100, 5, 25),
        Componente("CPU-R5-5600", "Procesador Ryzen 5 5600", "PROCESADOR",
                   {"socket": "AM4", "nucleos": 6, "tdp_w": 65}, 2600, 4, 100, True),
        Componente("CPU-R7-5700X", "Procesador Ryzen 7 5700X", "PROCESADOR",
                   {"socket": "AM4", "nucleos": 8, "tdp_w": 65}, 3900, 4, 100, True),
        Componente("RAM-16-DDR4", "Memoria 16 GB DDR4 3200", "MEMORIA_RAM",
                   {"tipo_memoria": "DDR4", "capacidad_gb": 16, "velocidad_mhz": 3200}, 700, 3, 50, True),
        Componente("SSD-1TB", "Unidad SSD NVMe 1 TB", "ALMACENAMIENTO", {}, 1100, 3, 20, True),
        Componente("PSU-650-B", "Fuente 650 W 80+ Bronze", "FUENTE_PODER",
                   {"form_factor": "ATX", "potencia_w": 650, "certificacion_nivel": 1}, 1200, 5, 15, True),
        Componente("GAB-ATX", "Gabinete ATX", "GABINETE", {}, 900, 4, 40, True),
        Componente("GPU-RTX-4060", "Tarjeta gráfica RTX 4060", "GPU", {}, 6500, 7, 5, True),
        Componente("ENS-BASE-AM4", "Subensamble base AM4 (placa + CPU)", "SUBENSAMBLE", {},
                   0, 1, 0, False, es_fabricado=True),
        Componente("PC-OFI-100", "PC de oficina", "PRODUCTO", {}, 0, 2, 0, False, es_fabricado=True),
        Componente("PC-GAM-200", "PC gamer", "PRODUCTO", {}, 0, 2, 0, False, es_fabricado=True),
        Componente("PC-WS-300", "Estación de trabajo", "PRODUCTO", {}, 0, 3, 0, False, es_fabricado=True),
        Componente("PC-MINI-400", "Mini PC (AM5)", "PRODUCTO", {}, 0, 2, 0, False, es_fabricado=True),
    ]
    boms = [
        BOM("ENS-BASE-AM4-v1", "ENS-BASE-AM4", "v1",
            [LineaBOM("MB-B550-PLUS", 1), LineaBOM("CPU-R5-5600", 1)]),
        BOM("PC-OFI-100-v1", "PC-OFI-100", "v1",
            [LineaBOM("ENS-BASE-AM4", 1), LineaBOM("RAM-16-DDR4", 1), LineaBOM("SSD-1TB", 1),
             LineaBOM("PSU-650-B", 1), LineaBOM("GAB-ATX", 1)]),
        BOM("PC-GAM-200-v1", "PC-GAM-200", "v1",
            [LineaBOM("ENS-BASE-AM4", 1), LineaBOM("RAM-16-DDR4", 2), LineaBOM("SSD-1TB", 1),
             LineaBOM("PSU-650-B", 1), LineaBOM("GAB-ATX", 1), LineaBOM("GPU-RTX-4060", 1)]),
        BOM("PC-WS-300-v1", "PC-WS-300", "v1",
            [LineaBOM("MB-B550-PLUS", 1), LineaBOM("CPU-R7-5700X", 1), LineaBOM("RAM-16-DDR4", 4),
             LineaBOM("SSD-1TB", 2), LineaBOM("PSU-650-B", 1), LineaBOM("GAB-ATX", 1)]),
        BOM("PC-MINI-400-v1", "PC-MINI-400", "v1",
            [LineaBOM("MB-B650-AURA", 1), LineaBOM("SSD-1TB", 1)]),
    ]
    ordenes = [
        OrdenFabricacion("OF-1001", "PC-OFI-100", 30, "PLANIFICADA", "PC-OFI-100-v1"),
        OrdenFabricacion("OF-1002", "PC-WS-300", 10, "PLANIFICADA", "PC-WS-300-v1"),
        OrdenFabricacion("OF-0990", "PC-GAM-200", 5, "EN_PROCESO", "PC-GAM-200-v1"),
        OrdenFabricacion("OF-0950", "PC-MINI-400", 8, "PLANIFICADA", "PC-MINI-400-v1"),
        OrdenFabricacion("OF-0900", "PC-OFI-100", 20, "TERMINADA", "PC-OFI-100-v1"),
    ]
    return ERP({c.sku: c for c in componentes}, {b.bom_id: b for b in boms}, ordenes)


DEMANDA_PEDIDO = {"PC-OFI-100": 30, "PC-WS-300": 10}


def ejecutar_escenario() -> dict:
    """Ejecuta el escenario AS-IS y TO-BE y devuelve los resultados."""
    # AS-IS: el MRP no conoce la descontinuación (solo lo sabe el proveedor).
    as_is = escenario_tarjeta_madre()
    mrp_as_is = as_is.mrp(DEMANDA_PEDIDO, aplicar_reglas=False)
    as_is.componentes["MB-B550-PLUS"].estado = DESCONTINUADO  # se entera después
    kpis_as_is = as_is.kpis(mrp_as_is, ordenes_retrasadas=["OF-1001", "OF-1002"])

    # TO-BE
    erp = escenario_tarjeta_madre()
    alerta = erp.cambiar_estado("MB-B550-PLUS", DESCONTINUADO, utc("2026-11-20T09:00:00"),
                                usuario="comprador01")
    # El job de detección corre cada 15 minutos; la alerta se emite en la siguiente ejecución.
    alerta.fecha_alerta = utc("2026-11-20T09:15:00")
    recs, descartados = erp.recomendar_sustitutos("MB-B550-PLUS")
    mrp_bloqueado = erp.mrp(DEMANDA_PEDIDO)
    kpis_deteccion = erp.kpis(mrp_bloqueado, ordenes_retrasadas=[])
    aut = erp.autorizar(recs[0], "ing.tecnico", ROL_RESPONSABLE_TECNICO, utc("2026-11-21T09:15:00"),
                        comentario="Mismo chipset y socket; validado en banco de pruebas.")
    aplicacion = erp.aplicar_sustitucion(aut, "resp.bom", utc("2026-11-21T10:00:00"))
    mrp_to_be = erp.mrp(DEMANDA_PEDIDO)
    kpis_to_be = erp.kpis(mrp_to_be, ordenes_retrasadas=[])
    return {
        "mrp_as_is": mrp_as_is, "kpis_as_is": kpis_as_is,
        "alerta": alerta, "recomendaciones": recs, "descartados": descartados,
        "mrp_bloqueado": mrp_bloqueado, "kpis_deteccion": kpis_deteccion, "autorizacion": aut, "aplicacion": aplicacion,
        "mrp_to_be": mrp_to_be, "kpis_to_be": kpis_to_be, "erp": erp,
    }


def _imprimir(r: dict) -> None:
    a = r["alerta"]
    print("=== AS-IS: MRP sin gestión de ciclo de vida ===")
    for c in r["mrp_as_is"]["compras"]:
        print(f"  Compra recomendada: {c['sku']:<14} {c['cantidad']:>4}")
    print(f"  KPIs AS-IS: {r['kpis_as_is']}")
    print("\n=== TO-BE: alerta generada ===")
    print(f"  Componente {a.sku} | prioridad {a.prioridad} | existencias {a.existencias} | "
          f"demanda abierta {a.demanda_abierta:g} | cobertura {a.cobertura:.0%}")
    for b in a.boms_afectadas:
        print(f"  BOM afectada nivel {b['nivel']}: {b['bom_id']:<16} ruta {b['ruta']}")
    print(f"  Órdenes afectadas: {a.ordenes_afectadas}")
    print("\n=== Recomendaciones del agente ===")
    for i, rec in enumerate(r["recomendaciones"], 1):
        print(f"  {i}. {rec.sku_sustituto:<15} puntuación {rec.puntuacion:.4f} {rec.detalle}")
    for sku, motivos in r["descartados"].items():
        print(f"  Descartado {sku:<15} {'; '.join(motivos)}")
    print("\n=== MRP mientras la sustitución está pendiente ===")
    print(f"  Consumo autorizado de stock: {r['mrp_bloqueado']['consumo_stock_descontinuado']}")
    print(f"  Faltantes bloqueados (sin compra): {r['mrp_bloqueado']['faltantes_bloqueados']}")
    for c in r["mrp_bloqueado"]["compras"]:
        print(f"  Compra recomendada: {c['sku']:<14} {c['cantidad']:>4}")
    print(f"  KPIs al detectar: {r['kpis_deteccion']}")
    print("\n=== Autorización y aplicación ===")
    aut = r["autorizacion"]
    print(f"  {aut.decision} por {aut.usuario} ({aut.rol}) el {aut.fecha.isoformat()}")
    print(f"  {r['aplicacion']}")
    print("\n=== MRP recalculado (TO-BE) ===")
    print(f"  Consumo autorizado de stock: {r['mrp_to_be']['consumo_stock_descontinuado']}")
    for c in r["mrp_to_be"]["compras"]:
        print(f"  Compra recomendada: {c['sku']:<14} {c['cantidad']:>4}")
    print(f"  KPIs TO-BE: {r['kpis_to_be']}")


if __name__ == "__main__":
    _imprimir(ejecutar_escenario())
