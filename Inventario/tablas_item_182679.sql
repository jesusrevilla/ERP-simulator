--- PROPUESTA DE LA TABLA ITEM
--- Autor: Alejandro Dominguez 182679
--- Se incluyen otras tablas necesarias para la creacion de la tabla ITEMS

--------> Para cumplir el requerimiento de valuacion de costos de inventario,
--        implemento un enum con los metodos contables automatizados

CREATE TYPE metodo_contable AS ENUM ('FIFO','PROMEDIO_MOVIL','ESTANDAR');

--------> Cumplo con el requerimiento de grupos de unidades de medida:

--- Unidades de medida (piezas, metros, etc...)
CREATE TABLE udm (
    udm_id      SERIAL PRIMARY KEY,
    name        VARCHAR(80) NOT NULL UNIQUE,
    unidad_base VARCHAR(20) NOT NULL            -- unidad base del grupo (PZA,M,etc...)
);

--- Se guarda la equivalencia (1 metro = nFactor metros para otra unidad)
CREATE TABLE udm_conversiones(
	udm_id          INT NOT NULL REFERENCES udm(udm_id),
	udm_codigo	    VARCHAR(20) NOT NULL UNIQUE,
    factor_a_base   NUMERIC(19,6) NOT NULL CHECK (factor_a_base > 0), --- nFactor
    PRIMARY KEY     (udm_id, udm_codigo)
);

---------> CREACION DE LA TABLA ITEMS

CREATE TABLE item(
    codigo          VARCHAR(50) PRIMARY KEY,
    descripcion     VARCHAR(255) NOT NULL,
    --> Cumpliendo el req de definir comportamiento
    es_de_venta     BOOLEAN NOT NULL DEFAULT TRUE,
    es_de_compra    BOOLEAN NOT NULL DEFAULT TRUE,
    es_inventario   BOOLEAN NOT NULL DEFAULT TRUE,
    --> Cumpliendo el req de trazabilidad lotes y series, en otra parte se enforzara RN02 pero aqui se deja la base
    es_por_lotes    BOOLEAN NOT NULL DEFAULT FALSE,
    es_por_serie    BOOLEAN NOT NULL DEFAULT FALSE,
    --> Se continua con el req de valuacion
    metodo_contable metodo_contable NOT NULL DEFAULT 'ESTANDAR', -- Por defecto se marca estandar
    costo_estandar  NUMERIC(19,6) NOT NULL DEFAULT 0 CHECK (costo_estandar >= 0),
    costo_promedio  NUMERIC(19,6) NOT NULL DEFAULT 0 CHECK (costo_promedio >= 0),
    udm_id          INT NOT NULL REFERENCES udm(udm_id),
    activo          BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en       TIMESTAMP NOT NULL DEFAULT now(),

    -- Creo las constraint para asegurar que si un item no es de inventario interno,
    -- no pueda gestionarse por lote o serie
    CONSTRAINT chk_item_tracking CHECK (es_inventario OR NOT (es_por_lotes OR es_por_serie)),
    CONSTRAINT chk_item_no_es_ambos CHECK (NOT (es_por_lotes AND es_por_serie))
)