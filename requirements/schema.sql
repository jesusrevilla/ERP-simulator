-- ==========================================
-- ESTRUCTURA SIMPLIFICADA: SIMULADOR ERP
-- Módulo: Recibos y Entregas
-- ==========================================

-- 1. Tabla de Productos (Inventario)
CREATE TABLE productos (
    id_producto SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    stock_actual INT NOT NULL DEFAULT 0 CHECK (stock_actual >= 0)
);

-- 2. Tabla de Órdenes (Compras y Ventas)
CREATE TABLE ordenes (
    id_orden SERIAL PRIMARY KEY,
    tipo VARCHAR(10) NOT NULL CHECK (tipo IN ('COMPRA', 'VENTA')),
    codigo VARCHAR(20) UNIQUE NOT NULL,
    estatus VARCHAR(20) NOT NULL DEFAULT 'PENDIENTE'
);

-- 3. Tabla de Movimientos de Almacén (Recibos y Entregas)
CREATE TABLE movimientos_almacen (
    id_movimiento SERIAL PRIMARY KEY,
    id_orden INT NOT NULL REFERENCES ordenes(id_orden),
    id_producto INT NOT NULL REFERENCES productos(id_producto),
    tipo_movimiento VARCHAR(10) NOT NULL CHECK (tipo_movimiento IN ('RECIBO', 'ENTREGA')),
    cantidad INT NOT NULL CHECK (cantidad > 0),
    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==========================================
-- TRIGGERS SIMPLIFICADOS (Reglas de Negocio)
-- ==========================================

-- Función para actualizar el inventario automáticamente
CREATE OR REPLACE FUNCTION fn_actualizar_inventario()
RETURNS TRIGGER AS $$
DECLARE
    v_stock INT;
BEGIN
    -- Si es un RECIBO, sumamos al inventario
    IF NEW.tipo_movimiento = 'RECIBO' THEN
        UPDATE productos 
        SET stock_actual = stock_actual + NEW.cantidad 
        WHERE id_producto = NEW.id_producto;
    
    -- Si es una ENTREGA, validamos stock y restamos
    ELSIF NEW.tipo_movimiento = 'ENTREGA' THEN
        SELECT stock_actual INTO v_stock FROM productos WHERE id_producto = NEW.id_producto;
        
        IF v_stock < NEW.cantidad THEN
            RAISE EXCEPTION 'Stock insuficiente. Disponible: %, Intenta entregar: %', v_stock, NEW.cantidad;
        END IF;
        
        UPDATE productos 
        SET stock_actual = stock_actual - NEW.cantidad 
        WHERE id_producto = NEW.id_producto;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger que se dispara tras cada recibo o entrega
CREATE TRIGGER trg_procesar_movimiento
BEFORE INSERT ON movimientos_almacen
FOR EACH ROW
EXECUTE FUNCTION fn_actualizar_inventario();
