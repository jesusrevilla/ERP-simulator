-- Consultas de revisión para integridad de inventario, ventas y finanzas.
-- Se basan en las tablas descritas por sql/Inventory_*.sql,
-- sql/Warehouse.sql y AR&AP/azul_ventas.sql.
-- Las definiciones del repositorio son propuestas separadas; ejecutar cada
-- consulta en una base que tenga instalada la tabla correspondiente.

-- Existencias negativas o reservas superiores a las existencias físicas.
-- Las restricciones de Inventory_Stock ya impiden valores negativos;
-- esta consulta ayuda a revisar datos existentes y reservas inconsistentes.
SELECT StockID, ItemID, WarehouseID, BatchID,
       QuantityOnHand, QuantityReserved
FROM Inventory_Stock
WHERE QuantityOnHand < 0
   OR QuantityReserved < 0
   OR QuantityReserved > QuantityOnHand;

-- Salidas pendientes cuya cantidad supera el disponible no reservado.
SELECT t.TransactionID, t.ItemID, t.SourceWarehouseID, t.BatchID,
       t.Quantity,
       (s.QuantityOnHand - s.QuantityReserved) AS AvailableQuantity
FROM Inventory_Transaction AS t
JOIN Inventory_Stock AS s
  ON s.ItemID = t.ItemID
 AND s.WarehouseID = t.SourceWarehouseID
 AND s.BatchID IS NOT DISTINCT FROM t.BatchID
WHERE t.TransactionType = 'SALIDA'
  AND t.Status = 'PENDIENTE'
  AND t.Quantity > (s.QuantityOnHand - s.QuantityReserved);

-- Transferencias pendientes sin origen o destino, o con el mismo almacén.
SELECT TransactionID, ItemID, SourceWarehouseID, DestinationWarehouseID,
       Quantity, Status
FROM Inventory_Transaction
WHERE TransactionType = 'TRANSFERENCIA'
  AND Status = 'PENDIENTE'
  AND (
      SourceWarehouseID IS NULL
      OR DestinationWarehouseID IS NULL
      OR SourceWarehouseID = DestinationWarehouseID
  );

-- Transacciones pendientes que señalan un almacén inactivo.
SELECT t.TransactionID, t.TransactionType, t.SourceWarehouseID,
       source.Name AS SourceName, t.DestinationWarehouseID,
       destination.Name AS DestinationName
FROM Inventory_Transaction AS t
LEFT JOIN Warehouse AS source
  ON source.WarehouseID = t.SourceWarehouseID
LEFT JOIN Warehouse AS destination
  ON destination.WarehouseID = t.DestinationWarehouseID
WHERE t.Status = 'PENDIENTE'
  AND (
      (t.SourceWarehouseID IS NOT NULL
       AND (source.WarehouseID IS NULL OR source.IsActive = FALSE))
      OR
      (t.DestinationWarehouseID IS NOT NULL
       AND (destination.WarehouseID IS NULL OR destination.IsActive = FALSE))
  );

-- Posibles transacciones repetidas con el mismo documento y datos.
-- Son candidatos para revisión: algunas líneas iguales pueden ser válidas.
SELECT ReferenceDocument, ItemID, TransactionType,
       SourceWarehouseID, DestinationWarehouseID, BatchID, Quantity,
       COUNT(*) AS Repetitions
FROM Inventory_Transaction
WHERE ReferenceDocument IS NOT NULL
GROUP BY ReferenceDocument, ItemID, TransactionType,
         SourceWarehouseID, DestinationWarehouseID, BatchID, Quantity
HAVING COUNT(*) > 1;

-- Facturas cuyo cliente no coincide con el cliente del pedido asociado.
SELECT f.factura_id, f.pedido_id,
       f.cliente_id AS cliente_factura,
       p.cliente_id AS cliente_pedido
FROM facturas_cliente AS f
JOIN pedidos_venta AS p
  ON p.pedido_id = f.pedido_id
WHERE f.cliente_id <> p.cliente_id;

-- Cobros aplicados que superan el monto recibido.
SELECT c.cobro_id, c.folio, c.monto,
       SUM(a.monto_aplicado) AS monto_aplicado
FROM cobros AS c
JOIN cobro_aplicacion AS a
  ON a.cobro_id = c.cobro_id
GROUP BY c.cobro_id, c.folio, c.monto
HAVING SUM(a.monto_aplicado) > c.monto;

-- Facturas con aplicaciones de cobro superiores al total de la factura.
SELECT f.factura_id, f.folio, f.total,
       SUM(a.monto_aplicado) AS monto_aplicado
FROM facturas_cliente AS f
JOIN cobro_aplicacion AS a
  ON a.factura_id = f.factura_id
GROUP BY f.factura_id, f.folio, f.total
HAVING SUM(a.monto_aplicado) > f.total;
