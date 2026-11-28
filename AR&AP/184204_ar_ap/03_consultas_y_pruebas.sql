INSERT INTO condiciones_pago (codigo, descripcion, dias_credito) VALUES
('CONTADO', 'Pago de contado', 0),
('NET15', 'Credito a 15 dias', 15),
('NET30', 'Credito a 30 dias', 30)
ON CONFLICT (codigo) DO NOTHING;

INSERT INTO ordenes_compra (oc_id, proveedor_id, fecha_emision, condicion_pago, estatus, total_oc) VALUES
(5, 1, CURRENT_DATE - INTERVAL '10 days', 'NET30', 'A', 1000.00)
ON CONFLICT (oc_id) DO NOTHING;

INSERT INTO oc_linea (oc_id, articulo, cantidad_ordenada, precio_unitario, cantidad_recibida, cantidad_facturada) VALUES
(5, 'A200', 20, 50.00, 0, 0)
ON CONFLICT (oc_id, articulo) DO NOTHING;

-- 1 Registrar recepcion parcial de 10 ynidades
SELECT * FROM registrar_recepcion(5, 1, 'A200', 10, 'agente_recepcion');

-- 2 Registrar factura de proveedor
SELECT * FROM registrar_factura_proveedor(
    p_proveedor_id := 1,
    p_recepcion_id := 1,
    p_oc_id := 5,
    p_fecha := CURRENT_DATE,
    p_condicion_pago := 'NET30',
    p_articulo := 'A200',
    p_cantidad := 10,
    p_precio_unitario := 50.00,
    p_usuario := 'agente_ap'
);

-- 3 Ordenes de compra con recepciones parciales pendientes de facturar
SELECT
    oc.oc_id,
    oc.proveedor_id,
    l.articulo,
    l.cantidad_ordenada,
    l.cantidad_recibida,
    l.cantidad_facturada,
    (l.cantidad_recibida - l.cantidad_facturada) AS pendiente_por_facturar
FROM ordenes_compra oc
JOIN oc_linea l ON l.oc_id = oc.oc_id
WHERE (l.cantidad_recibida - l.cantidad_facturada) > 0;

-- 4 Aplicar pago total a la factura 1 
SELECT * FROM aplicar_pago_proveedor(1, 1, 500.00, 'agente_ap');
SELECT * FROM aplicar_pago_proveedor(1, 1, 500.00, 'agente_ap');
