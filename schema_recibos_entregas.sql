-- ============================================================================
-- SIMULADOR ERP - MÓDULO DE COMPRAS, RECIBOS, ENTREGAS E INVENTARIO
-- Base de Datos Relacional Normalizada (3FN) - PostgreSQL 16+
-- Alumno: 177576 (RamoES12) / Referencia: Primera entrega.md (182234)
-- ============================================================================

BEGIN;

-- ----------------------------------------------------------------------------
-- 1. CATÁLOGOS BASE (Normalización 3FN)
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS unidades_medida (
    id SERIAL PRIMARY KEY,
    codigo VARCHAR(10) NOT NULL UNIQUE,
    nombre VARCHAR(50) NOT NULL,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS almacenes (
    id SERIAL PRIMARY KEY,
    codigo VARCHAR(20) NOT NULL UNIQUE,
    nombre VARCHAR(120) NOT NULL,
    ubicacion_fisica VARCHAR(200),
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ubicaciones_almacen (
    id SERIAL PRIMARY KEY,
    almacen_id INTEGER NOT NULL REFERENCES almacenes(id) ON DELETE RESTRICT,
    codigo_ubicacion VARCHAR(30) NOT NULL,
    zona VARCHAR(60) NOT NULL,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_almacen_ubicacion UNIQUE (almacen_id, codigo_ubicacion)
);

CREATE TABLE IF NOT EXISTS proveedores (
    id SERIAL PRIMARY KEY,
    codigo_proveedor VARCHAR(30) NOT NULL UNIQUE,
    nombre VARCHAR(150) NOT NULL,
    rfc VARCHAR(20) UNIQUE,
    contacto VARCHAR(100),
    telefono VARCHAR(20),
    email VARCHAR(120),
    estatus VARCHAR(20) NOT NULL DEFAULT 'ACTIVO'
        CHECK (estatus IN ('ACTIVO', 'SUSPENDIDO', 'BAJA')),
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_proveedor_estado_coherente CHECK (
        (estatus = 'ACTIVO' AND activo = TRUE) OR
        (estatus IN ('SUSPENDIDO', 'BAJA') AND activo = FALSE)
    )
);

CREATE TABLE IF NOT EXISTS clientes (
    id SERIAL PRIMARY KEY,
    codigo_cliente VARCHAR(30) NOT NULL UNIQUE,
    nombre VARCHAR(150) NOT NULL,
    rfc VARCHAR(20) UNIQUE,
    email VARCHAR(120),
    telefono VARCHAR(20),
    estatus VARCHAR(20) NOT NULL DEFAULT 'ACTIVO'
        CHECK (estatus IN ('ACTIVO', 'SUSPENDIDO', 'BAJA')),
    credito_autorizado BOOLEAN NOT NULL DEFAULT FALSE,
    limite_credito NUMERIC(14, 2) NOT NULL DEFAULT 0.00 CHECK (limite_credito >= 0),
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS productos (
    id SERIAL PRIMARY KEY,
    codigo_sku VARCHAR(40) NOT NULL,
    nombre VARCHAR(150) NOT NULL,
    descripcion TEXT,
    uom_id INTEGER NOT NULL REFERENCES unidades_medida(id) ON DELETE RESTRICT,
    peso_unitario_kg NUMERIC(10, 4) NOT NULL DEFAULT 0.0000 CHECK (peso_unitario_kg >= 0),
    stock_minimo NUMERIC(14, 4) NOT NULL DEFAULT 0.0000 CHECK (stock_minimo >= 0),
    requiere_lote BOOLEAN NOT NULL DEFAULT FALSE,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_productos_sku_ci
    ON productos (UPPER(TRIM(codigo_sku)));

CREATE TABLE IF NOT EXISTS inventario_stock (
    id SERIAL PRIMARY KEY,
    producto_id INTEGER NOT NULL REFERENCES productos(id) ON DELETE RESTRICT,
    almacen_id INTEGER NOT NULL REFERENCES almacenes(id) ON DELETE RESTRICT,
    stock_actual NUMERIC(14, 4) NOT NULL DEFAULT 0.0000 CHECK (stock_actual >= 0),
    stock_danado NUMERIC(14, 4) NOT NULL DEFAULT 0.0000 CHECK (stock_danado >= 0),
    stock_reservado NUMERIC(14, 4) NOT NULL DEFAULT 0.0000 CHECK (stock_reservado >= 0),
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_inventario_producto_almacen UNIQUE (producto_id, almacen_id),
    CONSTRAINT chk_reservado_no_excede_stock CHECK (stock_reservado <= stock_actual)
);

CREATE TABLE IF NOT EXISTS autorizaciones_gerenciales (
    id SERIAL PRIMARY KEY,
    codigo_autorizacion VARCHAR(40) NOT NULL UNIQUE,
    tipo_autorizacion VARCHAR(30) NOT NULL
        CHECK (tipo_autorizacion IN ('EXCESO_RECIBO', 'CREDITO_EXCEPCION')),
    gerente_nombre VARCHAR(120) NOT NULL,
    motivo TEXT NOT NULL,
    cantidad_extra_autorizada NUMERIC(14, 4) NOT NULL DEFAULT 0.0000 CHECK (cantidad_extra_autorizada >= 0),
    vigente BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_autorizacion TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ----------------------------------------------------------------------------
-- 2. COMPRAS Y MÓDULO DE RECIBOS (INBOUND)
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS ordenes_compra (
    id SERIAL PRIMARY KEY,
    codigo_oc VARCHAR(40) NOT NULL UNIQUE,
    proveedor_id INTEGER NOT NULL REFERENCES proveedores(id) ON DELETE RESTRICT,
    almacen_destino_id INTEGER NOT NULL REFERENCES almacenes(id) ON DELETE RESTRICT,
    fecha_emision DATE NOT NULL DEFAULT CURRENT_DATE,
    estado VARCHAR(20) NOT NULL DEFAULT 'BORRADOR'
        CHECK (estado IN ('BORRADOR', 'APROBADA', 'PARCIAL', 'RECIBIDA', 'CANCELADA')),
    observaciones TEXT,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ordenes_compra_detalle (
    id SERIAL PRIMARY KEY,
    orden_compra_id INTEGER NOT NULL REFERENCES ordenes_compra(id) ON DELETE RESTRICT,
    producto_id INTEGER NOT NULL REFERENCES productos(id) ON DELETE RESTRICT,
    cantidad_solicitada NUMERIC(14, 4) NOT NULL CHECK (cantidad_solicitada > 0),
    cantidad_recibida NUMERIC(14, 4) NOT NULL DEFAULT 0.0000 CHECK (cantidad_recibida >= 0),
    costo_unitario NUMERIC(14, 4) NOT NULL DEFAULT 0.0000 CHECK (costo_unitario >= 0),
    CONSTRAINT uq_oc_producto UNIQUE (orden_compra_id, producto_id)
);

CREATE TABLE IF NOT EXISTS recibos_mercancia (
    id SERIAL PRIMARY KEY,
    codigo_recibo VARCHAR(40) NOT NULL UNIQUE,
    orden_compra_id INTEGER NOT NULL REFERENCES ordenes_compra(id) ON DELETE RESTRICT,
    proveedor_id INTEGER NOT NULL REFERENCES proveedores(id) ON DELETE RESTRICT,
    almacen_id INTEGER NOT NULL REFERENCES almacenes(id) ON DELETE RESTRICT,
    autorizacion_gerencial_id INTEGER NULL REFERENCES autorizaciones_gerenciales(id) ON DELETE RESTRICT,
    estado VARCHAR(20) NOT NULL DEFAULT 'BORRADOR'
        CHECK (estado IN ('BORRADOR', 'EN_INSPECCION', 'APROBADO', 'RECHAZADO', 'CERRADO')),
    usuario_registro VARCHAR(100) NOT NULL,
    observaciones TEXT,
    fecha_recepcion TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_aprobacion TIMESTAMPTZ NULL
);

CREATE TABLE IF NOT EXISTS recibos_detalle (
    id SERIAL PRIMARY KEY,
    recibo_id INTEGER NOT NULL REFERENCES recibos_mercancia(id) ON DELETE RESTRICT,
    producto_id INTEGER NOT NULL REFERENCES productos(id) ON DELETE RESTRICT,
    ubicacion_id INTEGER NULL REFERENCES ubicaciones_almacen(id) ON DELETE RESTRICT,
    cantidad_esperada NUMERIC(14, 4) NOT NULL CHECK (cantidad_esperada > 0),
    cantidad_recibida NUMERIC(14, 4) NOT NULL CHECK (cantidad_recibida >= 0),
    cantidad_aceptada NUMERIC(14, 4) NOT NULL CHECK (cantidad_aceptada >= 0),
    cantidad_faltante NUMERIC(14, 4) NOT NULL DEFAULT 0.0000 CHECK (cantidad_faltante >= 0),
    cantidad_danada NUMERIC(14, 4) NOT NULL DEFAULT 0.0000 CHECK (cantidad_danada >= 0),
    estado_calidad VARCHAR(30) NOT NULL
        CHECK (estado_calidad IN ('EXACTO', 'FALTANTE', 'DANADO', 'PARCIAL_DANADO', 'EXCESO_AUTORIZADO')),
    lote VARCHAR(60),
    fecha_caducidad DATE,
    CONSTRAINT uq_recibo_producto UNIQUE (recibo_id, producto_id),
    CONSTRAINT chk_recibo_cuadre_cantidades CHECK (cantidad_aceptada + cantidad_danada = cantidad_recibida)
);

-- ----------------------------------------------------------------------------
-- 3. VENTAS Y MÓDULO DE ENTREGAS (OUTBOUND)
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS ordenes_venta (
    id SERIAL PRIMARY KEY,
    codigo_ov VARCHAR(40) NOT NULL UNIQUE,
    cliente_id INTEGER NOT NULL REFERENCES clientes(id) ON DELETE RESTRICT,
    almacen_origen_id INTEGER NOT NULL REFERENCES almacenes(id) ON DELETE RESTRICT,
    fecha_pedido DATE NOT NULL DEFAULT CURRENT_DATE,
    estado_pedido VARCHAR(20) NOT NULL DEFAULT 'BORRADOR'
        CHECK (estado_pedido IN ('BORRADOR', 'APROBADO', 'EN_DESPACHO', 'DESPACHADO', 'CANCELADO')),
    estado_pago VARCHAR(25) NOT NULL DEFAULT 'PENDIENTE'
        CHECK (estado_pago IN ('PENDIENTE', 'PAGADO', 'CREDITO_AUTORIZADO', 'RECHAZADO')),
    creado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ordenes_venta_detalle (
    id SERIAL PRIMARY KEY,
    orden_venta_id INTEGER NOT NULL REFERENCES ordenes_venta(id) ON DELETE RESTRICT,
    producto_id INTEGER NOT NULL REFERENCES productos(id) ON DELETE RESTRICT,
    cantidad_pedida NUMERIC(14, 4) NOT NULL CHECK (cantidad_pedida > 0),
    cantidad_despachada NUMERIC(14, 4) NOT NULL DEFAULT 0.0000 CHECK (cantidad_despachada >= 0),
    precio_unitario NUMERIC(14, 4) NOT NULL DEFAULT 0.0000 CHECK (precio_unitario >= 0),
    CONSTRAINT uq_ov_producto UNIQUE (orden_venta_id, producto_id)
);

CREATE TABLE IF NOT EXISTS entregas_mercancia (
    id SERIAL PRIMARY KEY,
    codigo_entrega VARCHAR(40) NOT NULL UNIQUE,
    numero_nota_salida VARCHAR(50) NOT NULL UNIQUE,
    orden_venta_id INTEGER NOT NULL REFERENCES ordenes_venta(id) ON DELETE RESTRICT,
    almacen_id INTEGER NOT NULL REFERENCES almacenes(id) ON DELETE RESTRICT,
    estado VARCHAR(20) NOT NULL DEFAULT 'BORRADOR'
        CHECK (estado IN ('BORRADOR', 'EMPACADO', 'CONFIRMADA', 'CERRADA', 'CANCELADA')),
    peso_total_kg NUMERIC(12, 4) NOT NULL DEFAULT 0.0000 CHECK (peso_total_kg >= 0),
    transportista VARCHAR(120),
    usuario_despacho VARCHAR(100) NOT NULL,
    fecha_entrega TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_confirmacion TIMESTAMPTZ NULL
);

CREATE TABLE IF NOT EXISTS entregas_detalle (
    id SERIAL PRIMARY KEY,
    entrega_id INTEGER NOT NULL REFERENCES entregas_mercancia(id) ON DELETE RESTRICT,
    producto_id INTEGER NOT NULL REFERENCES productos(id) ON DELETE RESTRICT,
    ubicacion_id INTEGER NULL REFERENCES ubicaciones_almacen(id) ON DELETE RESTRICT,
    cantidad_entregada NUMERIC(14, 4) NOT NULL CHECK (cantidad_entregada > 0),
    peso_subtotal_kg NUMERIC(12, 4) NOT NULL DEFAULT 0.0000 CHECK (peso_subtotal_kg >= 0),
    CONSTRAINT uq_entrega_producto UNIQUE (entrega_id, producto_id)
);

-- ----------------------------------------------------------------------------
-- 4. KARDEX INMUTABLE Y AUDITORÍA (Integridad de los Datos)
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS movimientos_inventario (
    id BIGSERIAL PRIMARY KEY,
    codigo_movimiento VARCHAR(50) NOT NULL UNIQUE,
    producto_id INTEGER NOT NULL REFERENCES productos(id) ON DELETE RESTRICT,
    almacen_id INTEGER NOT NULL REFERENCES almacenes(id) ON DELETE RESTRICT,
    tipo_movimiento VARCHAR(25) NOT NULL
        CHECK (tipo_movimiento IN ('ENTRADA_RECIBO', 'SALIDA_ENTREGA', 'INGRESO_DANADO', 'AJUSTE_ENTRADA', 'AJUSTE_SALIDA')),
    documento_tipo VARCHAR(20) NOT NULL CHECK (documento_tipo IN ('RECIBO', 'ENTREGA', 'AJUSTE')),
    documento_id INTEGER NOT NULL,
    cantidad NUMERIC(14, 4) NOT NULL CHECK (cantidad > 0),
    signo SMALLINT NOT NULL CHECK (signo IN (1, -1)),
    stock_anterior NUMERIC(14, 4) NOT NULL CHECK (stock_anterior >= 0),
    stock_posterior NUMERIC(14, 4) NOT NULL CHECK (stock_posterior >= 0),
    usuario_registro VARCHAR(100) NOT NULL,
    fecha_movimiento TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS auditoria_operaciones (
    id BIGSERIAL PRIMARY KEY,
    entidad VARCHAR(60) NOT NULL,
    entidad_id INTEGER NOT NULL,
    accion VARCHAR(30) NOT NULL,
    usuario VARCHAR(100) NOT NULL,
    detalle TEXT,
    fecha_evento TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ----------------------------------------------------------------------------
-- 5. REGLAS DE NEGOCIO Y TRANSACCIONALIDAD (Triggers PL/pgSQL)
-- ----------------------------------------------------------------------------

-- Regla Recibo 1: Proveedor activo y Orden de Compra aprobada o parcial
CREATE OR REPLACE FUNCTION fn_validar_recibo_cabecera()
RETURNS TRIGGER AS $$
DECLARE
    v_estatus_prov VARCHAR(20);
    v_activo_prov BOOLEAN;
    v_estado_oc VARCHAR(20);
    v_oc_prov_id INTEGER;
BEGIN
    SELECT proveedor_id, estado INTO v_oc_prov_id, v_estado_oc
    FROM ordenes_compra
    WHERE id = NEW.orden_compra_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'La orden de compra % no existe', NEW.orden_compra_id;
    END IF;

    IF v_oc_prov_id <> NEW.proveedor_id THEN
        RAISE EXCEPTION 'El proveedor del recibo no coincide con el proveedor de la orden de compra';
    END IF;

    IF v_estado_oc NOT IN ('APROBADA', 'PARCIAL') THEN
        RAISE EXCEPTION 'Solo se puede registrar un recibo contra una OC APROBADA o PARCIAL (estado actual: %)', v_estado_oc;
    END IF;

    SELECT estatus, activo INTO v_estatus_prov, v_activo_prov
    FROM proveedores
    WHERE id = NEW.proveedor_id;

    IF v_estatus_prov <> 'ACTIVO' OR v_activo_prov IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'Regla de Negocio (Proveedor Activo): No se puede registrar un recibo si el proveedor está en estado %', v_estatus_prov;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_validar_recibo_cabecera ON recibos_mercancia;
CREATE TRIGGER trg_validar_recibo_cabecera
BEFORE INSERT ON recibos_mercancia
FOR EACH ROW
EXECUTE FUNCTION fn_validar_recibo_cabecera();

-- Regla Recibo 2: No recibir de más (salvo autorización especial del gerente)
CREATE OR REPLACE FUNCTION fn_validar_recibo_detalle_exceso()
RETURNS TRIGGER AS $$
DECLARE
    v_oc_id INTEGER;
    v_auth_id INTEGER;
    v_solicitado NUMERIC(14, 4);
    v_recibido_previo NUMERIC(14, 4);
    v_extra_auth NUMERIC(14, 4) := 0;
    v_auth_vigente BOOLEAN := FALSE;
    v_auth_tipo VARCHAR(30);
BEGIN
    SELECT orden_compra_id, autorizacion_gerencial_id
    INTO v_oc_id, v_auth_id
    FROM recibos_mercancia
    WHERE id = NEW.recibo_id;

    SELECT cantidad_solicitada, cantidad_recibida
    INTO v_solicitado, v_recibido_previo
    FROM ordenes_compra_detalle
    WHERE orden_compra_id = v_oc_id AND producto_id = NEW.producto_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'El producto % no pertenece a la orden de compra %', NEW.producto_id, v_oc_id;
    END IF;

    IF (v_recibido_previo + NEW.cantidad_recibida) > v_solicitado THEN
        IF v_auth_id IS NULL THEN
            RAISE EXCEPTION 'Regla de Negocio (No recibir de más): Total recibido (%) supera lo pedido (%) sin autorización gerencial',
                (v_recibido_previo + NEW.cantidad_recibida), v_solicitado;
        END IF;

        SELECT tipo_autorizacion, cantidad_extra_autorizada, vigente
        INTO v_auth_tipo, v_extra_auth, v_auth_vigente
        FROM autorizaciones_gerenciales
        WHERE id = v_auth_id;

        IF NOT FOUND OR v_auth_vigente IS DISTINCT FROM TRUE OR v_auth_tipo <> 'EXCESO_RECIBO' THEN
            RAISE EXCEPTION 'La autorización gerencial % no es válida o no está vigente para exceso de recibo', v_auth_id;
        END IF;

        IF (v_recibido_previo + NEW.cantidad_recibida) > (v_solicitado + v_extra_auth) THEN
            RAISE EXCEPTION 'Total recibido (%) supera incluso el límite autorizado por gerencia (%)',
                (v_recibido_previo + NEW.cantidad_recibida), (v_solicitado + v_extra_auth);
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_validar_recibo_detalle_exceso ON recibos_detalle;
CREATE TRIGGER trg_validar_recibo_detalle_exceso
BEFORE INSERT ON recibos_detalle
FOR EACH ROW
EXECUTE FUNCTION fn_validar_recibo_detalle_exceso();

-- Regla Recibo 3: Al aprobar el recibo, actualizar inventario y estado de OC automáticamente
CREATE OR REPLACE FUNCTION fn_aprobar_recibo_inventario()
RETURNS TRIGGER AS $$
DECLARE
    v_det RECORD;
    v_stock_prev NUMERIC(14, 4);
    v_stock_post NUMERIC(14, 4);
    v_pendientes INTEGER;
BEGIN
    IF OLD.estado IN ('BORRADOR', 'EN_INSPECCION') AND NEW.estado = 'APROBADO' THEN
        NEW.fecha_aprobacion := COALESCE(NEW.fecha_aprobacion, CURRENT_TIMESTAMP);

        FOR v_det IN
            SELECT * FROM recibos_detalle WHERE recibo_id = NEW.id
        LOOP
            INSERT INTO inventario_stock (producto_id, almacen_id, stock_actual, stock_danado)
            VALUES (v_det.producto_id, NEW.almacen_id, 0, 0)
            ON CONFLICT (producto_id, almacen_id) DO NOTHING;

            SELECT stock_actual INTO v_stock_prev
            FROM inventario_stock
            WHERE producto_id = v_det.producto_id AND almacen_id = NEW.almacen_id
            FOR UPDATE;

            v_stock_post := v_stock_prev + v_det.cantidad_aceptada;

            UPDATE inventario_stock
            SET stock_actual = v_stock_post,
                stock_danado = stock_danado + v_det.cantidad_danada,
                actualizado_en = CURRENT_TIMESTAMP
            WHERE producto_id = v_det.producto_id AND almacen_id = NEW.almacen_id;

            IF v_det.cantidad_aceptada > 0 THEN
                INSERT INTO movimientos_inventario (
                    codigo_movimiento, producto_id, almacen_id, tipo_movimiento,
                    documento_tipo, documento_id, cantidad, signo,
                    stock_anterior, stock_posterior, usuario_registro
                ) VALUES (
                    'MOV-REC-' || NEW.id || '-' || v_det.producto_id,
                    v_det.producto_id, NEW.almacen_id, 'ENTRADA_RECIBO',
                    'RECIBO', NEW.id, v_det.cantidad_aceptada, 1,
                    v_stock_prev, v_stock_post, NEW.usuario_registro
                );
            END IF;

            UPDATE ordenes_compra_detalle
            SET cantidad_recibida = cantidad_recibida + v_det.cantidad_aceptada
            WHERE orden_compra_id = NEW.orden_compra_id AND producto_id = v_det.producto_id;
        END LOOP;

        SELECT COUNT(*) INTO v_pendientes
        FROM ordenes_compra_detalle
        WHERE orden_compra_id = NEW.orden_compra_id
          AND cantidad_recibida < cantidad_solicitada;

        UPDATE ordenes_compra
        SET estado = CASE WHEN v_pendientes = 0 THEN 'RECIBIDA' ELSE 'PARCIAL' END,
            actualizado_en = CURRENT_TIMESTAMP
        WHERE id = NEW.orden_compra_id;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_aprobar_recibo_inventario ON recibos_mercancia;
CREATE TRIGGER trg_aprobar_recibo_inventario
BEFORE UPDATE ON recibos_mercancia
FOR EACH ROW
EXECUTE FUNCTION fn_aprobar_recibo_inventario();

-- Regla Entrega 1 y 2: Pedido aprobado + pagado/crédito autorizado + stock suficiente + nota de salida
CREATE OR REPLACE FUNCTION fn_validar_entrega_cabecera()
RETURNS TRIGGER AS $$
DECLARE
    v_estado_pedido VARCHAR(20);
    v_estado_pago VARCHAR(25);
BEGIN
    SELECT estado_pedido, estado_pago
    INTO v_estado_pedido, v_estado_pago
    FROM ordenes_venta
    WHERE id = NEW.orden_venta_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'La orden de venta % no existe', NEW.orden_venta_id;
    END IF;

    IF v_estado_pedido NOT IN ('APROBADO', 'EN_DESPACHO') THEN
        RAISE EXCEPTION 'Regla de Negocio (Estado del pedido): La OV debe estar APROBADA para despacho (estado actual: %)', v_estado_pedido;
    END IF;

    IF v_estado_pago NOT IN ('PAGADO', 'CREDITO_AUTORIZADO') THEN
        RAISE EXCEPTION 'Regla de Negocio (Pago/Crédito): La OV debe estar PAGADA o con CREDITO_AUTORIZADO (estado actual: %)', v_estado_pago;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_validar_entrega_cabecera ON entregas_mercancia;
CREATE TRIGGER trg_validar_entrega_cabecera
BEFORE INSERT ON entregas_mercancia
FOR EACH ROW
EXECUTE FUNCTION fn_validar_entrega_cabecera();

CREATE OR REPLACE FUNCTION fn_confirmar_entrega_inventario()
RETURNS TRIGGER AS $$
DECLARE
    v_det RECORD;
    v_stock_prev NUMERIC(14, 4);
    v_stock_post NUMERIC(14, 4);
    v_pendientes INTEGER;
BEGIN
    IF OLD.estado IN ('BORRADOR', 'EMPACADO') AND NEW.estado = 'CONFIRMADA' THEN
        NEW.fecha_confirmacion := COALESCE(NEW.fecha_confirmacion, CURRENT_TIMESTAMP);

        FOR v_det IN
            SELECT * FROM entregas_detalle WHERE entrega_id = NEW.id
        LOOP
            SELECT stock_actual INTO v_stock_prev
            FROM inventario_stock
            WHERE producto_id = v_det.producto_id AND almacen_id = NEW.almacen_id
            FOR UPDATE;

            IF NOT FOUND OR v_stock_prev < v_det.cantidad_entregada THEN
                RAISE EXCEPTION 'Regla de Negocio (Stock insuficiente): Producto % dispone de % y se intenta entregar %',
                    v_det.producto_id, COALESCE(v_stock_prev, 0), v_det.cantidad_entregada;
            END IF;

            v_stock_post := v_stock_prev - v_det.cantidad_entregada;

            UPDATE inventario_stock
            SET stock_actual = v_stock_post,
                actualizado_en = CURRENT_TIMESTAMP
            WHERE producto_id = v_det.producto_id AND almacen_id = NEW.almacen_id;

            INSERT INTO movimientos_inventario (
                codigo_movimiento, producto_id, almacen_id, tipo_movimiento,
                documento_tipo, documento_id, cantidad, signo,
                stock_anterior, stock_posterior, usuario_registro
            ) VALUES (
                'MOV-ENT-' || NEW.id || '-' || v_det.producto_id,
                v_det.producto_id, NEW.almacen_id, 'SALIDA_ENTREGA',
                'ENTREGA', NEW.id, v_det.cantidad_entregada, -1,
                v_stock_prev, v_stock_post, NEW.usuario_despacho
            );

            UPDATE ordenes_venta_detalle
            SET cantidad_despachada = cantidad_despachada + v_det.cantidad_entregada
            WHERE orden_venta_id = NEW.orden_venta_id AND producto_id = v_det.producto_id;
        END LOOP;

        SELECT COUNT(*) INTO v_pendientes
        FROM ordenes_venta_detalle
        WHERE orden_venta_id = NEW.orden_venta_id
          AND cantidad_despachada < cantidad_pedida;

        UPDATE ordenes_venta
        SET estado_pedido = CASE WHEN v_pendientes = 0 THEN 'DESPACHADO' ELSE 'EN_DESPACHO' END,
            actualizado_en = CURRENT_TIMESTAMP
        WHERE id = NEW.orden_venta_id;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_confirmar_entrega_inventario ON entregas_mercancia;
CREATE TRIGGER trg_confirmar_entrega_inventario
BEFORE UPDATE ON entregas_mercancia
FOR EACH ROW
EXECUTE FUNCTION fn_confirmar_entrega_inventario();

-- Regla de Integridad: Inmutabilidad de registros cerrados / aprobados y del kardex
CREATE OR REPLACE FUNCTION fn_inmutabilidad_documentos_cerrados()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_TABLE_NAME = 'movimientos_inventario' THEN
        RAISE EXCEPTION 'Integridad de Datos: Los movimientos de inventario (kardex) son inmutables';
    END IF;

    IF TG_OP = 'DELETE' THEN
        IF OLD.estado IN ('APROBADO', 'CONFIRMADA', 'CERRADO', 'CERRADA') THEN
            RAISE EXCEPTION 'Integridad de Datos: No se puede eliminar un documento cerrado/aprobado';
        END IF;
        RETURN OLD;
    END IF;

    IF TG_OP = 'UPDATE' AND OLD.estado IN ('APROBADO', 'CONFIRMADA', 'CERRADO', 'CERRADA') THEN
        IF NOT (OLD.estado IN ('APROBADO', 'CONFIRMADA') AND NEW.estado IN ('CERRADO', 'CERRADA') AND OLD.id = NEW.id) THEN
            RAISE EXCEPTION 'Integridad de Datos: Un documento aprobado/confirmado/cerrado es inmutable';
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_inmutabilidad_recibos ON recibos_mercancia;
CREATE TRIGGER trg_inmutabilidad_recibos
BEFORE UPDATE OR DELETE ON recibos_mercancia
FOR EACH ROW
EXECUTE FUNCTION fn_inmutabilidad_documentos_cerrados();

DROP TRIGGER IF EXISTS trg_inmutabilidad_entregas ON entregas_mercancia;
CREATE TRIGGER trg_inmutabilidad_entregas
BEFORE UPDATE OR DELETE ON entregas_mercancia
FOR EACH ROW
EXECUTE FUNCTION fn_inmutabilidad_documentos_cerrados();

DROP TRIGGER IF EXISTS trg_inmutabilidad_kardex ON movimientos_inventario;
CREATE TRIGGER trg_inmutabilidad_kardex
BEFORE UPDATE OR DELETE ON movimientos_inventario
FOR EACH ROW
EXECUTE FUNCTION fn_inmutabilidad_documentos_cerrados();

CREATE OR REPLACE FUNCTION fn_inmutabilidad_detalles_cerrados()
RETURNS TRIGGER AS $$
DECLARE
    v_estado VARCHAR(20);
BEGIN
    IF TG_TABLE_NAME = 'recibos_detalle' THEN
        SELECT estado INTO v_estado
        FROM recibos_mercancia
        WHERE id = COALESCE(OLD.recibo_id, NEW.recibo_id);
    ELSE
        SELECT estado INTO v_estado
        FROM entregas_mercancia
        WHERE id = COALESCE(OLD.entrega_id, NEW.entrega_id);
    END IF;

    IF v_estado IN ('APROBADO', 'CONFIRMADA', 'CERRADO', 'CERRADA') THEN
        RAISE EXCEPTION 'Integridad de Datos: No se puede modificar ni eliminar el detalle de un documento %', v_estado;
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_inmutabilidad_recibos_detalle ON recibos_detalle;
CREATE TRIGGER trg_inmutabilidad_recibos_detalle
BEFORE INSERT OR UPDATE OR DELETE ON recibos_detalle
FOR EACH ROW
EXECUTE FUNCTION fn_inmutabilidad_detalles_cerrados();

DROP TRIGGER IF EXISTS trg_inmutabilidad_entregas_detalle ON entregas_detalle;
CREATE TRIGGER trg_inmutabilidad_entregas_detalle
BEFORE INSERT OR UPDATE OR DELETE ON entregas_detalle
FOR EACH ROW
EXECUTE FUNCTION fn_inmutabilidad_detalles_cerrados();

-- ----------------------------------------------------------------------------
-- 6. VISTA DE INTEGRIDAD: CUADRE DE INVENTARIO (Entradas - Salidas = Stock)
-- ----------------------------------------------------------------------------

CREATE OR REPLACE VIEW vw_cuadre_inventario AS
SELECT
    p.codigo_sku,
    p.nombre AS producto,
    a.codigo AS almacen,
    COALESCE(SUM(CASE WHEN m.signo = 1 THEN m.cantidad ELSE 0 END), 0) AS total_entradas,
    COALESCE(SUM(CASE WHEN m.signo = -1 THEN m.cantidad ELSE 0 END), 0) AS total_salidas,
    COALESCE(SUM(m.signo * m.cantidad), 0) AS stock_calculado_kardex,
    i.stock_actual AS stock_registrado,
    (i.stock_actual - COALESCE(SUM(m.signo * m.cantidad), 0)) AS diferencia
FROM inventario_stock i
JOIN productos p ON p.id = i.producto_id
JOIN almacenes a ON a.id = i.almacen_id
LEFT JOIN movimientos_inventario m
    ON m.producto_id = i.producto_id AND m.almacen_id = i.almacen_id
GROUP BY p.codigo_sku, p.nombre, a.codigo, i.stock_actual;

COMMIT;
