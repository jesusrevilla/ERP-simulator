-- =====================================================================
--  Fuentes:
--    [BPMN]  README_BPMN_hojas_de_ruta.md  (RF-xx / RN-xx)
--    [RUTAS] Rutas.md                      (etapas, Run Time, despacho,
--                                           integridad de datos)
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- 1. Seguridad: roles y usuarios                      [BPMN] carriles
-- ---------------------------------------------------------------------
CREATE TABLE rol (
    rol_id      INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    clave       VARCHAR(30)  NOT NULL UNIQUE,
    nombre      VARCHAR(80)  NOT NULL
);

CREATE TABLE usuario (
    usuario_id  INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    rol_id      INTEGER      NOT NULL REFERENCES rol (rol_id),
    nombre      VARCHAR(120) NOT NULL,
    correo      VARCHAR(120) NOT NULL UNIQUE,
    activo      BOOLEAN      NOT NULL DEFAULT TRUE
);

-- ---------------------------------------------------------------------
-- 2. Catalogos
-- ---------------------------------------------------------------------
-- [RUTAS] E2: cambio de almacen despues de la Etapa 1
CREATE TABLE almacen (
    almacen_id  INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo      VARCHAR(10)  NOT NULL UNIQUE,
    nombre      VARCHAR(80)  NOT NULL,
    activo      BOOLEAN      NOT NULL DEFAULT TRUE
);

-- [BPMN] RF-03 / RN-09: solo material de fabricacion propia lleva hoja
CREATE TABLE material (
    material_id     INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo          VARCHAR(30)   NOT NULL UNIQUE,
    descripcion     VARCHAR(150)  NOT NULL,
    unidad_medida   VARCHAR(10)   NOT NULL,
    tipo            VARCHAR(12)   NOT NULL
                    CHECK (tipo IN ('FABRICADO', 'COMPRADO')),
    costo_unitario  NUMERIC(14,4) NOT NULL DEFAULT 0 CHECK (costo_unitario >= 0),
    activo          BOOLEAN       NOT NULL DEFAULT TRUE
);

-- [RUTAS] E1b: descuento de inventario por almacen
CREATE TABLE existencia (
    material_id INTEGER       NOT NULL REFERENCES material (material_id),
    almacen_id  INTEGER       NOT NULL REFERENCES almacen (almacen_id),
    cantidad    NUMERIC(14,4) NOT NULL DEFAULT 0 CHECK (cantidad >= 0),
    PRIMARY KEY (material_id, almacen_id)
);

-- [BPMN] RF-02 / RN-06..08: centros de trabajo de las operaciones
CREATE TABLE centro_trabajo (
    centro_trabajo_id       INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo                  VARCHAR(20)   NOT NULL UNIQUE,
    nombre                  VARCHAR(100)  NOT NULL,
    capacidad_horas_dia     NUMERIC(6,2)  NOT NULL CHECK (capacidad_horas_dia > 0),
    costo_hora              NUMERIC(14,4) NOT NULL DEFAULT 0 CHECK (costo_hora >= 0),
    activo                  BOOLEAN       NOT NULL DEFAULT TRUE
);

-- [RUTAS] B2: capacidades (recursos) que se asignan por etapa
CREATE TABLE recurso (
    recurso_id          INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    centro_trabajo_id   INTEGER       REFERENCES centro_trabajo (centro_trabajo_id),
    codigo              VARCHAR(20)   NOT NULL UNIQUE,
    nombre              VARCHAR(100)  NOT NULL,
    tipo                VARCHAR(12)   NOT NULL
                        CHECK (tipo IN ('MAQUINA', 'MANO_OBRA', 'OTRO')),
    costo_hora          NUMERIC(14,4) NOT NULL DEFAULT 0 CHECK (costo_hora >= 0),
    activo              BOOLEAN       NOT NULL DEFAULT TRUE
);

-- [RUTAS] B1 / D1: maestro de etapas (Route Stage)
CREATE TABLE etapa_ruta (
    etapa_ruta_id   INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo          VARCHAR(20)  NOT NULL UNIQUE,
    descripcion     VARCHAR(150) NOT NULL,
    activo          BOOLEAN      NOT NULL DEFAULT TRUE
);

-- ---------------------------------------------------------------------
-- 3. Hoja de ruta (maestro)
-- ---------------------------------------------------------------------
-- [BPMN] RF-01, RN-01..05 (datos generales y numero), RF-05 (revision y
--        liberacion), RF-06 / RN-13 (versiones), RF-11 / RN-16 (bloqueo
--        u obsolescencia), RN-12 (aprobador distinto del creador)
-- [RUTAS] D2: Total Run Time
CREATE TABLE hoja_ruta (
    hoja_ruta_id        INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    numero              VARCHAR(20)   NOT NULL,
    version             INTEGER       NOT NULL DEFAULT 1 CHECK (version >= 1),
    descripcion         VARCHAR(200)  NOT NULL,
    estatus             VARCHAR(12)   NOT NULL DEFAULT 'BORRADOR'
                        CHECK (estatus IN ('BORRADOR', 'EN_REVISION', 'LIBERADA',
                                           'BLOQUEADA', 'OBSOLETA')),
    vigente_desde       DATE          NOT NULL,
    vigente_hasta       DATE,
    tiempo_total_min    NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (tiempo_total_min >= 0),
    hoja_origen_id      INTEGER       REFERENCES hoja_ruta (hoja_ruta_id),
    creado_por          INTEGER       NOT NULL REFERENCES usuario (usuario_id),
    creado_en           TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    aprobado_por        INTEGER       REFERENCES usuario (usuario_id),
    liberado_en         TIMESTAMP,
    CONSTRAINT uq_hoja_ruta_numero_version UNIQUE (numero, version),
    CONSTRAINT ck_hoja_ruta_vigencia
        CHECK (vigente_hasta IS NULL OR vigente_hasta >= vigente_desde),
    -- RN-12: segregacion de funciones
    CONSTRAINT ck_hoja_ruta_segregacion
        CHECK (aprobado_por IS NULL OR aprobado_por <> creado_por),
    CONSTRAINT ck_hoja_ruta_liberacion
        CHECK (estatus <> 'LIBERADA'
               OR (aprobado_por IS NOT NULL AND liberado_en IS NOT NULL))
);

-- [BPMN] RF-02, RN-06..08 (operaciones, centros y tiempos)
-- [RUTAS] B1 (etapas secuenciales), B3 (Run Time), B4 (dias de espera),
--         C1 (secuencia entera y correlativa)
CREATE TABLE hoja_ruta_operacion (
    hoja_ruta_operacion_id  INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    hoja_ruta_id            INTEGER       NOT NULL
                            REFERENCES hoja_ruta (hoja_ruta_id) ON DELETE CASCADE,
    secuencia               INTEGER       NOT NULL CHECK (secuencia >= 1),
    etapa_ruta_id           INTEGER       NOT NULL REFERENCES etapa_ruta (etapa_ruta_id),
    centro_trabajo_id       INTEGER       NOT NULL REFERENCES centro_trabajo (centro_trabajo_id),
    descripcion             VARCHAR(200),
    tiempo_preparacion_min  NUMERIC(10,2) NOT NULL DEFAULT 0 CHECK (tiempo_preparacion_min >= 0),
    tiempo_ejecucion_min    NUMERIC(10,2) NOT NULL CHECK (tiempo_ejecucion_min > 0),
    dias_espera             INTEGER       NOT NULL DEFAULT 0 CHECK (dias_espera >= 0),
    -- DEFERRABLE permite reenumerar al insertar una secuencia intermedia (D3)
    CONSTRAINT uq_hoja_ruta_operacion_secuencia
        UNIQUE (hoja_ruta_id, secuencia) DEFERRABLE INITIALLY IMMEDIATE
);

-- [RUTAS] B2: materiales por etapa
CREATE TABLE hoja_ruta_operacion_material (
    hoja_ruta_operacion_id  INTEGER       NOT NULL
                            REFERENCES hoja_ruta_operacion (hoja_ruta_operacion_id) ON DELETE CASCADE,
    material_id             INTEGER       NOT NULL REFERENCES material (material_id),
    cantidad_base           NUMERIC(14,4) NOT NULL CHECK (cantidad_base > 0),
    almacen_id              INTEGER       REFERENCES almacen (almacen_id),
    PRIMARY KEY (hoja_ruta_operacion_id, material_id)
);

-- [RUTAS] B2: capacidades por etapa
CREATE TABLE hoja_ruta_operacion_recurso (
    hoja_ruta_operacion_id  INTEGER       NOT NULL
                            REFERENCES hoja_ruta_operacion (hoja_ruta_operacion_id) ON DELETE CASCADE,
    recurso_id              INTEGER       NOT NULL REFERENCES recurso (recurso_id),
    horas_base              NUMERIC(10,2) NOT NULL CHECK (horas_base > 0),
    PRIMARY KEY (hoja_ruta_operacion_id, recurso_id)
);

-- [BPMN] RF-03, RN-09 (material propio), RN-10 (rangos de lote sin cruce)
CREATE TABLE hoja_ruta_asignacion (
    hoja_ruta_asignacion_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    hoja_ruta_id            INTEGER       NOT NULL
                            REFERENCES hoja_ruta (hoja_ruta_id) ON DELETE CASCADE,
    material_id             INTEGER       NOT NULL REFERENCES material (material_id),
    lote_minimo             NUMERIC(14,4) NOT NULL CHECK (lote_minimo > 0),
    lote_maximo             NUMERIC(14,4) NOT NULL,
    CONSTRAINT ck_hoja_ruta_asignacion_rango CHECK (lote_maximo >= lote_minimo),
    CONSTRAINT uq_hoja_ruta_asignacion UNIQUE (hoja_ruta_id, material_id, lote_minimo)
);

-- [BPMN] RF-07 (historial de estatus), RN-17 (motivo de bloqueo/obsolescencia)
CREATE TABLE hoja_ruta_historial (
    hoja_ruta_historial_id  INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    hoja_ruta_id            INTEGER      NOT NULL REFERENCES hoja_ruta (hoja_ruta_id),
    estatus_anterior        VARCHAR(12),
    estatus_nuevo           VARCHAR(12)  NOT NULL,
    usuario_id              INTEGER      NOT NULL REFERENCES usuario (usuario_id),
    fecha                   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    motivo                  VARCHAR(300),
    CONSTRAINT ck_hoja_ruta_historial_motivo
        CHECK (estatus_nuevo NOT IN ('BLOQUEADA', 'OBSOLETA')
               OR (motivo IS NOT NULL AND btrim(motivo) <> ''))
);

-- ---------------------------------------------------------------------
-- 4. Orden de produccion (copia de la hoja de ruta)
-- ---------------------------------------------------------------------
-- [BPMN] RF-08 / RN-14 (seleccion por material y lote), RF-04 / RN-15 /
--        RN-18 (copia de la hoja y tiempo total)
-- [RUTAS] C2 (horizonte de la orden), F3 (la orden conserva su ruta)
CREATE TABLE orden_produccion (
    orden_produccion_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    folio               VARCHAR(20)   NOT NULL UNIQUE,
    material_id         INTEGER       NOT NULL REFERENCES material (material_id),
    cantidad            NUMERIC(14,4) NOT NULL CHECK (cantidad > 0),
    almacen_id          INTEGER       NOT NULL REFERENCES almacen (almacen_id),
    hoja_ruta_id        INTEGER       NOT NULL REFERENCES hoja_ruta (hoja_ruta_id),
    estatus             VARCHAR(12)   NOT NULL DEFAULT 'PLANIFICADA'
                        CHECK (estatus IN ('PLANIFICADA', 'LIBERADA', 'CERRADA', 'CANCELADA')),
    fecha_inicio        DATE          NOT NULL,
    fecha_fin           DATE          NOT NULL,
    tiempo_total_min    NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (tiempo_total_min >= 0),
    costo_planificado   NUMERIC(16,4) NOT NULL DEFAULT 0,
    costo_real          NUMERIC(16,4) NOT NULL DEFAULT 0,
    creado_por          INTEGER       NOT NULL REFERENCES usuario (usuario_id),
    creado_en           TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_orden_produccion_horizonte CHECK (fecha_fin >= fecha_inicio)
);

-- Etapas copiadas a la orden: los cambios posteriores en la hoja de ruta
-- no las tocan (RN-15 / F3).
CREATE TABLE orden_produccion_etapa (
    orden_produccion_etapa_id   INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    orden_produccion_id         INTEGER       NOT NULL
                                REFERENCES orden_produccion (orden_produccion_id) ON DELETE CASCADE,
    secuencia                   INTEGER       NOT NULL CHECK (secuencia >= 1),
    etapa_ruta_id               INTEGER       NOT NULL REFERENCES etapa_ruta (etapa_ruta_id),
    centro_trabajo_id           INTEGER       NOT NULL REFERENCES centro_trabajo (centro_trabajo_id),
    almacen_id                  INTEGER       REFERENCES almacen (almacen_id),
    tiempo_preparacion_min      NUMERIC(10,2) NOT NULL DEFAULT 0 CHECK (tiempo_preparacion_min >= 0),
    tiempo_ejecucion_min        NUMERIC(10,2) NOT NULL CHECK (tiempo_ejecucion_min > 0),
    dias_espera                 INTEGER       NOT NULL DEFAULT 0 CHECK (dias_espera >= 0),
    fecha_inicio                DATE          NOT NULL,
    fecha_fin                   DATE          NOT NULL,
    estatus                     VARCHAR(12)   NOT NULL DEFAULT 'PENDIENTE'
                                CHECK (estatus IN ('PENDIENTE', 'EN_PROCESO', 'COMPLETADA')),
    CONSTRAINT uq_orden_produccion_etapa_secuencia
        UNIQUE (orden_produccion_id, secuencia) DEFERRABLE INITIALLY IMMEDIATE,
    CONSTRAINT ck_orden_produccion_etapa_fechas CHECK (fecha_fin >= fecha_inicio)
);

-- [RUTAS] F1: no puede haber lineas huerfanas, por eso la etapa es NOT NULL
CREATE TABLE orden_produccion_linea (
    orden_produccion_linea_id   INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    orden_produccion_id         INTEGER       NOT NULL
                                REFERENCES orden_produccion (orden_produccion_id) ON DELETE CASCADE,
    orden_produccion_etapa_id   INTEGER       NOT NULL
                                REFERENCES orden_produccion_etapa (orden_produccion_etapa_id),
    tipo                        VARCHAR(10)   NOT NULL CHECK (tipo IN ('MATERIAL', 'RECURSO')),
    material_id                 INTEGER       REFERENCES material (material_id),
    recurso_id                  INTEGER       REFERENCES recurso (recurso_id),
    almacen_id                  INTEGER       REFERENCES almacen (almacen_id),
    cantidad_planificada        NUMERIC(14,4) NOT NULL CHECK (cantidad_planificada > 0),
    cantidad_despachada         NUMERIC(14,4) NOT NULL DEFAULT 0 CHECK (cantidad_despachada >= 0),
    costo_unitario              NUMERIC(14,4) NOT NULL DEFAULT 0 CHECK (costo_unitario >= 0),
    CONSTRAINT ck_orden_produccion_linea_tipo
        CHECK ((tipo = 'MATERIAL' AND material_id IS NOT NULL AND recurso_id IS NULL
                                  AND almacen_id IS NOT NULL)
            OR (tipo = 'RECURSO'  AND recurso_id IS NOT NULL AND material_id IS NULL))
);

-- [RUTAS] C3 / E1a / E1b / E1c: despacho a produccion (Issue for Production)
CREATE TABLE despacho_produccion (
    despacho_produccion_id      INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    orden_produccion_id         INTEGER       NOT NULL REFERENCES orden_produccion (orden_produccion_id),
    orden_produccion_etapa_id   INTEGER       NOT NULL REFERENCES orden_produccion_etapa (orden_produccion_etapa_id),
    orden_produccion_linea_id   INTEGER       NOT NULL REFERENCES orden_produccion_linea (orden_produccion_linea_id),
    material_id                 INTEGER       NOT NULL REFERENCES material (material_id),
    almacen_id                  INTEGER       NOT NULL REFERENCES almacen (almacen_id),
    cantidad                    NUMERIC(14,4) NOT NULL CHECK (cantidad > 0),
    costo_unitario              NUMERIC(14,4) NOT NULL CHECK (costo_unitario >= 0),
    usuario_id                  INTEGER       NOT NULL REFERENCES usuario (usuario_id),
    fecha                       TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------------
-- 5. Indices
-- ---------------------------------------------------------------------
CREATE INDEX ix_hoja_ruta_estatus            ON hoja_ruta (estatus, vigente_desde, vigente_hasta);
CREATE INDEX ix_hoja_ruta_asignacion_mat     ON hoja_ruta_asignacion (material_id, lote_minimo, lote_maximo);
CREATE INDEX ix_hoja_ruta_historial_hoja     ON hoja_ruta_historial (hoja_ruta_id, fecha);
CREATE INDEX ix_orden_produccion_estatus     ON orden_produccion (estatus);
CREATE INDEX ix_orden_produccion_linea_etapa ON orden_produccion_linea (orden_produccion_etapa_id);
CREATE INDEX ix_despacho_produccion_etapa    ON despacho_produccion (orden_produccion_etapa_id);

-- ---------------------------------------------------------------------
-- 6. Reglas que no caben en un CHECK
-- ---------------------------------------------------------------------

-- RN-09 y RN-10: solo material fabricado, y sin cruce de rangos de lote
-- entre hojas distintas (las versiones de una misma hoja si comparten rango).
CREATE FUNCTION fn_validar_asignacion() RETURNS trigger AS $$
DECLARE
    v_numero hoja_ruta.numero%TYPE;
BEGIN
    IF (SELECT tipo FROM material WHERE material_id = NEW.material_id) <> 'FABRICADO' THEN
        RAISE EXCEPTION 'RN-09: el material % no es de fabricacion propia', NEW.material_id;
    END IF;

    SELECT numero INTO v_numero FROM hoja_ruta WHERE hoja_ruta_id = NEW.hoja_ruta_id;

    IF EXISTS (
        SELECT 1
        FROM hoja_ruta_asignacion a
        JOIN hoja_ruta h ON h.hoja_ruta_id = a.hoja_ruta_id
        WHERE a.material_id = NEW.material_id
          AND a.hoja_ruta_asignacion_id IS DISTINCT FROM NEW.hoja_ruta_asignacion_id
          AND h.numero <> v_numero
          AND h.estatus <> 'OBSOLETA'
          AND a.lote_minimo <= NEW.lote_maximo
          AND a.lote_maximo >= NEW.lote_minimo
    ) THEN
        RAISE EXCEPTION 'RN-10: el rango de lote % - % se cruza con otra hoja de ruta',
            NEW.lote_minimo, NEW.lote_maximo;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_validar_asignacion
BEFORE INSERT OR UPDATE ON hoja_ruta_asignacion
FOR EACH ROW EXECUTE FUNCTION fn_validar_asignacion();

-- RN-11: una hoja no sale de Borrador sin al menos una operacion.
CREATE FUNCTION fn_validar_envio_revision() RETURNS trigger AS $$
BEGIN
    IF NEW.estatus IN ('EN_REVISION', 'LIBERADA')
       AND NOT EXISTS (SELECT 1 FROM hoja_ruta_operacion WHERE hoja_ruta_id = NEW.hoja_ruta_id) THEN
        RAISE EXCEPTION 'RN-11: la hoja % no tiene operaciones', NEW.numero;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_validar_envio_revision
BEFORE UPDATE OF estatus ON hoja_ruta
FOR EACH ROW EXECUTE FUNCTION fn_validar_envio_revision();

-- [RUTAS] D2: Total Run Time de la hoja = suma de preparacion + ejecucion.
CREATE FUNCTION fn_actualizar_tiempo_total() RETURNS trigger AS $$
DECLARE
    v_hoja INTEGER := COALESCE(NEW.hoja_ruta_id, OLD.hoja_ruta_id);
BEGIN
    UPDATE hoja_ruta
       SET tiempo_total_min = (SELECT COALESCE(SUM(tiempo_preparacion_min + tiempo_ejecucion_min), 0)
                               FROM hoja_ruta_operacion WHERE hoja_ruta_id = v_hoja)
     WHERE hoja_ruta_id = v_hoja;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_actualizar_tiempo_total
AFTER INSERT OR UPDATE OR DELETE ON hoja_ruta_operacion
FOR EACH ROW EXECUTE FUNCTION fn_actualizar_tiempo_total();

-- RN-14: la orden solo toma una hoja Liberada y vigente en su fecha de inicio.
CREATE FUNCTION fn_validar_hoja_de_orden() RETURNS trigger AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM hoja_ruta h
        WHERE h.hoja_ruta_id = NEW.hoja_ruta_id
          AND h.estatus = 'LIBERADA'
          AND h.vigente_desde <= NEW.fecha_inicio
          AND (h.vigente_hasta IS NULL OR h.vigente_hasta >= NEW.fecha_inicio)
    ) THEN
        RAISE EXCEPTION 'RN-14: no existe hoja de ruta liberada y vigente para la orden %', NEW.folio;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_validar_hoja_de_orden
BEFORE INSERT ON orden_produccion
FOR EACH ROW EXECUTE FUNCTION fn_validar_hoja_de_orden();

-- [RUTAS] F3: la ruta asignada a la orden no se cambia despues.
CREATE FUNCTION fn_conservar_ruta_original() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'La orden % debe conservar su hoja de ruta original', OLD.folio;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_conservar_ruta_original
BEFORE UPDATE OF hoja_ruta_id ON orden_produccion
FOR EACH ROW WHEN (OLD.hoja_ruta_id IS DISTINCT FROM NEW.hoja_ruta_id)
EXECUTE FUNCTION fn_conservar_ruta_original();

-- [RUTAS] C2: las fechas de cada etapa caen dentro del horizonte de la orden.
CREATE FUNCTION fn_validar_horizonte_etapa() RETURNS trigger AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM orden_produccion o
        WHERE o.orden_produccion_id = NEW.orden_produccion_id
          AND NEW.fecha_inicio >= o.fecha_inicio
          AND NEW.fecha_fin    <= o.fecha_fin
    ) THEN
        RAISE EXCEPTION 'La etapa % queda fuera del horizonte de la orden', NEW.secuencia;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_validar_horizonte_etapa
BEFORE INSERT OR UPDATE ON orden_produccion_etapa
FOR EACH ROW EXECUTE FUNCTION fn_validar_horizonte_etapa();

-- [RUTAS] F2: no se borra una etapa con movimientos en una orden Liberada.
CREATE FUNCTION fn_bloquear_borrado_etapa() RETURNS trigger AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM orden_produccion o
               WHERE o.orden_produccion_id = OLD.orden_produccion_id AND o.estatus = 'LIBERADA')
       AND EXISTS (SELECT 1 FROM despacho_produccion d
                   WHERE d.orden_produccion_etapa_id = OLD.orden_produccion_etapa_id) THEN
        RAISE EXCEPTION 'No se puede borrar la etapa %: tiene movimientos en una orden liberada',
            OLD.secuencia;
    END IF;
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_bloquear_borrado_etapa
BEFORE DELETE ON orden_produccion_etapa
FOR EACH ROW EXECUTE FUNCTION fn_bloquear_borrado_etapa();

-- [RUTAS] C3 / C4 / E1a / E1b: el despacho exige orden Liberada y etapas
-- anteriores completamente despachadas; descuenta inventario y acumula
-- lo despachado y el costo real.
CREATE FUNCTION fn_registrar_despacho() RETURNS trigger AS $$
DECLARE
    v_secuencia INTEGER;
BEGIN
    IF (SELECT estatus FROM orden_produccion
        WHERE orden_produccion_id = NEW.orden_produccion_id) <> 'LIBERADA' THEN
        RAISE EXCEPTION 'La orden no esta liberada';
    END IF;

    SELECT secuencia INTO v_secuencia
    FROM orden_produccion_etapa
    WHERE orden_produccion_etapa_id = NEW.orden_produccion_etapa_id
      AND orden_produccion_id = NEW.orden_produccion_id;
    IF v_secuencia IS NULL THEN
        RAISE EXCEPTION 'La etapa no pertenece a la orden';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM orden_produccion_linea l
        JOIN orden_produccion_etapa e ON e.orden_produccion_etapa_id = l.orden_produccion_etapa_id
        WHERE l.orden_produccion_id = NEW.orden_produccion_id
          AND l.tipo = 'MATERIAL'
          AND e.secuencia < v_secuencia
          AND l.cantidad_despachada < l.cantidad_planificada
    ) THEN
        RAISE EXCEPTION 'Falta completar el despacho de una etapa anterior a la %', v_secuencia;
    END IF;

    UPDATE existencia
       SET cantidad = cantidad - NEW.cantidad
     WHERE material_id = NEW.material_id AND almacen_id = NEW.almacen_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'No hay existencia del material % en el almacen %',
            NEW.material_id, NEW.almacen_id;
    END IF;

    UPDATE orden_produccion_linea
       SET cantidad_despachada = cantidad_despachada + NEW.cantidad
     WHERE orden_produccion_linea_id = NEW.orden_produccion_linea_id;

    UPDATE orden_produccion
       SET costo_real = costo_real + NEW.cantidad * NEW.costo_unitario
     WHERE orden_produccion_id = NEW.orden_produccion_id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_registrar_despacho
BEFORE INSERT ON despacho_produccion
FOR EACH ROW EXECUTE FUNCTION fn_registrar_despacho();

-- ---------------------------------------------------------------------
-- 7. Datos semilla
-- ---------------------------------------------------------------------
INSERT INTO rol (clave, nombre) VALUES
    ('INGENIERO_PROCESOS', 'Ingeniero de procesos (Creador)'),
    ('JEFE_PRODUCCION',    'Jefe de produccion (Aprobador)'),
    ('PLANEADOR',          'Planeador de produccion');

COMMIT;
