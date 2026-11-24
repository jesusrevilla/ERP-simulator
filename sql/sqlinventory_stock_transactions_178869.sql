-- ============================================================================
-- Componente: Control de Existencias y Trazabilidad de Transacciones
-- Matrícula: 178869
-- Motor: PostgreSQL
-- ============================================================================

-- 1. TABLAS PRINCIPALES
CREATE TABLE IF NOT EXISTS Inventory_Stock (
    StockID SERIAL PRIMARY KEY,
    ItemID INT NOT NULL,
    WarehouseID INT NOT NULL,
    BatchID INT,
    QuantityOnHand NUMERIC(12, 2) NOT NULL DEFAULT 0.00 CHECK (QuantityOnHand >= 0),
    QuantityReserved NUMERIC(12, 2) NOT NULL DEFAULT 0.00 CHECK (QuantityReserved >= 0),
    LastUpdated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_stock_item_master FOREIGN KEY (ItemID) REFERENCES Item_Master(ItemID),
    CONSTRAINT fk_stock_warehouse FOREIGN KEY (WarehouseID) REFERENCES Warehouse(WarehouseID),
    CONSTRAINT fk_stock_item_batch FOREIGN KEY (BatchID) REFERENCES Item_Batch(BatchID),
    CONSTRAINT uq_item_warehouse_batch UNIQUE (ItemID, WarehouseID, BatchID)
);

CREATE TABLE IF NOT EXISTS Inventory_Transaction (
    TransactionID SERIAL PRIMARY KEY,
    ItemID INT NOT NULL,
    SourceWarehouseID INT,
    DestinationWarehouseID INT,
    BatchID INT,
    TransactionType VARCHAR(20) NOT NULL CHECK (TransactionType IN ('ENTRADA', 'SALIDA', 'TRANSFERENCIA', 'AJUSTE')),
    Quantity NUMERIC(12, 2) NOT NULL CHECK (Quantity > 0),
    UnitCost NUMERIC(10, 2) DEFAULT 0.00,
    ReferenceDocument VARCHAR(50),
    Status VARCHAR(20) NOT NULL DEFAULT 'PROCESADO' CHECK (Status IN ('PENDIENTE', 'PROCESADO', 'RECHAZADO', 'CANCELADO')),
    CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_trans_item_master FOREIGN KEY (ItemID) REFERENCES Item_Master(ItemID),
    CONSTRAINT fk_trans_source_warehouse FOREIGN KEY (SourceWarehouseID) REFERENCES Warehouse(WarehouseID),
    CONSTRAINT fk_trans_dest_warehouse FOREIGN KEY (DestinationWarehouseID) REFERENCES Warehouse(WarehouseID),
    CONSTRAINT fk_trans_item_batch FOREIGN KEY (BatchID) REFERENCES Item_Batch(BatchID)
);

-- 2. ÍNDICES DE OPTIMIZACIÓN
CREATE INDEX IF NOT EXISTS idx_stock_item_wh ON Inventory_Stock (ItemID, WarehouseID);
CREATE INDEX IF NOT EXISTS idx_trans_item_date ON Inventory_Transaction (ItemID, CreatedAt DESC);
CREATE INDEX IF NOT EXISTS idx_trans_type_status ON Inventory_Transaction (TransactionType, Status);

-- 3. FUNCIÓN Y TRIGGER DE INTEGRIDAD (Actualiza stock automáticamente)
CREATE OR REPLACE FUNCTION fn_update_inventory_stock()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.Status = 'PROCESADO' THEN
        IF NEW.TransactionType = 'ENTRADA' AND NEW.DestinationWarehouseID IS NOT NULL THEN
            INSERT INTO Inventory_Stock (ItemID, WarehouseID, BatchID, QuantityOnHand)
            VALUES (NEW.ItemID, NEW.DestinationWarehouseID, NEW.BatchID, NEW.Quantity)
            ON CONFLICT (ItemID, WarehouseID, BatchID)
            DO UPDATE SET QuantityOnHand = Inventory_Stock.QuantityOnHand + NEW.Quantity,
                          LastUpdated = CURRENT_TIMESTAMP;

        ELSIF NEW.TransactionType = 'SALIDA' AND NEW.SourceWarehouseID IS NOT NULL THEN
            UPDATE Inventory_Stock
            SET QuantityOnHand = QuantityOnHand - NEW.Quantity,
                LastUpdated = CURRENT_TIMESTAMP
            WHERE ItemID = NEW.ItemID
              AND WarehouseID = NEW.SourceWarehouseID
              AND (BatchID = NEW.BatchID OR (BatchID IS NULL AND NEW.BatchID IS NULL));
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_after_inventory_transaction
AFTER INSERT ON Inventory_Transaction
FOR EACH ROW
EXECUTE FUNCTION fn_update_inventory_stock();

-- 4. VISTA ANALÍTICA PARA AGENTES INTELIGENTES (Stock Crítico)
CREATE OR REPLACE VIEW vw_critical_inventory_stock AS
SELECT
    im.ItemID,
    im.ItemCode,
    im.Name AS ItemName,
    w.Name AS WarehouseName,
    s.QuantityOnHand,
    s.QuantityReserved,
    (s.QuantityOnHand - s.QuantityReserved) AS AvailableStock,
    im.SafetyStock
FROM Inventory_Stock s
JOIN Item_Master im ON s.ItemID = im.ItemID
JOIN Warehouse w ON s.WarehouseID = w.WarehouseID
WHERE (s.QuantityOnHand - s.QuantityReserved) < im.SafetyStock;

-- 5. CONSULTAS SQL DE APOYO A DECISIONES
-- Consulta A: Detectar artículos por debajo del stock de seguridad (dispara orden de compra)
SELECT * FROM vw_critical_inventory_stock ORDER BY AvailableStock ASC;

-- Consulta B: Trazabilidad de movimientos recientes por artículo
SELECT
    t.TransactionID,
    im.ItemCode,
    t.TransactionType,
    t.Quantity,
    t.ReferenceDocument,
    t.Status,
    t.CreatedAt
FROM Inventory_Transaction t
JOIN Item_Master im ON t.ItemID = im.ItemID
ORDER BY t.CreatedAt DESC
LIMIT 20;