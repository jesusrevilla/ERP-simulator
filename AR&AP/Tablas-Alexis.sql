-- 1. Catálogo de Condiciones de Pago
CREATE TABLE condiciones_pago (
    id_condicion SERIAL PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL,
    dias INT NOT NULL CHECK (dias >= 0)
);

-- 2. Catálogo de Impuestos
CREATE TABLE impuestos (
    id_impuesto SERIAL PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL,
    tasa DECIMAL(5, 4) NOT NULL CHECK (tasa IN (0.0000, 0.1600))
);
