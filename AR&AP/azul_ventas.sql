CREATE TABLE IF NOT EXISTS pedidos_venta (
    id_pedido SERIAL PRIMARY KEY,
    folio VARCHAR(30) NOT NULL,
    id_cliente INT NOT NULL,
    fecha DATE NOT NULL DEFAULT CURRENT_DATE,
    estatus CHAR(1) DEFAULT 'A' CHECK (estatus IN ('A', 'C', 'X')), -- A: Abierto, C: Cerrado, X: Cancelado
    subtotal DECIMAL(12,2) NOT NULL CHECK (subtotal >= 0),
    iva DECIMAL(12,2) NOT NULL CHECK (iva >= 0),
    total DECIMAL(12,2) NOT NULL CHECK (total >= 0),
    creado_por VARCHAR(50) NOT NULL,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    modificado_por VARCHAR(50),
    CONSTRAINT uq_pedido_folio UNIQUE (folio),
    FOREIGN KEY (id_cliente) REFERENCES clientes(id_cliente) ON DELETE RESTRICT
);