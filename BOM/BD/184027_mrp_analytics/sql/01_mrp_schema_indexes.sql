-- ============================================================================
-- 01_mrp_schema_indexes.sql
-- Capa analítica MRP, trazabilidad de versiones resueltas e índices BOM
-- Issue #269 - Integrante: Carlos Enrique López Núñez (Matrícula: 184027)
-- Compatible con BOM/BD/schema.sql (articulos, bom_cabecera, bom_detalle)
-- ============================================================================

CREATE TABLE IF NOT EXISTS mrp_explosion_runs (
    run_id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_id              VARCHAR(80) NULL,
    parent_sku            VARCHAR(50) NOT NULL REFERENCES articulos(sku) ON DELETE RESTRICT,
    cantidad_demanda      NUMERIC(14, 4) NOT NULL CHECK (cantidad_demanda > 0),
    fecha_demanda         TIMESTAMPTZ NOT NULL,
    estado_ejecucion      VARCHAR(30) NOT NULL
                          CHECK (estado_ejecucion IN (
                              'BOM.Exploded',
                              'BOM.ExplosionRejected',
                              'BOM.ValidationFailed'
                          )),
    costo_total_estimado  NUMERIC(16, 2) NOT NULL DEFAULT 0.00 CHECK (costo_total_estimado >= 0),
    payload_evento        JSONB NULL,
    mensaje_detalle       TEXT NULL,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS mrp_resolved_versions (
    resolved_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id          BIGINT NOT NULL REFERENCES mrp_explosion_runs(run_id) ON DELETE CASCADE,
    nivel           INT NOT NULL CHECK (nivel >= 0),
    parent_sku      VARCHAR(50) NOT NULL REFERENCES articulos(sku) ON DELETE RESTRICT,
    bom_id          BIGINT NOT NULL REFERENCES bom_cabecera(bom_id) ON DELETE RESTRICT,
    version_codigo  VARCHAR(20) NOT NULL,
    CONSTRAINT uq_mrp_run_nivel_parent UNIQUE (run_id, nivel, parent_sku)
);

CREATE TABLE IF NOT EXISTS mrp_summarized_requirements (
    req_id                    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id                    BIGINT NOT NULL REFERENCES mrp_explosion_runs(run_id) ON DELETE CASCADE,
    mp_sku                    VARCHAR(50) NOT NULL REFERENCES articulos(sku) ON DELETE RESTRICT,
    uom_base_id               VARCHAR(10) NOT NULL REFERENCES unidades_medida(uom_id) ON DELETE RESTRICT,
    cantidad_bruta_exacta     NUMERIC(16, 4) NOT NULL CHECK (cantidad_bruta_exacta > 0),
    cantidad_requerida_final  NUMERIC(16, 4) NOT NULL CHECK (cantidad_requerida_final > 0),
    costo_unitario            NUMERIC(14, 4) NOT NULL CHECK (costo_unitario >= 0),
    costo_total_estimado      NUMERIC(16, 2) NOT NULL CHECK (costo_total_estimado >= 0),
    CONSTRAINT uq_mrp_run_mp_sku UNIQUE (run_id, mp_sku)
);

CREATE INDEX IF NOT EXISTS idx_bom_cabecera_activo_vigencia
    ON bom_cabecera (parent_sku, fecha_inicio, fecha_fin)
    WHERE estado = 'ACTIVO';

CREATE INDEX IF NOT EXISTS idx_bom_detalle_bom_comp_inc
    ON bom_detalle (bom_id, component_sku)
    INCLUDE (cantidad, uom_id, scrap_merma);

CREATE INDEX IF NOT EXISTS idx_mrp_runs_parent_fecha
    ON mrp_explosion_runs (parent_sku, fecha_demanda DESC);

CREATE INDEX IF NOT EXISTS idx_mrp_req_run_id
    ON mrp_summarized_requirements (run_id);

CREATE INDEX IF NOT EXISTS idx_mrp_resolved_bom_id
    ON mrp_resolved_versions (bom_id);
