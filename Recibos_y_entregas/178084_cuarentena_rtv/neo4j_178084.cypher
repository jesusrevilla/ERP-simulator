// ============================================================================
// Consultas Cypher - Knowledge Graph de Recibos, Lotes, RTV y Entregas
// Matrícula: 178084 | Issue #305 y #306
// ============================================================================

// 1. Trazabilidad completa: Proveedor -> Recepción -> Lote -> Artículo / RTV / Entrega
MATCH (p:Proveedor {proyecto: '178084'})-[:SUMINISTRO]->(r:Recepcion)-[:CONTIENE]->(l:Lote)-[:ES_ARTICULO]->(a:Articulo)
OPTIONAL MATCH (l)-[:DEVUELTO_EN]->(rtv:DevolucionRTV)
OPTIONAL MATCH (l)-[:DESPACHADO_EN]->(e:Entrega)
RETURN
    p.codigo AS proveedor_codigo,
    p.nombre AS proveedor,
    r.folio_recepcion AS recepcion,
    a.sku AS sku,
    l.numero_lote AS lote,
    l.estatus_lote AS estatus,
    rtv.folio_rtv AS rtv,
    rtv.cantidad_devuelta AS cantidad_rtv,
    e.folio_entrega AS entrega,
    e.cliente AS cliente
ORDER BY l.numero_lote;

// 2. Ranking global de confiabilidad de proveedores (tasa de aprobación y conteo de RTV)
MATCH (p:Proveedor {proyecto: '178084'})-[:SUMINISTRO]->(:Recepcion)-[:CONTIENE]->(l:Lote)
OPTIONAL MATCH (l)-[:DEVUELTO_EN]->(rtv:DevolucionRTV)
WITH
    p,
    sum(l.cantidad_aprobada) AS aprobadas,
    sum(l.cantidad_rechazada) AS rechazadas,
    count(DISTINCT rtv) AS total_rtv
WITH
    p, aprobadas, rechazadas, total_rtv,
    (aprobadas + rechazadas) AS evaluadas
RETURN
    p.codigo AS codigo,
    p.nombre AS proveedor,
    aprobadas,
    rechazadas,
    total_rtv,
    CASE
        WHEN evaluadas = 0 THEN 100.0
        ELSE round((toFloat(aprobadas) / evaluadas) * 10000) / 100.0
    END AS tasa_aprobacion_pct
ORDER BY tasa_aprobacion_pct DESC, total_rtv ASC;

// 3. Recomendación del proveedor más confiable para un SKU específico (usada por el Agente IA)
// Parámetro esperado: $sku (ejemplo: 'SKU-BAT02')
MATCH (p:Proveedor {proyecto: '178084'})-[:SUMINISTRO]->(:Recepcion)-[:CONTIENE]->(l:Lote)-[:ES_ARTICULO]->(a:Articulo {sku: $sku})
OPTIONAL MATCH (l)-[:DEVUELTO_EN]->(rtv:DevolucionRTV)
WITH
    p,
    sum(l.cantidad_aprobada) AS aprobadas,
    sum(l.cantidad_rechazada) AS rechazadas,
    count(DISTINCT rtv) AS total_rtv
WITH
    p, aprobadas, rechazadas, total_rtv,
    (aprobadas + rechazadas) AS evaluadas
RETURN
    p.codigo AS codigo,
    p.nombre AS proveedor,
    aprobadas,
    rechazadas,
    total_rtv,
    CASE
        WHEN evaluadas = 0 THEN 100.0
        ELSE round((toFloat(aprobadas) / evaluadas) * 10000) / 100.0
    END AS tasa_aprobacion_pct
ORDER BY tasa_aprobacion_pct DESC, total_rtv ASC, aprobadas DESC;

// 4. Análisis de impacto: lotes con devoluciones RTV y clientes que recibieron del mismo lote
MATCH (p:Proveedor {proyecto: '178084'})-[:SUMINISTRO]->(r:Recepcion)-[:CONTIENE]->(l:Lote)-[:DEVUELTO_EN]->(rtv:DevolucionRTV)
OPTIONAL MATCH (l)-[:DESPACHADO_EN]->(e:Entrega)
RETURN
    p.nombre AS proveedor,
    l.numero_lote AS lote,
    rtv.folio_rtv AS folio_rtv,
    rtv.cantidad_devuelta AS unidades_rechazadas,
    rtv.motivo AS motivo,
    collect(DISTINCT e.cliente) AS clientes_impactados;