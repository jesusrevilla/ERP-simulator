-- Tabla de Stock Físico Actual
CREATE TABLE Inventory_Stock (
    StockID SERIAL PRIMARY KEY,
    ItemID INT NOT NULL,
    Warehouse VARCHAR(100) NOT NULL,
    QuantityAvailable INT NOT NULL CHECK (QuantityAvailable >= 0),
    LastUpdated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_item_stock
        FOREIGN KEY (ItemID)
        REFERENCES Item_Master(ItemID),
    CONSTRAINT unique_item_warehouse 
        UNIQUE (ItemID, Warehouse)
);

-- Tabla de Transacciones
CREATE TABLE Inventory_Transaction (
    TransactionID SERIAL PRIMARY KEY,
    MovementID INT NOT NULL,
    TransactionDate TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Effect VARCHAR(10) NOT NULL CHECK (Effect IN ('ADD', 'SUBTRACT')),
    Quantity INT NOT NULL,
    WarehouseAffected VARCHAR(100) NOT NULL,
    CONSTRAINT fk_movement_transaction
        FOREIGN KEY (MovementID)
        REFERENCES Inventory_Movements(MovementID)
);