// =====================================================================
// SKU Sentinel & Data Steward - consultas Cypher del agente (175805)
// Ejecutar después de cargar el grafo con 01_carga_grafo.cypher
// =====================================================================

// ---------------------------------------------------------------------
// Fase 1. Duplicados estructurales en el catálogo
// (misma categoría, marca, modelo, capacidad y tipo, sin importar mayúsculas)
// ---------------------------------------------------------------------
MATCH (a:Item), (b:Item)
WHERE a.ItemCode < b.ItemCode
  AND a.Category = b.Category
  AND toLower(a.marca) = toLower(b.marca)
  AND toLower(a.modelo) = toLower(b.modelo)
  AND a.capacidad = b.capacidad
  AND toLower(a.tipo) = toLower(b.tipo)
RETURN a.ItemCode AS sku_a, b.ItemCode AS sku_b, a.Category AS categoria;

// Fase 1. ¿Existe ya un artículo equivalente a uno que se quiere dar de alta?
// Parámetros: $categoria, $marca, $modelo, $capacidad, $tipo
MATCH (i:Item)
WHERE i.Category = $categoria
  AND toLower(i.marca) = toLower($marca)
  AND toLower(i.modelo) = toLower($modelo)
  AND i.capacidad = $capacidad
  AND toLower(i.tipo) = toLower($tipo)
RETURN i.ItemCode AS sku_existente, i.Description AS descripcion;

// ---------------------------------------------------------------------
// Fase 2. Violaciones de integridad en el catálogo
// ---------------------------------------------------------------------
MATCH (i:Item)
WHERE i.ListPrice < i.StandardCost
   OR NOT i.UnitOfMeasure IN ['PZA', 'KG', 'LT', 'M', 'CAJA']
   OR (i.EsCritico = true AND i.SafetyStock <= 0)
RETURN i.ItemCode AS sku,
       i.ListPrice < i.StandardCost AS precio_menor_al_costo,
       NOT i.UnitOfMeasure IN ['PZA', 'KG', 'LT', 'M', 'CAJA'] AS unidad_invalida,
       (i.EsCritico = true AND i.SafetyStock <= 0) AS safety_stock_invalido;

// ---------------------------------------------------------------------
// Fase 3. Sustitutos de un artículo crítico agotado
// Misma categoría, con existencias y compatible con la misma Motherboard.
// Parámetro: $codigo (por ejemplo 'SSD-SAM980-1TB')
// ---------------------------------------------------------------------
MATCH (origen:Item {ItemCode: $codigo})-[:COMPATIBLE_WITH]->(placa:Item {Category: 'Motherboard'})
      <-[:COMPATIBLE_WITH]-(sustituto:Item)
WHERE sustituto.Category = origen.Category
  AND sustituto.ItemCode <> origen.ItemCode
  AND sustituto.StockDisponible > 0
RETURN DISTINCT sustituto.ItemCode AS sustituto,
       sustituto.Description AS descripcion,
       sustituto.StockDisponible AS existencias,
       sustituto.SubstituteGroup = origen.SubstituteGroup AS mismo_grupo,
       abs(sustituto.ListPrice - origen.ListPrice) AS diferencia_precio
ORDER BY mismo_grupo DESC, diferencia_precio ASC
LIMIT 3;

// Fase 3. Artículos críticos que hoy no tienen existencias
MATCH (i:Item)
WHERE i.EsCritico = true AND i.StockDisponible <= 0
RETURN i.ItemCode AS sku, i.Description AS descripcion;

// ---------------------------------------------------------------------
// Fase 3. Segmentación ABC por valor de consumo anual
// A: hasta 80 % acumulado, B: hasta 95 %, C: el resto.
// ---------------------------------------------------------------------
MATCH (i:Item)
WITH i, i.DemandaAnual * i.StandardCost AS valor
ORDER BY valor DESC
WITH collect({sku: i.ItemCode, valor: valor}) AS filas, sum(valor) AS total
UNWIND range(0, size(filas) - 1) AS idx
WITH filas[idx] AS fila, total,
     reduce(acc = 0.0, f IN filas[0..idx] | acc + f.valor) AS acumulado_previo
RETURN fila.sku AS sku,
       fila.valor AS valor_anual,
       CASE WHEN acumulado_previo / total < 0.80 THEN 'A'
            WHEN acumulado_previo / total < 0.95 THEN 'B'
            ELSE 'C' END AS clase
ORDER BY valor_anual DESC;
