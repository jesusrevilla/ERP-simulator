-- Componente: Tablas Warehouse e Item_Batch (Matrícula: 179091)
-- Depende de: Item_Master (ItemID)

CREATE TABLE IF NOT EXISTS Warehouse (
    WarehouseID SERIAL PRIMARY KEY,
    WarehouseCode VARCHAR(20) NOT NULL UNIQUE,
    Name VARCHAR(100) NOT NULL,
    Location VARCHAR(200),
    WarehouseType VARCHAR(50) NOT NULL DEFAULT 'GENERAL'
        CHECK (WarehouseType IN ('GENERAL', 'MATERIA_PRIMA', 'PRODUCTO_TERMINADO', 'CUARENTENA')),
    IsActive BOOLEAN NOT NULL DEFAULT TRUE,
    CreatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS Item_Batch (
    BatchID SERIAL PRIMARY KEY,
    ItemID INT NOT NULL,
    BatchNumber VARCHAR(50) NOT NULL UNIQUE,
    ManufacturingDate DATE,
    ExpirationDate DATE,
    Status VARCHAR(20) NOT NULL DEFAULT 'DISPONIBLE'
        CHECK (Status IN ('DISPONIBLE', 'BLOQUEADO', 'VENCIDO', 'AGOTADO')),
    CreatedAt TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_batch_item_master
        FOREIGN KEY (ItemID)
        REFERENCES Item_Master(ItemID),

    CONSTRAINT chk_batch_dates
        CHECK (
            ExpirationDate IS NULL
            OR ManufacturingDate IS NULL
            OR ExpirationDate >= ManufacturingDate
        )
);
