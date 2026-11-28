-- ============================================================================
-- Consultas Analíticas SQL - Matrícula: 178084
-- ============================================================================

-- 1. Estado de inventario y disponibilidad ATP (Vista analítica)
SELECT *
FROM vw_inventario_atp_178084;

-- 2. Artículos críticos cuyo ATP cayó por debajo del stock mínimo
SELECT
    sku,
    nombre,
    stock_disponible,
    stock_cuarentena,
    stock_comprometido,
    atp,
    stock_minimo,
    (stock_minimo - atp) AS deficit_unidades
FROM vw_inventario_atp_178084
WHERE bajo_minimo = TRUE
ORDER BY atp ASC;

-- 3. Priorización FEFO: lotes disponibles ordenados por fecha de caducidad
SELECT
    a.sku,
    a.nombre AS articulo,
    l.numero_lote,
    l.cantidad_aprobada,
    l.fecha_caducidad,
    (l.fecha_caducidad - CURRENT_DATE) AS dias_restantes,
    CASE
        WHEN l.fecha_caducidad < CURRENT_DATE THEN 'VENCIDO - BLOQUEAR'
        WHEN l.fecha_caducidad <= CURRENT_DATE + INTERVAL '30 days' THEN 'PROXIMO A VENCER (FEFO)'
        ELSE 'VIGENTE'
    END AS estado_caducidad
FROM lotes_inspeccion_178084 l
JOIN articulos_178084 a ON a.articulo_id = l.articulo_id
WHERE l.estatus_lote = 'DISPONIBLE'
ORDER BY l.fecha_caducidad ASC;

-- 4. Lotes actualmente retenidos en cuarentena pendientes de dictamen
SELECT
    r.folio_recepcion,
    p.nombre AS proveedor,
    a.sku,
    l.numero_lote,
    l.cantidad_recibida,
    r.fecha_recepcion,
    l.fecha_caducidad
FROM lotes_inspeccion_178084 l
JOIN recepciones_178084 r ON r.recepcion_id = l.recepcion_id
JOIN proveedores_178084 p ON p.proveedor_id = r.proveedor_id
JOIN articulos_178084 a   ON a.articulo_id = l.articulo_id
WHERE l.estatus_lote = 'CUARENTENA'
ORDER BY r.fecha_recepcion ASC;

-- 5. Ranking de calidad de proveedores (Cumplimiento vs. Devoluciones RTV)
SELECT *
FROM vw_ranking_proveedores_178084;

-- 6. Trazabilidad documental completa: Proveedor -> Recepción -> Lote -> RTV / Entrega
SELECT
    p.codigo           AS proveedor,
    r.folio_recepcion,
    a.sku,
    l.numero_lote,
    l.estatus_lote,
    rtv.folio_rtv,
    rtv.cantidad_devuelta,
    e.folio_entrega,
    e.cliente,
    e.cantidad_entregada
FROM lotes_inspeccion_178084 l
JOIN recepciones_178084 r        ON r.recepcion_id = l.recepcion_id
JOIN proveedores_178084 p        ON p.proveedor_id = r.proveedor_id
JOIN articulos_178084 a          ON a.articulo_id = l.articulo_id
LEFT JOIN devoluciones_rtv_178084 rtv ON rtv.lote_id = l.lote_id
LEFT JOIN entregas_178084 e      ON e.lote_id = l.lote_id
ORDER BY l.lote_id;