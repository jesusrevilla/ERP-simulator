DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'resultado_operacion') THEN
        CREATE TYPE resultado_operacion AS (
            exito BOOLEAN,
            mensaje TEXT,
            registro_id BIGINT
        );
    END IF;
END$$;

CREATE TABLE IF NOT EXISTS condiciones_pago (
    codigo VARCHAR(20) PRIMARY KEY,
    descripcion VARCHAR(100) NOT NULL,
    dias_credito INT NOT NULL CHECK (dias_credito >= 0)
);

CREATE TABLE IF NOT EXISTS ordenes_compra (
    oc_id BIGSERIAL PRIMARY KEY,
    proveedor_id BIGINT NOT NULL,
    fecha_emision DATE NOT NULL DEFAULT CURRENT_DATE,
    condicion_pago VARCHAR(20) NOT NULL REFERENCES condiciones_pago(codigo),
    estatus VARCHAR(15) NOT NULL DEFAULT 'A' CHECK (estatus IN ('A', 'P', 'C', 'X')),
    total_oc NUMERIC(14, 2) NOT NULL DEFAULT 0 CHECK (total_oc >= 0)
);

CREATE TABLE IF NOT EXISTS oc_linea (
    oc_linea_id BIGSERIAL PRIMARY KEY,
    oc_id BIGINT NOT NULL REFERENCES ordenes_compra(oc_id) ON DELETE CASCADE,
    articulo VARCHAR(50) NOT NULL,
    cantidad_ordenada NUMERIC(14, 3) NOT NULL CHECK (cantidad_ordenada > 0),
    precio_unitario NUMERIC(14, 2) NOT NULL CHECK (precio_unitario >= 0),
    cantidad_recibida NUMERIC(14, 3) NOT NULL DEFAULT 0 CHECK (cantidad_recibida >= 0),
    cantidad_facturada NUMERIC(14, 3) NOT NULL DEFAULT 0 CHECK (cantidad_facturada >= 0),
    UNIQUE (oc_id, articulo)
);

CREATE TABLE IF NOT EXISTS recepciones (
    recepcion_id BIGSERIAL PRIMARY KEY,
    oc_id BIGINT NOT NULL REFERENCES ordenes_compra(oc_id),
    proveedor_id BIGINT NOT NULL,
    fecha_recepcion DATE NOT NULL DEFAULT CURRENT_DATE,
    usuario_registro VARCHAR(60) NOT NULL
);

CREATE TABLE IF NOT EXISTS recepcion_linea (
    recepcion_linea_id BIGSERIAL PRIMARY KEY,
    recepcion_id BIGINT NOT NULL REFERENCES recepciones(recepcion_id) ON DELETE CASCADE,
    oc_linea_id BIGINT NOT NULL REFERENCES oc_linea(oc_linea_id),
    articulo VARCHAR(50) NOT NULL,
    cantidad_recibida NUMERIC(14, 3) NOT NULL CHECK (cantidad_recibida > 0)
);

CREATE TABLE IF NOT EXISTS facturas_proveedor (
    factura_id BIGSERIAL PRIMARY KEY,
    proveedor_id BIGINT NOT NULL,
    recepcion_id BIGINT NOT NULL REFERENCES recepciones(recepcion_id),
    oc_id BIGINT NOT NULL REFERENCES ordenes_compra(oc_id),
    articulo VARCHAR(50) NOT NULL,
    fecha_emision DATE NOT NULL DEFAULT CURRENT_DATE,
    condicion_pago VARCHAR(20) NOT NULL REFERENCES condiciones_pago(codigo),
    cantidad_facturada NUMERIC(14, 3) NOT NULL CHECK (cantidad_facturada > 0),
    precio_unitario NUMERIC(14, 2) NOT NULL CHECK (precio_unitario >= 0),
    monto_total NUMERIC(14, 2) NOT NULL CHECK (monto_total > 0),
    saldo NUMERIC(14, 2) NOT NULL CHECK (saldo >= 0),
    estatus VARCHAR(15) NOT NULL DEFAULT 'A' CHECK (estatus IN ('A', 'P', 'C')),
    usuario_registro VARCHAR(60) NOT NULL,
    CONSTRAINT chk_fp_saldo_total CHECK (saldo <= monto_total)
);

CREATE TABLE IF NOT EXISTS pagos (
    pago_id BIGSERIAL PRIMARY KEY,
    proveedor_id BIGINT NOT NULL,
    fecha_pago DATE NOT NULL DEFAULT CURRENT_DATE,
    monto_total NUMERIC(14, 2) NOT NULL CHECK (monto_total > 0),
    usuario_registro VARCHAR(60) NOT NULL
);

CREATE TABLE IF NOT EXISTS pago_aplicacion (
    aplicacion_id BIGSERIAL PRIMARY KEY,
    pago_id BIGINT NOT NULL REFERENCES pagos(pago_id) ON DELETE CASCADE,
    factura_id BIGINT NOT NULL REFERENCES facturas_proveedor(factura_id),
    monto_aplicado NUMERIC(14, 2) NOT NULL CHECK (monto_aplicado > 0),
    fecha_aplicacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS facturas_cliente (
    factura_cliente_id BIGSERIAL PRIMARY KEY,
    cliente_id BIGINT NOT NULL,
    pedido_id BIGINT NOT NULL,
    fecha_emision DATE NOT NULL DEFAULT CURRENT_DATE,
    condicion_pago VARCHAR(20) NOT NULL REFERENCES condiciones_pago(codigo),
    monto_total NUMERIC(14, 2) NOT NULL CHECK (monto_total > 0),
    saldo NUMERIC(14, 2) NOT NULL CHECK (saldo >= 0),
    estatus VARCHAR(15) NOT NULL DEFAULT 'A' CHECK (estatus IN ('A', 'P', 'C')),
    CONSTRAINT chk_fc_saldo_total CHECK (saldo <= monto_total)
);

CREATE TABLE IF NOT EXISTS cobros (
    cobro_id BIGSERIAL PRIMARY KEY,
    cliente_id BIGINT NOT NULL,
    fecha_cobro DATE NOT NULL DEFAULT CURRENT_DATE,
    monto_total NUMERIC(14, 2) NOT NULL CHECK (monto_total > 0),
    usuario_registro VARCHAR(60) NOT NULL
);

CREATE TABLE IF NOT EXISTS cobro_aplicacion (
    cobro_aplicacion_id BIGSERIAL PRIMARY KEY,
    cobro_id BIGINT NOT NULL REFERENCES cobros(cobro_id) ON DELETE CASCADE,
    factura_cliente_id BIGINT NOT NULL REFERENCES facturas_cliente(factura_cliente_id),
    monto_aplicado NUMERIC(14, 2) NOT NULL CHECK (monto_aplicado > 0),
    fecha_aplicacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_fp_estatus_saldo ON facturas_proveedor (estatus, saldo);
CREATE INDEX IF NOT EXISTS idx_fc_estatus_saldo ON facturas_cliente (estatus, saldo);
CREATE INDEX IF NOT EXISTS idx_oc_linea_lookup ON oc_linea (oc_id, articulo);
