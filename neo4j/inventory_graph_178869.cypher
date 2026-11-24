// 1. Crear nodos base y relación de stock en almacén
MERGE (i:Item {itemId: 1, code: "CPU-R7", name: "CPU Ryzen 7", safetyStock: 10})
MERGE (w:Warehouse {warehouseId: 1, name: "Almacén Central"})
MERGE (i)-[s:STORED_IN]->(w)
SET s.quantityOnHand = 8, s.quantityReserved = 2;

// 2. Registrar una transacción de inventario en el grafo
MATCH (i:Item {itemId: 1}), (w:Warehouse {warehouseId: 1})
CREATE (t:InventoryTransaction {
    transactionId: 101,
    type: "SALIDA",
    quantity: 5,
    status: "PROCESADO",
    createdAt: datetime()
})
CREATE (t)-[:AFFECTS_ITEM]->(i)
CREATE (t)-[:FROM_WAREHOUSE]->(w);

// 3. Consulta Cypher para Agente Inteligente: Artículos en stock crítico
MATCH (i:Item)-[s:STORED_IN]->(w:Warehouse)
WHERE (s.quantityOnHand - s.quantityReserved) < i.safetyStock
RETURN i.code AS Codigo, i.name AS Articulo, w.name AS Almacen,
       (s.quantityOnHand - s.quantityReserved) AS Disponible, i.safetyStock AS Minimo;

// 4. Consulta Cypher de trazabilidad: Historial de transacciones de un artículo
MATCH (t:InventoryTransaction)-[:AFFECTS_ITEM]->(i:Item {code: "CPU-R7"})
OPTIONAL MATCH (t)-[:FROM_WAREHOUSE]->(w:Warehouse)
RETURN t.transactionId AS Folio, t.type AS Tipo, t.quantity AS Cantidad, w.name AS Almacen, t.createdAt AS Fecha
ORDER BY t.createdAt DESC;
