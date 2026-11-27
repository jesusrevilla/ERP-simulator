-- 1. Almacenes activos por tipo
SELECT WarehouseID, WarehouseCode, Name, Location, WarehouseType
FROM Warehouse
WHERE IsActive = TRUE
ORDER BY WarehouseType, WarehouseCode;

-- 2. Lotes disponibles con datos del artículo en Item_Master
SELECT
    b.BatchID,
    b.BatchNumber,
    m.ItemCode,
    m.Name AS ItemName,
    b.ManufacturingDate,
    b.ExpirationDate,
    b.Status
FROM Item_Batch b
JOIN Item_Master m ON b.ItemID = m.ItemID
WHERE b.Status = 'DISPONIBLE'
ORDER BY b.ExpirationDate ASC NULLS LAST;

-- 3. Lotes próximos a vencer en los próximos 30 días
SELECT
    b.BatchNumber,
    m.ItemCode,
    m.Name AS ItemName,
    b.ExpirationDate,
    b.Status
FROM Item_Batch b
JOIN Item_Master m ON b.ItemID = m.ItemID
WHERE b.ExpirationDate IS NOT NULL
  AND b.ExpirationDate <= CURRENT_DATE + INTERVAL '30 days'
  AND b.Status IN ('DISPONIBLE', 'BLOQUEADO');
