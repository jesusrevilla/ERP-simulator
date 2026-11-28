-- ============================================================================
-- Datos Semilla de Prueba - Matrícula: 178084
-- ============================================================================

-- 1. Proveedores (alta, media y baja confiabilidad)
INSERT INTO proveedores_178084 (codigo, nombre, activo) VALUES
('PROV-01', 'TechComponents MX', TRUE),
('PROV-02', 'GlobalChip Supply', TRUE),
('PROV-03', 'ElectroBarato SA', TRUE);

-- 2. Artículos (el stock disponible/cuarentena se actualiza vía triggers y SP)
INSERT INTO articulos_178084 (sku, nombre, stock_comprometido, stock_minimo) VALUES
('SKU-PT01',  'Pasta Térmica Pro 5g',   15, 20),
('SKU-BAT02', 'Batería CMOS CR2032',    25, 30),
('SKU-SSD03', 'SSD NVMe 1TB Gen4',      10, 15),
('SKU-PSU04', 'Fuente de Poder 750W',    5, 10);

-- 3. Recepciones de mercancía vinculadas a Órdenes de Compra
INSERT INTO recepciones_178084 (folio_recepcion, folio_oc, proveedor_id, almacen, fecha_recepcion) VALUES
('REC-178084-001', 'OC-2026-101', 1, 'ALM-CENTRAL', CURRENT_DATE - INTERVAL '10 days'),
('REC-178084-002', 'OC-2026-102', 2, 'ALM-CENTRAL', CURRENT_DATE - INTERVAL '5 days'),
('REC-178084-003', 'OC-2026-103', 3, 'ALM-CENTRAL', CURRENT_DATE - INTERVAL '20 days'),
('REC-178084-004', 'OC-2026-104', 2, 'ALM-NORTE',   CURRENT_DATE - INTERVAL '2 days');

-- 4. Lotes recibidos (todos entran automáticamente a CUARENTENA por trigger)
INSERT INTO lotes_inspeccion_178084
    (numero_lote, recepcion_id, articulo_id, cantidad_recibida, fecha_caducidad)
VALUES
-- Pasta Térmica (PROV-01): un lote próximo a caducar (FEFO) y otro lejano
('LOT-PT-01',   1, 1, 30, CURRENT_DATE + INTERVAL '12 days'),
('LOT-PT-02',   1, 1, 40, CURRENT_DATE + INTERVAL '180 days'),

-- Batería CMOS: proveedores 1, 2 y 3 (con rechazos RTV y un lote ya vencido)
('LOT-BAT-00',  1, 2, 10, CURRENT_DATE + INTERVAL '90 days'),
('LOT-BAT-01',  2, 2, 20, CURRENT_DATE + INTERVAL '20 days'),
('LOT-BAT-EXP', 3, 2, 10, CURRENT_DATE - INTERVAL '5 days'),

-- SSD NVMe: un lote liberado y otro retenido en CUARENTENA
('LOT-SSD-01',  1, 3, 15, CURRENT_DATE + INTERVAL '365 days'),
('LOT-SSD-Q01', 4, 3, 25, CURRENT_DATE + INTERVAL '300 days'),

-- Fuente 750W: recepción con rechazo parcial (genera RTV)
('LOT-PSU-01',  2, 4, 50, CURRENT_DATE + INTERVAL '240 days');

-- 5. Dictamen de calidad mediante el procedimiento almacenado
--    (LOT-SSD-Q01 se deja intencionalmente en CUARENTENA)
CALL sp_dictaminar_lote(1, 30, 0, NULL);
CALL sp_dictaminar_lote(2, 40, 0, NULL);
CALL sp_dictaminar_lote(3, 10, 0, NULL);
CALL sp_dictaminar_lote(4, 15, 5, 'Empaque dañado por humedad');
CALL sp_dictaminar_lote(5, 5,  5, 'Celdas con voltaje fuera de especificación');
CALL sp_dictaminar_lote(6, 15, 0, NULL);
CALL sp_dictaminar_lote(8, 40, 10, 'Conectores defectuosos en prueba eléctrica');

-- 6. Entregas válidas (el trigger valida lote DISPONIBLE/vigente y descuenta stock)
INSERT INTO entregas_178084 (folio_entrega, cliente, lote_id, articulo_id, cantidad_entregada) VALUES
('ENT-178084-001', 'TechAssembly Línea A', 1, 1, 10),
('ENT-178084-002', 'TechAssembly Línea B', 3, 2, 10),
('ENT-178084-003', 'Ensambles del Centro', 8, 4, 10);