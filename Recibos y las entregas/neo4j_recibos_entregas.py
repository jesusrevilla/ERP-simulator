"""Módulo Neo4j para Compras, Recibos, Entregas e Inventario (ERP Simulator).

Modela en grafo las entidades y relaciones del flujo Inbound/Outbound:
- (:OrdenCompra)-[:EMITIDA_A]->(:Proveedor)
- (:OrdenCompra)-[:SOLICITA {cantidad_solicitada, cantidad_recibida, costo_unitario}]->(:Producto)
- (:ReciboMercancia)-[:RESPALDA]->(:OrdenCompra)
- (:ReciboMercancia)-[:RECIBE {cantidad_esperada, cantidad_aceptada, cantidad_danada, cantidad_faltante, estado_calidad}]->(:Producto)
- (:AutorizacionGerencial)-[:AUTORIZA_EXCESO]->(:ReciboMercancia)
- (:Cliente)-[:REALIZA]->(:OrdenVenta)-[:INCLUYE {cantidad_pedida, cantidad_despachada}]->(:Producto)
- (:EntregaMercancia)-[:DESPACHA_PEDIDO]->(:OrdenVenta)
- (:EntregaMercancia)-[:ENTREGA {cantidad_entregada, peso_subtotal_kg}]->(:Producto)
- (:EntregaMercancia)-[:EMITE_COMPROBANTE]->(:NotaSalida)
- (:Almacen)-[:TIENE_STOCK {stock_actual, stock_danado}]->(:Producto)
- (:ReciboMercancia|EntregaMercancia)-[:GENERA_MOVIMIENTO]->(:MovimientoInventario)-[:AFECTA_PRODUCTO]->(:Producto)

Todas las consultas usan Cypher parametrizado y MERGE idempotente (sin DETACH DELETE global).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


CONSTRAINTS_CYPHER: List[str] = [
    "CREATE CONSTRAINT erp_proveedor_codigo IF NOT EXISTS FOR (p:Proveedor) REQUIRE p.codigo_proveedor IS UNIQUE",
    "CREATE CONSTRAINT erp_cliente_codigo IF NOT EXISTS FOR (c:Cliente) REQUIRE c.codigo_cliente IS UNIQUE",
    "CREATE CONSTRAINT erp_producto_sku IF NOT EXISTS FOR (pr:Producto) REQUIRE pr.codigo_sku IS UNIQUE",
    "CREATE CONSTRAINT erp_almacen_codigo IF NOT EXISTS FOR (a:Almacen) REQUIRE a.codigo_almacen IS UNIQUE",
    "CREATE CONSTRAINT erp_oc_codigo IF NOT EXISTS FOR (oc:OrdenCompra) REQUIRE oc.codigo_oc IS UNIQUE",
    "CREATE CONSTRAINT erp_recibo_codigo IF NOT EXISTS FOR (r:ReciboMercancia) REQUIRE r.codigo_recibo IS UNIQUE",
    "CREATE CONSTRAINT erp_ov_codigo IF NOT EXISTS FOR (ov:OrdenVenta) REQUIRE ov.codigo_ov IS UNIQUE",
    "CREATE CONSTRAINT erp_entrega_codigo IF NOT EXISTS FOR (e:EntregaMercancia) REQUIRE e.codigo_entrega IS UNIQUE",
    "CREATE CONSTRAINT erp_nota_salida IF NOT EXISTS FOR (ns:NotaSalida) REQUIRE ns.numero_nota IS UNIQUE",
    "CREATE CONSTRAINT erp_autorizacion_codigo IF NOT EXISTS FOR (ag:AutorizacionGerencial) REQUIRE ag.codigo_autorizacion IS UNIQUE",
    "CREATE CONSTRAINT erp_movimiento_codigo IF NOT EXISTS FOR (m:MovimientoInventario) REQUIRE m.codigo_movimiento IS UNIQUE",
]

MERGE_PROVEEDOR_CYPHER = """
MERGE (p:Proveedor {codigo_proveedor: $codigo_proveedor})
SET p.nombre = $nombre,
    p.estatus = $estatus,
    p.activo = ($estatus = 'ACTIVO')
RETURN p.codigo_proveedor AS codigo_proveedor, p.estatus AS estatus
"""

MERGE_CLIENTE_CYPHER = """
MERGE (c:Cliente {codigo_cliente: $codigo_cliente})
SET c.nombre = $nombre,
    c.estatus = $estatus,
    c.credito_autorizado = $credito_autorizado
RETURN c.codigo_cliente AS codigo_cliente
"""

MERGE_ALMACEN_CYPHER = """
MERGE (a:Almacen {codigo_almacen: $codigo_almacen})
SET a.nombre = $nombre
RETURN a.codigo_almacen AS codigo_almacen
"""

MERGE_PRODUCTO_CYPHER = """
MERGE (pr:Producto {codigo_sku: $codigo_sku})
SET pr.nombre = $nombre,
    pr.unidad_medida = $unidad_medida,
    pr.peso_unitario_kg = $peso_unitario_kg
WITH pr
MATCH (a:Almacen {codigo_almacen: $codigo_almacen})
MERGE (a)-[s:TIENE_STOCK]->(pr)
ON CREATE SET s.stock_actual = 0.0, s.stock_danado = 0.0
RETURN pr.codigo_sku AS codigo_sku
"""

MERGE_AUTORIZACION_CYPHER = """
MERGE (ag:AutorizacionGerencial {codigo_autorizacion: $codigo_autorizacion})
SET ag.tipo_autorizacion = $tipo_autorizacion,
    ag.gerente_nombre = $gerente_nombre,
    ag.motivo = $motivo,
    ag.cantidad_extra_autorizada = $cantidad_extra_autorizada,
    ag.vigente = $vigente
RETURN ag.codigo_autorizacion AS codigo_autorizacion
"""

MERGE_ORDEN_COMPRA_CYPHER = """
MATCH (p:Proveedor {codigo_proveedor: $codigo_proveedor})
MATCH (a:Almacen {codigo_almacen: $codigo_almacen})
MERGE (oc:OrdenCompra {codigo_oc: $codigo_oc})
SET oc.estado = $estado,
    oc.fecha_emision = $fecha_emision
MERGE (oc)-[:EMITIDA_A]->(p)
MERGE (oc)-[:DESTINO_ALMACEN]->(a)
WITH oc
UNWIND $lineas AS linea
MATCH (pr:Producto {codigo_sku: linea.codigo_sku})
MERGE (oc)-[sol:SOLICITA]->(pr)
SET sol.cantidad_solicitada = linea.cantidad_solicitada,
    sol.cantidad_recibida = coalesce(sol.cantidad_recibida, 0.0),
    sol.costo_unitario = linea.costo_unitario
RETURN oc.codigo_oc AS codigo_oc
"""

VALIDAR_OC_PROVEEDOR_CYPHER = """
MATCH (oc:OrdenCompra {codigo_oc: $codigo_oc})-[:EMITIDA_A]->(p:Proveedor)
MATCH (oc)-[:DESTINO_ALMACEN]->(a:Almacen)
OPTIONAL MATCH (oc)-[sol:SOLICITA]->(pr:Producto)
RETURN oc.estado AS oc_estado,
       p.codigo_proveedor AS codigo_proveedor,
       p.estatus AS proveedor_estatus,
       p.activo AS proveedor_activo,
       a.codigo_almacen AS codigo_almacen,
       collect({
           codigo_sku: pr.codigo_sku,
           cantidad_solicitada: sol.cantidad_solicitada,
           cantidad_recibida: sol.cantidad_recibida
       }) AS lineas
"""

REGISTRAR_RECIBO_CYPHER = """
MATCH (oc:OrdenCompra {codigo_oc: $codigo_oc})-[:DESTINO_ALMACEN]->(a:Almacen)
MERGE (r:ReciboMercancia {codigo_recibo: $codigo_recibo})
SET r.estado = 'BORRADOR',
    r.usuario_registro = $usuario_registro,
    r.fecha_recepcion = $fecha_recepcion
MERGE (r)-[:RESPALDA]->(oc)
MERGE (r)-[:EN_ALMACEN]->(a)
WITH r
UNWIND $lineas AS linea
MATCH (pr:Producto {codigo_sku: linea.codigo_sku})
MERGE (r)-[rec:RECIBE]->(pr)
SET rec.cantidad_esperada = linea.cantidad_esperada,
    rec.cantidad_recibida = linea.cantidad_recibida,
    rec.cantidad_aceptada = linea.cantidad_aceptada,
    rec.cantidad_faltante = linea.cantidad_faltante,
    rec.cantidad_danada = linea.cantidad_danada,
    rec.estado_calidad = linea.estado_calidad
RETURN r.codigo_recibo AS codigo_recibo
"""

VINCULAR_AUTORIZACION_RECIBO_CYPHER = """
MATCH (ag:AutorizacionGerencial {codigo_autorizacion: $codigo_autorizacion})
MATCH (r:ReciboMercancia {codigo_recibo: $codigo_recibo})
WHERE ag.vigente = true AND ag.tipo_autorizacion = 'EXCESO_RECIBO'
MERGE (ag)-[:AUTORIZA_EXCESO]->(r)
RETURN ag.codigo_autorizacion AS codigo_autorizacion
"""

APROBAR_RECIBO_STOCK_CYPHER = """
MATCH (r:ReciboMercancia {codigo_recibo: $codigo_recibo})-[:RESPALDA]->(oc:OrdenCompra)
MATCH (r)-[:EN_ALMACEN]->(a:Almacen)
WHERE r.estado IN ['BORRADOR', 'EN_INSPECCION']
SET r.estado = 'APROBADO',
    r.fecha_aprobacion = $fecha_aprobacion
WITH r, oc, a
MATCH (r)-[rec:RECIBE]->(pr:Producto)
MATCH (a)-[s:TIENE_STOCK]->(pr)
MATCH (oc)-[sol:SOLICITA]->(pr)
WITH r, oc, a, pr, rec, s, sol, s.stock_actual AS stock_prev
SET s.stock_actual = stock_prev + rec.cantidad_aceptada,
    s.stock_danado = s.stock_danado + rec.cantidad_danada,
    sol.cantidad_recibida = sol.cantidad_recibida + rec.cantidad_aceptada
FOREACH (_ IN CASE WHEN rec.cantidad_aceptada > 0 THEN [1] ELSE [] END |
    MERGE (m:MovimientoInventario {codigo_movimiento: 'MOV-' + r.codigo_recibo + '-' + pr.codigo_sku})
    SET m.tipo_movimiento = 'ENTRADA_RECIBO',
        m.cantidad = rec.cantidad_aceptada,
        m.signo = 1,
        m.stock_anterior = stock_prev,
        m.stock_posterior = stock_prev + rec.cantidad_aceptada,
        m.fecha_movimiento = $fecha_aprobacion
    MERGE (r)-[:GENERA_MOVIMIENTO]->(m)
    MERGE (m)-[:AFECTA_PRODUCTO]->(pr)
    MERGE (m)-[:EN_ALMACEN]->(a)
)
WITH oc
MATCH (oc)-[all_sol:SOLICITA]->(:Producto)
WITH oc, sum(CASE WHEN all_sol.cantidad_recibida < all_sol.cantidad_solicitada THEN 1 ELSE 0 END) AS pendientes
SET oc.estado = CASE WHEN pendientes = 0 THEN 'RECIBIDA' ELSE 'PARCIAL' END
RETURN oc.estado AS oc_estado
"""

MERGE_ORDEN_VENTA_CYPHER = """
MATCH (c:Cliente {codigo_cliente: $codigo_cliente})
MATCH (a:Almacen {codigo_almacen: $codigo_almacen})
MERGE (ov:OrdenVenta {codigo_ov: $codigo_ov})
SET ov.estado_pedido = $estado_pedido,
    ov.estado_pago = $estado_pago
MERGE (c)-[:REALIZA]->(ov)
MERGE (ov)-[:ORIGEN_ALMACEN]->(a)
WITH ov
UNWIND $lineas AS linea
MATCH (pr:Producto {codigo_sku: linea.codigo_sku})
MERGE (ov)-[inc:INCLUYE]->(pr)
SET inc.cantidad_pedida = linea.cantidad_pedida,
    inc.cantidad_despachada = coalesce(inc.cantidad_despachada, 0.0)
RETURN ov.codigo_ov AS codigo_ov
"""

VALIDAR_OV_Y_STOCK_CYPHER = """
MATCH (ov:OrdenVenta {codigo_ov: $codigo_ov})-[:ORIGEN_ALMACEN]->(a:Almacen)
MATCH (ov)-[inc:INCLUYE]->(pr:Producto)
OPTIONAL MATCH (a)-[s:TIENE_STOCK]->(pr)
RETURN ov.estado_pedido AS estado_pedido,
       ov.estado_pago AS estado_pago,
       a.codigo_almacen AS codigo_almacen,
       collect({
           codigo_sku: pr.codigo_sku,
           cantidad_pedida: inc.cantidad_pedida,
           cantidad_despachada: inc.cantidad_despachada,
           stock_actual: coalesce(s.stock_actual, 0.0),
           peso_unitario_kg: pr.peso_unitario_kg
       }) AS lineas
"""

CONFIRMAR_ENTREGA_STOCK_CYPHER = """
MATCH (ov:OrdenVenta {codigo_ov: $codigo_ov})-[:ORIGEN_ALMACEN]->(a:Almacen)
MERGE (e:EntregaMercancia {codigo_entrega: $codigo_entrega})
SET e.estado = 'CONFIRMADA',
    e.peso_total_kg = $peso_total_kg,
    e.usuario_despacho = $usuario_despacho,
    e.fecha_confirmacion = $fecha_confirmacion
MERGE (e)-[:DESPACHA_PEDIDO]->(ov)
MERGE (e)-[:EN_ALMACEN]->(a)
MERGE (ns:NotaSalida {numero_nota: $numero_nota_salida})
SET ns.fecha_emision = $fecha_confirmacion,
    ns.peso_total_kg = $peso_total_kg
MERGE (e)-[:EMITE_COMPROBANTE]->(ns)
WITH e, ov, a
UNWIND $lineas AS linea
MATCH (pr:Producto {codigo_sku: linea.codigo_sku})
MATCH (a)-[s:TIENE_STOCK]->(pr)
MATCH (ov)-[inc:INCLUYE]->(pr)
WHERE s.stock_actual >= linea.cantidad_entregada
WITH e, ov, a, pr, s, inc, linea, s.stock_actual AS stock_prev
MERGE (e)-[ent:ENTREGA]->(pr)
SET ent.cantidad_entregada = linea.cantidad_entregada,
    ent.peso_subtotal_kg = linea.peso_subtotal_kg
SET s.stock_actual = stock_prev - linea.cantidad_entregada,
    inc.cantidad_despachada = inc.cantidad_despachada + linea.cantidad_entregada
MERGE (m:MovimientoInventario {codigo_movimiento: 'MOV-' + e.codigo_entrega + '-' + pr.codigo_sku})
SET m.tipo_movimiento = 'SALIDA_ENTREGA',
    m.cantidad = linea.cantidad_entregada,
    m.signo = -1,
    m.stock_anterior = stock_prev,
    m.stock_posterior = stock_prev - linea.cantidad_entregada,
    m.fecha_movimiento = $fecha_confirmacion
MERGE (e)-[:GENERA_MOVIMIENTO]->(m)
MERGE (m)-[:AFECTA_PRODUCTO]->(pr)
MERGE (m)-[:EN_ALMACEN]->(a)
WITH ov
MATCH (ov)-[all_inc:INCLUYE]->(:Producto)
WITH ov, sum(CASE WHEN all_inc.cantidad_despachada < all_inc.cantidad_pedida THEN 1 ELSE 0 END) AS pendientes
SET ov.estado_pedido = CASE WHEN pendientes = 0 THEN 'DESPACHADO' ELSE 'EN_DESPACHO' END
RETURN ov.estado_pedido AS ov_estado
"""

CUADRE_INVENTARIO_CYPHER = """
MATCH (a:Almacen {codigo_almacen: $codigo_almacen})-[s:TIENE_STOCK]->(pr:Producto {codigo_sku: $codigo_sku})
OPTIONAL MATCH (m:MovimientoInventario)-[:AFECTA_PRODUCTO]->(pr)
WHERE (m)-[:EN_ALMACEN]->(a)
WITH pr.codigo_sku AS sku,
     a.codigo_almacen AS almacen,
     s.stock_actual AS stock_actual,
     sum(CASE WHEN m.signo = 1 THEN m.cantidad ELSE 0.0 END) AS entradas,
     sum(CASE WHEN m.signo = -1 THEN m.cantidad ELSE 0.0 END) AS salidas
RETURN sku,
       almacen,
       entradas,
       salidas,
       (entradas - salidas) AS stock_calculado,
       stock_actual,
       (stock_actual - (entradas - salidas)) AS diferencia
"""


class Neo4jBusinessError(Exception):
    """Violación de regla de negocio o integridad en el grafo Neo4j."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class RecibosEntregasNeo4j:
    """Capa de acceso y validación de reglas de negocio sobre Neo4j."""

    def __init__(self, driver: Any, database: Optional[str] = None) -> None:
        self.driver = driver
        self.database = database or os.getenv("NEO4J_DATABASE", "neo4j")

    @classmethod
    def from_env(cls) -> "RecibosEntregasNeo4j":
        from neo4j import GraphDatabase

        uri = os.getenv("NEO4J_URI")
        if not uri:
            host = os.getenv("NEO4J_HOST", "localhost")
            port = os.getenv("NEO4J_PORT", "7687")
            uri = f"bolt://{host}:{port}"
        user = os.getenv("NEO4J_USER", os.getenv("NEO4J_USERNAME", "neo4j"))
        password = os.getenv("NEO4J_PASSWORD", "password")
        driver = GraphDatabase.driver(uri, auth=(user, password))
        driver.verify_connectivity()
        return cls(driver)

    def _run(self, query: str, **params: Any) -> List[Dict[str, Any]]:
        records, _, _ = self.driver.execute_query(query, database_=self.database, **params)
        return [r.data() for r in records]

    def inicializar_esquema(self) -> None:
        for stmt in CONSTRAINTS_CYPHER:
            self._run(stmt)

    def registrar_maestros(
        self,
        proveedor: Dict[str, Any],
        cliente: Dict[str, Any],
        almacen: Dict[str, Any],
        productos: List[Dict[str, Any]],
    ) -> None:
        self._run(MERGE_PROVEEDOR_CYPHER, **proveedor)
        self._run(MERGE_CLIENTE_CYPHER, **cliente)
        self._run(MERGE_ALMACEN_CYPHER, **almacen)
        for prod in productos:
            self._run(
                MERGE_PRODUCTO_CYPHER,
                codigo_sku=prod["codigo_sku"],
                nombre=prod["nombre"],
                unidad_medida=prod.get("unidad_medida", "PZA"),
                peso_unitario_kg=float(prod.get("peso_unitario_kg", 1.0)),
                codigo_almacen=almacen["codigo_almacen"],
            )

    def registrar_autorizacion_gerencial(self, auth: Dict[str, Any]) -> None:
        self._run(MERGE_AUTORIZACION_CYPHER, **auth)

    def crear_orden_compra(
        self,
        codigo_oc: str,
        codigo_proveedor: str,
        codigo_almacen: str,
        lineas: List[Dict[str, Any]],
        estado: str = "APROBADA",
    ) -> None:
        self._run(
            MERGE_ORDEN_COMPRA_CYPHER,
            codigo_oc=codigo_oc,
            codigo_proveedor=codigo_proveedor,
            codigo_almacen=codigo_almacen,
            estado=estado,
            fecha_emision=_now_iso(),
            lineas=lineas,
        )

    def registrar_y_aprobar_recibo(
        self,
        codigo_recibo: str,
        codigo_oc: str,
        lineas: List[Dict[str, Any]],
        usuario_registro: str,
        codigo_autorizacion: Optional[str] = None,
        extra_autorizado: float = 0.0,
    ) -> Dict[str, Any]:
        info = self._run(VALIDAR_OC_PROVEEDOR_CYPHER, codigo_oc=codigo_oc)
        if not info:
            raise Neo4jBusinessError(f"Orden de compra '{codigo_oc}' no encontrada en Neo4j.")
        oc_data = info[0]
        if oc_data["proveedor_estatus"] != "ACTIVO" or not oc_data["proveedor_activo"]:
            raise Neo4jBusinessError(
                f"Regla de negocio (Proveedor activo): Proveedor en estado {oc_data['proveedor_estatus']}."
            )
        if oc_data["oc_estado"] not in ("APROBADA", "PARCIAL"):
            raise Neo4jBusinessError(
                f"OC '{codigo_oc}' debe estar APROBADA o PARCIAL (actual: {oc_data['oc_estado']})."
            )

        oc_lines = {l["codigo_sku"]: l for l in oc_data["lineas"]}
        for l in lineas:
            sku = l["codigo_sku"]
            if sku not in oc_lines:
                raise Neo4jBusinessError(f"SKU '{sku}' no pertenece a OC '{codigo_oc}'.")
            pendiente = float(oc_lines[sku]["cantidad_solicitada"]) - float(
                oc_lines[sku]["cantidad_recibida"]
            )
            total_rec = float(l["cantidad_aceptada"]) + float(l.get("cantidad_danada", 0.0))
            if total_rec > pendiente:
                if not codigo_autorizacion or total_rec > (pendiente + extra_autorizado):
                    raise Neo4jBusinessError(
                        f"Regla de negocio (No recibir de más): SKU '{sku}' recibe {total_rec} > pendiente {pendiente}."
                    )

        self._run(
            REGISTRAR_RECIBO_CYPHER,
            codigo_recibo=codigo_recibo,
            codigo_oc=codigo_oc,
            usuario_registro=usuario_registro,
            fecha_recepcion=_now_iso(),
            lineas=lineas,
        )
        if codigo_autorizacion:
            self._run(
                VINCULAR_AUTORIZACION_RECIBO_CYPHER,
                codigo_autorizacion=codigo_autorizacion,
                codigo_recibo=codigo_recibo,
            )
        res = self._run(
            APROBAR_RECIBO_STOCK_CYPHER,
            codigo_recibo=codigo_recibo,
            fecha_aprobacion=_now_iso(),
        )
        return res[0] if res else {"oc_estado": "APROBADA"}

    def crear_orden_venta(
        self,
        codigo_ov: str,
        codigo_cliente: str,
        codigo_almacen: str,
        lineas: List[Dict[str, Any]],
        estado_pedido: str = "APROBADO",
        estado_pago: str = "PAGADO",
    ) -> None:
        self._run(
            MERGE_ORDEN_VENTA_CYPHER,
            codigo_ov=codigo_ov,
            codigo_cliente=codigo_cliente,
            codigo_almacen=codigo_almacen,
            estado_pedido=estado_pedido,
            estado_pago=estado_pago,
            lineas=lineas,
        )

    def confirmar_entrega(
        self,
        codigo_entrega: str,
        codigo_ov: str,
        lineas_solicitud: List[Dict[str, Any]],
        usuario_despacho: str,
        numero_nota_salida: Optional[str] = None,
    ) -> Dict[str, Any]:
        info = self._run(VALIDAR_OV_Y_STOCK_CYPHER, codigo_ov=codigo_ov)
        if not info:
            raise Neo4jBusinessError(f"Orden de venta '{codigo_ov}' no encontrada en Neo4j.")
        ov_data = info[0]
        if ov_data["estado_pedido"] not in ("APROBADO", "EN_DESPACHO"):
            raise Neo4jBusinessError(
                f"Regla de negocio (Estado del pedido): OV en estado {ov_data['estado_pedido']}."
            )
        if ov_data["estado_pago"] not in ("PAGADO", "CREDITO_AUTORIZADO"):
            raise Neo4jBusinessError(
                f"Regla de negocio (Pago/Crédito): OV con estado de pago {ov_data['estado_pago']}."
            )

        ov_lines = {l["codigo_sku"]: l for l in ov_data["lineas"]}
        lineas_confirmar: List[Dict[str, Any]] = []
        peso_total = 0.0
        for item in lineas_solicitud:
            sku = item["codigo_sku"]
            qty = float(item["cantidad_entregada"])
            if sku not in ov_lines:
                raise Neo4jBusinessError(f"SKU '{sku}' no pertenece a OV '{codigo_ov}'.")
            stock_disp = float(ov_lines[sku]["stock_actual"])
            if stock_disp < qty:
                raise Neo4jBusinessError(
                    f"Regla de negocio (Validación de inventario): Stock insuficiente para '{sku}' "
                    f"(disponible={stock_disp}, solicitado={qty})."
                )
            peso_sub = round(qty * float(ov_lines[sku]["peso_unitario_kg"]), 2)
            peso_total = round(peso_total + peso_sub, 2)
            lineas_confirmar.append(
                {
                    "codigo_sku": sku,
                    "cantidad_entregada": qty,
                    "peso_subtotal_kg": peso_sub,
                }
            )

        nota = numero_nota_salida or f"NS-{codigo_entrega}"
        res = self._run(
            CONFIRMAR_ENTREGA_STOCK_CYPHER,
            codigo_entrega=codigo_entrega,
            codigo_ov=codigo_ov,
            numero_nota_salida=nota,
            peso_total_kg=peso_total,
            usuario_despacho=usuario_despacho,
            fecha_confirmacion=_now_iso(),
            lineas=lineas_confirmar,
        )
        return res[0] if res else {"ov_estado": "DESPACHADO"}

    def verificar_cuadre_inventario(self, codigo_sku: str, codigo_almacen: str) -> Dict[str, Any]:
        rows = self._run(
            CUADRE_INVENTARIO_CYPHER,
            codigo_sku=codigo_sku,
            codigo_almacen=codigo_almacen,
        )
        if not rows:
            raise Neo4jBusinessError(f"No existe inventario para '{codigo_sku}' en '{codigo_almacen}'.")
        row = rows[0]
        row["cuadra"] = round(float(row["diferencia"]), 4) == 0.0
        return row
