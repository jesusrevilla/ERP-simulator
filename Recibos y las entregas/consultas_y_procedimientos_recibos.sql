-- ============================================================================
-- PROCEDIMIENTOS ALMACENADOS Y CONSULTAS ANALÍTICAS PARA AGENTES INTELIGENTES
-- Módulo: Compras, Recibos, Entregas e Inventario (PostgreSQL 16+)
-- Matrícula: 177576 (RamoES12)
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. PROCEDIMIENTOS ALMACENADOS Y FUNCIONES DE APOYO OPERATIVO
-- ----------------------------------------------------------------------------

-- Procedimiento 1: Aprobar recibo de mercancía de forma transaccional (ACID)
CREATE OR REPLACE PROCEDURE sp_aprobar_recibo_mercancia(
    IN p_codigo_recibo VARCHAR(40),
    IN p_usuario_aprueba VARCHAR(100)
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_recibo_id INTEGER;
    v_estado_actual VARCHAR(20);
BEGIN
    SELECT id, estado INTO v_recibo_id, v_estado_actual
    FROM recibos_mercancia
    WHERE codigo_recibo = p_codigo_recibo
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'El recibo % no existe', p_codigo_recibo;
    END IF;

    IF v_estado_actual NOT IN ('BORRADOR', 'EN_INSPECCION') THEN
        RAISE EXCEPTION 'El recibo % no puede aprobarse desde el estado %', p_codigo_recibo, v_estado_actual;
    END IF;

    -- El trigger trg_aprobar_recibo_inventario suma stock, inserta kardex y actualiza OC
    UPDATE recibos_mercancia
    SET estado = 'APROBADO',
        usuario_registro = p_usuario_aprueba,
        fecha_aprobacion = CURRENT_TIMESTAMP
    WHERE id = v_recibo_id;

    INSERT INTO auditoria_operaciones (entidad, entidad_id, accion, usuario, detalle)
    VALUES ('recibos_mercancia', v_recibo_id, 'APROBACION_RECIBO', p_usuario_aprueba,
            'Recibo ' || p_codigo_recibo || ' aprobado mediante sp_aprobar_recibo_mercancia');
END;
$$;

-- Procedimiento 2: Reservar stock físico para picking (evita doble asignación concurrente)
CREATE OR REPLACE PROCEDURE sp_reservar_stock_picking(
    IN p_codigo_sku VARCHAR(40),
    IN p_codigo_almacen VARCHAR(20),
    IN p_cantidad NUMERIC(14, 4),
    IN p_usuario VARCHAR(100)
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_producto_id INTEGER;
    v_almacen_id INTEGER;
    v_disponible NUMERIC(14, 4);
BEGIN
    SELECT id INTO v_producto_id FROM productos WHERE UPPER(TRIM(codigo_sku)) = UPPER(TRIM(p_codigo_sku)) AND activo = TRUE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Producto % no existe o está inactivo', p_codigo_sku;
    END IF;

    SELECT id INTO v_almacen_id FROM almacenes WHERE codigo = p_codigo_almacen AND activo = TRUE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Almacén % no existe o está inactivo', p_codigo_almacen;
    END IF;

    SELECT (stock_actual - stock_reservado) INTO v_disponible
    FROM inventario_stock
    WHERE producto_id = v_producto_id AND almacen_id = v_almacen_id
    FOR UPDATE;

    IF NOT FOUND OR v_disponible < p_cantidad THEN
        RAISE EXCEPTION 'Stock libre insuficiente para picking de %: libre=%, solicitado=%',
            p_codigo_sku, COALESCE(v_disponible, 0), p_cantidad;
    END IF;

    UPDATE inventario_stock
    SET stock_reservado = stock_reservado + p_cantidad,
        actualizado_en = CURRENT_TIMESTAMP
    WHERE producto_id = v_producto_id AND almacen_id = v_almacen_id;

    INSERT INTO auditoria_operaciones (entidad, entidad_id, accion, usuario, detalle)
    VALUES ('inventario_stock', v_producto_id, 'RESERVA_PICKING', p_usuario,
            'Reserva de ' || p_cantidad || ' unidades de ' || p_codigo_sku || ' en ' || p_codigo_almacen);
END;
$$;

-- Procedimiento 3: Confirmar entrega de mercancía y emitir nota de salida
CREATE OR REPLACE PROCEDURE sp_confirmar_entrega_salida(
    IN p_codigo_entrega VARCHAR(40),
    IN p_usuario_despacho VARCHAR(100)
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_entrega_id INTEGER;
    v_estado_actual VARCHAR(20);
BEGIN
    SELECT id, estado INTO v_entrega_id, v_estado_actual
    FROM entregas_mercancia
    WHERE codigo_entrega = p_codigo_entrega
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'La entrega % no existe', p_codigo_entrega;
    END IF;

    IF v_estado_actual NOT IN ('BORRADOR', 'EMPACADO') THEN
        RAISE EXCEPTION 'La entrega % no puede confirmarse desde estado %', p_codigo_entrega, v_estado_actual;
    END IF;

    -- El trigger trg_confirmar_entrega_inventario valida stock, descuenta y genera kardex
    UPDATE entregas_mercancia
    SET estado = 'CONFIRMADA',
        usuario_despacho = p_usuario_despacho,
        fecha_confirmacion = CURRENT_TIMESTAMP
    WHERE id = v_entrega_id;

    INSERT INTO auditoria_operaciones (entidad, entidad_id, accion, usuario, detalle)
    VALUES ('entregas_mercancia', v_entrega_id, 'CONFIRMACION_ENTREGA', p_usuario_despacho,
            'Entrega ' || p_codigo_entrega || ' confirmada mediante sp_confirmar_entrega_salida');
END;
$$;

-- ----------------------------------------------------------------------------
-- 2. CONSULTAS SQL ANALÍTICAS PARA AGENTES INTELIGENTES DEL ERP
-- ----------------------------------------------------------------------------

-- Q1. Inventarios críticos (debajo o en el punto de reorden / stock_minimo)
-- Decisión soportada: Agente de compras/MRP dispara solicitud automática de OC.
SELECT
    p.codigo_sku,
    p.nombre AS producto,
    a.codigo AS almacen,
    i.stock_actual,
    i.stock_reservado,
    (i.stock_actual - i.stock_reservado) AS stock_disponible_neto,
    p.stock_minimo,
    GREATEST(p.stock_minimo - (i.stock_actual - i.stock_reservado), 0) AS deficit_reorden
FROM inventario_stock i
JOIN productos p ON p.id = i.producto_id
JOIN almacenes a ON a.id = i.almacen_id
WHERE p.activo = TRUE
  AND (i.stock_actual - i.stock_reservado) <= p.stock_minimo
ORDER BY deficit_reorden DESC, p.codigo_sku ASC;

-- Q2. Proveedores con mayor cumplimiento (tasa de entrega completa y calidad sin daños)
-- Decisión soportada: Agente de selección de proveedores prioriza al proveedor más confiable.
SELECT
    pr.codigo_proveedor,
    pr.nombre AS proveedor,
    pr.estatus,
    COUNT(DISTINCT oc.id) AS total_ordenes,
    COALESCE(SUM(ocd.cantidad_solicitada), 0) AS unidades_solicitadas,
    COALESCE(SUM(ocd.cantidad_recibida), 0) AS unidades_aceptadas,
    COALESCE(SUM(rd.cantidad_danada), 0) AS unidades_danadas,
    ROUND(
        CASE
            WHEN COALESCE(SUM(ocd.cantidad_solicitada), 0) = 0 THEN 0
            ELSE (SUM(ocd.cantidad_recibida) / SUM(ocd.cantidad_solicitada)) * 100.0
        END, 2
    ) AS porcentaje_cumplimiento
FROM proveedores pr
LEFT JOIN ordenes_compra oc ON oc.proveedor_id = pr.id
LEFT JOIN ordenes_compra_detalle ocd ON ocd.orden_compra_id = oc.id
LEFT JOIN recibos_mercancia rm ON rm.orden_compra_id = oc.id AND rm.estado IN ('APROBADO', 'CERRADO')
LEFT JOIN recibos_detalle rd ON rd.recibo_id = rm.id AND rd.producto_id = ocd.producto_id
GROUP BY pr.codigo_proveedor, pr.nombre, pr.estatus
ORDER BY porcentaje_cumplimiento DESC, unidades_danadas ASC;

-- Q3. Productos más despachados (demanda histórica de salida)
-- Decisión soportada: Agente de planeación ajusta stock mínimo y zonas de putaway de alta rotación.
SELECT
    p.codigo_sku,
    p.nombre AS producto,
    COUNT(DISTINCT em.id) AS total_entregas,
    SUM(ed.cantidad_entregada) AS total_unidades_entregadas,
    SUM(ed.peso_subtotal_kg) AS peso_total_despachado_kg
FROM entregas_detalle ed
JOIN entregas_mercancia em ON em.id = ed.entrega_id
JOIN productos p ON p.id = ed.producto_id
WHERE em.estado IN ('CONFIRMADA', 'CERRADA')
GROUP BY p.codigo_sku, p.nombre
ORDER BY total_unidades_entregadas DESC;

-- Q4. Órdenes pendientes (Órdenes de Compra pendientes de recepción y Órdenes de Venta listas para despacho)
-- Decisión soportada: Agente de logística prioriza recepción en andén y surtido de pedidos pagados.
SELECT
    'COMPRA' AS tipo_orden,
    oc.codigo_oc AS codigo_documento,
    pr.nombre AS socio_negocio,
    oc.estado AS estado_actual,
    SUM(ocd.cantidad_solicitada - ocd.cantidad_recibida) AS unidades_pendientes
FROM ordenes_compra oc
JOIN proveedores pr ON pr.id = oc.proveedor_id
JOIN ordenes_compra_detalle ocd ON ocd.orden_compra_id = oc.id
WHERE oc.estado IN ('APROBADA', 'PARCIAL')
GROUP BY oc.codigo_oc, pr.nombre, oc.estado
HAVING SUM(ocd.cantidad_solicitada - ocd.cantidad_recibida) > 0
UNION ALL
SELECT
    'VENTA' AS tipo_orden,
    ov.codigo_ov AS codigo_documento,
    c.nombre AS socio_negocio,
    ov.estado_pedido || ' / ' || ov.estado_pago AS estado_actual,
    SUM(ovd.cantidad_pedida - ovd.cantidad_despachada) AS unidades_pendientes
FROM ordenes_venta ov
JOIN clientes c ON c.id = ov.cliente_id
JOIN ordenes_venta_detalle ovd ON ovd.orden_venta_id = ov.id
WHERE ov.estado_pedido IN ('APROBADO', 'EN_DESPACHO')
  AND ov.estado_pago IN ('PAGADO', 'CREDITO_AUTORIZADO')
GROUP BY ov.codigo_ov, c.nombre, ov.estado_pedido, ov.estado_pago
HAVING SUM(ovd.cantidad_pedida - ovd.cantidad_despachada) > 0;

-- Q5. Cuadre e integridad de inventario (Entradas - Salidas = Stock actual)
-- Decisión soportada: Agente auditor valida consistencia antes de cerrar despacho contable.
SELECT *
FROM vw_cuadre_inventario
WHERE diferencia <> 0 OR stock_registrado >= 0
ORDER BY ABS(diferencia) DESC, codigo_sku ASC;
