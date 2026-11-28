-- ============================================================================
-- Proyecto Integrador Base de Datos (#305) - Matrícula: 178084
-- Módulo: Control de Calidad en Recepción (Cuarentena), Lotes y Devoluciones RTV
-- Motor: PostgreSQL 16
-- ============================================================================

-- Limpieza idempotente para permitir re-ejecución segura en pruebas y CI
DROP VIEW IF EXISTS vw_ranking_proveedores_178084 CASCADE;
DROP VIEW IF EXISTS vw_inventario_atp_178084 CASCADE;

DROP TABLE IF EXISTS entregas_178084 CASCADE;
DROP TABLE IF EXISTS devoluciones_rtv_178084 CASCADE;
DROP TABLE IF EXISTS lotes_inspeccion_178084 CASCADE;
DROP TABLE IF EXISTS recepciones_178084 CASCADE;
DROP TABLE IF EXISTS articulos_178084 CASCADE;
DROP TABLE IF EXISTS proveedores_178084 CASCADE;

-- ----------------------------------------------------------------------------
-- 1. TABLAS PRINCIPALES (6 ENTIDADES)
-- ----------------------------------------------------------------------------

CREATE TABLE proveedores_178084 (
    proveedor_id SERIAL PRIMARY KEY,
    codigo       VARCHAR(20) NOT NULL UNIQUE,
    nombre       VARCHAR(120) NOT NULL,
    activo       BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE articulos_178084 (
    articulo_id        SERIAL PRIMARY KEY,
    sku                VARCHAR(30) NOT NULL UNIQUE,
    nombre             VARCHAR(120) NOT NULL,
    stock_disponible   INTEGER NOT NULL DEFAULT 0 CHECK (stock_disponible >= 0),
    stock_cuarentena   INTEGER NOT NULL DEFAULT 0 CHECK (stock_cuarentena >= 0),
    stock_comprometido INTEGER NOT NULL DEFAULT 0 CHECK (stock_comprometido >= 0),
    stock_minimo       INTEGER NOT NULL DEFAULT 10 CHECK (stock_minimo >= 0)
);

CREATE TABLE recepciones_178084 (
    recepcion_id    SERIAL PRIMARY KEY,
    folio_recepcion VARCHAR(30) NOT NULL UNIQUE,
    folio_oc        VARCHAR(30) NOT NULL,
    proveedor_id    INTEGER NOT NULL REFERENCES proveedores_178084(proveedor_id),
    almacen         VARCHAR(50) NOT NULL,
    fecha_recepcion DATE NOT NULL DEFAULT CURRENT_DATE,
    estatus         VARCHAR(20) NOT NULL DEFAULT 'EN_INSPECCION'
                    CHECK (estatus IN ('EN_INSPECCION', 'CERRADA'))
);

CREATE TABLE lotes_inspeccion_178084 (
    lote_id            SERIAL PRIMARY KEY,
    numero_lote        VARCHAR(40) NOT NULL UNIQUE,
    recepcion_id       INTEGER NOT NULL REFERENCES recepciones_178084(recepcion_id),
    articulo_id        INTEGER NOT NULL REFERENCES articulos_178084(articulo_id),
    cantidad_recibida  INTEGER NOT NULL CHECK (cantidad_recibida > 0),
    cantidad_aprobada  INTEGER NOT NULL DEFAULT 0 CHECK (cantidad_aprobada >= 0),
    cantidad_rechazada INTEGER NOT NULL DEFAULT 0 CHECK (cantidad_rechazada >= 0),
    fecha_caducidad    DATE NOT NULL,
    estatus_lote       VARCHAR(20) NOT NULL DEFAULT 'CUARENTENA'
                       CHECK (estatus_lote IN ('CUARENTENA', 'DISPONIBLE', 'RECHAZADO', 'VENCIDO')),
    CONSTRAINT chk_balance_inspeccion_178084
        CHECK (cantidad_aprobada + cantidad_rechazada <= cantidad_recibida)
);

CREATE TABLE devoluciones_rtv_178084 (
    rtv_id            SERIAL PRIMARY KEY,
    folio_rtv         VARCHAR(40) NOT NULL UNIQUE,
    lote_id           INTEGER NOT NULL REFERENCES lotes_inspeccion_178084(lote_id),
    proveedor_id      INTEGER NOT NULL REFERENCES proveedores_178084(proveedor_id),
    cantidad_devuelta INTEGER NOT NULL CHECK (cantidad_devuelta > 0),
    motivo            TEXT NOT NULL,
    fecha_creacion    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE entregas_178084 (
    entrega_id         SERIAL PRIMARY KEY,
    folio_entrega      VARCHAR(30) NOT NULL UNIQUE,
    cliente            VARCHAR(120) NOT NULL,
    lote_id            INTEGER NOT NULL REFERENCES lotes_inspeccion_178084(lote_id),
    articulo_id        INTEGER NOT NULL REFERENCES articulos_178084(articulo_id),
    cantidad_entregada INTEGER NOT NULL CHECK (cantidad_entregada > 0),
    fecha_entrega      DATE NOT NULL DEFAULT CURRENT_DATE,
    estatus            VARCHAR(20) NOT NULL DEFAULT 'DESPACHADA'
                       CHECK (estatus IN ('DESPACHADA', 'CANCELADA'))
);

-- ----------------------------------------------------------------------------
-- 2. ÍNDICES DE RENDIMIENTO
-- ----------------------------------------------------------------------------

CREATE INDEX idx_recepciones_proveedor_178084
    ON recepciones_178084 (proveedor_id);

CREATE INDEX idx_lotes_fefo_178084
    ON lotes_inspeccion_178084 (articulo_id, estatus_lote, fecha_caducidad);

CREATE INDEX idx_rtv_proveedor_178084
    ON devoluciones_rtv_178084 (proveedor_id);

CREATE INDEX idx_entregas_lote_178084
    ON entregas_178084 (lote_id);

-- ----------------------------------------------------------------------------
-- 3. TRIGGERS DE INTEGRIDAD
-- ----------------------------------------------------------------------------

-- Regla 1: Todo lote recién recibido ingresa automáticamente a stock_cuarentena
CREATE OR REPLACE FUNCTION fn_ingreso_cuarentena_178084()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE articulos_178084
       SET stock_cuarentena = stock_cuarentena + NEW.cantidad_recibida
     WHERE articulo_id = NEW.articulo_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_ingreso_cuarentena_178084
AFTER INSERT ON lotes_inspeccion_178084
FOR EACH ROW
EXECUTE FUNCTION fn_ingreso_cuarentena_178084();

-- Regla 3A: Validar antes de insertar una entrega que el lote esté DISPONIBLE,
-- no vencido, corresponda al artículo y exista stock_disponible suficiente
CREATE OR REPLACE FUNCTION fn_validar_entrega_178084()
RETURNS TRIGGER AS $$
DECLARE
    v_lote      RECORD;
    v_stock_dis INTEGER;
BEGIN
    SELECT numero_lote, articulo_id, estatus_lote, fecha_caducidad
      INTO v_lote
      FROM lotes_inspeccion_178084
     WHERE lote_id = NEW.lote_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Lote % no existe.', NEW.lote_id;
    END IF;

    IF v_lote.articulo_id <> NEW.articulo_id THEN
        RAISE EXCEPTION 'El lote % no pertenece al artículo %.',
            v_lote.numero_lote, NEW.articulo_id;
    END IF;

    IF v_lote.estatus_lote <> 'DISPONIBLE' THEN
        RAISE EXCEPTION 'Entrega bloqueada: el lote % tiene estatus % (debe ser DISPONIBLE).',
            v_lote.numero_lote, v_lote.estatus_lote;
    END IF;

    IF v_lote.fecha_caducidad < CURRENT_DATE THEN
        RAISE EXCEPTION 'Entrega bloqueada: el lote % está vencido (caducidad: %).',
            v_lote.numero_lote, v_lote.fecha_caducidad;
    END IF;

    SELECT stock_disponible
      INTO v_stock_dis
      FROM articulos_178084
     WHERE articulo_id = NEW.articulo_id
       FOR UPDATE;

    IF v_stock_dis < NEW.cantidad_entregada THEN
        RAISE EXCEPTION 'Entrega bloqueada: stock disponible insuficiente (disponible: %, solicitado: %).',
            v_stock_dis, NEW.cantidad_entregada;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validar_entrega_178084
BEFORE INSERT ON entregas_178084
FOR EACH ROW
EXECUTE FUNCTION fn_validar_entrega_178084();

-- Regla 3B: Descontar automáticamente el stock disponible tras confirmar entrega
CREATE OR REPLACE FUNCTION fn_descontar_stock_entrega_178084()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.estatus = 'DESPACHADA' THEN
        UPDATE articulos_178084
           SET stock_disponible = stock_disponible - NEW.cantidad_entregada
         WHERE articulo_id = NEW.articulo_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_descontar_stock_entrega_178084
AFTER INSERT ON entregas_178084
FOR EACH ROW
EXECUTE FUNCTION fn_descontar_stock_entrega_178084();

-- ----------------------------------------------------------------------------
-- 4. PROCEDIMIENTO ALMACENADO: DICTAMEN DE CALIDAD Y GENERACIÓN DE RTV
-- ----------------------------------------------------------------------------

-- Regla 2: Libera piezas aprobadas de cuarentena a disponible y genera RTV si hay rechazos
CREATE OR REPLACE PROCEDURE sp_dictaminar_lote(
    p_lote_id            INTEGER,
    p_cantidad_aprobada  INTEGER,
    p_cantidad_rechazada INTEGER,
    p_motivo_rechazo     TEXT DEFAULT 'Rechazo en inspección de calidad'
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_lote         RECORD;
    v_proveedor_id INTEGER;
    v_nuevo_estado VARCHAR(20);
    v_pendientes   INTEGER;
    v_folio_rtv    VARCHAR(40);
BEGIN
    SELECT l.lote_id, l.numero_lote, l.recepcion_id, l.articulo_id,
           l.cantidad_recibida, l.estatus_lote
      INTO v_lote
      FROM lotes_inspeccion_178084 l
     WHERE l.lote_id = p_lote_id
       FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'No existe el lote con ID %.', p_lote_id;
    END IF;

    IF v_lote.estatus_lote <> 'CUARENTENA' THEN
        RAISE EXCEPTION 'El lote % ya fue dictaminado (estatus actual: %).',
            v_lote.numero_lote, v_lote.estatus_lote;
    END IF;

    IF p_cantidad_aprobada < 0 OR p_cantidad_rechazada < 0 THEN
        RAISE EXCEPTION 'Las cantidades aprobada y rechazada no pueden ser negativas.';
    END IF;

    IF (p_cantidad_aprobada + p_cantidad_rechazada) <> v_lote.cantidad_recibida THEN
        RAISE EXCEPTION 'La suma aprobada (%) + rechazada (%) debe igualar cantidad recibida (%).',
            p_cantidad_aprobada, p_cantidad_rechazada, v_lote.cantidad_recibida;
    END IF;

    v_nuevo_estado := CASE
        WHEN p_cantidad_aprobada > 0 THEN 'DISPONIBLE'
        ELSE 'RECHAZADO'
    END;

    -- Actualizar lote
    UPDATE lotes_inspeccion_178084
       SET cantidad_aprobada  = p_cantidad_aprobada,
           cantidad_rechazada = p_cantidad_rechazada,
           estatus_lote       = v_nuevo_estado
     WHERE lote_id = p_lote_id;

    -- Trasladar de stock_cuarentena a stock_disponible
    UPDATE articulos_178084
       SET stock_cuarentena = stock_cuarentena - v_lote.cantidad_recibida,
           stock_disponible = stock_disponible + p_cantidad_aprobada
     WHERE articulo_id = v_lote.articulo_id;

    -- Generar devolución a proveedor (RTV) automáticamente si existen piezas rechazadas
    IF p_cantidad_rechazada > 0 THEN
        SELECT proveedor_id
          INTO v_proveedor_id
          FROM recepciones_178084
         WHERE recepcion_id = v_lote.recepcion_id;

        v_folio_rtv := 'RTV-' || v_lote.numero_lote;

        INSERT INTO devoluciones_rtv_178084 (
            folio_rtv, lote_id, proveedor_id, cantidad_devuelta, motivo
        ) VALUES (
            v_folio_rtv, p_lote_id, v_proveedor_id, p_cantidad_rechazada,
            COALESCE(p_motivo_rechazo, 'Rechazo en inspección de calidad')
        );
    END IF;

    -- Cerrar la recepción si ya no quedan lotes en cuarentena
    SELECT COUNT(*)
      INTO v_pendientes
      FROM lotes_inspeccion_178084
     WHERE recepcion_id = v_lote.recepcion_id
       AND estatus_lote = 'CUARENTENA';

    IF v_pendientes = 0 THEN
        UPDATE recepciones_178084
           SET estatus = 'CERRADA'
         WHERE recepcion_id = v_lote.recepcion_id;
    END IF;
END;
$$;

-- ----------------------------------------------------------------------------
-- 5. VISTAS ANALÍTICAS (CONSUMIDAS POR CONSULTAS SQL Y AGENTE IA)
-- ----------------------------------------------------------------------------

CREATE OR REPLACE VIEW vw_inventario_atp_178084 AS
SELECT
    a.articulo_id,
    a.sku,
    a.nombre,
    a.stock_disponible,
    a.stock_cuarentena,
    a.stock_comprometido,
    (a.stock_disponible - a.stock_comprometido) AS atp,
    a.stock_minimo,
    ((a.stock_disponible - a.stock_comprometido) < a.stock_minimo) AS bajo_minimo
FROM articulos_178084 a
ORDER BY a.articulo_id;

CREATE OR REPLACE VIEW vw_ranking_proveedores_178084 AS
SELECT
    p.proveedor_id,
    p.codigo,
    p.nombre,
    COALESCE(SUM(l.cantidad_recibida), 0)  AS total_recibido,
    COALESCE(SUM(l.cantidad_aprobada), 0)  AS total_aprobado,
    COALESCE(SUM(l.cantidad_rechazada), 0) AS total_rechazado,
    COUNT(DISTINCT rtv.rtv_id)             AS total_rtv,
    CASE
        WHEN COALESCE(SUM(l.cantidad_aprobada + l.cantidad_rechazada), 0) = 0 THEN 100.00
        ELSE ROUND(
            (SUM(l.cantidad_aprobada)::NUMERIC
            / SUM(l.cantidad_aprobada + l.cantidad_rechazada)::NUMERIC) * 100,
            2
        )
    END AS porcentaje_cumplimiento
FROM proveedores_178084 p
LEFT JOIN recepciones_178084 r       ON r.proveedor_id = p.proveedor_id
LEFT JOIN lotes_inspeccion_178084 l  ON l.recepcion_id = r.recepcion_id
LEFT JOIN devoluciones_rtv_178084 rtv ON rtv.lote_id = l.lote_id
GROUP BY p.proveedor_id, p.codigo, p.nombre
ORDER BY porcentaje_cumplimiento DESC, total_rechazado ASC;