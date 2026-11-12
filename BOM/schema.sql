CREATE EXTENSION IF NOT EXISTS btree_gist;

-- CATÁLOGOS BASE: UNIDADES DE MEDIDA Y CONVERSIONES
CREATE TABLE unidades_medida (
    uom_id VARCHAR(10) PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL,
    dimension VARCHAR(20) NOT NULL CHECK (dimension IN ('LONGITUD', 'MASA', 'VOLUMEN', 'CONTEO', 'TIEMPO')),
    precision_decimales SMALLINT NOT NULL DEFAULT 0 CHECK (precision_decimales >= 0 AND precision_decimales <= 6),
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE conversiones_uom (
    conversion_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    uom_origen_id VARCHAR(10) NOT NULL REFERENCES unidades_medida(uom_id) ON DELETE RESTRICT,
    uom_destino_id VARCHAR(10) NOT NULL REFERENCES unidades_medida(uom_id) ON DELETE RESTRICT,
    factor_multiplicador NUMERIC(18, 8) NOT NULL CHECK (factor_multiplicador > 0),
    sku_especifico VARCHAR(50) NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_conversion UNIQUE (uom_origen_id, uom_destino_id, sku_especifico),
    CONSTRAINT chk_distintas_unidades CHECK (uom_origen_id <> uom_destino_id)
);

CREATE TABLE articulos (
    sku VARCHAR(50) PRIMARY KEY,
    descripcion VARCHAR(255) NOT NULL,
    tipo_item VARCHAR(2) NOT NULL CHECK (tipo_item IN ('PT', 'SE', 'MP')),
    uom_base_id VARCHAR(10) NOT NULL REFERENCES unidades_medida(uom_id) ON DELETE RESTRICT,
    es_discreto BOOLEAN NOT NULL DEFAULT TRUE,
    costo_estandar NUMERIC(14, 4) NOT NULL DEFAULT 0.0000 CHECK (costo_estandar >= 0),
    tamano_lote_minimo NUMERIC(14, 4) NOT NULL DEFAULT 1.0000 CHECK (tamano_lote_minimo > 0),
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

--CABECERA DEL BILL OF MATERIALS (BOM_HEADER)--

CREATE TABLE bom_cabecera (
    bom_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    parent_sku VARCHAR(50) NOT NULL REFERENCES articulos(sku) ON DELETE RESTRICT,
    version_codigo VARCHAR(20) NOT NULL,
    cantidad_base NUMERIC(14, 4) NOT NULL DEFAULT 1.0000 CHECK (cantidad_base > 0),
    uom_id VARCHAR(10) NOT NULL REFERENCES unidades_medida(uom_id) ON DELETE RESTRICT,
    estado VARCHAR(15) NOT NULL DEFAULT 'BORRADOR' CHECK (estado IN ('BORRADOR', 'ACTIVO', 'INACTIVO', 'OBSOLETO')),
    fecha_inicio TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_fin TIMESTAMPTZ NULL,
    notas_ingenieria TEXT NULL,
    usuario_creacion VARCHAR(100) NOT NULL,
    usuario_aprobacion VARCHAR(100) NULL,
    fecha_aprobacion TIMESTAMPTZ NULL,
    version_concurrencia INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_parent_version UNIQUE (parent_sku, version_codigo),
    CONSTRAINT chk_rango_fechas CHECK (fecha_fin IS NULL OR fecha_fin > fecha_inicio),
    CONSTRAINT chk_auditoria_aprobacion CHECK (
        (estado = 'BORRADOR' AND usuario_aprobacion IS NULL AND fecha_aprobacion IS NULL) OR
        (estado <> 'BORRADOR' AND usuario_aprobacion IS NOT NULL AND fecha_aprobacion IS NOT NULL)
    )
);

ALTER TABLE bom_cabecera
ADD CONSTRAINT no_traslape_versiones_activas
EXCLUDE USING gist (
    parent_sku WITH =,
    tstzrange(fecha_inicio, COALESCE(fecha_fin, 'infinity'::TIMESTAMPTZ), '[)') WITH &&
) WHERE (estado = 'ACTIVO');

CREATE TABLE bom_detalle (
    linea_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    bom_id BIGINT NOT NULL REFERENCES bom_cabecera(bom_id) ON DELETE RESTRICT,
    component_sku VARCHAR(50) NOT NULL REFERENCES articulos(sku) ON DELETE RESTRICT,
    cantidad NUMERIC(14, 4) NOT NULL CHECK (cantidad > 0),
    uom_id VARCHAR(10) NOT NULL REFERENCES unidades_medida(uom_id) ON DELETE RESTRICT,
    scrap_merma NUMERIC(5, 4) NOT NULL DEFAULT 0.0000 CHECK (scrap_merma >= 0.0000 AND scrap_merma < 1.0000),
    notas_posicion VARCHAR(100) NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_bom_componente UNIQUE (bom_id, component_sku)
);

CREATE TABLE ordenes_produccion (
    orden_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo_orden VARCHAR(50) NOT NULL UNIQUE,
    parent_sku VARCHAR(50) NOT NULL REFERENCES articulos(sku) ON DELETE RESTRICT,
    bom_id BIGINT NOT NULL REFERENCES bom_cabecera(bom_id) ON DELETE RESTRICT,
    cantidad_requerida NUMERIC(14, 4) NOT NULL CHECK (cantidad_requerida > 0),
    fecha_requerida DATE NOT NULL,
    estado VARCHAR(20) NOT NULL DEFAULT 'PLANIFICADA' 
        CHECK (estado IN ('PLANIFICADA', 'LIBERADA', 'EN_PROCESO', 'TERMINADA', 'CANCELADA')),
    usuario_creacion VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE orden_bom_snapshots (
    snapshot_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    orden_id BIGINT NOT NULL REFERENCES ordenes_produccion(orden_id) ON DELETE CASCADE,
    nivel INT NOT NULL CHECK (nivel >= 0),
    sku_padre VARCHAR(50) NOT NULL,
    sku_componente VARCHAR(50) NOT NULL,
    version_bom VARCHAR(20) NOT NULL,
    cantidad_neta NUMERIC(14, 4) NOT NULL,
    cantidad_bruta NUMERIC(14, 4) NOT NULL,
    scrap_aplicado NUMERIC(5, 4) NOT NULL,
    uom_id VARCHAR(10) NOT NULL,
    costo_unitario_historico NUMERIC(14, 4) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- AUDITORIA --

CREATE TABLE auditoria_bom (
    auditoria_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entidad_afectada VARCHAR(50) NOT NULL,
    registro_id VARCHAR(50) NOT NULL,
    accion VARCHAR(10) NOT NULL CHECK (accion IN ('INSERT', 'UPDATE', 'DELETE')),
    usuario VARCHAR(100) NOT NULL DEFAULT CURRENT_USER,
    fecha_hora TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    valores_anteriores JSONB NULL,
    valores_nuevos JSONB NULL,
    direccion_ip INET NULL
);
