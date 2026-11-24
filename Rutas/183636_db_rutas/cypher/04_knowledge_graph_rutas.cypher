// ============================================================================
// Issue #249 - Knowledge Graph de Rutas Operativas (Neo4j / Cypher)
// Matrícula: 183636
// ============================================================================

// 1. Carga de Nodos (Idempotente con MERGE)
MERGE (p:Producto {sku: 'SKU-1001', nombre: 'Chasis Industrial X1'})

MERGE (r1:Ruta {codigo: 'RUT-CHASIS-A', tipo: 'Principal'})
MERGE (r2:Ruta {codigo: 'RUT-CHASIS-B', tipo: 'Alternativa'})

MERGE (e1:EstacionTrabajo {codigo: 'EST-CORTE', nombre: 'Corte CNC', estado: 'ACTIVA'})
MERGE (e2:EstacionTrabajo {codigo: 'EST-SOLD',  nombre: 'Soldadura Robotizada', estado: 'ACTIVA'})
MERGE (e3:EstacionTrabajo {codigo: 'EST-ENS',   nombre: 'Ensamble Final', estado: 'ACTIVA'})
MERGE (e4:EstacionTrabajo {codigo: 'EST-CAL',   nombre: 'Inspección de Calidad', estado: 'ACTIVA'})

MERGE (op1:Operacion {id: 'OP-A1', nombre: 'Corte de lámina principal', tiempo_min: 60})
MERGE (op2:Operacion {id: 'OP-A2', nombre: 'Soldadura estructural', tiempo_min: 125})
MERGE (op3:Operacion {id: 'OP-A3', nombre: 'Ensamble de componentes', tiempo_min: 70})
MERGE (op4:Operacion {id: 'OP-A4', nombre: 'Prueba de tolerancias', tiempo_min: 40})

MERGE (op5:Operacion {id: 'OP-B1', nombre: 'Corte de lámina modular', tiempo_min: 50})
MERGE (op6:Operacion {id: 'OP-B2', nombre: 'Ensamble modular rápido', tiempo_min: 85})
MERGE (op7:Operacion {id: 'OP-B3', nombre: 'Prueba de tolerancias', tiempo_min: 35})

// 2. Creación de Relaciones
MERGE (p)-[:USA_RUTA]->(r1)
MERGE (p)-[:USA_RUTA]->(r2)

MERGE (r1)-[:INCLUYE {secuencia: 1}]->(op1)
MERGE (r1)-[:INCLUYE {secuencia: 2}]->(op2)
MERGE (r1)-[:INCLUYE {secuencia: 3}]->(op3)
MERGE (r1)-[:INCLUYE {secuencia: 4}]->(op4)

MERGE (op1)-[:PRECEDE_A {tiempo_traslado_min: 5}]->(op2)
MERGE (op2)-[:PRECEDE_A {tiempo_traslado_min: 10}]->(op3)
MERGE (op3)-[:PRECEDE_A {tiempo_traslado_min: 5}]->(op4)

MERGE (op1)-[:SE_EJECUTA_EN]->(e1)
MERGE (op2)-[:SE_EJECUTA_EN]->(e2)
MERGE (op3)-[:SE_EJECUTA_EN]->(e3)
MERGE (op4)-[:SE_EJECUTA_EN]->(e4)

MERGE (r2)-[:INCLUYE {secuencia: 1}]->(op5)
MERGE (r2)-[:INCLUYE {secuencia: 2}]->(op6)
MERGE (r2)-[:INCLUYE {secuencia: 3}]->(op7)

MERGE (op5)-[:PRECEDE_A {tiempo_traslado_min: 5}]->(op6)
MERGE (op6)-[:PRECEDE_A {tiempo_traslado_min: 5}]->(op7)

MERGE (op5)-[:SE_EJECUTA_EN]->(e1)
MERGE (op6)-[:SE_EJECUTA_EN]->(e3)
MERGE (op7)-[:SE_EJECUTA_EN]->(e4);

// ============================================================================
// CONSULTAS CYPHER PARA AGENTES INTELIGENTES
// ============================================================================

// Consulta 1: Análisis de impacto si falla la estación de Soldadura ('EST-SOLD')
MATCH (p:Producto)-[:USA_RUTA]->(r:Ruta)-[:INCLUYE]->(op:Operacion)-[:SE_EJECUTA_EN]->(e:EstacionTrabajo {codigo: 'EST-SOLD'})
RETURN p.sku AS ProductoAfectado, r.codigo AS RutaImpactada, op.nombre AS OperacionBloqueada;

// Consulta 2: Encontrar rutas alternativas para 'SKU-1001' que NO pasen por 'EST-SOLD'
MATCH (p:Producto {sku: 'SKU-1001'})-[:USA_RUTA]->(r:Ruta)-[:INCLUYE]->(op:Operacion)
WHERE NOT EXISTS {
    MATCH (r)-[:INCLUYE]->(:Operacion)-[:SE_EJECUTA_EN]->(:EstacionTrabajo {codigo: 'EST-SOLD'})
}
RETURN r.codigo AS RutaAlternativa, SUM(op.tiempo_min) AS TiempoTotalMin
ORDER BY TiempoTotalMin ASC;