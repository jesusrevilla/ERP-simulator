CREATE TABLE clientes(
    id_cliente SERIAL PRIMARY KEY,
    codigo VARCHAR(20) UNIQUE NO NULL,
    razon_social VARCHAR(150) NOT NULL,
    rfc VARCHAR(13) UNIQUE NOT NULL,
    direccion TEXT NOT NULL,
    contacto VARCHAR(100),
    id_condicion INT NOT NULL REFERENCES condiciones_pago(id_condicion),
    limite_credito DECIMAL(12, 2) NOT NULL CHECK (limite_credito >= 0),
    estatus CHAR(1) NOT NULL CHECK (estatus IN('A','I','X'))
);
    
    