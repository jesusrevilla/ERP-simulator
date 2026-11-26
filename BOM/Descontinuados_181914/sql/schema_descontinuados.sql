-- =============================================================================
-- Gestión de componentes descontinuados en BOM — Matrícula 181914 (issue #239)
-- Extensión de BOM/BD/schema.sql (PostgreSQL 15+). Ejecutar después de él.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Catálogo técnico: categoría y especificaciones
-- -----------------------------------------------------------------------------
ALTER TABLE articulos ADD COLUMN IF NOT EXISTS categoria VARCHAR(30) NOT NULL DEFAULT 'GENERAL';

CREATE TABLE articulo_especificaciones (
    sku             VARCHAR(50) NOT NULL REFERENCES articulos(sku) ON DELETE RESTRICT,
    atributo        VARCHAR(40) NOT NULL,
    valor_texto     VARCHAR(100) NULL,
    valor_numerico  NUMERIC(14, 4) NULL,
    unidad          VARCHAR(10) NULL,
    PRIMARY KEY (sku, atributo),
    CONSTRAINT chk_un_valor CHECK ((valor_texto IS NULL) <> (valor_numerico IS NULL))
);

-- Reglas de compatibilidad por categoría (RN-05).
CREATE TABLE criterios_compatibilidad (
    categoria   VARCHAR(30) NOT NULL,
    atributo    VARCHAR(40) NOT NULL,
    regla       VARCHAR(10) NOT NULL CHECK (regla IN ('IGUAL', 'MINIMO', 'MAXIMO')),
    obligatorio BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (categoria, atributo)
);

-- -----------------------------------------------------------------------------
-- 2. Ciclo de vida del componente (RN-01)
-- -----------------------------------------------------------------------------
CREATE TABLE componente_ciclo_vida (
    sku                    VARCHAR(50) PRIMARY KEY REFERENCES articulos(sku) ON DELETE RESTRICT,
    estado                 VARCHAR(25) NOT NULL DEFAULT 'ACTIVO'
                           CHECK (estado IN ('ACTIVO', 'PROXIMO_A_DESCONTINUAR', 'DESCONTINUADO')),
    fecha_anuncio_eol      DATE NULL,
    fecha_ultima_compra    DATE NULL,           -- Last Time Buy informado por el proveedor
    fecha_descontinuacion  TIMESTAMPTZ NULL,
    uso_stock_autorizado   BOOLEAN NOT NULL DEFAULT FALSE,
    fuente                 VARCHAR(100) NULL,   -- proveedor / boletín PCN que lo notificó
    usuario                VARCHAR(100) NOT NULL,
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_fecha_desc CHECK (estado <> 'DESCONTINUADO' OR fecha_descontinuacion IS NOT NULL)
);

CREATE TABLE componente_ciclo_vida_historial (
    historial_id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sku             VARCHAR(50) NOT NULL REFERENCES articulos(sku) ON DELETE RESTRICT,
    estado_anterior VARCHAR(25) NULL,
    estado_nuevo    VARCHAR(25) NOT NULL,
    usuario         VARCHAR(100) NOT NULL,
    fecha           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- 3. Abastecimiento: proveedores y existencias
-- -----------------------------------------------------------------------------
CREATE TABLE proveedores (
    proveedor_id VARCHAR(20) PRIMARY KEY,
    nombre       VARCHAR(120) NOT NULL,
    activo       BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE articulo_proveedor (
    sku                 VARCHAR(50) NOT NULL REFERENCES articulos(sku) ON DELETE RESTRICT,
    proveedor_id        VARCHAR(20) NOT NULL REFERENCES proveedores(proveedor_id) ON DELETE RESTRICT,
    costo               NUMERIC(14, 4) NOT NULL CHECK (costo >= 0),
    tiempo_entrega_dias INT NOT NULL CHECK (tiempo_entrega_dias >= 0),
    disponible          BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (sku, proveedor_id)
);

CREATE TABLE existencias (
    sku                 VARCHAR(50) NOT NULL REFERENCES articulos(sku) ON DELETE RESTRICT,
    almacen             VARCHAR(20) NOT NULL,
    cantidad_disponible NUMERIC(14, 4) NOT NULL DEFAULT 0 CHECK (cantidad_disponible >= 0),
    cantidad_reservada  NUMERIC(14, 4) NOT NULL DEFAULT 0 CHECK (cantidad_reservada >= 0),
    PRIMARY KEY (sku, almacen)
);

-- -----------------------------------------------------------------------------
-- 4. Alertas, recomendaciones, autorizaciones e historial de sustituciones
-- -----------------------------------------------------------------------------
CREATE TABLE alertas_descontinuacion (
    alerta_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sku              VARCHAR(50) NOT NULL REFERENCES articulos(sku) ON DELETE RESTRICT,
    fecha_registro   TIMESTAMPTZ NOT NULL,   -- cuándo se registró la descontinuación
    fecha_alerta     TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    prioridad        VARCHAR(10) NOT NULL CHECK (prioridad IN ('BAJA', 'MEDIA', 'ALTA', 'CRITICA')),
    estado           VARCHAR(15) NOT NULL DEFAULT 'ABIERTA'
                     CHECK (estado IN ('ABIERTA', 'EN_EVALUACION', 'RESUELTA', 'DESCARTADA')),
    existencias      NUMERIC(14, 4) NOT NULL DEFAULT 0,
    demanda_abierta  NUMERIC(14, 4) NOT NULL DEFAULT 0,
    fecha_cierre     TIMESTAMPTZ NULL,
    CONSTRAINT chk_alerta_fechas CHECK (fecha_alerta >= fecha_registro)
);

CREATE TABLE alerta_bom_afectada (
    alerta_id BIGINT NOT NULL REFERENCES alertas_descontinuacion(alerta_id) ON DELETE RESTRICT,
    bom_id    BIGINT NOT NULL REFERENCES bom_cabecera(bom_id) ON DELETE RESTRICT,
    nivel     INT NOT NULL CHECK (nivel >= 1),
    ruta      TEXT NOT NULL,
    PRIMARY KEY (alerta_id, bom_id)
);

CREATE TABLE recomendaciones_sustitucion (
    recomendacion_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    alerta_id        BIGINT NOT NULL REFERENCES alertas_descontinuacion(alerta_id) ON DELETE RESTRICT,
    sku_original     VARCHAR(50) NOT NULL REFERENCES articulos(sku) ON DELETE RESTRICT,
    sku_sustituto    VARCHAR(50) NOT NULL REFERENCES articulos(sku) ON DELETE RESTRICT,
    posicion         SMALLINT NOT NULL CHECK (posicion >= 1),
    puntuacion       NUMERIC(6, 4) NOT NULL CHECK (puntuacion BETWEEN 0 AND 1),
    detalle          JSONB NOT NULL,           -- puntuación por criterio
    justificacion    TEXT NOT NULL,
    modelo_version   VARCHAR(40) NOT NULL,     -- trazabilidad del agente
    created_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_sustituto_distinto CHECK (sku_original <> sku_sustituto),
    CONSTRAINT uq_rec_posicion UNIQUE (alerta_id, posicion)
);

CREATE TABLE autorizaciones_sustitucion (
    autorizacion_id  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    recomendacion_id BIGINT NOT NULL REFERENCES recomendaciones_sustitucion(recomendacion_id) ON DELETE RESTRICT,
    usuario          VARCHAR(100) NOT NULL,
    rol              VARCHAR(30) NOT NULL CHECK (rol = 'RESPONSABLE_TECNICO'),   -- RN-06
    decision         VARCHAR(10) NOT NULL CHECK (decision IN ('APROBADA', 'RECHAZADA')),
    comentario       TEXT NULL,
    fecha            TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE sustituciones_bom (
    sustitucion_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    autorizacion_id  BIGINT NOT NULL REFERENCES autorizaciones_sustitucion(autorizacion_id) ON DELETE RESTRICT,
    bom_anterior_id  BIGINT NOT NULL REFERENCES bom_cabecera(bom_id) ON DELETE RESTRICT,
    bom_nueva_id     BIGINT NOT NULL REFERENCES bom_cabecera(bom_id) ON DELETE RESTRICT,
    sku_original     VARCHAR(50) NOT NULL REFERENCES articulos(sku) ON DELETE RESTRICT,
    sku_sustituto    VARCHAR(50) NOT NULL REFERENCES articulos(sku) ON DELETE RESTRICT,
    politica         VARCHAR(20) NOT NULL DEFAULT 'AGOTAR_EXISTENCIAS'
                     CHECK (politica IN ('INMEDIATA', 'AGOTAR_EXISTENCIAS')),
    usuario          VARCHAR(100) NOT NULL,
    fecha_efectiva   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_bom_distinta CHECK (bom_anterior_id <> bom_nueva_id)
);

-- Evaluación de órdenes antes de aplicar la sustitución (RN-07).
CREATE TABLE sustitucion_evaluacion_ordenes (
    sustitucion_id BIGINT NOT NULL REFERENCES sustituciones_bom(sustitucion_id) ON DELETE RESTRICT,
    orden_id       BIGINT NOT NULL REFERENCES ordenes_produccion(orden_id) ON DELETE RESTRICT,
    decision       VARCHAR(15) NOT NULL CHECK (decision IN ('CONSERVAR', 'REPLANIFICAR')),
    PRIMARY KEY (sustitucion_id, orden_id)
);

-- Salida del MRP necesaria para medir recomendaciones inválidas (KPI 4).
CREATE TABLE recomendaciones_compra (
    recomendacion_compra_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    corrida_mrp             VARCHAR(30) NOT NULL,
    sku                     VARCHAR(50) NOT NULL REFERENCES articulos(sku) ON DELETE RESTRICT,
    cantidad                NUMERIC(14, 4) NOT NULL CHECK (cantidad > 0),
    tipo                    VARCHAR(15) NOT NULL DEFAULT 'ORDINARIA'
                            CHECK (tipo IN ('ORDINARIA', 'ULTIMA_COMPRA')),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Fechas de compromiso de órdenes para medir retrasos (KPI 5).
ALTER TABLE ordenes_produccion ADD COLUMN IF NOT EXISTS fecha_fin_real DATE NULL;
ALTER TABLE ordenes_produccion ADD COLUMN IF NOT EXISTS causa_retraso VARCHAR(40) NULL;

-- -----------------------------------------------------------------------------
-- 5. Reglas en base de datos
-- -----------------------------------------------------------------------------

-- Where-used multinivel de BOM activas: todas las BOM que contienen p_sku.
CREATE OR REPLACE FUNCTION fn_boms_afectadas(p_sku VARCHAR)
RETURNS TABLE (bom_id BIGINT, parent_sku VARCHAR, nivel INT, ruta TEXT)
LANGUAGE sql STABLE AS $$
    WITH RECURSIVE uso AS (
        SELECT c.bom_id, c.parent_sku, 1 AS nivel,
               (c.parent_sku || ' > ' || d.component_sku)::TEXT AS ruta,
               ARRAY[d.component_sku, c.parent_sku]::VARCHAR[] AS visitados
        FROM bom_detalle d
        JOIN bom_cabecera c ON c.bom_id = d.bom_id
        WHERE d.component_sku = p_sku AND c.estado = 'ACTIVO'
        UNION ALL
        SELECT c.bom_id, c.parent_sku, u.nivel + 1,
               c.parent_sku || ' > ' || u.ruta,
               u.visitados || c.parent_sku
        FROM uso u
        JOIN bom_detalle d ON d.component_sku = u.parent_sku
        JOIN bom_cabecera c ON c.bom_id = d.bom_id
        WHERE c.estado = 'ACTIVO' AND NOT c.parent_sku = ANY (u.visitados)   -- protección contra ciclos
    )
    SELECT DISTINCT ON (uso.bom_id) uso.bom_id, uso.parent_sku, uso.nivel, uso.ruta
    FROM uso ORDER BY uso.bom_id, uso.nivel;
$$;

-- Detección automática: al pasar a DESCONTINUADO o PROXIMO_A_DESCONTINUAR se
-- registra el historial y se genera la alerta con las BOM afectadas (RF-03).
CREATE OR REPLACE FUNCTION fn_ciclo_vida_cambio()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    v_alerta BIGINT;
    v_boms INT;
    v_ordenes INT;
    v_stock NUMERIC;
    v_prioridad VARCHAR(10);
BEGIN
    IF TG_OP = 'UPDATE' AND OLD.estado = NEW.estado THEN
        RETURN NEW;
    END IF;
    IF TG_OP = 'UPDATE' AND OLD.estado = 'DESCONTINUADO' THEN
        RAISE EXCEPTION 'Transición no permitida: DESCONTINUADO -> %', NEW.estado;
    END IF;

    INSERT INTO componente_ciclo_vida_historial (sku, estado_anterior, estado_nuevo, usuario)
    VALUES (NEW.sku, CASE WHEN TG_OP = 'UPDATE' THEN OLD.estado END, NEW.estado, NEW.usuario);

    IF NEW.estado = 'ACTIVO' THEN
        RETURN NEW;
    END IF;

    SELECT count(*) INTO v_boms FROM fn_boms_afectadas(NEW.sku);
    SELECT count(DISTINCT o.orden_id) INTO v_ordenes
    FROM ordenes_produccion o
    WHERE o.estado IN ('PLANIFICADA', 'LIBERADA', 'EN_PROCESO')
      AND (o.parent_sku = NEW.sku
           OR o.bom_id IN (SELECT a.bom_id FROM fn_boms_afectadas(NEW.sku) a));
    SELECT COALESCE(sum(cantidad_disponible - cantidad_reservada), 0) INTO v_stock
    FROM existencias WHERE sku = NEW.sku;

    v_prioridad := CASE
        WHEN v_boms = 0 THEN 'BAJA'
        WHEN NEW.estado = 'DESCONTINUADO' AND v_ordenes > 0 THEN 'CRITICA'
        WHEN v_ordenes > 0 OR (NEW.estado = 'DESCONTINUADO' AND v_boms >= 3) THEN 'ALTA'
        ELSE 'MEDIA' END;

    INSERT INTO alertas_descontinuacion (sku, fecha_registro, prioridad, existencias)
    VALUES (NEW.sku, COALESCE(NEW.fecha_descontinuacion, CURRENT_TIMESTAMP), v_prioridad, v_stock)
    RETURNING alerta_id INTO v_alerta;

    INSERT INTO alerta_bom_afectada (alerta_id, bom_id, nivel, ruta)
    SELECT v_alerta, a.bom_id, a.nivel, a.ruta FROM fn_boms_afectadas(NEW.sku) a;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_ciclo_vida_cambio
AFTER INSERT OR UPDATE OF estado ON componente_ciclo_vida
FOR EACH ROW EXECUTE FUNCTION fn_ciclo_vida_cambio();

-- RN-02: un descontinuado no genera recomendaciones ordinarias de compra.
CREATE OR REPLACE FUNCTION fn_bloquear_compra_descontinuado()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.tipo = 'ORDINARIA' AND EXISTS (
        SELECT 1 FROM componente_ciclo_vida
        WHERE sku = NEW.sku AND estado = 'DESCONTINUADO') THEN
        RAISE EXCEPTION 'RN-02: % está descontinuado; no se permiten compras ordinarias', NEW.sku;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_bloquear_compra_descontinuado
BEFORE INSERT OR UPDATE ON recomendaciones_compra
FOR EACH ROW EXECUTE FUNCTION fn_bloquear_compra_descontinuado();

-- RN-06 / RN-05: solo se aplica una sustitución autorizada, coherente con la
-- recomendación y con un sustituto no descontinuado.
CREATE OR REPLACE FUNCTION fn_validar_sustitucion()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    r RECORD;
BEGIN
    SELECT a.decision, rs.sku_original, rs.sku_sustituto INTO r
    FROM autorizaciones_sustitucion a
    JOIN recomendaciones_sustitucion rs ON rs.recomendacion_id = a.recomendacion_id
    WHERE a.autorizacion_id = NEW.autorizacion_id;

    IF r.decision IS DISTINCT FROM 'APROBADA' THEN
        RAISE EXCEPTION 'RN-06: la sustitución requiere una autorización APROBADA';
    END IF;
    IF r.sku_original <> NEW.sku_original OR r.sku_sustituto <> NEW.sku_sustituto THEN
        RAISE EXCEPTION 'RN-06: la sustitución no coincide con la recomendación autorizada';
    END IF;
    IF EXISTS (SELECT 1 FROM componente_ciclo_vida
               WHERE sku = NEW.sku_sustituto AND estado = 'DESCONTINUADO') THEN
        RAISE EXCEPTION 'RN-05: el sustituto % está descontinuado', NEW.sku_sustituto;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_validar_sustitucion
BEFORE INSERT ON sustituciones_bom
FOR EACH ROW EXECUTE FUNCTION fn_validar_sustitucion();

-- RN-08: el historial de sustituciones y autorizaciones es inmutable.
CREATE OR REPLACE FUNCTION fn_historial_inmutable()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'RN-08: % es un registro histórico y no puede modificarse', TG_TABLE_NAME;
END;
$$;

CREATE TRIGGER trg_sustituciones_inmutables
BEFORE UPDATE OR DELETE ON sustituciones_bom
FOR EACH ROW EXECUTE FUNCTION fn_historial_inmutable();

CREATE TRIGGER trg_autorizaciones_inmutables
BEFORE UPDATE OR DELETE ON autorizaciones_sustitucion
FOR EACH ROW EXECUTE FUNCTION fn_historial_inmutable();

CREATE TRIGGER trg_ciclo_vida_historial_inmutable
BEFORE UPDATE OR DELETE ON componente_ciclo_vida_historial
FOR EACH ROW EXECUTE FUNCTION fn_historial_inmutable();

-- Índices de apoyo a consultas where-used y KPIs.
CREATE INDEX IF NOT EXISTS ix_bom_detalle_componente ON bom_detalle (component_sku);
CREATE INDEX IF NOT EXISTS ix_alertas_sku ON alertas_descontinuacion (sku, estado);
CREATE INDEX IF NOT EXISTS ix_reco_compra_corrida ON recomendaciones_compra (corrida_mrp);
