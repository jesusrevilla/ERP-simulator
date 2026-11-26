"""
Agente Inteligente: TransactGuard AI
Tema: Integridad de las Transacciones en ERP
Alumno: Oscar Octavio García Maya (Matrícula: 182889)
Arquitectura: Knowledge Graph en memoria + Sistema Experto y Planeación
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Optional


@dataclass
class Nodo:
    id: str
    etiqueta: str
    propiedades: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Relacion:
    origen: str
    tipo: str
    destino: str
    propiedades: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IncidenciaIntegridad:
    regla_id: str
    severidad: str
    documento_id: str
    tipo_documento: str
    descripcion: str
    accion_planificada: str
    area_escalamiento: str


class KnowledgeGraphERP:
    """Grafo de conocimiento en memoria que replica el esquema Cypher del ERP."""

    def __init__(self):
        self.nodos: Dict[str, Nodo] = {}
        self.relaciones: List[Relacion] = []

    def agregar_nodo(self, nodo_id: str, etiqueta: str, **props) -> None:
        self.nodos[nodo_id] = Nodo(id=nodo_id, etiqueta=etiqueta, propiedades=props)

    def agregar_relacion(self, origen: str, tipo: str, destino: str, **props) -> None:
        self.relaciones.append(Relacion(origen=origen, tipo=tipo, destino=destino, propiedades=props))

    def vecinos_salientes(self, nodo_id: str, tipo_rel: str) -> List[Nodo]:
        return [
            self.nodos[r.destino]
            for r in self.relaciones
            if r.origen == nodo_id and r.tipo == tipo_rel and r.destino in self.nodos
        ]

    def vecinos_entrantes(self, nodo_id: str, tipo_rel: str) -> List[Nodo]:
        return [
            self.nodos[r.origen]
            for r in self.relaciones
            if r.destino == nodo_id and r.tipo == tipo_rel and r.origen in self.nodos
        ]

    def poblar_escenarios_erp(self) -> None:
        # Usuarios y roles
        self.agregar_nodo("USR-01", "Usuario", nombre="Ana Sofía Morales", rol="Comprador", departamento="Compras")
        self.agregar_nodo("USR-02", "Usuario", nombre="Carlos Mendoza", rol="Gerente Compras", departamento="Compras")
        self.agregar_nodo("USR-03", "Usuario", nombre="Luis Fernando Ruiz", rol="Almacenista", departamento="Almacén")
        self.agregar_nodo("USR-04", "Usuario", nombre="Mariana Torres", rol="Analista CXP", departamento="Finanzas")
        self.agregar_nodo("USR-05", "Usuario", nombre="Roberto Vega", rol="Tesorero", departamento="Finanzas")

        # Proveedores
        self.agregar_nodo("PROV-10", "Proveedor", razon_social="Aceros y Perfiles del Centro S.A.")
        self.agregar_nodo("PROV-20", "Proveedor", razon_social="Suministros Industriales Potosí")
        self.agregar_nodo("PROV-30", "Proveedor", razon_social="Logística y Empaques Bajío")

        # ESCENARIO A: Transacción Íntegra (3-Way Match válido y SoD correcto)
        self.agregar_nodo("OC-1001", "OrdenCompra", fecha="2026-11-10", monto=15000.00, estado="APROBADA")
        self.agregar_nodo("REC-2001", "Recepcion", fecha="2026-11-12", cantidad=100, estado="COMPLETA")
        self.agregar_nodo("FAC-3001", "Factura", fecha="2026-11-13", monto=15000.00, estado="VALIDADA")
        self.agregar_nodo("PAG-4001", "Pago", fecha="2026-11-15", monto=15000.00, estado="LIQUIDADO")

        self.agregar_relacion("USR-01", "CREA", "OC-1001")
        self.agregar_relacion("USR-02", "APRUEBA", "OC-1001")
        self.agregar_relacion("OC-1001", "DIRIGIDA_A", "PROV-10")
        self.agregar_relacion("REC-2001", "RESPALDA", "OC-1001")
        self.agregar_relacion("FAC-3001", "FACTURA_DE", "OC-1001")
        self.agregar_relacion("FAC-3001", "AMPARADA_POR", "REC-2001")
        self.agregar_relacion("PAG-4001", "LIQUIDA", "FAC-3001")

        # ESCENARIO B: Factura sin Recepción de Mercancía (Falla 3-Way Match)
        self.agregar_nodo("OC-1002", "OrdenCompra", fecha="2026-11-14", monto=28500.00, estado="APROBADA")
        self.agregar_nodo("FAC-3002", "Factura", fecha="2026-11-16", monto=28500.00, estado="PENDIENTE_PAGO")

        self.agregar_relacion("USR-01", "CREA", "OC-1002")
        self.agregar_relacion("USR-02", "APRUEBA", "OC-1002")
        self.agregar_relacion("OC-1002", "DIRIGIDA_A", "PROV-20")
        self.agregar_relacion("FAC-3002", "FACTURA_DE", "OC-1002")

        # ESCENARIO C: Violación de Segregación de Funciones (Auto-aprobación)
        self.agregar_nodo("OC-1003", "OrdenCompra", fecha="2026-11-18", monto=42000.00, estado="APROBADA")
        self.agregar_nodo("REC-2003", "Recepcion", fecha="2026-11-19", cantidad=50, estado="COMPLETA")
        self.agregar_nodo("FAC-3003", "Factura", fecha="2026-11-20", monto=42000.00, estado="VALIDADA")

        self.agregar_relacion("USR-02", "CREA", "OC-1003")
        self.agregar_relacion("USR-02", "APRUEBA", "OC-1003")
        self.agregar_relacion("OC-1003", "DIRIGIDA_A", "PROV-30")
        self.agregar_relacion("REC-2003", "RESPALDA", "OC-1003")
        self.agregar_relacion("FAC-3003", "FACTURA_DE", "OC-1003")
        self.agregar_relacion("FAC-3003", "AMPARADA_POR", "REC-2003")

        # ESCENARIO D: Discrepancia de Monto (+25%) y Pago Duplicado
        self.agregar_nodo("OC-1004", "OrdenCompra", fecha="2026-11-19", monto=10000.00, estado="APROBADA")
        self.agregar_nodo("REC-2004", "Recepcion", fecha="2026-11-20", cantidad=20, estado="COMPLETA")
        self.agregar_nodo("FAC-3004", "Factura", fecha="2026-11-21", monto=12500.00, estado="PAGADA")
        self.agregar_nodo("PAG-4004A", "Pago", fecha="2026-11-22", monto=12500.00, estado="LIQUIDADO")
        self.agregar_nodo("PAG-4004B", "Pago", fecha="2026-11-22", monto=12500.00, estado="LIQUIDADO")

        self.agregar_relacion("USR-01", "CREA", "OC-1004")
        self.agregar_relacion("USR-02", "APRUEBA", "OC-1004")
        self.agregar_relacion("OC-1004", "DIRIGIDA_A", "PROV-10")
        self.agregar_relacion("REC-2004", "RESPALDA", "OC-1004")
        self.agregar_relacion("FAC-3004", "FACTURA_DE", "OC-1004")
        self.agregar_relacion("FAC-3004", "AMPARADA_POR", "REC-2004")
        self.agregar_relacion("PAG-4004A", "LIQUIDA", "FAC-3004")
        self.agregar_relacion("PAG-4004B", "LIQUIDA", "FAC-3004")


class TransactGuardAgent:
    """Sistema Experto y módulo de planeación sobre el Knowledge Graph del ERP."""

    TOLERANCIA_MONTO_PCT = 0.02

    def __init__(self, grafo: KnowledgeGraphERP):
        self.grafo = grafo
        self.incidencias: List[IncidenciaIntegridad] = []

    def percibir_transacciones(self) -> List[Dict[str, Any]]:
        facturas = [n for n in self.grafo.nodos.values() if n.etiqueta == "Factura"]
        cadenas = []

        for fac in sorted(facturas, key=lambda x: x.id):
            ocs = self.grafo.vecinos_salientes(fac.id, "FACTURA_DE")
            recs = self.grafo.vecinos_salientes(fac.id, "AMPARADA_POR")
            pagos = self.grafo.vecinos_entrantes(fac.id, "LIQUIDA")

            oc: Optional[Nodo] = ocs[0] if ocs else None
            rec: Optional[Nodo] = recs[0] if recs else None
            creadores = self.grafo.vecinos_entrantes(oc.id, "CREA") if oc else []
            aprobadores = self.grafo.vecinos_entrantes(oc.id, "APRUEBA") if oc else []

            cadenas.append({
                "factura_id": fac.id,
                "factura_monto": fac.propiedades.get("monto", 0.0),
                "oc_id": oc.id if oc else None,
                "oc_monto": oc.propiedades.get("monto", 0.0) if oc else 0.0,
                "recepcion_id": rec.id if rec else None,
                "creador": creadores[0] if creadores else None,
                "aprobador": aprobadores[0] if aprobadores else None,
                "pagos": pagos,
            })
        return cadenas

    def evaluar_reglas_integridad(self, cadenas: List[Dict[str, Any]]) -> None:
        self.incidencias.clear()

        for tx in cadenas:
            fac_id = tx["factura_id"]
            oc_id = tx["oc_id"]
            rec_id = tx["recepcion_id"]
            fac_monto = tx["factura_monto"]
            oc_monto = tx["oc_monto"]
            creador = tx["creador"]
            aprobador = tx["aprobador"]
            pagos = tx["pagos"]

            # Regla 1: Conciliación a Tres Vías (3-Way Matching)
            if not oc_id or not rec_id:
                faltante = "Orden de Compra y Recepción" if not oc_id else "Recepción de Almacén"
                self.incidencias.append(IncidenciaIntegridad(
                    regla_id="R1_THREE_WAY_MATCH",
                    severidad="CRITICA",
                    documento_id=fac_id,
                    tipo_documento="Factura",
                    descripcion=f"Factura {fac_id} carece de {faltante} vinculada en el grafo.",
                    accion_planificada="RETENER_FACTURA_Y_BLOQUEAR_PAGO",
                    area_escalamiento="Contraloría y Almacén",
                ))

            # Regla 2: Tolerancia de importe (2%)
            if oc_id and oc_monto > 0:
                variacion = abs(fac_monto - oc_monto) / oc_monto
                if variacion > self.TOLERANCIA_MONTO_PCT:
                    self.incidencias.append(IncidenciaIntegridad(
                        regla_id="R2_DISCREPANCIA_MONTO",
                        severidad="ALTA",
                        documento_id=fac_id,
                        tipo_documento="Factura",
                        descripcion=(
                            f"Monto de {fac_id} (${fac_monto:,.2f}) difiere en {variacion*100:.1f}% "
                            f"respecto a {oc_id} (${oc_monto:,.2f})."
                        ),
                        accion_planificada="RETENER_POR_DIFERENCIA_PRECIO",
                        area_escalamiento="Gerencia de Compras y CXP",
                    ))

            # Regla 3: Segregación de Funciones (SoD)
            if creador and aprobador and creador.id == aprobador.id:
                self.incidencias.append(IncidenciaIntegridad(
                    regla_id="R3_VIOLACION_SOD",
                    severidad="CRITICA",
                    documento_id=oc_id,
                    tipo_documento="OrdenCompra",
                    descripcion=(
                        f"Conflicto SoD en {oc_id}: {creador.propiedades['nombre']} "
                        f"({creador.id}) creó y aprobó la misma operación."
                    ),
                    accion_planificada="MARCAR_AUDITORIA_INTERNA",
                    area_escalamiento="Auditoría Interna y Dirección Financiera",
                ))

            # Regla 4: Detección de Pagos Duplicados
            if len(pagos) > 1:
                total_pagado = sum(p.propiedades.get("monto", 0.0) for p in pagos)
                ids_pagos = ", ".join(p.id for p in pagos)
                self.incidencias.append(IncidenciaIntegridad(
                    regla_id="R4_PAGO_DUPLICADO",
                    severidad="CRITICA",
                    documento_id=fac_id,
                    tipo_documento="Factura",
                    descripcion=(
                        f"La factura {fac_id} presenta {len(pagos)} pagos asociados "
                        f"({ids_pagos}) por un total de ${total_pagado:,.2f}."
                    ),
                    accion_planificada="ESCALAR_RECUPERACION_TESORERIA",
                    area_escalamiento="Tesorería y Auditoría Financiera",
                ))

    def ejecutar_plan_acciones(self) -> None:
        timestamp = datetime.now().isoformat(timespec="seconds")
        for idx, inc in enumerate(self.incidencias, start=1):
            alerta_id = f"ALT-{idx:03d}"
            nodo_doc = self.grafo.nodos.get(inc.documento_id)
            if nodo_doc:
                nodo_doc.propiedades["estado"] = "RETENIDO_POR_AUDITORIA"
                nodo_doc.propiedades["ultima_auditoria"] = timestamp

            self.grafo.agregar_nodo(
                alerta_id,
                "AlertaAuditoria",
                regla=inc.regla_id,
                severidad=inc.severidad,
                accion=inc.accion_planificada,
                escalado_a=inc.area_escalamiento,
            )
            self.grafo.agregar_relacion(alerta_id, "AUDITA_A", inc.documento_id)

    def imprimir_reporte(self, total_cadenas: int) -> None:
        print("=" * 80)
        print("  TRANSACTGUARD AI - AUDITORÍA DE INTEGRIDAD TRANSACCIONAL (ERP)")
        print("  Alumno: Oscar Octavio García Maya | Matrícula: 182889")
        print("=" * 80)
        print(f"Nodos en Knowledge Graph : {len(self.grafo.nodos)} | Relaciones: {len(self.grafo.relaciones)}")
        print(f"Cadenas evaluadas        : {total_cadenas}")
        print(f"Incidencias detectadas   : {len(self.incidencias)}")
        print("-" * 80)

        for idx, inc in enumerate(self.incidencias, start=1):
            print(f"\n[{idx}] ALERTA {inc.regla_id} | Severidad: {inc.severidad}")
            print(f"    Documento afectado : {inc.tipo_documento} ({inc.documento_id})")
            print(f"    Hallazgo           : {inc.descripcion}")
            print(f"    Acción ejecutada   : {inc.accion_planificada}")
            print(f"    Escalamiento       : {inc.area_escalamiento}")

        print("\n" + "-" * 80)
        print("NODOS (:AlertaAuditoria) GENERADOS EN EL GRAFO:")
        for nodo in self.grafo.nodos.values():
            if nodo.etiqueta == "AlertaAuditoria":
                print(f"  * ({nodo.id}:AlertaAuditoria) -[:AUDITA_A]-> Estado doc: RETENIDO_POR_AUDITORIA | {nodo.propiedades}")
        print("=" * 80)


if __name__ == "__main__":
    grafo_erp = KnowledgeGraphERP()
    grafo_erp.poblar_escenarios_erp()

    agente = TransactGuardAgent(grafo_erp)
    transacciones = agente.percibir_transacciones()
    agente.evaluar_reglas_integridad(transacciones)
    agente.ejecutar_plan_acciones()
    agente.imprimir_reporte(total_cadenas=len(transacciones))
