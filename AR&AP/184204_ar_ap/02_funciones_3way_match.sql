CREATE OR REPLACE FUNCTION registrar_recepcion(
    p_oc_id BIGINT,
    p_proveedor_id BIGINT,
    p_articulo VARCHAR,
    p_cantidad NUMERIC,
    p_usuario VARCHAR,
    p_fecha DATE DEFAULT CURRENT_DATE
)
RETURNS resultado_operacion
LANGUAGE plpgsql
AS $$
DECLARE
    v_oc_linea_id BIGINT;
    v_ordenada NUMERIC(14, 3);
    v_recibida NUMERIC(14, 3);
    v_recepcion_id BIGINT;
BEGIN
    SELECT oc_linea_id, cantidad_ordenada, cantidad_recibida
    INTO v_oc_linea_id, v_ordenada, v_recibida
    FROM oc_linea
    WHERE oc_id = p_oc_id AND articulo = p_articulo
    FOR UPDATE;

    IF NOT FOUND THEN
        RETURN ROW(FALSE, 'Linea de orden de compra no encontrada para el articulo indicado', NULL::BIGINT)::resultado_operacion;
    END IF;

    IF p_cantidad <= 0 OR (v_recibida + p_cantidad) > v_ordenada THEN
        RETURN ROW(FALSE, 'La cantidad a recibir excede la cantidad ordenada en la OC', NULL::BIGINT)::resultado_operacion;
    END IF;

    INSERT INTO recepciones (oc_id, proveedor_id, fecha_recepcion, usuario_registro)
    VALUES (p_oc_id, p_proveedor_id, p_fecha, p_usuario)
    RETURNING recepcion_id INTO v_recepcion_id;

    INSERT INTO recepcion_linea (recepcion_id, oc_linea_id, articulo, cantidad_recibida)
    VALUES (v_recepcion_id, v_oc_linea_id, p_articulo, p_cantidad);

    UPDATE oc_linea
    SET cantidad_recibida = cantidad_recibida + p_cantidad
    WHERE oc_linea_id = v_oc_linea_id;

    RETURN ROW(TRUE, 'Recepcion registrada correctamente', v_recepcion_id)::resultado_operacion;
END;
$$;

CREATE OR REPLACE FUNCTION registrar_factura_proveedor(
    p_proveedor_id BIGINT,
    p_recepcion_id BIGINT,
    p_oc_id BIGINT,
    p_fecha DATE,
    p_condicion_pago VARCHAR,
    p_articulo VARCHAR,
    p_cantidad NUMERIC,
    p_precio_unitario NUMERIC,
    p_usuario VARCHAR
)
RETURNS resultado_operacion
LANGUAGE plpgsql
AS $$
DECLARE
    v_oc_linea_id BIGINT;
    v_oc_precio NUMERIC(14, 2);
    v_cant_recibida NUMERIC(14, 3);
    v_cant_facturada NUMERIC(14, 3);
    v_recepcion_oc_id BIGINT;
    v_monto NUMERIC(14, 2);
    v_factura_id BIGINT;
BEGIN
    SELECT oc_id INTO v_recepcion_oc_id
    FROM recepciones
    WHERE recepcion_id = p_recepcion_id AND proveedor_id = p_proveedor_id;

    IF NOT FOUND OR v_recepcion_oc_id <> p_oc_id THEN
        RETURN ROW(FALSE, 'Recepcion invalida o no corresponde a la orden de compra y proveedor', NULL::BIGINT)::resultado_operacion;
    END IF;

    SELECT oc_linea_id, precio_unitario, cantidad_recibida, cantidad_facturada
    INTO v_oc_linea_id, v_oc_precio, v_cant_recibida, v_cant_facturada
    FROM oc_linea
    WHERE oc_id = p_oc_id AND articulo = p_articulo
    FOR UPDATE;

    IF NOT FOUND THEN
        RETURN ROW(FALSE, 'Articulo no pertenece a la orden de compra indicada', NULL::BIGINT)::resultado_operacion;
    END IF;

    IF p_precio_unitario <> v_oc_precio THEN
        RETURN ROW(FALSE, format('Discrepancia 3-Way Match: precio facturado (%s) distinto al precio de OC (%s)', p_precio_unitario, v_oc_precio), NULL::BIGINT)::resultado_operacion;
    END IF;

    IF p_cantidad <= 0 OR (v_cant_facturada + p_cantidad) > v_cant_recibida THEN
        RETURN ROW(FALSE, format('Discrepancia 3-Way Match: cantidad facturada acumulada (%s) supera la cantidad recibida (%s)', (v_cant_facturada + p_cantidad), v_cant_recibida), NULL::BIGINT)::resultado_operacion;
    END IF;

    v_monto := ROUND(p_cantidad * p_precio_unitario, 2);

    INSERT INTO facturas_proveedor (
        proveedor_id, recepcion_id, oc_id, articulo, fecha_emision,
        condicion_pago, cantidad_facturada, precio_unitario,
        monto_total, saldo, estatus, usuario_registro
    )
    VALUES (
        p_proveedor_id, p_recepcion_id, p_oc_id, p_articulo, p_fecha,
        p_condicion_pago, p_cantidad, p_precio_unitario,
        v_monto, v_monto, 'A', p_usuario
    )
    RETURNING factura_id INTO v_factura_id;

    UPDATE oc_linea
    SET cantidad_facturada = cantidad_facturada + p_cantidad
    WHERE oc_linea_id = v_oc_linea_id;

    RETURN ROW(TRUE, 'Factura de proveedor validada por 3-Way Match y registrada', v_factura_id)::resultado_operacion;
END;
$$;

CREATE OR REPLACE FUNCTION aplicar_pago_proveedor(
    p_factura_id BIGINT,
    p_proveedor_id BIGINT,
    p_monto NUMERIC,
    p_usuario VARCHAR,
    p_fecha DATE DEFAULT CURRENT_DATE
)
RETURNS resultado_operacion
LANGUAGE plpgsql
AS $$
DECLARE
    v_saldo NUMERIC(14, 2);
    v_nuevo_saldo NUMERIC(14, 2);
    v_nuevo_estatus VARCHAR(15);
    v_pago_id BIGINT;
BEGIN
    SELECT saldo
    INTO v_saldo
    FROM facturas_proveedor
    WHERE factura_id = p_factura_id AND proveedor_id = p_proveedor_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RETURN ROW(FALSE, 'Factura de proveedor no encontrada', NULL::BIGINT)::resultado_operacion;
    END IF;

    IF p_monto <= 0 OR p_monto > v_saldo THEN
        RETURN ROW(FALSE, format('Monto de pago (%s) invalido o mayor al saldo pendiente (%s)', p_monto, v_saldo), NULL::BIGINT)::resultado_operacion;
    END IF;

    v_nuevo_saldo := v_saldo - p_monto;
    v_nuevo_estatus := CASE WHEN v_nuevo_saldo = 0 THEN 'C' ELSE 'P' END;

    INSERT INTO pagos (proveedor_id, fecha_pago, monto_total, usuario_registro)
    VALUES (p_proveedor_id, p_fecha, p_monto, p_usuario)
    RETURNING pago_id INTO v_pago_id;

    INSERT INTO pago_aplicacion (pago_id, factura_id, monto_aplicado)
    VALUES (v_pago_id, p_factura_id, p_monto);

    UPDATE facturas_proveedor
    SET saldo = v_nuevo_saldo,
        estatus = v_nuevo_estatus
    WHERE factura_id = p_factura_id;

    RETURN ROW(TRUE, format('Pago aplicado. Nuevo saldo: %s, estatus: %s', v_nuevo_saldo, v_nuevo_estatus), v_pago_id)::resultado_operacion;
END;
$$;

CREATE OR REPLACE FUNCTION registrar_factura_cliente(
    p_cliente_id BIGINT,
    p_pedido_id BIGINT,
    p_condicion_pago VARCHAR,
    p_monto_total NUMERIC,
    p_limite_credito NUMERIC,
    p_fecha DATE DEFAULT CURRENT_DATE
)
RETURNS resultado_operacion
LANGUAGE plpgsql
AS $$
DECLARE
    v_saldo_actual NUMERIC(14, 2);
    v_factura_cliente_id BIGINT;
BEGIN
    IF p_monto_total <= 0 THEN
        RETURN ROW(FALSE, 'El monto de la factura debe ser mayor a cero', NULL::BIGINT)::resultado_operacion;
    END IF;

    SELECT COALESCE(SUM(saldo), 0)
    INTO v_saldo_actual
    FROM facturas_cliente
    WHERE cliente_id = p_cliente_id AND estatus <> 'C'
    FOR UPDATE;

    IF (v_saldo_actual + p_monto_total) > p_limite_credito THEN
        RETURN ROW(FALSE, 'La factura excede el limite de credito disponible del cliente', NULL::BIGINT)::resultado_operacion;
    END IF;

    INSERT INTO facturas_cliente (
        cliente_id, pedido_id, fecha_emision, condicion_pago, monto_total, saldo, estatus
    )
    VALUES (
        p_cliente_id, p_pedido_id, p_fecha, p_condicion_pago, p_monto_total, p_monto_total, 'A'
    )
    RETURNING factura_cliente_id INTO v_factura_cliente_id;

    RETURN ROW(TRUE, 'Factura de cliente registrada con validacion de credito', v_factura_cliente_id)::resultado_operacion;
END;
$$;

CREATE OR REPLACE FUNCTION aplicar_cobro_cliente(
    p_factura_cliente_id BIGINT,
    p_cliente_id BIGINT,
    p_monto NUMERIC,
    p_usuario VARCHAR,
    p_fecha DATE DEFAULT CURRENT_DATE
)
RETURNS resultado_operacion
LANGUAGE plpgsql
AS $$
DECLARE
    v_saldo NUMERIC(14, 2);
    v_nuevo_saldo NUMERIC(14, 2);
    v_nuevo_estatus VARCHAR(15);
    v_cobro_id BIGINT;
BEGIN
    SELECT saldo
    INTO v_saldo
    FROM facturas_cliente
    WHERE factura_cliente_id = p_factura_cliente_id AND cliente_id = p_cliente_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RETURN ROW(FALSE, 'Factura de cliente no encontrada', NULL::BIGINT)::resultado_operacion;
    END IF;

    IF p_monto <= 0 OR p_monto > v_saldo THEN
        RETURN ROW(FALSE, format('Monto de cobro (%s) invalido o mayor al saldo pendiente (%s)', p_monto, v_saldo), NULL::BIGINT)::resultado_operacion;
    END IF;

    v_nuevo_saldo := v_saldo - p_monto;
    v_nuevo_estatus := CASE WHEN v_nuevo_saldo = 0 THEN 'C' ELSE 'P' END;

    INSERT INTO cobros (cliente_id, fecha_cobro, monto_total, usuario_registro)
    VALUES (p_cliente_id, p_fecha, p_monto, p_usuario)
    RETURNING cobro_id INTO v_cobro_id;

    INSERT INTO cobro_aplicacion (cobro_id, factura_cliente_id, monto_aplicado)
    VALUES (v_cobro_id, p_factura_cliente_id, p_monto);

    UPDATE facturas_cliente
    SET saldo = v_nuevo_saldo,
        estatus = v_nuevo_estatus
    WHERE factura_cliente_id = p_factura_cliente_id;

    RETURN ROW(TRUE, format('Cobro aplicado. Nuevo saldo: %s, estatus: %s', v_nuevo_saldo, v_nuevo_estatus), v_cobro_id)::resultado_operacion;
END;
$$;
