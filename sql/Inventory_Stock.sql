CREATE TABLE Inventory_Stock (
    StockID SERIAL PRIMARY KEY,
    ItemID INT NOT NULL,
    WarehouseID INT NOT NULL,
    BatchID INT,
    QuantityOnHand NUMERIC(12, 2) NOT NULL DEFAULT 0.00 CHECK (QuantityOnHand >= 0),
    QuantityReserved NUMERIC(12, 2) NOT NULL DEFAULT 0.00 CHECK (QuantityReserved >= 0),
    LastUpdated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 
    CONSTRAINT fk_stock_item_master
        FOREIGN KEY (ItemID)
        REFERENCES Item_Master(ItemID),
    CONSTRAINT fk_stock_warehouse
        FOREIGN KEY (WarehouseID)
        REFERENCES Warehouse(WarehouseID),
    CONSTRAINT fk_stock_item_batch
        FOREIGN KEY (BatchID)
        REFERENCES Item_Batch(BatchID),
    CONSTRAINT uq_item_warehouse_batch
        UNIQUE (ItemID, WarehouseID, BatchID)
);
