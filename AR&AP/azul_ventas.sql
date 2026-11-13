-- pedidos de venta
CREATE TABLE pedidos_venta (
    pedido_id SERIAL PRIMARY KEY,
    folio VARCHAR(20) UNIQUE NOT NULL,
    cliente_id INT NOT NULL REFERENCES clientes(id_cliente) ON DELETE RESTRICT,
    fecha DATE NOT NULL,
    estatus CHAR(1) DEFAULT 'A' CHECK (estatus IN ('A','C','X')),  -- A=abierto, C=cerrado, X=cancelado
    subtotal NUMERIC(12,2) NOT NULL CHECK (subtotal >= 0),
    iva NUMERIC(12,2) NOT NULL CHECK (iva >= 0),
    total NUMERIC(12,2) NOT NULL CHECK (total >= 0),
    creado_por VARCHAR(50),
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    modificado_por VARCHAR(50),
    CHECK (total = subtotal + iva)
);

-- lineas de pedido de venta
CREATE TABLE pedido_linea (
    linea_id SERIAL PRIMARY KEY,
    pedido_id INT NOT NULL REFERENCES pedidos_venta(pedido_id) ON DELETE RESTRICT,
    articulo VARCHAR(100) NOT NULL,
    cantidad NUMERIC(10,2) NOT NULL CHECK (cantidad > 0),
    precio_unitario NUMERIC(10,2) NOT NULL CHECK (precio_unitario >= 0),
    cantidad_facturada NUMERIC(10,2) DEFAULT 0 CHECK (cantidad_facturada >= 0),
    CHECK (cantidad_facturada <= cantidad)
);

-- facturas de cliente
CREATE TABLE facturas_cliente (
    factura_id SERIAL PRIMARY KEY,
    folio VARCHAR(20) UNIQUE NOT NULL,
    cliente_id INT NOT NULL REFERENCES clientes(id_cliente) ON DELETE RESTRICT,
    pedido_id INT REFERENCES pedidos_venta(pedido_id) ON DELETE RESTRICT,
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

-- lineas de factura de cliente
CREATE TABLE factura_cliente_linea (
    linea_id SERIAL PRIMARY KEY,
    factura_id INT NOT NULL REFERENCES facturas_cliente(factura_id) ON DELETE RESTRICT,
    pedido_linea_id INT REFERENCES pedido_linea(linea_id) ON DELETE RESTRICT,
    articulo VARCHAR(100) NOT NULL,
    cantidad NUMERIC(10,2) NOT NULL CHECK (cantidad > 0),
    precio_unitario NUMERIC(10,2) NOT NULL CHECK (precio_unitario >= 0)
);

-- cobros (pagos recibidos de clientes)
CREATE TABLE cobros (
    cobro_id SERIAL PRIMARY KEY,
    folio VARCHAR(20) UNIQUE NOT NULL,
    cliente_id INT NOT NULL REFERENCES clientes(id_cliente) ON DELETE RESTRICT,
    fecha DATE NOT NULL,
    monto NUMERIC(12,2) NOT NULL CHECK (monto > 0),
    metodo_pago VARCHAR(20) NOT NULL,  -- transferencia, cheque, efectivo, etc.
    creado_por VARCHAR(50),
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    modificado_por VARCHAR(50)
);

-- aplicación de cobros a facturas
CREATE TABLE cobro_aplicacion (
    aplicacion_id SERIAL PRIMARY KEY,
    cobro_id INT NOT NULL REFERENCES cobros(cobro_id) ON DELETE RESTRICT,
    factura_id INT NOT NULL REFERENCES facturas_cliente(factura_id) ON DELETE RESTRICT,
    monto_aplicado NUMERIC(12,2) NOT NULL CHECK (monto_aplicado > 0),
    UNIQUE(cobro_id, factura_id) 
);

-- notas de crédito de cliente
CREATE TABLE notas_credito_cliente (
    nota_id SERIAL PRIMARY KEY,
    folio VARCHAR(20) UNIQUE NOT NULL,
    factura_id INT REFERENCES facturas_cliente(factura_id) ON DELETE RESTRICT,
    cliente_id INT NOT NULL REFERENCES clientes(id_cliente) ON DELETE RESTRICT,
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

-- indices para optimizar el rendimiento
CREATE INDEX idx_pedido_cliente ON pedidos_venta(cliente_id);
CREATE INDEX idx_pedido_fecha ON pedidos_venta(fecha);
CREATE INDEX idx_pedido_estatus ON pedidos_venta(estatus);
CREATE INDEX idx_pedidolinea_pedido ON pedido_linea(pedido_id);
CREATE INDEX idx_factura_cliente ON facturas_cliente(cliente_id);
CREATE INDEX idx_factura_vencimiento ON facturas_cliente(fecha_vencimiento);
CREATE INDEX idx_factura_estatus ON facturas_cliente(estatus);
CREATE INDEX idx_cobro_cliente ON cobros(cliente_id);
CREATE INDEX idx_cobroaplicacion_factura ON cobro_aplicacion(factura_id);
