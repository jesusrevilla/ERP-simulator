-- cuentas contables
CREATE TABLE cuentas_contables (
    cuenta_id  SERIAL PRIMARY KEY,
    codigo VARCHAR(10)UNIQUE NOT NULL,
    nombre VARCHAR(100)NOT NULL,
    tipo CHAR(1)NOT NULL CHECK (tipo IN ('A','P','C','I','G')),  -- A=Activo, P=Pasivo, C=Capital, I=Ingreso, G=Gasto
    activa BOOLEAN NOT NULL DEFAULT TRUE
);
-- asiento contable
CREATE TABLE asientos_contables (
    asiento_id SERIAL PRIMARY KEY,
    tipo_doc VARCHAR(30) NOT NULL,   -- FACT_CLI, COBRO, FACT_PROV, PAGO_PROV
    folio VARCHAR(20) NOT NULL,
    fecha DATE NOT NULL,
    descripcion VARCHAR(200),
    estatus CHAR(1) DEFAULT 'A' CHECK (estatus IN ('A','C','X')),  -- A=Abierto, C=Cerrado, X=Cancelado
    creado_por VARCHAR(50),
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    modificado_por VARCHAR(50),
    UNIQUE (tipo_doc, folio)
);
-- lineas del asiento (cargos y abonos)
CREATE TABLE detalle_asiento (
    detalle_id SERIAL PRIMARY KEY,
    asiento_id INT NOT NULL REFERENCES asientos_contables(asiento_id)ON DELETE RESTRICT,
    cuenta_id  INT NOT NULL REFERENCES cuentas_contables(cuenta_id)ON DELETE RESTRICT,
    cargo NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (cargo >= 0),
    abono NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (abono >= 0),
    CHECK ((cargo > 0 AND abono = 0) OR (abono > 0 AND cargo = 0))
);
-- bitacora
CREATE TABLE bitacora (
    bitacora_id BIGSERIAL PRIMARY KEY,
    tabla VARCHAR(50) NOT NULL,
    operacion CHAR(1) NOT NULL CHECK (operacion IN ('I','U','D')),  -- I=Insert, U=Update, D=Delete
    registro_id VARCHAR(50),
    usuario VARCHAR(50) NOT NULL,
    fecha TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,
    datos_anteriores JSONB,
    datos_nuevos     JSONB
);
-- indices
CREATE INDEX idx_detalle_asiento ON detalle_asiento(asiento_id);
CREATE INDEX idx_detalle_cuenta ON detalle_asiento(cuenta_id);
CREATE INDEX idx_asiento_fecha ON asientos_contables(fecha);
CREATE INDEX idx_bitacora_tabla ON bitacora(tabla, registro_id);
-- Cuentas que usan los asientos
INSERT INTO cuentas_contables (codigo, nombre, tipo) VALUES
    ('1100', 'Clientes',        'A'),
    ('1200', 'Bancos',          'A'),
    ('1300', 'Inventario',      'A'),
    ('1400', 'IVA acreditable', 'A'),
    ('2100', 'Proveedores',     'P'),
    ('2200', 'IVA trasladado',  'P'),
    ('4100', 'Ventas',          'I');