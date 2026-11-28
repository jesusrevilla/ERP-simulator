CREATE TABLE Inventory_Transaction (
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
 
    CONSTRAINT fk_trans_item_master
        FOREIGN KEY (ItemID)
        REFERENCES Item_Master(ItemID),
    CONSTRAINT fk_trans_source_warehouse
        FOREIGN KEY (SourceWarehouseID)
        REFERENCES Warehouse(WarehouseID),
    CONSTRAINT fk_trans_dest_warehouse
        FOREIGN KEY (DestinationWarehouseID)
        REFERENCES Warehouse(WarehouseID),
    CONSTRAINT fk_trans_item_batch
        FOREIGN KEY (BatchID)
        REFERENCES Item_Batch(BatchID)
);
