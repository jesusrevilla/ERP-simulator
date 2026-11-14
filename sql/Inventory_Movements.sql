CREATE TABLE Inventory_Movements (
    MovementID SERIAL PRIMARY KEY,
    ItemID INT NOT NULL,
    MovementType VARCHAR(20) NOT NULL CHECK (MovementType IN ('ENTRADA', 'SALIDA', 'TRANSFERENCIA')),
    Quantity INT NOT NULL CHECK (Quantity > 0),
    SourceWarehouse VARCHAR(100),
    DestinationWarehouse VARCHAR(100),
    LotOrSerial VARCHAR(50),
    Status VARCHAR(20) NOT NULL DEFAULT 'PROCESADO' CHECK (Status IN ('PROCESADO', 'RECHAZADO')),
    CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_item_master
        FOREIGN KEY (ItemID) 
        REFERENCES Item_Master(ItemID)
);