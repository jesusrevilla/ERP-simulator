-- 1. Tabla Maestra de Artículos
CREATE TABLE Item_Master (
    ItemID SERIAL PRIMARY KEY,
    SKU VARCHAR(50) UNIQUE NOT NULL,
    Description TEXT NOT NULL,
    LifecycleStatus VARCHAR(20) DEFAULT 'En Desarrollo', -- Estados: Activo, Obsoleto, En Desarrollo
    BaseUoM VARCHAR(10) NOT NULL,
    SupplierID INT,
    LeadTimeDays INT,
    CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Tabla de Movimientos
CREATE TABLE Inventory_Movements (
    MovementID SERIAL PRIMARY KEY,
    MovementType VARCHAR(20) NOT NULL CHECK (MovementType IN ('ENTRADA', 'SALIDA', 'TRANSFERENCIA')),
    RequestedBy VARCHAR(100),
    Status VARCHAR(20) DEFAULT 'PROCESADO',
    CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Tabla de Stock Físico Actual
CREATE TABLE Inventory_Stock (
    StockID SERIAL PRIMARY KEY,
    ItemID INT NOT NULL,
    Warehouse VARCHAR(100) NOT NULL,
    QuantityAvailable INT NOT NULL CHECK (QuantityAvailable >= 0), -- Regla: Cero Inventario Negativo
    LastUpdated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_item_stock
        FOREIGN KEY (ItemID)
        REFERENCES Item_Master(ItemID),
    CONSTRAINT unique_item_warehouse 
        UNIQUE (ItemID, Warehouse)
);

-- 4. Tabla de Transacciones (CORREGIDA: Se añadió ItemID)
CREATE TABLE Inventory_Transaction (
    TransactionID SERIAL PRIMARY KEY,
    MovementID INT NOT NULL,
    ItemID INT NOT NULL, -- Dato indispensable para saber qué artículo se está moviendo
    TransactionDate TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Effect VARCHAR(10) NOT NULL CHECK (Effect IN ('ADD', 'SUBTRACT')),
    Quantity INT NOT NULL,
    WarehouseAffected VARCHAR(100) NOT NULL,
    CONSTRAINT fk_movement_transaction
        FOREIGN KEY (MovementID)
        REFERENCES Inventory_Movements(MovementID),
    CONSTRAINT fk_item_transaction
        FOREIGN KEY (ItemID)
        REFERENCES Item_Master(ItemID)
);

-- 5. Función y Trigger para automatizar el cálculo de stock (Flujo del Jefe de Almacén)
CREATE OR REPLACE FUNCTION fn_process_inventory_transaction()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.Effect = 'ADD' THEN
        -- Entrada o suma por transferencia
        INSERT INTO Inventory_Stock (ItemID, Warehouse, QuantityAvailable)
        VALUES (NEW.ItemID, NEW.WarehouseAffected, NEW.Quantity)
        ON CONFLICT (ItemID, Warehouse)
        DO UPDATE SET 
            QuantityAvailable = Inventory_Stock.QuantityAvailable + NEW.Quantity,
            LastUpdated = CURRENT_TIMESTAMP;

    ELSIF NEW.Effect = 'SUBTRACT' THEN
        -- Salida o resta por transferencia
        UPDATE Inventory_Stock
        SET QuantityAvailable = QuantityAvailable - NEW.Quantity,
            LastUpdated = CURRENT_TIMESTAMP
        WHERE ItemID = NEW.ItemID AND Warehouse = NEW.WarehouseAffected;

        -- Si no existe registro previo en stock para descontar
        IF NOT FOUND THEN
            RAISE EXCEPTION 'Stock no encontrado para ItemID % en el almacén %', NEW.ItemID, NEW.WarehouseAffected;
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_inventory_transaction_after_insert
AFTER INSERT ON Inventory_Transaction
FOR EACH ROW
EXECUTE FUNCTION fn_process_inventory_transaction();