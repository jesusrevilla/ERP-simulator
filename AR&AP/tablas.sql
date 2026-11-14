-- TABLA: Órdenes de Compra
CREATE TABLE ordenes_compra (
    oc_id SERIAL PRIMARY KEY,
    folio VARCHAR(20) UNIQUE NOT NULL,
    proveedor_id INT NOT NULL REFERENCES proveedores(id_proveedor) ON DELETE RESTRICT,
    fecha DATE NOT NULL,
    estatus CHAR(1) DEFAULT 'A' CHECK (estatus IN ('A','C','X')),  -- A=Abierto, C=Cerrado, X=Cancelado
    subtotal NUMERIC(12,2) NOT NULL CHECK (subtotal >= 0),
    iva NUMERIC(12,2) NOT NULL CHECK (iva >= 0),
    total NUMERIC(12,2) NOT NULL CHECK (total >= 0),
    creado_por VARCHAR(50),
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    modificado_por VARCHAR(50),
    CHECK (total = subtotal + iva)
);

-- TABLA: Líneas de Orden de Compra
CREATE TABLE oc_linea (
    linea_id SERIAL PRIMARY KEY,
    oc_id INT NOT NULL REFERENCES ordenes_compra(oc_id) ON DELETE RESTRICT,
    articulo VARCHAR(100) NOT NULL,
    cantidad NUMERIC(10,2) NOT NULL CHECK (cantidad > 0),
    precio_unitario NUMERIC(10,2) NOT NULL CHECK (precio_unitario >= 0),
    cantidad_recibida NUMERIC(10,2) DEFAULT 0 CHECK (cantidad_recibida >= 0),
    cantidad_facturada NUMERIC(10,2) DEFAULT 0 CHECK (cantidad_facturada >= 0),
    CHECK (cantidad_recibida <= cantidad),
    CHECK (cantidad_facturada <= cantidad),
    CHECK (cantidad_facturada <= cantidad_recibida)
);

-- TABLA: Recepciones de Mercancía
CREATE TABLE recepciones (
    recepcion_id SERIAL PRIMARY KEY,
    folio VARCHAR(20) UNIQUE NOT NULL,
    oc_id INT NOT NULL REFERENCES ordenes_compra(oc_id) ON DELETE RESTRICT,
    fecha DATE NOT NULL,
    estatus CHAR(1) DEFAULT 'A' CHECK (estatus IN ('A','C','X')),
    creado_por VARCHAR(50),
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    modificado_por VARCHAR(50)
);

-- TABLA: Líneas de Recepción
CREATE TABLE recepcion_linea (
    linea_id SERIAL PRIMARY KEY,
    recepcion_id INT NOT NULL REFERENCES recepciones(recepcion_id) ON DELETE RESTRICT,
    oc_linea_id INT NOT NULL REFERENCES oc_linea(linea_id) ON DELETE RESTRICT,
    articulo VARCHAR(100) NOT NULL,
    cantidad_recibida NUMERIC(10,2) NOT NULL CHECK (cantidad_recibida > 0)
);

-- TABLA: Facturas de Proveedor
CREATE TABLE facturas_proveedor (
    factura_id SERIAL PRIMARY KEY,
    folio VARCHAR(20) UNIQUE NOT NULL,
    proveedor_id INT NOT NULL REFERENCES proveedores(id_proveedor) ON DELETE RESTRICT,
    recepcion_id INT REFERENCES recepciones(recepcion_id) ON DELETE RESTRICT,
    oc_id INT REFERENCES ordenes_compra(oc_id) ON DELETE RESTRICT,
    fecha DATE NOT NULL,
    fecha_vencimiento DATE NOT NULL CHECK (fecha_vencimiento >= fecha),
    estatus CHAR(1) DEFAULT 'A' CHECK (estatus IN ('A','C','X')),
    subtotal NUMERIC(12,2) NOT NULL CHECK (subtotal >= 0),
    iva NUMERIC(12,2) NOT NULL CHECK (iva >= 0),
    total NUMERIC(12,2) NOT NULL CHECK (total >= 0),
    saldo NUMERIC(12,2) NOT NULL CHECK (saldo >= 0),
    creado_por VARCHAR(50),
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    modificado_por VARCHAR(50),
    CHECK (total = subtotal + iva),
    CHECK (saldo <= total)
);

-- TABLA: Líneas de Factura de Proveedor
CREATE TABLE factura_proveedor_linea (
    linea_id SERIAL PRIMARY KEY,
    factura_id INT NOT NULL REFERENCES facturas_proveedor(factura_id) ON DELETE RESTRICT,
    oc_linea_id INT REFERENCES oc_linea(linea_id) ON DELETE RESTRICT,
    articulo VARCHAR(100) NOT NULL,
    cantidad NUMERIC(10,2) NOT NULL CHECK (cantidad > 0),
    precio_unitario NUMERIC(10,2) NOT NULL CHECK (precio_unitario >= 0)
);

-- TABLA: Pagos a Proveedores
CREATE TABLE pagos (
    pago_id SERIAL PRIMARY KEY,
    folio VARCHAR(20) UNIQUE NOT NULL,
    proveedor_id INT NOT NULL REFERENCES proveedores(id_proveedor) ON DELETE RESTRICT,
    fecha DATE NOT NULL,
    monto NUMERIC(12,2) NOT NULL CHECK (monto > 0),
    metodo_pago VARCHAR(20) NOT NULL,  -- 'Transferencia', 'Cheque', 'Efectivo'
    creado_por VARCHAR(50),
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    modificado_por VARCHAR(50)
);

-- TABLA: Aplicación de Pagos a Facturas
CREATE TABLE pago_aplicacion (
    aplicacion_id SERIAL PRIMARY KEY,
    pago_id INT NOT NULL REFERENCES pagos(pago_id) ON DELETE RESTRICT,
    factura_id INT NOT NULL REFERENCES facturas_proveedor(factura_id) ON DELETE RESTRICT,
    monto_aplicado NUMERIC(12,2) NOT NULL CHECK (monto_aplicado > 0),
    UNIQUE(pago_id, factura_id)  -- No se puede aplicar el mismo pago dos veces a la misma factura
);

-- TABLA: Notas de Crédito de Proveedor
CREATE TABLE notas_credito_proveedor (
    nota_id SERIAL PRIMARY KEY,
    folio VARCHAR(20) UNIQUE NOT NULL,
    factura_id INT REFERENCES facturas_proveedor(factura_id) ON DELETE RESTRICT,
    proveedor_id INT NOT NULL REFERENCES proveedores(id_proveedor) ON DELETE RESTRICT,
    fecha DATE NOT NULL,
    motivo VARCHAR(200) NOT NULL,
    subtotal NUMERIC(12,2) NOT NULL CHECK (subtotal > 0),
    iva NUMERIC(12,2) NOT NULL CHECK (iva >= 0),
    total NUMERIC(12,2) NOT NULL CHECK (total > 0),
    creado_por VARCHAR(50),
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    modificado_por VARCHAR(50),
    CHECK (total = subtotal + iva)
);

-- ÍNDICES PARA MEJOR RENDIMIENTO
CREATE INDEX idx_oc_proveedor ON ordenes_compra(proveedor_id);
CREATE INDEX idx_oc_fecha ON ordenes_compra(fecha);
CREATE INDEX idx_oc_estatus ON ordenes_compra(estatus);
CREATE INDEX idx_oclinea_oc ON oc_linea(oc_id);
CREATE INDEX idx_recepcion_oc ON recepciones(oc_id);
CREATE INDEX idx_factura_proveedor ON facturas_proveedor(proveedor_id);
CREATE INDEX idx_factura_vencimiento ON facturas_proveedor(fecha_vencimiento);
CREATE INDEX idx_factura_estatus ON facturas_proveedor(estatus);
CREATE INDEX idx_pago_proveedor ON pagos(proveedor_id);
CREATE INDEX idx_pagoaplicacion_factura ON pago_aplicacion(factura_id);