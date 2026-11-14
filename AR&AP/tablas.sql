--Tabla ordenenes de compra
CREATE TABLE OrdenesCompra (
    OCID SERIAL PRIMARY KEY,
    Folio VARCHAR(20) UNIQUE NOT NULL,
    ProveedorID INT NOT NULL -- REFERENCES Proveedores(ProveedorID) ON DELETE RESTRICT,
    Fecha DATE NOT NULL,
    Estatus CHAR(1) DEFAULT 'A' CHECK (Estatus IN ('A','C','X')),  -- A=Abierto, C=Cerrado, X=Cancelado
    Subtotal NUMERIC(12,2) NOT NULL CHECK (Subtotal >= 0),
    IVA NUMERIC(12,2) NOT NULL CHECK (IVA >= 0),
    Total NUMERIC(12,2) NOT NULL CHECK (Total >= 0),
    CreadoPor VARCHAR(50),
    FechaCreacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ModificadoPor VARCHAR(50),
    CHECK (Total = Subtotal + IVA)
);