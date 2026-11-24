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

-- 3. Tabla de Clientes (Datos Maestros)
CREATE TABLE clientes (
    id_cliente SERIAL PRIMARY KEY,
    codigo VARCHAR(20) UNIQUE NOT NULL,
    razon_social VARCHAR(150) NOT NULL,
    rfc VARCHAR(13) UNIQUE NOT NULL,
    direccion TEXT NOT NULL,
    contacto VARCHAR(100),
    id_condicion INT NOT NULL REFERENCES condiciones_pago(id_condicion),
    limite_credito DECIMAL(12, 2) NOT NULL CHECK (limite_credito >= 0),
    estatus CHAR(1) NOT NULL CHECK (estatus IN ('A', 'I', 'X')) -- A:activo, I:inactivo, X:cancelado
);

-- 4. Tabla de Proveedores (Datos Maestros)
CREATE TABLE proveedores (
    id_proveedor SERIAL PRIMARY KEY,
    codigo VARCHAR(20) UNIQUE NOT NULL,
    razon_social VARCHAR(150) NOT NULL,
    rfc VARCHAR(13) UNIQUE NOT NULL,
    direccion TEXT NOT NULL,
    contacto VARCHAR(100),
    id_condicion INT NOT NULL REFERENCES condiciones_pago(id_condicion),
    estatus CHAR(1) NOT NULL CHECK (estatus IN ('A', 'I', 'X')) -- A: Activo, I: Inactivo, X: Cancelado
);

-- 5. Tabla de Usuarios
CREATE TABLE usuarios (
    id_usuario SERIAL PRIMARY KEY,
    nombre_usuario VARCHAR(50) UNIQUE NOT NULL,
    rol VARCHAR(30) NOT NULL CHECK (rol IN ('ventas', 'compras', 'cobranza', 'pagos', 'administrador')),
    estatus CHAR(1) NOT NULL DEFAULT 'A' CHECK (estatus IN ('A', 'I'))
);
