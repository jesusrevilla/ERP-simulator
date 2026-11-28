-- ============================================================================
-- 03_seed_test_data.sql
-- Datos de prueba controlados para validar RN01-RN08, PU08, PU09 y Cost Roll-up
-- Issue #269 - Integrante 4 (Matrícula: 184027)
-- ============================================================================

INSERT INTO unidades_medida (uom_id, nombre, dimension, precision_decimales)
VALUES
    ('PCS', 'Pieza', 'CONTEO', 0),
    ('KG',  'Kilogramo', 'MASA', 4),
    ('G',   'Gramo', 'MASA', 4)
ON CONFLICT (uom_id) DO NOTHING;

INSERT INTO conversiones_uom (uom_origen_id, uom_destino_id, factor_multiplicador, sku_especifico)
SELECT v.orig, v.dest, v.fac, NULL
FROM (VALUES
    ('G',  'KG', 0.00100000),
    ('KG', 'G',  1000.00000000)
) AS v(orig, dest, fac)
WHERE NOT EXISTS (
    SELECT 1 FROM conversiones_uom c
    WHERE c.uom_origen_id = v.orig
      AND c.uom_destino_id = v.dest
      AND c.sku_especifico IS NULL
);

INSERT INTO articulos (sku, descripcion, tipo_item, uom_base_id, es_discreto, costo_estandar, activo)
VALUES
    ('PC001',      'Gaming PC Estándar',            'PT', 'PCS', TRUE,  0.0000,   TRUE),
    ('SE-COOL',    'Subensamble Enfriamiento',      'SE', 'PCS', TRUE,  0.0000,   TRUE),
    ('GPU001',     'Tarjeta Gráfica RTX',           'MP', 'PCS', TRUE,  500.0000, TRUE),
    ('TORN-M3',    'Tornillo M3 Acero',             'MP', 'PCS', TRUE,  0.1000,   TRUE),
    ('PC-PRO',     'Workstation Pro con Merma/UOM', 'PT', 'PCS', TRUE,  0.0000,   TRUE),
    ('SE-CHASIS',  'Subensamble Chasis Reforzado',  'SE', 'PCS', TRUE,  0.0000,   TRUE),
    ('PASTA-TER',  'Pasta Térmica Conductiva',      'MP', 'KG',  FALSE, 120.0000, TRUE),
    ('PT-SIN-VIG', 'Producto Sin Versión Activa',   'PT', 'PCS', TRUE,  0.0000,   TRUE)
ON CONFLICT (sku) DO NOTHING;

INSERT INTO bom_cabecera (
    parent_sku, version_codigo, cantidad_base, uom_id, estado,
    fecha_inicio, fecha_fin, usuario_creacion, usuario_aprobacion, fecha_aprobacion
)
VALUES
    ('PC001',      'v1.0', 1.0000, 'PCS', 'ACTIVO',   '2026-01-01 00:00:00+00', NULL, 'ing_184027', 'apr_184027', '2026-01-01 00:00:00+00'),
    ('SE-COOL',    'v1.0', 1.0000, 'PCS', 'ACTIVO',   '2026-01-01 00:00:00+00', NULL, 'ing_184027', 'apr_184027', '2026-01-01 00:00:00+00'),
    ('PC-PRO',     'v1.0', 1.0000, 'PCS', 'ACTIVO',   '2026-01-01 00:00:00+00', NULL, 'ing_184027', 'apr_184027', '2026-01-01 00:00:00+00'),
    ('SE-CHASIS',  'v1.0', 1.0000, 'PCS', 'ACTIVO',   '2026-01-01 00:00:00+00', NULL, 'ing_184027', 'apr_184027', '2026-01-01 00:00:00+00'),
    ('PT-SIN-VIG', 'v0.1', 1.0000, 'PCS', 'BORRADOR', '2026-01-01 00:00:00+00', NULL, 'ing_184027', NULL,         NULL)
ON CONFLICT (parent_sku, version_codigo) DO NOTHING;

INSERT INTO bom_detalle (bom_id, component_sku, cantidad, uom_id, scrap_merma, notas_posicion)
SELECT bc.bom_id, v.comp, v.cant, v.uom, v.scrap, v.nota
FROM bom_cabecera bc
JOIN (VALUES
    ('GPU001',  1.0000, 'PCS', 0.0000, 'Slot PCIe'),
    ('SE-COOL', 1.0000, 'PCS', 0.0000, 'Bahía térmica'),
    ('TORN-M3', 0.4000, 'PCS', 0.0000, 'Rama 1 directa')
) AS v(comp, cant, uom, scrap, nota) ON TRUE
WHERE bc.parent_sku = 'PC001' AND bc.version_codigo = 'v1.0'
ON CONFLICT (bom_id, component_sku) DO NOTHING;

INSERT INTO bom_detalle (bom_id, component_sku, cantidad, uom_id, scrap_merma, notas_posicion)
SELECT bc.bom_id, 'TORN-M3', 0.4000, 'PCS', 0.0000, 'Rama 2 en subensamble'
FROM bom_cabecera bc
WHERE bc.parent_sku = 'SE-COOL' AND bc.version_codigo = 'v1.0'
ON CONFLICT (bom_id, component_sku) DO NOTHING;

INSERT INTO bom_detalle (bom_id, component_sku, cantidad, uom_id, scrap_merma, notas_posicion)
SELECT bc.bom_id, v.comp, v.cant, v.uom, v.scrap, v.nota
FROM bom_cabecera bc
JOIN (VALUES
    ('GPU001',    2.0000,  'PCS', 0.0000, 'Dual GPU'),
    ('SE-CHASIS', 1.0000,  'PCS', 0.0000, 'Estructura'),
    ('PASTA-TER', 10.0000, 'G',   0.2000, 'Aplicación térmica con 20% merma'),
    ('TORN-M3',   5.0000,  'PCS', 0.0000, 'Fijación principal')
) AS v(comp, cant, uom, scrap, nota) ON TRUE
WHERE bc.parent_sku = 'PC-PRO' AND bc.version_codigo = 'v1.0'
ON CONFLICT (bom_id, component_sku) DO NOTHING;

INSERT INTO bom_detalle (bom_id, component_sku, cantidad, uom_id, scrap_merma, notas_posicion)
SELECT bc.bom_id, 'TORN-M3', 3.0000, 'PCS', 0.2500, 'Tornillería chasis con 25% merma'
FROM bom_cabecera bc
WHERE bc.parent_sku = 'SE-CHASIS' AND bc.version_codigo = 'v1.0'
ON CONFLICT (bom_id, component_sku) DO NOTHING;
