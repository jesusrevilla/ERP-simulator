// Tablas (nodos y relaciones) del modulo de Reglas de OC y OP en Neo4j.
// Uso:
//   cypher-shell -a bolt://localhost:7687 -u neo4j -p SuperPassword123 \
//     -f reglas_oc_y_op/esquema_neo4j.cypher
//
// En Neo4j Community solo existen las restricciones de UNICIDAD; las de
// existencia y tipo son de Enterprise. Por eso al final van las consultas que
// verifican la integridad descrita en la seccion 3 de reglas_oc_y_op.md.

// --- Restricciones e indices ---
CREATE CONSTRAINT proveedor_id IF NOT EXISTS FOR (n:Proveedor) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT material_id IF NOT EXISTS FOR (n:Material) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT producto_id IF NOT EXISTS FOR (n:ProductoTerminado) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT oc_id IF NOT EXISTS FOR (n:OrdenCompra) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT op_id IF NOT EXISTS FOR (n:OrdenProduccion) REQUIRE n.id IS UNIQUE;

CREATE INDEX material_punto_reorden IF NOT EXISTS FOR (n:Material) ON (n.punto_reorden);
CREATE INDEX oc_estado IF NOT EXISTS FOR (n:OrdenCompra) ON (n.estado);
CREATE INDEX op_estado IF NOT EXISTS FOR (n:OrdenProduccion) ON (n.estado);

// --- Estructura del grafo (un ejemplo de cada nodo y relacion) ---
// Proveedor y materia prima
MERGE (pv:Proveedor {id: "PROV-001"})
SET pv.nombre = "Aceros del Norte", pv.activo = true;

UNWIND [
  {id: "MP-50", descripcion: "Lamina de acero 1.2mm", fisico: 90.0, reservado: 10.0, reorden: 120.0},
  {id: "MP-51", descripcion: "Tornilleria M6", fisico: 40.0, reservado: 0.0, reorden: 20.0}
] AS row
MERGE (m:Material {id: row.id})
SET m.descripcion = row.descripcion, m.stock_fisico = row.fisico,
    m.stock_reservado = row.reservado, m.punto_reorden = row.reorden, m.unidad_medida = "PZA";

// Producto terminado; la lista de materiales es la relacion REQUIERE
MERGE (pt:ProductoTerminado {id: "PT-100"})
SET pt.descripcion = "Gabinete metalico", pt.stock_fisico = 0.0, pt.bom_vigente = true;

UNWIND [{material_id: "MP-50", cantidad: 4.0}, {material_id: "MP-51", cantidad: 1.0}] AS row
MATCH (pt:ProductoTerminado {id: "PT-100"}), (m:Material {id: row.material_id})
MERGE (pt)-[r:REQUIERE]->(m)
SET r.cantidad_requerida = row.cantidad;

// Orden de compra: apunta a su proveedor y a los materiales que pide
MATCH (pv:Proveedor {id: "PROV-001"})
MERGE (oc:OrdenCompra {id: "OC-001"})
SET oc.estado = "Pendiente", oc.fecha_creacion = datetime("2026-11-10T09:00:00Z")
MERGE (oc)-[:SOLICITADA_A]->(pv);

MATCH (oc:OrdenCompra {id: "OC-001"}), (m:Material {id: "MP-50"})
MERGE (oc)-[i:PIDE]->(m)
SET i.cantidad = 150.0, i.cantidad_recibida = 0.0, i.precio_unitario = 180.5;

// Orden de produccion: apunta al producto y a los componentes que consume
MATCH (pt:ProductoTerminado {id: "PT-100"})
MERGE (op:OrdenProduccion {id: "OP-100"})
SET op.estado = "Planeada", op.cantidad_a_fabricar = 10.0
MERGE (op)-[:PRODUCE]->(pt);

UNWIND [{material_id: "MP-50", requerida: 40.0}, {material_id: "MP-51", requerida: 10.0}] AS row
MATCH (op:OrdenProduccion {id: "OP-100"}), (m:Material {id: row.material_id})
MERGE (op)-[c:CONSUME]->(m)
SET c.cantidad_requerida = row.requerida, c.cantidad_consumida = 0.0;

// --- Validaciones: devuelven filas SOLO si hay violaciones de integridad ---

// El stock fisico nunca puede ser negativo, ni reservarse mas de lo que existe
MATCH (m:Material)
WHERE m.stock_fisico < 0 OR m.stock_reservado < 0 OR m.stock_reservado > m.stock_fisico
RETURN "stock invalido" AS violacion, m.id AS nodo;

// Cantidades y precios de la OC deben ser >= 0
MATCH (oc:OrdenCompra)-[i:PIDE]->(:Material)
WHERE i.cantidad <= 0 OR i.precio_unitario < 0
RETURN "cantidad o precio invalido" AS violacion, oc.id AS nodo;

// Referencia obligatoria: toda OC con un proveedor activo
MATCH (oc:OrdenCompra)
WHERE NOT EXISTS { MATCH (oc)-[:SOLICITADA_A]->(:Proveedor {activo: true}) }
RETURN "OC sin proveedor activo" AS violacion, oc.id AS nodo;

// Validacion de pago: no hay OC Pagada sin recepcion completa
MATCH (oc:OrdenCompra)-[i:PIDE]->(:Material)
WHERE oc.estado = "Pagada" AND i.cantidad_recibida < i.cantidad
RETURN "pago sin recepcion" AS violacion, oc.id AS nodo;

// Referencia obligatoria: toda OP con un BOM vigente
MATCH (op:OrdenProduccion)
WHERE NOT EXISTS {
  MATCH (op)-[:PRODUCE]->(pt:ProductoTerminado)
  WHERE pt.bom_vigente = true AND EXISTS { MATCH (pt)-[:REQUIERE]->(:Material) }
}
RETURN "OP sin BOM vigente" AS violacion, op.id AS nodo;

// Reserva de materiales: una OP En Proceso exige el stock ya reservado
MATCH (op:OrdenProduccion)-[c:CONSUME]->(m:Material)
WHERE op.estado = "En Proceso" AND m.stock_reservado < c.cantidad_requerida
RETURN "OP En Proceso sin reserva" AS violacion, op.id AS nodo;

// --- Consultas del MRP ---

// Sugerir OC cuando el disponible cae bajo el punto de reorden
MATCH (m:Material)
WITH m, m.stock_fisico - m.stock_reservado + coalesce(m.stock_transito, 0) AS disponible
WHERE disponible < m.punto_reorden
RETURN m.id AS material, disponible, m.punto_reorden AS punto_reorden;

// Explosion de materiales para 10 unidades de producto terminado
MATCH (pt:ProductoTerminado {id: "PT-100"})-[r:REQUIERE]->(m:Material)
RETURN m.id AS material, r.cantidad_requerida * 10 AS necesaria,
       m.stock_fisico - m.stock_reservado AS disponible;
