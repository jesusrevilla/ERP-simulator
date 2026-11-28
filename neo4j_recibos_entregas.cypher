// ============================================================================
// SIMULADOR ERP - MODELO DE GRAFO NEO4J: COMPRAS, RECIBOS, ENTREGAS E INVENTARIO
// ============================================================================

// 1. RESTRICCIONES DE UNICIDAD (Integridad Referencial y Normalización en Grafo)
CREATE CONSTRAINT erp_proveedor_codigo IF NOT EXISTS
FOR (p:Proveedor) REQUIRE p.codigo_proveedor IS UNIQUE;

CREATE CONSTRAINT erp_cliente_codigo IF NOT EXISTS
FOR (c:Cliente) REQUIRE c.codigo_cliente IS UNIQUE;

CREATE CONSTRAINT erp_producto_sku IF NOT EXISTS
FOR (pr:Producto) REQUIRE pr.codigo_sku IS UNIQUE;

CREATE CONSTRAINT erp_almacen_codigo IF NOT EXISTS
FOR (a:Almacen) REQUIRE a.codigo_almacen IS UNIQUE;

CREATE CONSTRAINT erp_oc_codigo IF NOT EXISTS
FOR (oc:OrdenCompra) REQUIRE oc.codigo_oc IS UNIQUE;

CREATE CONSTRAINT erp_recibo_codigo IF NOT EXISTS
FOR (r:ReciboMercancia) REQUIRE r.codigo_recibo IS UNIQUE;

CREATE CONSTRAINT erp_ov_codigo IF NOT EXISTS
FOR (ov:OrdenVenta) REQUIRE ov.codigo_ov IS UNIQUE;

CREATE CONSTRAINT erp_entrega_codigo IF NOT EXISTS
FOR (e:EntregaMercancia) REQUIRE e.codigo_entrega IS UNIQUE;

CREATE CONSTRAINT erp_nota_salida IF NOT EXISTS
FOR (ns:NotaSalida) REQUIRE ns.numero_nota IS UNIQUE;

CREATE CONSTRAINT erp_autorizacion_codigo IF NOT EXISTS
FOR (ag:AutorizacionGerencial) REQUIRE ag.codigo_autorizacion IS UNIQUE;

CREATE CONSTRAINT erp_movimiento_codigo IF NOT EXISTS
FOR (m:MovimientoInventario) REQUIRE m.codigo_movimiento IS UNIQUE;

// 2. ÍNDICES DE CONSULTA OPERATIVA
CREATE INDEX idx_proveedor_estatus IF NOT EXISTS
FOR (p:Proveedor) ON (p.estatus);

CREATE INDEX idx_recibo_estado IF NOT EXISTS
FOR (r:ReciboMercancia) ON (r.estado);

CREATE INDEX idx_entrega_estado IF NOT EXISTS
FOR (e:EntregaMercancia) ON (e.estado);

// 3. CONSULTA DE CUADRE DE INVENTARIO (Entradas - Salidas = Stock actual)
// MATCH (a:Almacen)-[s:TIENE_STOCK]->(pr:Producto)
// OPTIONAL MATCH (m:MovimientoInventario)-[:AFECTA_PRODUCTO]->(pr)
// WHERE (m)-[:EN_ALMACEN]->(a)
// WITH a, pr, s.stock_actual AS stock_actual,
//      sum(CASE WHEN m.signo = 1 THEN m.cantidad ELSE 0 END) AS total_entradas,
//      sum(CASE WHEN m.signo = -1 THEN m.cantidad ELSE 0 END) AS total_salidas
// RETURN pr.codigo_sku AS sku,
//        a.codigo_almacen AS almacen,
//        total_entradas,
//        total_salidas,
//        (total_entradas - total_salidas) AS stock_calculado,
//        stock_actual,
//        (stock_actual - (total_entradas - total_salidas)) AS diferencia;
