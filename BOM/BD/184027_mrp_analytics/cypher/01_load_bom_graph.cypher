CREATE CONSTRAINT bom_item_sku_unique IF NOT EXISTS
FOR (i:BOMItem) REQUIRE i.sku IS UNIQUE;

UNWIND [
  {sku: 'PC001',      descripcion: 'Gaming PC Estándar',            tipo_item: 'PT', uom_base: 'PCS', es_discreto: true,  costo: 0.0,   activo: true},
  {sku: 'SE-COOL',    descripcion: 'Subensamble Enfriamiento',      tipo_item: 'SE', uom_base: 'PCS', es_discreto: true,  costo: 0.0,   activo: true},
  {sku: 'GPU001',     descripcion: 'Tarjeta Gráfica RTX',           tipo_item: 'MP', uom_base: 'PCS', es_discreto: true,  costo: 500.0, activo: true},
  {sku: 'TORN-M3',    descripcion: 'Tornillo M3 Acero',             tipo_item: 'MP', uom_base: 'PCS', es_discreto: true,  costo: 0.10,  activo: true},
  {sku: 'PC-PRO',     descripcion: 'Workstation Pro con Merma/UOM', tipo_item: 'PT', uom_base: 'PCS', es_discreto: true,  costo: 0.0,   activo: true},
  {sku: 'SE-CHASIS',  descripcion: 'Subensamble Chasis Reforzado',  tipo_item: 'SE', uom_base: 'PCS', es_discreto: true,  costo: 0.0,   activo: true},
  {sku: 'PASTA-TER',  descripcion: 'Pasta Térmica Conductiva',      tipo_item: 'MP', uom_base: 'KG',  es_discreto: false, costo: 120.0, activo: true},
  {sku: 'PT-SIN-VIG', descripcion: 'Producto Sin Versión Activa',   tipo_item: 'PT', uom_base: 'PCS', es_discreto: true,  costo: 0.0,   activo: true}
] AS item
MERGE (n:BOMItem {sku: item.sku})
SET n.descripcion = item.descripcion,
    n.tipo_item   = item.tipo_item,
    n.uom_base    = item.uom_base,
    n.es_discreto = item.es_discreto,
    n.costo       = item.costo,
    n.activo      = item.activo;

UNWIND [
  {parent: 'PC001',     child: 'GPU001',    version: 'v1.0', cantidad: 1.0,  cantidad_base: 1.0, factor_uom: 1.0,   scrap_merma: 0.0,  estado: 'ACTIVO', fecha_inicio: '2026-01-01T00:00:00Z', fecha_fin: null},
  {parent: 'PC001',     child: 'SE-COOL',   version: 'v1.0', cantidad: 1.0,  cantidad_base: 1.0, factor_uom: 1.0,   scrap_merma: 0.0,  estado: 'ACTIVO', fecha_inicio: '2026-01-01T00:00:00Z', fecha_fin: null},
  {parent: 'PC001',     child: 'TORN-M3',   version: 'v1.0', cantidad: 0.4,  cantidad_base: 1.0, factor_uom: 1.0,   scrap_merma: 0.0,  estado: 'ACTIVO', fecha_inicio: '2026-01-01T00:00:00Z', fecha_fin: null},
  {parent: 'SE-COOL',   child: 'TORN-M3',   version: 'v1.0', cantidad: 0.4,  cantidad_base: 1.0, factor_uom: 1.0,   scrap_merma: 0.0,  estado: 'ACTIVO', fecha_inicio: '2026-01-01T00:00:00Z', fecha_fin: null},
  {parent: 'PC-PRO',    child: 'GPU001',    version: 'v1.0', cantidad: 2.0,  cantidad_base: 1.0, factor_uom: 1.0,   scrap_merma: 0.0,  estado: 'ACTIVO', fecha_inicio: '2026-01-01T00:00:00Z', fecha_fin: null},
  {parent: 'PC-PRO',    child: 'SE-CHASIS', version: 'v1.0', cantidad: 1.0,  cantidad_base: 1.0, factor_uom: 1.0,   scrap_merma: 0.0,  estado: 'ACTIVO', fecha_inicio: '2026-01-01T00:00:00Z', fecha_fin: null},
  {parent: 'PC-PRO',    child: 'PASTA-TER', version: 'v1.0', cantidad: 10.0, cantidad_base: 1.0, factor_uom: 0.001, scrap_merma: 0.20, estado: 'ACTIVO', fecha_inicio: '2026-01-01T00:00:00Z', fecha_fin: null},
  {parent: 'PC-PRO',    child: 'TORN-M3',   version: 'v1.0', cantidad: 5.0,  cantidad_base: 1.0, factor_uom: 1.0,   scrap_merma: 0.0,  estado: 'ACTIVO', fecha_inicio: '2026-01-01T00:00:00Z', fecha_fin: null},
  {parent: 'SE-CHASIS', child: 'TORN-M3',   version: 'v1.0', cantidad: 3.0,  cantidad_base: 1.0, factor_uom: 1.0,   scrap_merma: 0.25, estado: 'ACTIVO', fecha_inicio: '2026-01-01T00:00:00Z', fecha_fin: null}
] AS rel
MATCH (p:BOMItem {sku: rel.parent}), (c:BOMItem {sku: rel.child})
MERGE (p)-[r:BOM_REQUIRES {version: rel.version}]->(c)
SET r.cantidad      = rel.cantidad,
    r.cantidad_base = rel.cantidad_base,
    r.factor_uom    = rel.factor_uom,
    r.scrap_merma   = rel.scrap_merma,
    r.estado        = rel.estado,
    r.fecha_inicio  = datetime(rel.fecha_inicio),
    r.fecha_fin     = CASE WHEN rel.fecha_fin IS NULL THEN null ELSE datetime(rel.fecha_fin) END;

MATCH (n:BOMItem) RETURN count(n) AS total_nodos_bom;
