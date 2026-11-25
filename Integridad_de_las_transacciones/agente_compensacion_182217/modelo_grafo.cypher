// ============================================================================
// Knowledge Graph - Agente de Compensación Transaccional y Deadlocks (182217)
// Módulo: Integridad_de_las_transacciones
// ============================================================================

// 1. Limpieza selectiva (solo nodos del escenario ERP)
MATCH (n)
WHERE n:OrdenVenta OR n:Transaccion OR n:MovimientoInventario
   OR n:CuentaPorCobrar OR n:PolizaContable OR n:Compensacion OR n:AlertaIntegridad
DETACH DELETE n;

// 2. Restricciones de unicidad
CREATE CONSTRAINT orden_venta_id IF NOT EXISTS FOR (o:OrdenVenta) REQUIRE o.id IS UNIQUE;
CREATE CONSTRAINT transaccion_id IF NOT EXISTS FOR (t:Transaccion) REQUIRE t.id IS UNIQUE;
CREATE CONSTRAINT poliza_id IF NOT EXISTS FOR (p:PolizaContable) REQUIRE p.id IS UNIQUE;

// 3. Carga de 4 escenarios de prueba
// ESCENARIO 1: Transacción íntegra (sana)
CREATE (o1:OrdenVenta {id: 'OV-101', cliente: 'Aceros Potosí', total: 1500.0})
CREATE (t1:Transaccion {id: 'TX-1001', estado: 'COMPLETADA', modulo: 'VENTAS'})
CREATE (i1:MovimientoInventario {id: 'INV-101', producto: 'Valvula-Industrial', cantidad: -10, estado: 'APLICADO'})
CREATE (c1:CuentaPorCobrar {id: 'CXC-101', monto: 1500.0, estado: 'ACTIVA'})
CREATE (p1:PolizaContable {id: 'POL-101', tipo: 'NORMAL', cargos: 1500.0, abonos: 1500.0, estado: 'CUADRADA'})
CREATE (o1)-[:GENERA]->(t1)
CREATE (t1)-[:AFECTA_INVENTARIO]->(i1)
CREATE (t1)-[:GENERA_CXC]->(c1)
CREATE (t1)-[:REGISTRA_POLIZA]->(p1)

// ESCENARIO 2: Transacción fallida a mitad de flujo (requiere Patrón Saga)
CREATE (o2:OrdenVenta {id: 'OV-102', cliente: 'Manufacturas SLP', total: 4200.0})
CREATE (t2:Transaccion {id: 'TX-1002', estado: 'FALLIDA', modulo: 'VENTAS', error: 'Timeout en pasarela bancaria'})
CREATE (i2:MovimientoInventario {id: 'INV-102', producto: 'Sensor-Presion', cantidad: -5, estado: 'APLICADO'})
CREATE (c2:CuentaPorCobrar {id: 'CXC-102', monto: 4200.0, estado: 'ACTIVA'})
CREATE (p2:PolizaContable {id: 'POL-102', tipo: 'NORMAL', cargos: 4200.0, abonos: 4200.0, estado: 'PENDIENTE'})
CREATE (o2)-[:GENERA]->(t2)
CREATE (t2)-[:AFECTA_INVENTARIO]->(i2)
CREATE (t2)-[:GENERA_CXC]->(c2)
CREATE (t2)-[:REGISTRA_POLIZA]->(p2)

// ESCENARIO 3: Póliza descuadrada (incumple Partida Doble)
CREATE (o3:OrdenVenta {id: 'OV-103', cliente: 'Logística Bajío', total: 2500.0})
CREATE (t3:Transaccion {id: 'TX-1003', estado: 'COMPLETADA', modulo: 'CONTABILIDAD'})
CREATE (p3:PolizaContable {id: 'POL-103', tipo: 'NORMAL', cargos: 2500.0, abonos: 2000.0, estado: 'PENDIENTE'})
CREATE (o3)-[:GENERA]->(t3)
CREATE (t3)-[:REGISTRA_POLIZA]->(p3)

// ESCENARIO 4: Ciclo de bloqueo mutuo (Deadlock concurrente)
CREATE (t4:Transaccion {id: 'TX-1004', estado: 'EN_PROCESO', modulo: 'INVENTARIO'})
CREATE (t5:Transaccion {id: 'TX-1005', estado: 'EN_PROCESO', modulo: 'INVENTARIO'})
CREATE (t4)-[:BLOQUEA {recurso: 'STOCK-SKU-99'}]->(t5)
CREATE (t5)-[:BLOQUEA {recurso: 'CUENTA-CLI-42'}]->(t4);

// ============================================================================
// CONSULTAS ANALÍTICAS DEL AGENTE (Para verificar en Neo4j AuraDB)
// ============================================================================

// A) Detectar ciclos de Deadlock:
// MATCH p = (t:Transaccion)-[:BLOQUEA*2..5]->(t) RETURN p;

// B) Auditar pólizas descuadradas (Partida Doble):
// MATCH (t:Transaccion)-[:REGISTRA_POLIZA]->(p:PolizaContable)
// WHERE abs(p.cargos - p.abonos) > 0.01 RETURN t, p;

// C) Visualizar todo el grafo resultante tras correr el agente Python:
// MATCH (n)
// WHERE n:OrdenVenta OR n:Transaccion OR n:MovimientoInventario
//    OR n:CuentaPorCobrar OR n:PolizaContable OR n:Compensacion OR n:AlertaIntegridad
// OPTIONAL MATCH (n)-[r]->(m)
// RETURN n, r, m;