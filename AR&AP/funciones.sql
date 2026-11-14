-- Tipo de retorno para las funciones
CREATE TYPE resultado_operacion AS (
    exito BOOLEAN,
    mensaje TEXT,
    registro_id INT
);

-- FUNCIÓN: Registrar Recepción de Mercancía
CREATE OR REPLACE FUNCTION registrar_recepcion(
    p_oc_id INT,
    p_fecha DATE,
    p_articulo VARCHAR,
    p_cantidad NUMERIC,
    p_usuario VARCHAR
) RETURNS resultado_operacion AS $$
DECLARE
    v_recepcion_id INT;
    v_oc_linea_id INT;
    v_cantidad_pendiente NUMERIC;
    v_folio VARCHAR;
    v_resultado resultado_operacion;
BEGIN
    -- Buscar línea de OC
    SELECT linea_id, (cantidad - cantidad_recibida)
    INTO v_oc_linea_id, v_cantidad_pendiente
    FROM oc_linea
    WHERE oc_id = p_oc_id AND articulo = p_articulo
    LIMIT 1;

    IF v_oc_linea_id IS NULL THEN
        v_resultado.exito := FALSE;
        v_resultado.mensaje := 'Error: Artículo no encontrado en la OC';
        v_resultado.registro_id := NULL;
        RETURN v_resultado;
    END IF;

    -- Validar que no se reciba más de lo pendiente
    IF p_cantidad > v_cantidad_pendiente THEN
        v_resultado.exito := FALSE;
        v_resultado.mensaje := 'Error: Cantidad a recibir (' || p_cantidad || 
                               ') excede lo pendiente en OC (' || v_cantidad_pendiente || ')';
        v_resultado.registro_id := NULL;
        RETURN v_resultado;
    END IF;

    -- Generar folio de recepción
    v_folio := 'REC-' || LPAD((SELECT COUNT(*)+1 FROM recepciones)::TEXT, 6, '0');

    -- Insertar recepción
    INSERT INTO recepciones (folio, oc_id, fecha, creado_por)
    VALUES (v_folio, p_oc_id, p_fecha, p_usuario)
    RETURNING recepcion_id INTO v_recepcion_id;

    -- Insertar línea de recepción
    INSERT INTO recepcion_linea (recepcion_id, oc_linea_id, articulo, cantidad_recibida)
    VALUES (v_recepcion_id, v_oc_linea_id, p_articulo, p_cantidad);

    -- Actualizar cantidad recibida en OC
    UPDATE oc_linea
    SET cantidad_recibida = cantidad_recibida + p_cantidad
    WHERE linea_id = v_oc_linea_id;

    v_resultado.exito := TRUE;
    v_resultado.mensaje := 'Recepción registrada exitosamente con Folio: ' || v_folio;
    v_resultado.registro_id := v_recepcion_id;
    RETURN v_resultado;
END;
$$ LANGUAGE plpgsql;

-- FUNCIÓN: Registrar Factura de Proveedor (3-Way Match)
CREATE OR REPLACE FUNCTION registrar_factura_proveedor(
    p_proveedor_id INT,
    p_recepcion_id INT,
    p_oc_id INT,
    p_fecha DATE,
    p_condicion_pago VARCHAR,
    p_articulo VARCHAR,
    p_cantidad NUMERIC,
    p_precio_unitario NUMERIC,
    p_usuario VARCHAR
) RETURNS resultado_operacion AS $$
DECLARE
    v_subtotal NUMERIC;
    v_iva NUMERIC;
    v_total NUMERIC;
    v_fecha_venc DATE;
    v_factura_id INT;
    v_oc_linea_id INT;
    v_oc_precio NUMERIC;
    v_oc_cantidad_pendiente NUMERIC;
    v_cantidad_recibida NUMERIC;
    v_folio VARCHAR;
    v_dias INT;
    v_resultado resultado_operacion;
BEGIN
    -- Obtener datos de la línea de OC
    SELECT linea_id, precio_unitario, (cantidad - cantidad_facturada)
    INTO v_oc_linea_id, v_oc_precio, v_oc_cantidad_pendiente
    FROM oc_linea
    WHERE oc_id = p_oc_id AND articulo = p_articulo
    LIMIT 1;

    IF v_oc_linea_id IS NULL THEN
        v_resultado.exito := FALSE;
        v_resultado.mensaje := 'Error: Artículo no encontrado en la OC';
        v_resultado.registro_id := NULL;
        RETURN v_resultado;
    END IF;

    -- VALIDACIÓN 1: Precio debe coincidir con la OC (3-way match)
    IF p_precio_unitario <> v_oc_precio THEN
        v_resultado.exito := FALSE;
        v_resultado.mensaje := 'Error 3-way match: Precio de factura (' || p_precio_unitario || 
                               ') no coincide con OC (' || v_oc_precio || ')';
        v_resultado.registro_id := NULL;
        RETURN v_resultado;
    END IF;

    -- VALIDACIÓN 2: No facturar más de lo pendiente en la OC
    IF p_cantidad > v_oc_cantidad_pendiente THEN
        v_resultado.exito := FALSE;
        v_resultado.mensaje := 'Error: Cantidad a facturar (' || p_cantidad || 
                               ') excede lo pendiente en OC (' || v_oc_cantidad_pendiente || ')';
        v_resultado.registro_id := NULL;
        RETURN v_resultado;
    END IF;

    -- VALIDACIÓN 3: No facturar más de lo recibido
    SELECT COALESCE(SUM(cantidad_recibida), 0)
    INTO v_cantidad_recibida
    FROM recepcion_linea
    WHERE oc_linea_id = v_oc_linea_id;

    IF p_cantidad > v_cantidad_recibida THEN
        v_resultado.exito := FALSE;
        v_resultado.mensaje := 'Error: Cantidad a facturar (' || p_cantidad || 
                               ') excede lo recibido (' || v_cantidad_recibida || ')';
        v_resultado.registro_id := NULL;
        RETURN v_resultado;
    END IF;

    -- Calcular totales
    v_subtotal := p_cantidad * p_precio_unitario;
    v_iva := v_subtotal * 0.16;
    v_total := v_subtotal + v_iva;

    -- Obtener días de la condición de pago
    SELECT dias INTO v_dias
    FROM condiciones_pago
    WHERE codigo = p_condicion_pago;

    -- Calcular fecha de vencimiento
    v_fecha_venc := p_fecha + (v_dias || ' days')::INTERVAL;

    -- Generar folio consecutivo
    v_folio := 'FP-' || LPAD((SELECT COUNT(*)+1 FROM facturas_proveedor)::TEXT, 6, '0');

    -- Insertar factura
    INSERT INTO facturas_proveedor (
        folio, proveedor_id, recepcion_id, oc_id, fecha, fecha_vencimiento,
        subtotal, iva, total, saldo, creado_por
    ) VALUES (
        v_folio, p_proveedor_id, p_recepcion_id, p_oc_id, p_fecha, v_fecha_venc,
        v_subtotal, v_iva, v_total, v_total, p_usuario
    ) RETURNING factura_id INTO v_factura_id;

    -- Insertar línea de factura
    INSERT INTO factura_proveedor_linea (factura_id, oc_linea_id, articulo, cantidad, precio_unitario)
    VALUES (v_factura_id, v_oc_linea_id, p_articulo, p_cantidad, p_precio_unitario);

    -- Actualizar cantidad facturada en OC
    UPDATE oc_linea
    SET cantidad_facturada = cantidad_facturada + p_cantidad
    WHERE linea_id = v_oc_linea_id;

    v_resultado.exito := TRUE;
    v_resultado.mensaje := 'Factura registrada exitosamente con Folio: ' || v_folio;
    v_resultado.registro_id := v_factura_id;
    RETURN v_resultado;
END;
$$ LANGUAGE plpgsql;

-- FUNCIÓN: Aplicar Pago a Factura
CREATE OR REPLACE FUNCTION aplicar_pago_proveedor(
    p_proveedor_id INT,
    p_factura_id INT,
    p_monto NUMERIC,
    p_fecha DATE,
    p_metodo_pago VARCHAR,
    p_usuario VARCHAR
) RETURNS resultado_operacion AS $$
DECLARE
    v_saldo NUMERIC;
    v_pago_id INT;
    v_folio VARCHAR;
    v_resultado resultado_operacion;
BEGIN
    -- Bloqueo de fila para concurrencia
    SELECT saldo INTO v_saldo
    FROM facturas_proveedor
    WHERE factura_id = p_factura_id
    FOR UPDATE;

    IF v_saldo IS NULL THEN
        v_resultado.exito := FALSE;
        v_resultado.mensaje := 'Error: Factura no encontrada';
        v_resultado.registro_id := NULL;
        RETURN v_resultado;
    END IF;

    -- VALIDACIÓN: El pago no puede exceder el saldo
    IF p_monto > v_saldo THEN
        v_resultado.exito := FALSE;
        v_resultado.mensaje := 'Error: Pago (' || p_monto || 
                               ') mayor al saldo de la factura (' || v_saldo || ')';
        v_resultado.registro_id := NULL;
        RETURN v_resultado;
    END IF;

    -- Generar folio de pago
    v_folio := 'PG-' || LPAD((SELECT COUNT(*)+1 FROM pagos)::TEXT, 6, '0');

    -- Registrar pago
    INSERT INTO pagos (folio, proveedor_id, fecha, monto, metodo_pago, creado_por)
    VALUES (v_folio, p_proveedor_id, p_fecha, p_monto, p_metodo_pago, p_usuario)
    RETURNING pago_id INTO v_pago_id;

    -- Aplicar pago a factura
    INSERT INTO pago_aplicacion (pago_id, factura_id, monto_aplicado)
    VALUES (v_pago_id, p_factura_id, p_monto);

    -- Actualizar saldo y estatus de factura
    UPDATE facturas_proveedor
    SET saldo = saldo - p_monto,
        estatus = CASE WHEN (saldo - p_monto) = 0 THEN 'C' ELSE 'A' END
    WHERE factura_id = p_factura_id;

    v_resultado.exito := TRUE;
    v_resultado.mensaje := 'Pago aplicado exitosamente. Folio: ' || v_folio;
    v_resultado.registro_id := v_pago_id;
    RETURN v_resultado;
END;
$$ LANGUAGE plpgsql;