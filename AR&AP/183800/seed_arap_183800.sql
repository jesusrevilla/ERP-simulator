-- =====================================================================
-- seed_arap_183800.sql                                      Matrícula 183800
-- Datos de prueba mínimos para alimentar y probar el Knowledge Graph.
--
-- Orden de carga de las tablas del equipo (todas en AR&AP/):
--   1) Tablas-Alexis.sql        (catálogos: condiciones_pago, clientes, ...)
--   2) tablas.sql               (A/P)
--   3) azul_ventas.sql          (A/R)
--   4) miriam_contabilidad.sql  (cuentas contables; opcional)
--   5) este archivo
--
-- Los folios OC-4001, RM-5001, FP-6001, PP-7001, PV-1001, FC-2001, CB-3001 y
-- CB-3002 y sus importes coinciden con los eventos de Eventos_ISA95.json
-- (fuente 181585), así esos eventos se enlazan con documentos reales.
-- Los demás documentos dan variedad a las consultas de riesgo:
--   * C002 tiene 3 facturas abiertas y vencidas (cadena de deuda).
--   * El artículo A200 solo lo surte P001 (proveedor único); A300 lo surten
--     P001 y P002.
--   * OC-4003 está recibida pero sin facturar.
-- fecha_creacion se fija a mano para poder probar la extracción incremental
-- (con :'desde' = 2025-11-01 solo entran los documentos de noviembre).
-- =====================================================================

INSERT INTO condiciones_pago (nombre, dias) VALUES ('Contado', 0), ('Crédito 30 días', 30);

INSERT INTO clientes (codigo, razon_social, rfc, direccion, contacto, id_condicion, limite_credito, estatus)
VALUES
 ('C001', 'Comercializadora Alfa SA de CV', 'CAL010101AA1', 'Av. Reforma 100, CDMX', 'Ana López',
  (SELECT id_condicion FROM condiciones_pago WHERE nombre = 'Crédito 30 días'), 5000.00, 'A'),
 ('C002', 'Distribuidora Beta SA de CV', 'DBE020202BB2', 'Calle 5 de Mayo 20, Guadalajara', 'Luis Pérez',
  (SELECT id_condicion FROM condiciones_pago WHERE nombre = 'Crédito 30 días'), 3000.00, 'A');

INSERT INTO proveedores (codigo, razon_social, rfc, direccion, contacto, id_condicion, estatus)
VALUES
 ('P001', 'Componentes Gamma SA de CV', 'CGA010101CC1', 'Parque Industrial 1, Querétaro', 'Marta Ruiz',
  (SELECT id_condicion FROM condiciones_pago WHERE nombre = 'Crédito 30 días'), 'A'),
 ('P002', 'Suministros Delta SA de CV', 'SDE020202DD2', 'Zona Industrial 7, Monterrey', 'Jorge Díaz',
  (SELECT id_condicion FROM condiciones_pago WHERE nombre = 'Crédito 30 días'), 'A');

-- ------------------------- A/R -------------------------------------
INSERT INTO pedidos_venta (folio, cliente_id, fecha, estatus, subtotal, iva, total, fecha_creacion) VALUES
 ('PV-1001', (SELECT id_cliente FROM clientes WHERE codigo='C001'), '2025-11-10', 'C', 1000.00, 160.00, 1160.00, '2025-11-10 20:00:01'),
 ('PV-1002', (SELECT id_cliente FROM clientes WHERE codigo='C002'), '2025-09-01', 'C', 2000.00, 320.00, 2320.00, '2025-09-01 09:00:00'),
 ('PV-1003', (SELECT id_cliente FROM clientes WHERE codigo='C002'), '2025-09-18', 'C', 1000.00, 160.00, 1160.00, '2025-09-18 09:00:00');

INSERT INTO pedido_linea (pedido_id, articulo, cantidad, precio_unitario, cantidad_facturada) VALUES
 ((SELECT pedido_id FROM pedidos_venta WHERE folio='PV-1001'), 'A100', 10, 100.00, 10),
 ((SELECT pedido_id FROM pedidos_venta WHERE folio='PV-1002'), 'A100', 20, 100.00, 20),
 ((SELECT pedido_id FROM pedidos_venta WHERE folio='PV-1003'), 'A100', 10, 100.00, 10);

INSERT INTO facturas_cliente (folio, cliente_id, pedido_id, fecha, fecha_vencimiento, estatus, subtotal, iva, total, saldo, fecha_creacion) VALUES
 ('FC-2001', (SELECT id_cliente FROM clientes WHERE codigo='C001'), (SELECT pedido_id FROM pedidos_venta WHERE folio='PV-1001'),
  '2025-11-10', '2025-12-10', 'C', 1000.00, 160.00, 1160.00,    0.00, '2025-11-10 20:00:03'),
 ('FC-2002', (SELECT id_cliente FROM clientes WHERE codigo='C002'), (SELECT pedido_id FROM pedidos_venta WHERE folio='PV-1002'),
  '2025-09-05', '2025-10-05', 'A', 2000.00, 320.00, 2320.00, 1320.00, '2025-09-05 09:00:00'),
 ('FC-2003', (SELECT id_cliente FROM clientes WHERE codigo='C002'), (SELECT pedido_id FROM pedidos_venta WHERE folio='PV-1003'),
  '2025-09-20', '2025-10-20', 'A', 1000.00, 160.00, 1160.00, 1160.00, '2025-09-20 09:00:00'),
 ('FC-2004', (SELECT id_cliente FROM clientes WHERE codigo='C002'), NULL,
  '2025-10-10', '2025-11-10', 'A',  500.00,  80.00,  580.00,  580.00, '2025-10-10 09:00:00');

INSERT INTO factura_cliente_linea (factura_id, articulo, cantidad, precio_unitario) VALUES
 ((SELECT factura_id FROM facturas_cliente WHERE folio='FC-2001'), 'A100', 10, 100.00),
 ((SELECT factura_id FROM facturas_cliente WHERE folio='FC-2002'), 'A100', 20, 100.00),
 ((SELECT factura_id FROM facturas_cliente WHERE folio='FC-2003'), 'A100', 10, 100.00),
 ((SELECT factura_id FROM facturas_cliente WHERE folio='FC-2004'), 'A100',  5, 100.00);

INSERT INTO cobros (folio, cliente_id, fecha, monto, metodo_pago, fecha_creacion) VALUES
 ('CB-3001', (SELECT id_cliente FROM clientes WHERE codigo='C001'), '2025-11-15',  500.00, 'Transferencia', '2025-11-15 10:00:00'),
 ('CB-3002', (SELECT id_cliente FROM clientes WHERE codigo='C001'), '2025-11-30',  660.00, 'Transferencia', '2025-11-30 10:00:00'),
 ('CB-3003', (SELECT id_cliente FROM clientes WHERE codigo='C002'), '2025-10-20', 1000.00, 'Cheque',        '2025-10-20 10:00:00');

INSERT INTO cobro_aplicacion (cobro_id, factura_id, monto_aplicado) VALUES
 ((SELECT cobro_id FROM cobros WHERE folio='CB-3001'), (SELECT factura_id FROM facturas_cliente WHERE folio='FC-2001'),  500.00),
 ((SELECT cobro_id FROM cobros WHERE folio='CB-3002'), (SELECT factura_id FROM facturas_cliente WHERE folio='FC-2001'),  660.00),
 ((SELECT cobro_id FROM cobros WHERE folio='CB-3003'), (SELECT factura_id FROM facturas_cliente WHERE folio='FC-2002'), 1000.00);

-- ------------------------- A/P -------------------------------------
INSERT INTO ordenes_compra (folio, proveedor_id, fecha, estatus, subtotal, iva, total, fecha_creacion) VALUES
 ('OC-4001', (SELECT id_proveedor FROM proveedores WHERE codigo='P001'), '2025-11-10', 'C',  500.00,  80.00,  580.00, '2025-11-10 20:00:06'),
 ('OC-4002', (SELECT id_proveedor FROM proveedores WHERE codigo='P002'), '2025-10-01', 'A', 1000.00, 160.00, 1160.00, '2025-10-01 09:00:00'),
 ('OC-4003', (SELECT id_proveedor FROM proveedores WHERE codigo='P001'), '2025-10-15', 'A', 1000.00, 160.00, 1160.00, '2025-10-15 09:00:00');

INSERT INTO oc_linea (oc_id, articulo, cantidad, precio_unitario, cantidad_recibida, cantidad_facturada) VALUES
 ((SELECT oc_id FROM ordenes_compra WHERE folio='OC-4001'), 'A200', 10, 50.00, 10, 10),
 ((SELECT oc_id FROM ordenes_compra WHERE folio='OC-4002'), 'A300', 20, 50.00, 20, 20),
 ((SELECT oc_id FROM ordenes_compra WHERE folio='OC-4003'), 'A300', 20, 50.00, 20,  0);

INSERT INTO recepciones (folio, oc_id, fecha, estatus, fecha_creacion) VALUES
 ('RM-5001', (SELECT oc_id FROM ordenes_compra WHERE folio='OC-4001'), '2025-11-10', 'C', '2025-11-10 20:00:07'),
 ('RM-5002', (SELECT oc_id FROM ordenes_compra WHERE folio='OC-4002'), '2025-10-05', 'C', '2025-10-05 09:00:00'),
 ('RM-5003', (SELECT oc_id FROM ordenes_compra WHERE folio='OC-4003'), '2025-10-20', 'A', '2025-10-20 09:00:00');

INSERT INTO recepcion_linea (recepcion_id, oc_linea_id, articulo, cantidad_recibida) VALUES
 ((SELECT recepcion_id FROM recepciones WHERE folio='RM-5001'),
  (SELECT l.linea_id FROM oc_linea l JOIN ordenes_compra o ON o.oc_id=l.oc_id WHERE o.folio='OC-4001' AND l.articulo='A200'), 'A200', 10),
 ((SELECT recepcion_id FROM recepciones WHERE folio='RM-5002'),
  (SELECT l.linea_id FROM oc_linea l JOIN ordenes_compra o ON o.oc_id=l.oc_id WHERE o.folio='OC-4002' AND l.articulo='A300'), 'A300', 20),
 ((SELECT recepcion_id FROM recepciones WHERE folio='RM-5003'),
  (SELECT l.linea_id FROM oc_linea l JOIN ordenes_compra o ON o.oc_id=l.oc_id WHERE o.folio='OC-4003' AND l.articulo='A300'), 'A300', 20);

INSERT INTO facturas_proveedor (folio, proveedor_id, recepcion_id, oc_id, fecha, fecha_vencimiento, estatus, subtotal, iva, total, saldo, fecha_creacion) VALUES
 ('FP-6001', (SELECT id_proveedor FROM proveedores WHERE codigo='P001'),
  (SELECT recepcion_id FROM recepciones WHERE folio='RM-5001'), (SELECT oc_id FROM ordenes_compra WHERE folio='OC-4001'),
  '2025-11-10', '2025-12-10', 'C',  500.00,  80.00,  580.00,    0.00, '2025-11-10 20:00:09'),
 ('FP-6002', (SELECT id_proveedor FROM proveedores WHERE codigo='P002'),
  (SELECT recepcion_id FROM recepciones WHERE folio='RM-5002'), (SELECT oc_id FROM ordenes_compra WHERE folio='OC-4002'),
  '2025-10-10', '2025-11-09', 'A', 1000.00, 160.00, 1160.00, 1160.00, '2025-10-10 09:00:00');

INSERT INTO factura_proveedor_linea (factura_id, oc_linea_id, articulo, cantidad, precio_unitario) VALUES
 ((SELECT factura_id FROM facturas_proveedor WHERE folio='FP-6001'),
  (SELECT l.linea_id FROM oc_linea l JOIN ordenes_compra o ON o.oc_id=l.oc_id WHERE o.folio='OC-4001' AND l.articulo='A200'), 'A200', 10, 50.00),
 ((SELECT factura_id FROM facturas_proveedor WHERE folio='FP-6002'),
  (SELECT l.linea_id FROM oc_linea l JOIN ordenes_compra o ON o.oc_id=l.oc_id WHERE o.folio='OC-4002' AND l.articulo='A300'), 'A300', 20, 50.00);

INSERT INTO pagos (folio, proveedor_id, fecha, monto, metodo_pago, fecha_creacion) VALUES
 ('PP-7001', (SELECT id_proveedor FROM proveedores WHERE codigo='P001'), '2025-11-25', 580.00, 'Transferencia', '2025-11-25 10:00:00');

INSERT INTO pago_aplicacion (pago_id, factura_id, monto_aplicado) VALUES
 ((SELECT pago_id FROM pagos WHERE folio='PP-7001'), (SELECT factura_id FROM facturas_proveedor WHERE folio='FP-6001'), 580.00);
