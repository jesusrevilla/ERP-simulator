-- ============================================================================
-- 04_analytical_queries.sql
-- Consultas analíticas MRP, detección de componentes compartidos, auditoría
-- previa de vigencias y validación de rendimiento con EXPLAIN ANALYZE
-- Issue #269 - Integrante 4 (Matrícula: 184027)
-- ============================================================================

-- Q1. Explosión multinivel aplanada (Summarized BOM) para PC001 (caso RN08 / PU09)
SELECT * FROM fn_explode_bom_summarized('PC001', 1.0, '2026-11-10 08:00:00+00');

-- Q2. Explosión multinivel con merma (RN08) y conversión de UOM (G -> KG)
SELECT * FROM fn_explode_bom_summarized('PC-PRO', 5.0, '2026-11-10 08:00:00+00');

-- Q3. Cost Roll-up multinivel por Producto Terminado y Subensamble
SELECT * FROM fn_bom_cost_rollup('2026-11-10 08:00:00+00');

-- Q4. Detección de Materias Primas compartidas entre 2 o más ramas de un mismo PT
SELECT
    p.sku AS producto_padre,
    e.mp_sku AS materia_prima_compartida,
    e.rutas_detectadas,
    e.cantidad_bruta_exacta,
    e.cantidad_requerida_final
FROM articulos p
CROSS JOIN LATERAL fn_explode_bom_summarized(p.sku, 1.0, '2026-11-10 08:00:00+00') e
WHERE p.tipo_item = 'PT'
  AND p.activo = TRUE
  AND EXISTS (
      SELECT 1 FROM bom_cabecera bc
      WHERE bc.parent_sku = p.sku
        AND bc.estado = 'ACTIVO'
        AND bc.fecha_inicio <= '2026-11-10 08:00:00+00'
        AND (bc.fecha_fin IS NULL OR '2026-11-10 08:00:00+00' < bc.fecha_fin)
  )
  AND e.rutas_detectadas >= 2
ORDER BY p.sku, e.rutas_detectadas DESC;

-- Q5. Auditoría previa MRP: PT/SE activos sin versión ACTIVA vigente o sin detalle
SELECT
    a.sku,
    a.descripcion,
    a.tipo_item,
    CASE
        WHEN bc.bom_id IS NULL THEN 'SIN_VERSION_ACTIVA_VIGENTE'
        WHEN NOT EXISTS (SELECT 1 FROM bom_detalle bd WHERE bd.bom_id = bc.bom_id) THEN 'BOM_VACIO_SIN_COMPONENTES'
        ELSE 'OK'
    END AS diagnostico_mrp
FROM articulos a
LEFT JOIN bom_cabecera bc
  ON bc.parent_sku = a.sku
 AND bc.estado = 'ACTIVO'
 AND bc.fecha_inicio <= '2026-11-10 08:00:00+00'
 AND (bc.fecha_fin IS NULL OR '2026-11-10 08:00:00+00' < bc.fecha_fin)
WHERE a.tipo_item IN ('PT', 'SE')
  AND a.activo = TRUE
ORDER BY diagnostico_mrp DESC, a.sku;

-- Q6. Plan de ejecución (EXPLAIN ANALYZE) sobre la consulta recursiva indexada
EXPLAIN (ANALYZE, BUFFERS)
WITH RECURSIVE bom_tree AS (
    SELECT
        0 AS nivel,
        bc.parent_sku,
        bd.component_sku,
        (bd.cantidad / (bc.cantidad_base * (1.0 - bd.scrap_merma))) AS factor,
        ARRAY[bc.parent_sku::TEXT, bd.component_sku::TEXT] AS ruta
    FROM bom_cabecera bc
    JOIN bom_detalle bd ON bd.bom_id = bc.bom_id
    WHERE bc.parent_sku = 'PC001'
      AND bc.estado = 'ACTIVO'
      AND bc.fecha_inicio <= '2026-11-10 08:00:00+00'
      AND (bc.fecha_fin IS NULL OR '2026-11-10 08:00:00+00' < bc.fecha_fin)

    UNION ALL

    SELECT
        bt.nivel + 1,
        bc.parent_sku,
        bd.component_sku,
        bt.factor * (bd.cantidad / (bc.cantidad_base * (1.0 - bd.scrap_merma))),
        bt.ruta || bd.component_sku::TEXT
    FROM bom_tree bt
    JOIN bom_cabecera bc
      ON bc.parent_sku = bt.component_sku
     AND bc.estado = 'ACTIVO'
     AND bc.fecha_inicio <= '2026-11-10 08:00:00+00'
     AND (bc.fecha_fin IS NULL OR '2026-11-10 08:00:00+00' < bc.fecha_fin)
    JOIN bom_detalle bd ON bd.bom_id = bc.bom_id
    WHERE NOT (bd.component_sku = ANY(bt.ruta))
)
SELECT
    bt.component_sku AS mp_sku,
    SUM(bt.factor) AS bruta_exacta,
    CEIL(SUM(bt.factor)) AS requerida_final
FROM bom_tree bt
JOIN articulos a ON a.sku = bt.component_sku
WHERE a.tipo_item = 'MP'
GROUP BY bt.component_sku;
