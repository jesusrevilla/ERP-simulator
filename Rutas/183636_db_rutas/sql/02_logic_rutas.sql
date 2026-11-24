-- ============================================================================
-- Issue #249 - Vistas, Procedimientos y Triggers (PostgreSQL)
-- ============================================================================

-- 1. Función y Trigger de Auditoría Automática
CREATE OR REPLACE FUNCTION fn_auditar_ruta_operaciones()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO auditoria_rutas (operacion_id, ruta_id, accion, detalle_cambio)
        VALUES (
            NEW.operacion_id,
            NEW.ruta_id,
            'INSERT',
            FORMAT('Se agregó operación "%s" (Secuencia %s, Ejecución: %s min)', NEW.nombre_operacion, NEW.numero_secuencia, NEW.tiempo_ejecucion_min)
        );
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO auditoria_rutas (operacion_id, ruta_id, accion, detalle_cambio)
        VALUES (
            NEW.operacion_id,
            NEW.ruta_id,
            'UPDATE',
            FORMAT('Operación "%s" actualizada. Tiempo ejecución: %s -> %s min', NEW.nombre_operacion, OLD.tiempo_ejecucion_min, NEW.tiempo_ejecucion_min)
        );
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO auditoria_rutas (operacion_id, ruta_id, accion, detalle_cambio)
        VALUES (
            OLD.operacion_id,
            OLD.ruta_id,
            'DELETE',
            FORMAT('Se eliminó operación "%s" (Secuencia %s)', OLD.nombre_operacion, OLD.numero_secuencia)
        );
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_auditar_ruta_operaciones
AFTER INSERT OR UPDATE OR DELETE ON ruta_operaciones
FOR EACH ROW
EXECUTE FUNCTION fn_auditar_ruta_operaciones();

-- 2. Procedimiento Almacenado para registrar operación y recalcular tiempo total de la ruta
CREATE OR REPLACE PROCEDURE sp_registrar_operacion_ruta(
    p_ruta_id INT,
    p_estacion_id INT,
    p_secuencia INT,
    p_nombre_operacion VARCHAR,
    p_tiempo_setup INT,
    p_tiempo_ejecucion INT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_estado_estacion VARCHAR(20);
BEGIN
    SELECT estado INTO v_estado_estacion
    FROM estaciones_trabajo
    WHERE estacion_id = p_estacion_id;

    IF v_estado_estacion IS NULL THEN
        RAISE EXCEPTION 'La estación de trabajo % no existe.', p_estacion_id;
    ELSIF v_estado_estacion <> 'ACTIVA' THEN
        RAISE EXCEPTION 'La estación % no está ACTIVA (Estado actual: %).', p_estacion_id, v_estado_estacion;
    END IF;

    INSERT INTO ruta_operaciones (
        ruta_id, estacion_id, numero_secuencia, nombre_operacion, tiempo_setup_min, tiempo_ejecucion_min
    )
    VALUES (
        p_ruta_id, p_estacion_id, p_secuencia, p_nombre_operacion, p_tiempo_setup, p_tiempo_ejecucion
    );

    -- Recalcular tiempo total estimado en el encabezado de la ruta
    UPDATE rutas
    SET tiempo_total_estimado_min = (
        SELECT COALESCE(SUM(tiempo_setup_min + tiempo_ejecucion_min), 0)
        FROM ruta_operaciones
        WHERE ruta_id = p_ruta_id
    )
    WHERE ruta_id = p_ruta_id;
END;
$$;

-- 3. Vista Analítica: Resumen de Costos y Tiempos por Ruta
CREATE OR REPLACE VIEW vw_resumen_rutas AS
SELECT
    r.ruta_id,
    r.codigo_ruta,
    r.producto_sku,
    COUNT(ro.operacion_id) AS total_operaciones,
    r.tiempo_total_estimado_min,
    ROUND(SUM(((ro.tiempo_setup_min + ro.tiempo_ejecucion_min) / 60.0) * e.costo_por_hora), 2) AS costo_estimado_usd
FROM rutas r
LEFT JOIN ruta_operaciones ro ON r.ruta_id = ro.ruta_id
LEFT JOIN estaciones_trabajo e ON ro.estacion_id = e.estacion_id
WHERE r.activa = TRUE
GROUP BY r.ruta_id, r.codigo_ruta, r.producto_sku, r.tiempo_total_estimado_min;

-- 4. Vista Analítica: Detección de Cuellos de Botella en Estaciones
CREATE OR REPLACE VIEW vw_carga_estaciones AS
SELECT
    e.estacion_id,
    e.codigo,
    e.nombre,
    e.estado,
    e.capacidad_diaria_min,
    COALESCE(SUM(ro.tiempo_setup_min + ro.tiempo_ejecucion_min), 0) AS carga_asignada_min,
    ROUND(
        (COALESCE(SUM(ro.tiempo_setup_min + ro.tiempo_ejecucion_min), 0)::NUMERIC / e.capacidad_diaria_min) * 100,
        2
    ) AS porcentaje_ocupacion
FROM estaciones_trabajo e
LEFT JOIN ruta_operaciones ro ON e.estacion_id = ro.estacion_id
GROUP BY e.estacion_id, e.codigo, e.nombre, e.estado, e.capacidad_diaria_min;