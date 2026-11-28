// C1. Explosión aplanada de PC001 (RN08 + PU09)
WITH 1.0 AS demanda, datetime('2026-11-10T08:00:00Z') AS fecha_demanda
MATCH p = (root:BOMItem {sku: 'PC001', activo: true})-[:BOM_REQUIRES*1..10]->(mp:BOMItem {tipo_item: 'MP', activo: true})
WHERE ALL(r IN relationships(p) WHERE r.estado = 'ACTIVO'
      AND r.fecha_inicio <= fecha_demanda
      AND (r.fecha_fin IS NULL OR fecha_demanda < r.fecha_fin))
  AND ALL(n IN nodes(p) WHERE n.activo = true)
WITH mp, demanda,
     reduce(acc = 1.0, r IN relationships(p) |
       acc * ((r.cantidad * r.factor_uom) / (r.cantidad_base * (1.0 - r.scrap_merma)))
     ) AS factor_ruta
WITH mp, demanda, count(*) AS rutas_detectadas, sum(factor_ruta) AS factor_total
WITH mp, rutas_detectadas, (factor_total * demanda) AS bruta_exacta
WITH mp, rutas_detectadas, bruta_exacta,
     CASE WHEN mp.es_discreto THEN ceil(bruta_exacta) ELSE round(bruta_exacta, 4) END AS cantidad_final
RETURN mp.sku AS mp_sku,
       mp.uom_base AS uom,
       rutas_detectadas,
       round(bruta_exacta, 4) AS cantidad_bruta_exacta,
       cantidad_final AS cantidad_requerida_final,
       round(cantidad_final * mp.costo, 2) AS costo_total_estimado
ORDER BY mp_sku;

// C2. Explosión aplanada de PC-PRO (merma + conversión G->KG)
WITH 1.0 AS demanda, datetime('2026-11-10T08:00:00Z') AS fecha_demanda
MATCH p = (root:BOMItem {sku: 'PC-PRO', activo: true})-[:BOM_REQUIRES*1..10]->(mp:BOMItem {tipo_item: 'MP', activo: true})
WHERE ALL(r IN relationships(p) WHERE r.estado = 'ACTIVO'
      AND r.fecha_inicio <= fecha_demanda
      AND (r.fecha_fin IS NULL OR fecha_demanda < r.fecha_fin))
  AND ALL(n IN nodes(p) WHERE n.activo = true)
WITH mp, demanda,
     reduce(acc = 1.0, r IN relationships(p) |
       acc * ((r.cantidad * r.factor_uom) / (r.cantidad_base * (1.0 - r.scrap_merma)))
     ) AS factor_ruta
WITH mp, demanda, count(*) AS rutas_detectadas, sum(factor_ruta) AS factor_total
WITH mp, rutas_detectadas, (factor_total * demanda) AS bruta_exacta
WITH mp, rutas_detectadas, bruta_exacta,
     CASE WHEN mp.es_discreto THEN ceil(bruta_exacta) ELSE round(bruta_exacta, 4) END AS cantidad_final
RETURN mp.sku AS mp_sku,
       mp.uom_base AS uom,
       rutas_detectadas,
       round(bruta_exacta, 4) AS cantidad_bruta_exacta,
       cantidad_final AS cantidad_requerida_final,
       round(cantidad_final * mp.costo, 2) AS costo_total_estimado
ORDER BY mp_sku;

// C3. Cost Roll-up multinivel sobre todos los PT y SE activos
WITH datetime('2026-11-10T08:00:00Z') AS fecha_demanda
MATCH p = (root:BOMItem)-[:BOM_REQUIRES*1..10]->(mp:BOMItem {tipo_item: 'MP', activo: true})
WHERE root.tipo_item IN ['PT', 'SE'] AND root.activo = true
  AND ALL(r IN relationships(p) WHERE r.estado = 'ACTIVO'
      AND r.fecha_inicio <= fecha_demanda
      AND (r.fecha_fin IS NULL OR fecha_demanda < r.fecha_fin))
WITH root, mp,
     reduce(acc = 1.0, r IN relationships(p) |
       acc * ((r.cantidad * r.factor_uom) / (r.cantidad_base * (1.0 - r.scrap_merma)))
     ) AS factor_ruta
WITH root, mp, sum(factor_ruta) AS bruta_mp
WITH root, mp, bruta_mp,
     CASE WHEN mp.es_discreto THEN ceil(bruta_mp) ELSE round(bruta_mp, 4) END AS cant_final_mp
WITH root.sku AS parent_sku,
     root.tipo_item AS tipo_item,
     count(mp) AS total_materias_primas,
     sum(bruta_mp * mp.costo) AS suma_exacta,
     sum(cant_final_mp * mp.costo) AS suma_rollup
RETURN parent_sku,
       tipo_item,
       total_materias_primas,
       round(suma_exacta, 4) AS costo_exacto_sin_ceil,
       round(suma_rollup, 2) AS costo_estandar_rollup
ORDER BY tipo_item, parent_sku;

// C4. Where-Used + Sensibilidad financiera (+15% en GPU001)
WITH 'GPU001' AS mp_objetivo, 0.15 AS incremento_pct, datetime('2026-11-10T08:00:00Z') AS fecha_demanda
MATCH p = (pt:BOMItem {tipo_item: 'PT', activo: true})-[:BOM_REQUIRES*1..10]->(mp:BOMItem {sku: mp_objetivo})
WHERE ALL(r IN relationships(p) WHERE r.estado = 'ACTIVO'
      AND r.fecha_inicio <= fecha_demanda
      AND (r.fecha_fin IS NULL OR fecha_demanda < r.fecha_fin))
WITH pt, mp, incremento_pct,
     reduce(acc = 1.0, r IN relationships(p) |
       acc * ((r.cantidad * r.factor_uom) / (r.cantidad_base * (1.0 - r.scrap_merma)))
     ) AS factor_ruta
WITH pt, mp, incremento_pct, sum(factor_ruta) AS bruta_mp
WITH pt, mp, incremento_pct,
     CASE WHEN mp.es_discreto THEN ceil(bruta_mp) ELSE round(bruta_mp, 4) END AS cant_final
RETURN pt.sku AS producto_afectado,
       mp.sku AS materia_prima,
       cant_final AS cantidad_requerida,
       round(cant_final * mp.costo, 2) AS costo_actual_mp,
       round(cant_final * mp.costo * incremento_pct, 2) AS impacto_incremento_15pct
ORDER BY impacto_incremento_15pct DESC;
