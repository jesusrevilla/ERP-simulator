-- =====================================================================
-- extraccion_incremental.sql                                Matrícula 183800
-- Consultas de lectura que alimentan el Knowledge Graph (PostgreSQL -> Neo4j)
--
-- Cómo se usa
--   * sync_postgres_neo4j.py lee este archivo: cada bloque "-- name: xxx"
--     es una consulta, y :'desde' se sustituye por la marca de agua
--     (última sincronización).
--   * También se puede probar a mano en psql:
--         \set desde '2025-11-01 00:00:00'
--         \i extraccion_incremental.sql
--
-- Reglas del incremental
--   * Los encabezados (pedidos, facturas, cobros, OC, recepciones, pagos)
--     tienen fecha_creacion, así que se filtran con  fecha_creacion >= :'desde'.
--     Se usa ">=" (y no ">") para no perder filas con la misma marca de
--     tiempo; reprocesarlas es seguro porque el sincronizador usa MERGE.
--   * Las líneas y aplicaciones no tienen fecha propia: se extraen cuando su
--     documento padre cumple el filtro.
--   * Los catálogos (clientes, proveedores, cuentas) son pequeños y no tienen
--     fecha_creacion: se leen completos en cada corrida.
--   * Límite conocido: un cambio de estatus o saldo en un documento viejo
--     no cambia fecha_creacion. Para recogerlo hay que correr el modo
--     "completo" (o agregar una columna fecha_modificacion a las tablas).
--   * No usar el símbolo de porcentaje en estas consultas (psycopg2 lo
--     interpreta como parámetro).
-- =====================================================================

-- name: clientes
SELECT c.id_cliente   AS id,
       c.codigo,
       c.razon_social,
       c.rfc,
       c.limite_credito,
       c.estatus,
       cp.dias        AS dias_credito
FROM clientes c
JOIN condiciones_pago cp ON cp.id_condicion = c.id_condicion;

-- name: proveedores
SELECT p.id_proveedor AS id,
       p.codigo,
       p.razon_social,
       p.rfc,
       p.estatus,
       cp.dias        AS dias_credito
FROM proveedores p
JOIN condiciones_pago cp ON cp.id_condicion = p.id_condicion;

-- name: cuentas_contables
-- (opcional: viene de AR&AP/miriam_contabilidad.sql)
SELECT cuenta_id AS id, codigo, nombre, tipo, activa
FROM cuentas_contables;

-- ---------------------------------------------------------------------
-- A/R : ciclo de venta
-- ---------------------------------------------------------------------

-- name: pedidos_venta
SELECT p.pedido_id AS id, p.folio, c.rfc AS cliente_rfc,
       p.fecha, p.estatus, p.subtotal, p.iva, p.total, p.fecha_creacion
FROM pedidos_venta p
JOIN clientes c ON c.id_cliente = p.cliente_id
WHERE p.fecha_creacion >= :'desde';

-- name: pedido_lineas
SELECT p.folio AS documento_folio,
       l.articulo,
       SUM(l.cantidad) AS cantidad,
       ROUND(SUM(l.cantidad * l.precio_unitario) / SUM(l.cantidad), 2) AS precio_unitario
FROM pedido_linea l
JOIN pedidos_venta p ON p.pedido_id = l.pedido_id
WHERE p.fecha_creacion >= :'desde'
GROUP BY p.folio, l.articulo;

-- name: facturas_cliente
SELECT f.factura_id AS id, f.folio, c.rfc AS cliente_rfc, pv.folio AS pedido_folio,
       f.fecha, f.fecha_vencimiento, f.estatus,
       f.subtotal, f.iva, f.total, f.saldo, f.fecha_creacion
FROM facturas_cliente f
JOIN clientes c ON c.id_cliente = f.cliente_id
LEFT JOIN pedidos_venta pv ON pv.pedido_id = f.pedido_id
WHERE f.fecha_creacion >= :'desde';

-- name: cobros
SELECT cb.cobro_id AS id, cb.folio, c.rfc AS cliente_rfc,
       cb.fecha, cb.monto, cb.metodo_pago, cb.fecha_creacion
FROM cobros cb
JOIN clientes c ON c.id_cliente = cb.cliente_id
WHERE cb.fecha_creacion >= :'desde';

-- name: cobro_aplicaciones
SELECT cb.folio AS cobro_folio, f.folio AS factura_folio, a.monto_aplicado
FROM cobro_aplicacion a
JOIN cobros cb ON cb.cobro_id = a.cobro_id
JOIN facturas_cliente f ON f.factura_id = a.factura_id
WHERE cb.fecha_creacion >= :'desde';

-- ---------------------------------------------------------------------
-- A/P : ciclo de compra
-- ---------------------------------------------------------------------

-- name: ordenes_compra
SELECT oc.oc_id AS id, oc.folio, p.rfc AS proveedor_rfc,
       oc.fecha, oc.estatus, oc.subtotal, oc.iva, oc.total, oc.fecha_creacion
FROM ordenes_compra oc
JOIN proveedores p ON p.id_proveedor = oc.proveedor_id
WHERE oc.fecha_creacion >= :'desde';

-- name: oc_lineas
SELECT oc.folio AS documento_folio,
       l.articulo,
       SUM(l.cantidad) AS cantidad,
       ROUND(SUM(l.cantidad * l.precio_unitario) / SUM(l.cantidad), 2) AS precio_unitario
FROM oc_linea l
JOIN ordenes_compra oc ON oc.oc_id = l.oc_id
WHERE oc.fecha_creacion >= :'desde'
GROUP BY oc.folio, l.articulo;

-- name: recepciones
SELECT r.recepcion_id AS id, r.folio, oc.folio AS oc_folio,
       r.fecha, r.estatus, r.fecha_creacion
FROM recepciones r
JOIN ordenes_compra oc ON oc.oc_id = r.oc_id
WHERE r.fecha_creacion >= :'desde';

-- name: facturas_proveedor
SELECT f.factura_id AS id, f.folio, p.rfc AS proveedor_rfc,
       r.folio AS recepcion_folio, oc.folio AS oc_folio,
       f.fecha, f.fecha_vencimiento, f.estatus,
       f.subtotal, f.iva, f.total, f.saldo, f.fecha_creacion
FROM facturas_proveedor f
JOIN proveedores p ON p.id_proveedor = f.proveedor_id
LEFT JOIN recepciones r ON r.recepcion_id = f.recepcion_id
LEFT JOIN ordenes_compra oc ON oc.oc_id = f.oc_id
WHERE f.fecha_creacion >= :'desde';

-- name: pagos
SELECT pg.pago_id AS id, pg.folio, p.rfc AS proveedor_rfc,
       pg.fecha, pg.monto, pg.metodo_pago, pg.fecha_creacion
FROM pagos pg
JOIN proveedores p ON p.id_proveedor = pg.proveedor_id
WHERE pg.fecha_creacion >= :'desde';

-- name: pago_aplicaciones
SELECT pg.folio AS pago_folio, f.folio AS factura_folio, a.monto_aplicado
FROM pago_aplicacion a
JOIN pagos pg ON pg.pago_id = a.pago_id
JOIN facturas_proveedor f ON f.factura_id = a.factura_id
WHERE pg.fecha_creacion >= :'desde';
