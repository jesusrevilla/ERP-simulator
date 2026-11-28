-- ============================================================================
-- 02_mrp_functions_views.sql
-- Motor Analítico MRP: Resolución de Vigencias, Conversión UOM,
-- Explosión Aplanada (WITH RECURSIVE + RN08 + PU09), Cost Roll-up y Trigger
-- Issue #269 - Integrante 4 (Matrícula: 184027)
-- ============================================================================

-- 1. Factor de conversión UOM (integración con Issue 1: conversiones_uom)
CREATE OR REPLACE FUNCTION fn_obtener_factor_uom(
    p_uom_origen  VARCHAR(10),
    p_uom_destino VARCHAR(10),
    p_sku         VARCHAR(50) DEFAULT NULL
)
RETURNS NUMERIC(18, 8)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_factor NUMERIC(18, 8);
BEGIN
    IF p_uom_origen = p_uom_destino THEN
        RETURN 1.00000000;
    END IF;

    -- Prioridad 1: conversión específica para el SKU; Prioridad 2: conversión general
    SELECT factor_multiplicador
      INTO v_factor
      FROM conversiones_uom
     WHERE uom_origen_id = p_uom_origen
       AND uom_destino_id = p_uom_destino
       AND (sku_especifico = p_sku OR sku_especifico IS NULL)
     ORDER BY (sku_especifico IS NULL) ASC
     LIMIT 1;

    IF v_factor IS NULL THEN
        RAISE EXCEPTION 'BOM.ValidationFailed: No existe conversión UOM de % hacia % para SKU %.',
            p_uom_origen, p_uom_destino, COALESCE(p_sku, 'GENERICO');
    END IF;

    RETURN v_factor;
END;
$$;

-- 2. Selección estricta de versión ACTIVA vigente en [fecha_inicio, fecha_fin) (RN01, RN06, RN07, RN-15, PU08)
CREATE OR REPLACE FUNCTION fn_resolver_version_vigente(
    p_parent_sku  VARCHAR(50),
    p_fecha       TIMESTAMPTZ,
    p_permitir_mp BOOLEAN DEFAULT FALSE
)
RETURNS TABLE (
    bom_id          BIGINT,
    parent_sku      VARCHAR(50),
    version_codigo  VARCHAR(20),
    cantidad_base   NUMERIC(14, 4),
    uom_id          VARCHAR(10),
    uom_base_id     VARCHAR(10)
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_item       RECORD;
    v_count      INT;
    v_line_count INT;
    v_header     RECORD;
BEGIN
    SELECT a.sku, a.tipo_item, a.activo, a.uom_base_id
      INTO v_item
      FROM articulos a
     WHERE a.sku = p_parent_sku;

    IF NOT FOUND OR NOT v_item.activo THEN
        RAISE EXCEPTION 'BOM.ValidationFailed: Artículo "%" inexistente o inactivo en catálogo maestro.', p_parent_sku;
    END IF;

    IF v_item.tipo_item = 'MP' THEN
        IF p_permitir_mp THEN
            RETURN;
        END IF;
        RAISE EXCEPTION 'BOM.ValidationFailed: Materia Prima "%" no puede tener BOM (RN01/RN-15).', p_parent_sku;
    END IF;

    SELECT COUNT(*)
      INTO v_count
      FROM bom_cabecera bc
     WHERE bc.parent_sku = p_parent_sku
       AND bc.estado = 'ACTIVO'
       AND bc.fecha_inicio <= p_fecha
       AND (bc.fecha_fin IS NULL OR p_fecha < bc.fecha_fin);

    IF v_count = 0 THEN
        RAISE EXCEPTION 'BOM.ExplosionRejected: No existe versión ACTIVA para "%" en %.', p_parent_sku, p_fecha;
    END IF;

    IF v_count > 1 THEN
        RAISE EXCEPTION 'BOM.ConcurrencyConflict: Traslape de vigencias activas para "%".', p_parent_sku;
    END IF;

    SELECT bc.bom_id, bc.parent_sku, bc.version_codigo, bc.cantidad_base, bc.uom_id
      INTO v_header
      FROM bom_cabecera bc
     WHERE bc.parent_sku = p_parent_sku
       AND bc.estado = 'ACTIVO'
       AND bc.fecha_inicio <= p_fecha
       AND (bc.fecha_fin IS NULL OR p_fecha < bc.fecha_fin)
     LIMIT 1;

    SELECT COUNT(*)
      INTO v_line_count
      FROM bom_detalle bd
     WHERE bd.bom_id = v_header.bom_id;

    IF v_line_count = 0 THEN
        RAISE EXCEPTION 'BOM.ValidationFailed: BOM "%" de "%" no tiene componentes (RN01).',
            v_header.version_codigo, p_parent_sku;
    END IF;

    bom_id         := v_header.bom_id;
    parent_sku     := v_header.parent_sku;
    version_codigo := v_header.version_codigo;
    cantidad_base  := v_header.cantidad_base;
    uom_id         := v_header.uom_id;
    uom_base_id    := v_item.uom_base_id;
    RETURN NEXT;
END;
$$;

-- 3. Explosión multinivel aplanada (Summarized BOM) con RN08 y redondeo final PU09
CREATE OR REPLACE FUNCTION fn_explode_bom_summarized(
    p_parent_sku       VARCHAR(50),
    p_cantidad_demanda NUMERIC(14, 4),
    p_fecha_demanda    TIMESTAMPTZ
)
RETURNS TABLE (
    mp_sku                   VARCHAR(50),
    uom_base_id              VARCHAR(10),
    es_discreto              BOOLEAN,
    rutas_detectadas         BIGINT,
    cantidad_bruta_exacta    NUMERIC(16, 4),
    cantidad_requerida_final NUMERIC(16, 4),
    costo_unitario           NUMERIC(14, 4),
    costo_total_estimado     NUMERIC(16, 2)
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_ciclo_ruta  TEXT;
    v_mp_inactiva VARCHAR(50);
BEGIN
    IF p_cantidad_demanda IS NULL OR p_cantidad_demanda <= 0 THEN
        RAISE EXCEPTION 'BOM.ValidationFailed: La cantidad de demanda debe ser mayor a cero.';
    END IF;

    -- Verificación de salvaguarda anti-ciclos e integridad de hojas inactivas
    WITH RECURSIVE bom_tree AS (
        SELECT
            0 AS nivel,
            v.parent_sku AS sku_padre,
            d.component_sku,
            a_comp.tipo_item AS comp_tipo,
            a_comp.activo AS comp_activo,
            (d.component_sku = v.parent_sku) AS es_ciclo,
            ARRAY[v.parent_sku::TEXT, d.component_sku::TEXT] AS ruta
        FROM fn_resolver_version_vigente(p_parent_sku, p_fecha_demanda, FALSE) v
        JOIN bom_detalle d ON d.bom_id = v.bom_id
        JOIN articulos a_comp ON a_comp.sku = d.component_sku

        UNION ALL

        SELECT
            bt.nivel + 1,
            v.parent_sku,
            d.component_sku,
            a_comp.tipo_item,
            a_comp.activo,
            (d.component_sku = ANY(bt.ruta)) AS es_ciclo,
            bt.ruta || d.component_sku::TEXT
        FROM bom_tree bt
        CROSS JOIN LATERAL fn_resolver_version_vigente(bt.component_sku, p_fecha_demanda, TRUE) v
        JOIN bom_detalle d ON d.bom_id = v.bom_id
        JOIN articulos a_comp ON a_comp.sku = d.component_sku
        WHERE NOT bt.es_ciclo
          AND bt.nivel < 50
    )
    SELECT
        (SELECT array_to_string(ruta, ' -> ') FROM bom_tree WHERE es_ciclo LIMIT 1),
        (SELECT component_sku FROM bom_tree WHERE comp_tipo = 'MP' AND NOT comp_activo LIMIT 1)
      INTO v_ciclo_ruta, v_mp_inactiva;

    IF v_ciclo_ruta IS NOT NULL THEN
        RAISE EXCEPTION 'BOM.ValidationFailed: Ciclo estructural detectado -> % (RN03/RN-13).', v_ciclo_ruta;
    END IF;

    IF v_mp_inactiva IS NOT NULL THEN
        RAISE EXCEPTION 'BOM.ValidationFailed: Materia Prima "%" inactiva en catálogo maestro.', v_mp_inactiva;
    END IF;

    -- Explosión ponderada RN08 + consolidación de ramas + redondeo PU09 al final
    RETURN QUERY
    WITH RECURSIVE bom_tree AS (
        SELECT
            0 AS nivel,
            d.component_sku,
            a_comp.tipo_item AS comp_tipo,
            a_comp.uom_base_id AS comp_uom_base,
            a_comp.es_discreto AS comp_discreto,
            a_comp.costo_estandar AS comp_costo,
            (
                (d.cantidad * fn_obtener_factor_uom(d.uom_id, a_comp.uom_base_id, d.component_sku))
                / (
                    v.cantidad_base
                    * fn_obtener_factor_uom(v.uom_id, v.uom_base_id, v.parent_sku)
                    * (1.0 - d.scrap_merma)
                )
            )::NUMERIC(24, 10) AS factor_unitario,
            ARRAY[v.parent_sku::TEXT, d.component_sku::TEXT] AS ruta
        FROM fn_resolver_version_vigente(p_parent_sku, p_fecha_demanda, FALSE) v
        JOIN bom_detalle d ON d.bom_id = v.bom_id
        JOIN articulos a_comp ON a_comp.sku = d.component_sku

        UNION ALL

        SELECT
            bt.nivel + 1,
            d.component_sku,
            a_comp.tipo_item,
            a_comp.uom_base_id,
            a_comp.es_discreto,
            a_comp.costo_estandar,
            (
                bt.factor_unitario
                * (d.cantidad * fn_obtener_factor_uom(d.uom_id, a_comp.uom_base_id, d.component_sku))
                / (
                    v.cantidad_base
                    * fn_obtener_factor_uom(v.uom_id, v.uom_base_id, v.parent_sku)
                    * (1.0 - d.scrap_merma)
                )
            )::NUMERIC(24, 10),
            bt.ruta || d.component_sku::TEXT
        FROM bom_tree bt
        CROSS JOIN LATERAL fn_resolver_version_vigente(bt.component_sku, p_fecha_demanda, TRUE) v
        JOIN bom_detalle d ON d.bom_id = v.bom_id
        JOIN articulos a_comp ON a_comp.sku = d.component_sku
        WHERE NOT (d.component_sku = ANY(bt.ruta))
          AND bt.nivel < 50
    ),
    hojas_consolidadas AS (
        SELECT
            bt.component_sku AS sku,
            bt.comp_uom_base AS uom_base,
            bt.comp_discreto AS discreto,
            bt.comp_costo AS costo_unit,
            COUNT(*)::BIGINT AS num_rutas,
            (SUM(bt.factor_unitario) * p_cantidad_demanda) AS bruta_sin_redondeo
        FROM bom_tree bt
        WHERE bt.comp_tipo = 'MP'
        GROUP BY bt.component_sku, bt.comp_uom_base, bt.comp_discreto, bt.comp_costo
    )
    SELECT
        hc.sku::VARCHAR(50) AS mp_sku,
        hc.uom_base::VARCHAR(10) AS uom_base_id,
        hc.discreto AS es_discreto,
        hc.num_rutas AS rutas_detectadas,
        ROUND(hc.bruta_sin_redondeo, 4)::NUMERIC(16, 4) AS cantidad_bruta_exacta,
        (
            CASE
                WHEN hc.discreto THEN CEIL(hc.bruta_sin_redondeo)
                ELSE ROUND(hc.bruta_sin_redondeo, 4)
            END
        )::NUMERIC(16, 4) AS cantidad_requerida_final,
        hc.costo_unit::NUMERIC(14, 4) AS costo_unitario,
        ROUND(
            (
                CASE
                    WHEN hc.discreto THEN CEIL(hc.bruta_sin_redondeo)
                    ELSE ROUND(hc.bruta_sin_redondeo, 4)
                END
            ) * hc.costo_unit,
            2
        )::NUMERIC(16, 2) AS costo_total_estimado
    FROM hojas_consolidadas hc
    ORDER BY hc.sku;
END;
$$;

-- 4. Ejecución persistente y atómica de corrida MRP (genera payload JSONB BOM.Exploded para Issue 5)
CREATE OR REPLACE FUNCTION fn_ejecutar_corrida_mrp(
    p_parent_sku       VARCHAR(50),
    p_cantidad_demanda NUMERIC(14, 4),
    p_fecha_demanda    TIMESTAMPTZ,
    p_event_id         VARCHAR(80) DEFAULT 'EVT-MRP-201'
)
RETURNS TABLE (
    run_id               BIGINT,
    estado_ejecucion     VARCHAR(30),
    costo_total_estimado NUMERIC(16, 2),
    payload_evento       JSONB
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_run_id      BIGINT;
    v_costo_total NUMERIC(16, 2);
    v_payload     JSONB;
BEGIN
    -- Inserta cabecera inicial de la corrida
    INSERT INTO mrp_explosion_runs (
        event_id, parent_sku, cantidad_demanda, fecha_demanda, estado_ejecucion
    )
    VALUES (
        p_event_id, p_parent_sku, p_cantidad_demanda, p_fecha_demanda, 'BOM.Exploded'
    )
    RETURNING mrp_explosion_runs.run_id INTO v_run_id;

    -- Persiste requerimientos consolidados (si falla la explosión, toda la transacción hace rollback)
    INSERT INTO mrp_summarized_requirements (
        run_id, mp_sku, uom_base_id, cantidad_bruta_exacta,
        cantidad_requerida_final, costo_unitario, costo_total_estimado
    )
    SELECT
        v_run_id,
        e.mp_sku,
        e.uom_base_id,
        e.cantidad_bruta_exacta,
        e.cantidad_requerida_final,
        e.costo_unitario,
        e.costo_total_estimado
    FROM fn_explode_bom_summarized(p_parent_sku, p_cantidad_demanda, p_fecha_demanda) e;

    -- Persiste versiones resueltas por nivel (BOM.VersionResolved)
    WITH RECURSIVE versiones_tree AS (
        SELECT
            0 AS nivel,
            v.parent_sku,
            v.bom_id,
            v.version_codigo,
            d.component_sku,
            ARRAY[v.parent_sku::TEXT, d.component_sku::TEXT] AS ruta
        FROM fn_resolver_version_vigente(p_parent_sku, p_fecha_demanda, FALSE) v
        JOIN bom_detalle d ON d.bom_id = v.bom_id

        UNION ALL

        SELECT
            vt.nivel + 1,
            v.parent_sku,
            v.bom_id,
            v.version_codigo,
            d.component_sku,
            vt.ruta || d.component_sku::TEXT
        FROM versiones_tree vt
        CROSS JOIN LATERAL fn_resolver_version_vigente(vt.component_sku, p_fecha_demanda, TRUE) v
        JOIN bom_detalle d ON d.bom_id = v.bom_id
        WHERE NOT (d.component_sku = ANY(vt.ruta))
          AND vt.nivel < 50
    )
    INSERT INTO mrp_resolved_versions (run_id, nivel, parent_sku, bom_id, version_codigo)
    SELECT DISTINCT v_run_id, vt.nivel, vt.parent_sku, vt.bom_id, vt.version_codigo
    FROM versiones_tree vt
    ON CONFLICT ON CONSTRAINT uq_mrp_run_nivel_parent DO NOTHING;

    -- Calcula costo total y construye payload JSONB compatible con BOMGraphExplosionAgent e Issue 5
    SELECT COALESCE(SUM(r.costo_total_estimado), 0.00)
      INTO v_costo_total
      FROM mrp_summarized_requirements r
     WHERE r.run_id = v_run_id;

    SELECT jsonb_build_object(
        'evento', 'BOM.Exploded',
        'event_id', p_event_id,
        'run_id', v_run_id,
        'producto_padre', p_parent_sku,
        'demanda', p_cantidad_demanda,
        'fecha_demanda', p_fecha_demanda,
        'costo_total_estimado', v_costo_total,
        'versiones_resueltas', (
            SELECT COALESCE(jsonb_agg(
                jsonb_build_object(
                    'nivel', rv.nivel,
                    'parent_sku', rv.parent_sku,
                    'bom_id', rv.bom_id,
                    'version_codigo', rv.version_codigo
                ) ORDER BY rv.nivel, rv.parent_sku
            ), '[]'::JSONB)
            FROM mrp_resolved_versions rv
            WHERE rv.run_id = v_run_id
        ),
        'materiales_aplanados', (
            SELECT COALESCE(jsonb_agg(
                jsonb_build_object(
                    'sku', sr.mp_sku,
                    'uom', sr.uom_base_id,
                    'cantidad_bruta_exacta', sr.cantidad_bruta_exacta,
                    'cantidad_requerida_final', sr.cantidad_requerida_final,
                    'costo_unitario', sr.costo_unitario,
                    'costo_total_estimado', sr.costo_total_estimado
                ) ORDER BY sr.mp_sku
            ), '[]'::JSONB)
            FROM mrp_summarized_requirements sr
            WHERE sr.run_id = v_run_id
        )
    )
    INTO v_payload;

    UPDATE mrp_explosion_runs
       SET costo_total_estimado = v_costo_total,
           payload_evento       = v_payload,
           mensaje_detalle      = 'Explosión aplanada y Cost Roll-up completados correctamente.'
     WHERE mrp_explosion_runs.run_id = v_run_id;

    run_id               := v_run_id;
    estado_ejecucion     := 'BOM.Exploded';
    costo_total_estimado := v_costo_total;
    payload_evento       := v_payload;
    RETURN NEXT;
END;
$$;

-- 5. Función y Vista analítica de Cost Roll-up por fecha
CREATE OR REPLACE FUNCTION fn_bom_cost_rollup(
    p_fecha TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
)
RETURNS TABLE (
    parent_sku               VARCHAR(50),
    descripcion              VARCHAR(255),
    tipo_item                VARCHAR(2),
    version_codigo           VARCHAR(20),
    total_materias_primas    BIGINT,
    costo_exacto_sin_ceil    NUMERIC(16, 4),
    costo_estandar_rollup    NUMERIC(16, 2)
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    rec RECORD;
BEGIN
    FOR rec IN
        SELECT bc.parent_sku, a.descripcion, a.tipo_item, bc.version_codigo
          FROM bom_cabecera bc
          JOIN articulos a ON a.sku = bc.parent_sku
         WHERE bc.estado = 'ACTIVO'
           AND a.activo = TRUE
           AND bc.fecha_inicio <= p_fecha
           AND (bc.fecha_fin IS NULL OR p_fecha < bc.fecha_fin)
         ORDER BY a.tipo_item, bc.parent_sku
    LOOP
        BEGIN
            RETURN QUERY
            SELECT
                rec.parent_sku,
                rec.descripcion,
                rec.tipo_item,
                rec.version_codigo,
                COUNT(*)::BIGINT,
                ROUND(SUM(e.cantidad_bruta_exacta * e.costo_unitario), 4)::NUMERIC(16, 4),
                ROUND(SUM(e.costo_total_estimado), 2)::NUMERIC(16, 2)
            FROM fn_explode_bom_summarized(rec.parent_sku, 1.0, p_fecha) e;
        EXCEPTION
            WHEN OTHERS THEN
                CONTINUE;
        END;
    END LOOP;
END;
$$;

CREATE OR REPLACE VIEW v_bom_cost_rollup AS
SELECT *
FROM fn_bom_cost_rollup(CURRENT_TIMESTAMP);

-- 6. Trigger de auditoría automática hacia auditoria_bom (integración con Issue 5)
CREATE OR REPLACE FUNCTION fn_trg_auditar_mrp_run()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO auditoria_bom (
        entidad_afectada,
        registro_id,
        accion,
        valores_anteriores,
        valores_nuevos
    )
    VALUES (
        'mrp_explosion_runs',
        NEW.run_id::TEXT,
        TG_OP,
        CASE WHEN TG_OP = 'UPDATE' THEN to_jsonb(OLD) ELSE NULL END,
        to_jsonb(NEW)
    );
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_mrp_run_audit_bom ON mrp_explosion_runs;
CREATE TRIGGER trg_mrp_run_audit_bom
AFTER INSERT OR UPDATE ON mrp_explosion_runs
FOR EACH ROW
EXECUTE FUNCTION fn_trg_auditar_mrp_run();
