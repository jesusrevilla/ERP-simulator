-- =====================================================================
--  Motor de Programación de Fechas y Costeo Planificado de Órdenes
--  de Producción por Hoja de Ruta
--
--  Autor:      Diego Luna Saucedo - 184814
--  Issue:      #300
--  Requiere:   Rutas/Scheme.sql (se ejecuta DESPUÉS de ese script)
--
--  Este script SOLO agrega objetos nuevos. No modifica ni borra
--  ninguna tabla, función o trigger de Rutas/Scheme.sql.
--
--  Supuestos de cálculo (documentados en README_184814.md):
--    * tiempo_ejecucion_min es por unidad; tiempo_preparacion_min es
--      una sola vez por etapa.
--    * dias_espera son días naturales que la etapa espera ANTES de
--      iniciar (desde el fin de la etapa anterior o desde el inicio
--      de la orden, si es la primera).
--    * Un día es laborable si así lo indica calendario_laboral; si la
--      fecha no está registrada, se consideran laborables de lunes a
--      viernes.
--    * Capacidad infinita: cada orden se programa por separado y los
--      choques entre órdenes se detectan en vw_carga_centro_dia.
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- 1. Tablas nuevas
-- ---------------------------------------------------------------------

-- Días laborables y no laborables de la planta.
CREATE TABLE calendario_laboral (
    fecha       DATE         PRIMARY KEY,
    laborable   BOOLEAN      NOT NULL,
    motivo      VARCHAR(120),
    CONSTRAINT ck_calendario_motivo
        CHECK (laborable OR (motivo IS NOT NULL AND btrim(motivo) <> ''))
);

-- Fecha que se le prometió al cliente o a la planta para cada orden.
CREATE TABLE orden_fecha_compromiso (
    orden_produccion_id INTEGER   PRIMARY KEY
                        REFERENCES orden_produccion (orden_produccion_id) ON DELETE CASCADE,
    fecha_compromiso    DATE      NOT NULL,
    registrado_en       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Horas que cada etapa ocupa de su centro de trabajo en cada día.
CREATE TABLE orden_etapa_carga_dia (
    orden_produccion_etapa_id   INTEGER      NOT NULL
                                REFERENCES orden_produccion_etapa (orden_produccion_etapa_id)
                                ON DELETE CASCADE,
    fecha                       DATE         NOT NULL,
    horas                       NUMERIC(8,2) NOT NULL CHECK (horas > 0),
    PRIMARY KEY (orden_produccion_etapa_id, fecha)
);

-- Bitácora de auditoría de cada programación, costeo o retraso.
-- En PROGRAMACION las fechas son las de la orden; en RETRASO, las de la
-- etapa retrasada.
CREATE TABLE orden_programacion_log (
    orden_programacion_log_id   INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    orden_produccion_id         INTEGER       NOT NULL
                                REFERENCES orden_produccion (orden_produccion_id),
    tipo                        VARCHAR(12)   NOT NULL
                                CHECK (tipo IN ('PROGRAMACION', 'COSTEO', 'RETRASO')),
    fecha_fin_anterior          DATE,
    fecha_fin_nueva             DATE,
    costo_anterior              NUMERIC(16,4),
    costo_nuevo                 NUMERIC(16,4),
    motivo                      VARCHAR(300),
    ejecutado_por               INTEGER       REFERENCES usuario (usuario_id),
    ejecutado_en                TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------------
-- 2. Índices
-- ---------------------------------------------------------------------
CREATE INDEX ix_carga_dia_fecha        ON orden_etapa_carga_dia (fecha);
CREATE INDEX ix_programacion_log_orden ON orden_programacion_log (orden_produccion_id, ejecutado_en);
CREATE INDEX ix_op_etapa_centro_fechas ON orden_produccion_etapa (centro_trabajo_id, fecha_inicio, fecha_fin);

-- ---------------------------------------------------------------------
-- 3. La bitácora no se puede modificar ni borrar
-- ---------------------------------------------------------------------
CREATE FUNCTION fn_bitacora_inmutable() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'La bitácora de programación no se puede modificar ni borrar';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_bitacora_inmutable
BEFORE UPDATE OR DELETE ON orden_programacion_log
FOR EACH ROW EXECUTE FUNCTION fn_bitacora_inmutable();

-- ---------------------------------------------------------------------
-- 4. Calendario
-- ---------------------------------------------------------------------
CREATE FUNCTION fn_es_laborable(p_fecha DATE) RETURNS BOOLEAN AS $$
    SELECT COALESCE(
        (SELECT c.laborable FROM calendario_laboral c WHERE c.fecha = p_fecha),
        EXTRACT(ISODOW FROM p_fecha) <= 5
    );
$$ LANGUAGE sql STABLE;

-- Primer día laborable que sea igual o posterior a p_fecha.
CREATE FUNCTION fn_siguiente_laborable(p_fecha DATE) RETURNS DATE AS $$
DECLARE
    v_fecha DATE := p_fecha;
BEGIN
    WHILE NOT fn_es_laborable(v_fecha) LOOP
        v_fecha := v_fecha + 1;
        IF v_fecha > p_fecha + 366 THEN
            RAISE EXCEPTION 'No hay días laborables en el año posterior a %', p_fecha;
        END IF;
    END LOOP;
    RETURN v_fecha;
END;
$$ LANGUAGE plpgsql STABLE;

-- ---------------------------------------------------------------------
-- 5. Copiar la hoja de ruta a la orden (etapas y líneas)
--    Solo se usa cuando la orden todavía no tiene etapas.
-- ---------------------------------------------------------------------
CREATE FUNCTION fn_generar_etapas_orden(p_orden_id INTEGER) RETURNS INTEGER AS $$
DECLARE
    o       orden_produccion%ROWTYPE;
    v_total INTEGER;
BEGIN
    SELECT * INTO o FROM orden_produccion WHERE orden_produccion_id = p_orden_id;

    -- Las fechas se dejan provisionalmente en el inicio de la orden;
    -- fn_programar_orden las calcula enseguida.
    INSERT INTO orden_produccion_etapa (
        orden_produccion_id, secuencia, etapa_ruta_id, centro_trabajo_id, almacen_id,
        tiempo_preparacion_min, tiempo_ejecucion_min, dias_espera, fecha_inicio, fecha_fin)
    SELECT o.orden_produccion_id, op.secuencia, op.etapa_ruta_id, op.centro_trabajo_id,
           o.almacen_id, op.tiempo_preparacion_min, op.tiempo_ejecucion_min, op.dias_espera,
           o.fecha_inicio, o.fecha_inicio
    FROM hoja_ruta_operacion op
    WHERE op.hoja_ruta_id = o.hoja_ruta_id;
    GET DIAGNOSTICS v_total = ROW_COUNT;

    IF v_total = 0 THEN
        RAISE EXCEPTION 'La hoja de ruta de la orden % no tiene operaciones', o.folio;
    END IF;

    -- Materiales: cantidad base por unidad × cantidad de la orden.
    INSERT INTO orden_produccion_linea (
        orden_produccion_id, orden_produccion_etapa_id, tipo, material_id,
        almacen_id, cantidad_planificada, costo_unitario)
    SELECT o.orden_produccion_id, e.orden_produccion_etapa_id, 'MATERIAL', m.material_id,
           COALESCE(hm.almacen_id, o.almacen_id), hm.cantidad_base * o.cantidad, m.costo_unitario
    FROM hoja_ruta_operacion op
    JOIN hoja_ruta_operacion_material hm ON hm.hoja_ruta_operacion_id = op.hoja_ruta_operacion_id
    JOIN material m                      ON m.material_id = hm.material_id
    JOIN orden_produccion_etapa e        ON e.orden_produccion_id = o.orden_produccion_id
                                        AND e.secuencia = op.secuencia
    WHERE op.hoja_ruta_id = o.hoja_ruta_id;

    -- Recursos: horas base por unidad × cantidad de la orden.
    INSERT INTO orden_produccion_linea (
        orden_produccion_id, orden_produccion_etapa_id, tipo, recurso_id,
        cantidad_planificada, costo_unitario)
    SELECT o.orden_produccion_id, e.orden_produccion_etapa_id, 'RECURSO', r.recurso_id,
           hr.horas_base * o.cantidad, r.costo_hora
    FROM hoja_ruta_operacion op
    JOIN hoja_ruta_operacion_recurso hr ON hr.hoja_ruta_operacion_id = op.hoja_ruta_operacion_id
    JOIN recurso r                      ON r.recurso_id = hr.recurso_id
    JOIN orden_produccion_etapa e       ON e.orden_produccion_id = o.orden_produccion_id
                                       AND e.secuencia = op.secuencia
    WHERE op.hoja_ruta_id = o.hoja_ruta_id;

    RETURN v_total;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------
-- 6. Costeo planificado
--    material + recurso + centro de trabajo (horas × costo por hora)
-- ---------------------------------------------------------------------
CREATE FUNCTION fn_calcular_costo_planificado(
    p_orden_id    INTEGER,
    p_motivo      VARCHAR DEFAULT 'Recálculo de costo planificado',
    p_usuario_id  INTEGER DEFAULT NULL,
    p_registrar   BOOLEAN DEFAULT TRUE
) RETURNS TABLE (
    costo_material  NUMERIC,
    costo_recurso   NUMERIC,
    costo_centro    NUMERIC,
    costo_total     NUMERIC
) AS $$
DECLARE
    o          orden_produccion%ROWTYPE;
    v_material NUMERIC;
    v_recurso  NUMERIC;
    v_centro   NUMERIC;
BEGIN
    SELECT * INTO o FROM orden_produccion WHERE orden_produccion_id = p_orden_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'No existe la orden de producción %', p_orden_id;
    END IF;

    SELECT COALESCE(SUM(l.cantidad_planificada * l.costo_unitario)
                    FILTER (WHERE l.tipo = 'MATERIAL'), 0),
           COALESCE(SUM(l.cantidad_planificada * l.costo_unitario)
                    FILTER (WHERE l.tipo = 'RECURSO'), 0)
      INTO v_material, v_recurso
    FROM orden_produccion_linea l
    WHERE l.orden_produccion_id = p_orden_id;

    SELECT COALESCE(SUM((e.tiempo_preparacion_min + e.tiempo_ejecucion_min * o.cantidad)
                        / 60.0 * ct.costo_hora), 0)
      INTO v_centro
    FROM orden_produccion_etapa e
    JOIN centro_trabajo ct ON ct.centro_trabajo_id = e.centro_trabajo_id
    WHERE e.orden_produccion_id = p_orden_id;

    costo_material := round(v_material, 4);
    costo_recurso  := round(v_recurso, 4);
    costo_centro   := round(v_centro, 4);
    costo_total    := costo_material + costo_recurso + costo_centro;

    UPDATE orden_produccion
       SET costo_planificado = costo_total
     WHERE orden_produccion_id = p_orden_id;

    IF p_registrar THEN
        INSERT INTO orden_programacion_log (
            orden_produccion_id, tipo, costo_anterior, costo_nuevo, motivo, ejecutado_por)
        VALUES (p_orden_id, 'COSTEO', o.costo_planificado, costo_total, p_motivo, p_usuario_id);
    END IF;

    RETURN NEXT;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------
-- 7. Programación de fechas
--    Calcula inicio y fin de cada etapa PENDIENTE de la orden; las
--    etapas EN_PROCESO o COMPLETADA conservan sus fechas.
-- ---------------------------------------------------------------------
CREATE FUNCTION fn_programar_orden(
    p_orden_id    INTEGER,
    p_motivo      VARCHAR DEFAULT NULL,
    p_usuario_id  INTEGER DEFAULT NULL
) RETURNS TABLE (
    orden_produccion_id INTEGER,
    fecha_fin_anterior  DATE,
    fecha_fin_nueva     DATE,
    costo_planificado   NUMERIC
) AS $$
#variable_conflict use_column
DECLARE
    o            orden_produccion%ROWTYPE;
    e            RECORD;
    v_cursor     DATE;
    v_inicio     DATE;
    v_dia        DATE;
    v_restante   NUMERIC;
    v_horas      NUMERIC;
    v_fin_orden  DATE;
    v_costo      NUMERIC;
BEGIN
    SELECT * INTO o FROM orden_produccion op
    WHERE op.orden_produccion_id = p_orden_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'No existe la orden de producción %', p_orden_id;
    END IF;
    IF o.estatus IN ('CERRADA', 'CANCELADA') THEN
        RAISE EXCEPTION 'La orden % está % y no se puede programar', o.folio, o.estatus;
    END IF;
    IF o.estatus = 'LIBERADA' AND (p_motivo IS NULL OR btrim(p_motivo) = '') THEN
        RAISE EXCEPTION 'La orden % ya está liberada: indique el motivo de la reprogramación', o.folio;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM orden_produccion_etapa x
                   WHERE x.orden_produccion_id = p_orden_id) THEN
        PERFORM fn_generar_etapas_orden(p_orden_id);
    END IF;

    -- Fechas de trabajo en una tabla temporal: primero se calcula todo,
    -- después se actualiza la orden y las etapas.
    CREATE TEMP TABLE IF NOT EXISTS tmp_programa (
        etapa_id INTEGER, fecha_inicio DATE, fecha_fin DATE
    ) ON COMMIT DROP;
    CREATE TEMP TABLE IF NOT EXISTS tmp_carga (
        etapa_id INTEGER, fecha DATE, horas NUMERIC
    ) ON COMMIT DROP;
    TRUNCATE tmp_programa;
    TRUNCATE tmp_carga;

    v_cursor := o.fecha_inicio;

    FOR e IN
        SELECT pe.orden_produccion_etapa_id, pe.secuencia, pe.estatus,
               pe.tiempo_preparacion_min, pe.tiempo_ejecucion_min, pe.dias_espera,
               pe.fecha_inicio, pe.fecha_fin, ct.capacidad_horas_dia
        FROM orden_produccion_etapa pe
        JOIN centro_trabajo ct ON ct.centro_trabajo_id = pe.centro_trabajo_id
        WHERE pe.orden_produccion_id = p_orden_id
        ORDER BY pe.secuencia
    LOOP
        IF e.estatus <> 'PENDIENTE' THEN
            -- Ya inició: se respetan sus fechas y su carga.
            INSERT INTO tmp_programa VALUES (e.orden_produccion_etapa_id, e.fecha_inicio, e.fecha_fin);
            v_cursor := GREATEST(v_cursor, e.fecha_fin + 1);
            CONTINUE;
        END IF;

        v_inicio   := fn_siguiente_laborable(v_cursor + e.dias_espera);
        v_restante := (e.tiempo_preparacion_min + e.tiempo_ejecucion_min * o.cantidad) / 60.0;
        v_dia      := v_inicio;

        LOOP
            v_horas := LEAST(v_restante, e.capacidad_horas_dia);
            INSERT INTO tmp_carga VALUES (e.orden_produccion_etapa_id, v_dia, round(v_horas, 2));
            v_restante := v_restante - v_horas;
            EXIT WHEN v_restante <= 0;
            v_dia := fn_siguiente_laborable(v_dia + 1);
        END LOOP;

        INSERT INTO tmp_programa VALUES (e.orden_produccion_etapa_id, v_inicio, v_dia);
        v_cursor := v_dia + 1;
    END LOOP;

    SELECT max(t.fecha_fin) INTO v_fin_orden FROM tmp_programa t;

    -- Primero el horizonte de la orden, para que tr_validar_horizonte_etapa
    -- (Scheme.sql) acepte las nuevas fechas de las etapas.
    UPDATE orden_produccion op
       SET fecha_fin = v_fin_orden
     WHERE op.orden_produccion_id = p_orden_id;

    UPDATE orden_produccion_etapa pe
       SET fecha_inicio = t.fecha_inicio,
           fecha_fin    = t.fecha_fin
      FROM tmp_programa t
     WHERE pe.orden_produccion_etapa_id = t.etapa_id
       AND pe.estatus = 'PENDIENTE';

    DELETE FROM orden_etapa_carga_dia c
     USING orden_produccion_etapa pe
     WHERE c.orden_produccion_etapa_id = pe.orden_produccion_etapa_id
       AND pe.orden_produccion_id = p_orden_id
       AND pe.estatus = 'PENDIENTE';

    INSERT INTO orden_etapa_carga_dia (orden_produccion_etapa_id, fecha, horas)
    SELECT t.etapa_id, t.fecha, t.horas FROM tmp_carga t WHERE t.horas > 0;

    SELECT c.costo_total INTO v_costo
    FROM fn_calcular_costo_planificado(p_orden_id, NULL, p_usuario_id, FALSE) c;

    INSERT INTO orden_programacion_log (
        orden_produccion_id, tipo, fecha_fin_anterior, fecha_fin_nueva,
        costo_anterior, costo_nuevo, motivo, ejecutado_por)
    VALUES (p_orden_id, 'PROGRAMACION', o.fecha_fin, v_fin_orden,
            o.costo_planificado, v_costo,
            COALESCE(p_motivo, 'Programación de la orden'), p_usuario_id);

    orden_produccion_id := p_orden_id;
    fecha_fin_anterior  := o.fecha_fin;
    fecha_fin_nueva     := v_fin_orden;
    costo_planificado   := v_costo;
    RETURN NEXT;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------
-- 8. Registrar el retraso de una etapa y reprogramar lo que sigue
-- ---------------------------------------------------------------------
CREATE FUNCTION fn_registrar_retraso(
    p_etapa_id    INTEGER,
    p_dias        INTEGER,
    p_motivo      VARCHAR,
    p_usuario_id  INTEGER DEFAULT NULL
) RETURNS TABLE (
    orden_produccion_id INTEGER,
    fecha_fin_anterior  DATE,
    fecha_fin_nueva     DATE,
    costo_planificado   NUMERIC
) AS $$
#variable_conflict use_column
DECLARE
    e         orden_produccion_etapa%ROWTYPE;
    o         orden_produccion%ROWTYPE;
    v_nuevo   DATE;
BEGIN
    IF p_dias IS NULL OR p_dias < 1 THEN
        RAISE EXCEPTION 'El retraso debe ser de al menos 1 día';
    END IF;
    IF p_motivo IS NULL OR btrim(p_motivo) = '' THEN
        RAISE EXCEPTION 'Indique el motivo del retraso';
    END IF;

    SELECT * INTO e FROM orden_produccion_etapa x WHERE x.orden_produccion_etapa_id = p_etapa_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'No existe la etapa %', p_etapa_id;
    END IF;
    IF e.estatus = 'COMPLETADA' THEN
        RAISE EXCEPTION 'La etapa % ya está completada', e.secuencia;
    END IF;

    SELECT * INTO o FROM orden_produccion x
    WHERE x.orden_produccion_id = e.orden_produccion_id FOR UPDATE;

    -- Se recorren p_dias días laborables a partir del fin actual.
    v_nuevo := e.fecha_fin;
    FOR i IN 1..p_dias LOOP
        v_nuevo := fn_siguiente_laborable(v_nuevo + 1);
    END LOOP;

    UPDATE orden_produccion x
       SET fecha_fin = GREATEST(x.fecha_fin, v_nuevo)
     WHERE x.orden_produccion_id = o.orden_produccion_id;

    -- La etapa retrasada se marca EN_PROCESO para que conserve su nueva fecha.
    UPDATE orden_produccion_etapa x
       SET fecha_fin = v_nuevo,
           estatus   = 'EN_PROCESO'
     WHERE x.orden_produccion_etapa_id = p_etapa_id;

    INSERT INTO orden_programacion_log (
        orden_produccion_id, tipo, fecha_fin_anterior, fecha_fin_nueva, motivo, ejecutado_por)
    VALUES (o.orden_produccion_id, 'RETRASO', e.fecha_fin, v_nuevo,
            format('Etapa %s: %s', e.secuencia, p_motivo), p_usuario_id);

    RETURN QUERY
    SELECT * FROM fn_programar_orden(o.orden_produccion_id,
                                     format('Reprogramación por retraso de la etapa %s', e.secuencia),
                                     p_usuario_id);
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------
-- 9. Reenumeración de secuencias (nodo D3)
--    Recorre +1 todas las operaciones desde p_desde_secuencia para dejar
--    libre ese número e insertar ahí una operación intermedia.
-- ---------------------------------------------------------------------
CREATE FUNCTION fn_reenumerar_secuencia(
    p_hoja_ruta_id     INTEGER,
    p_desde_secuencia  INTEGER
) RETURNS INTEGER AS $$
DECLARE
    v_estatus hoja_ruta.estatus%TYPE;
    v_total   INTEGER;
BEGIN
    SELECT estatus INTO v_estatus FROM hoja_ruta
    WHERE hoja_ruta_id = p_hoja_ruta_id FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'No existe la hoja de ruta %', p_hoja_ruta_id;
    END IF;
    IF v_estatus NOT IN ('BORRADOR', 'EN_REVISION') THEN
        RAISE EXCEPTION 'Solo se reenumeran hojas en BORRADOR o EN_REVISION (estatus actual: %)', v_estatus;
    END IF;
    IF p_desde_secuencia IS NULL OR p_desde_secuencia < 1 THEN
        RAISE EXCEPTION 'La secuencia inicial debe ser mayor o igual a 1';
    END IF;

    -- uq_hoja_ruta_operacion_secuencia es DEFERRABLE: se revisa al final
    -- de la sentencia, así que el recorrido +1 no choca a la mitad.
    UPDATE hoja_ruta_operacion
       SET secuencia = secuencia + 1
     WHERE hoja_ruta_id = p_hoja_ruta_id
       AND secuencia >= p_desde_secuencia;
    GET DIAGNOSTICS v_total = ROW_COUNT;

    RETURN v_total;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------
-- 10. Vistas para los agentes
-- ---------------------------------------------------------------------

-- Programa de cada orden, etapa por etapa, con holgura contra el compromiso.
CREATE VIEW vw_programa_ordenes AS
SELECT o.orden_produccion_id,
       o.folio,
       o.estatus                       AS estatus_orden,
       o.cantidad,
       e.orden_produccion_etapa_id,
       e.secuencia,
       er.codigo                       AS etapa,
       ct.codigo                       AS centro_trabajo,
       e.estatus                       AS estatus_etapa,
       e.fecha_inicio,
       e.fecha_fin,
       (SELECT count(*) FROM orden_etapa_carga_dia c
        WHERE c.orden_produccion_etapa_id = e.orden_produccion_etapa_id) AS dias_laborables,
       o.fecha_fin                     AS fecha_fin_orden,
       fc.fecha_compromiso,
       fc.fecha_compromiso - o.fecha_fin AS holgura_dias
FROM orden_produccion o
JOIN orden_produccion_etapa e ON e.orden_produccion_id = o.orden_produccion_id
JOIN etapa_ruta er            ON er.etapa_ruta_id = e.etapa_ruta_id
JOIN centro_trabajo ct        ON ct.centro_trabajo_id = e.centro_trabajo_id
LEFT JOIN orden_fecha_compromiso fc ON fc.orden_produccion_id = o.orden_produccion_id;

-- Horas programadas por centro y día contra su capacidad.
CREATE VIEW vw_carga_centro_dia AS
SELECT ct.centro_trabajo_id,
       ct.codigo                               AS centro_trabajo,
       c.fecha,
       sum(c.horas)                            AS horas_programadas,
       ct.capacidad_horas_dia,
       round(sum(c.horas) / ct.capacidad_horas_dia * 100, 1) AS porcentaje_uso,
       sum(c.horas) > ct.capacidad_horas_dia   AS sobrecargado,
       string_agg(DISTINCT o.folio, ', ' ORDER BY o.folio) AS ordenes
FROM orden_etapa_carga_dia c
JOIN orden_produccion_etapa e ON e.orden_produccion_etapa_id = c.orden_produccion_etapa_id
JOIN orden_produccion o       ON o.orden_produccion_id = e.orden_produccion_id
JOIN centro_trabajo ct        ON ct.centro_trabajo_id = e.centro_trabajo_id
WHERE o.estatus IN ('PLANIFICADA', 'LIBERADA')
GROUP BY ct.centro_trabajo_id, ct.codigo, c.fecha, ct.capacidad_horas_dia;

-- Costo planificado contra real, por orden y por etapa.
-- El costo real viene de los despachos de material (tr_registrar_despacho en
-- Scheme.sql), así que la desviación se mide sobre lo YA despachado:
--   costo_estandar_despachado = cantidad despachada × costo planificado
--   costo_real_despachado     = cantidad despachada × costo real del despacho
-- Así una etapa sin despachos no aparece como -100 %.
CREATE VIEW vw_desviacion_costos AS
WITH etapa AS (
    SELECT o.orden_produccion_id,
           o.folio,
           e.secuencia,
           COALESCE(l.material_planificado, 0) + COALESCE(l.recurso_planificado, 0)
         + (e.tiempo_preparacion_min + e.tiempo_ejecucion_min * o.cantidad) / 60.0 * ct.costo_hora
               AS costo_planificado,
           COALESCE(l.material_planificado, 0)        AS costo_material_planificado,
           COALESCE(d.estandar, 0)                    AS costo_estandar_despachado,
           COALESCE(d.real, 0)                        AS costo_real_despachado
    FROM orden_produccion_etapa e
    JOIN orden_produccion o ON o.orden_produccion_id = e.orden_produccion_id
    JOIN centro_trabajo ct  ON ct.centro_trabajo_id = e.centro_trabajo_id
    LEFT JOIN LATERAL (
        SELECT sum(x.cantidad_planificada * x.costo_unitario) FILTER (WHERE x.tipo = 'MATERIAL') AS material_planificado,
               sum(x.cantidad_planificada * x.costo_unitario) FILTER (WHERE x.tipo = 'RECURSO')  AS recurso_planificado
        FROM orden_produccion_linea x
        WHERE x.orden_produccion_etapa_id = e.orden_produccion_etapa_id
    ) l ON TRUE
    LEFT JOIN LATERAL (
        SELECT sum(dp.cantidad * li.costo_unitario) AS estandar,
               sum(dp.cantidad * dp.costo_unitario) AS real
        FROM despacho_produccion dp
        JOIN orden_produccion_linea li ON li.orden_produccion_linea_id = dp.orden_produccion_linea_id
        WHERE dp.orden_produccion_etapa_id = e.orden_produccion_etapa_id
    ) d ON TRUE
),
nivel AS (
    SELECT 'ETAPA'::VARCHAR(5) AS nivel, folio, secuencia, costo_planificado,
           costo_material_planificado, costo_estandar_despachado, costo_real_despachado
    FROM etapa
    UNION ALL
    SELECT 'ORDEN', folio, NULL, sum(costo_planificado), sum(costo_material_planificado),
           sum(costo_estandar_despachado), sum(costo_real_despachado)
    FROM etapa
    GROUP BY folio
)
SELECT nivel,
       folio,
       secuencia,
       round(costo_planificado, 2)                                   AS costo_planificado,
       round(costo_estandar_despachado, 2)                           AS costo_estandar_despachado,
       round(costo_real_despachado, 2)                               AS costo_real_despachado,
       round(costo_real_despachado - costo_estandar_despachado, 2)   AS desviacion,
       CASE WHEN costo_estandar_despachado > 0
            THEN round((costo_real_despachado - costo_estandar_despachado)
                       / costo_estandar_despachado * 100, 2)
       END                                                           AS desviacion_pct,
       CASE WHEN costo_material_planificado > 0
            THEN round(costo_estandar_despachado / costo_material_planificado * 100, 1)
       END                                                           AS avance_despacho_pct
FROM nivel;

COMMIT;
