-- ---------------------------------------------------------------------
-- 3. ALMACENES Y UBICACIONES
-- ---------------------------------------------------------------------
CREATE TABLE warehouse (
    warehouse_id  SERIAL PRIMARY KEY,
    code          VARCHAR(20) NOT NULL UNIQUE,
    name          VARCHAR(100) NOT NULL,
    type          warehouse_type NOT NULL DEFAULT 'NORMAL',
    active        BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE bin_location (
    bin_id        SERIAL PRIMARY KEY,
    warehouse_id  INT NOT NULL REFERENCES warehouse(warehouse_id),
    code          VARCHAR(30) NOT NULL,
    UNIQUE (warehouse_id, code)
);

-- ---------------------------------------------------------------------
-- 4. LOTES Y SERIES
-- ---------------------------------------------------------------------
CREATE TABLE batch (
    batch_id      BIGSERIAL PRIMARY KEY,
    item_code     VARCHAR(50) NOT NULL REFERENCES item(item_code),
    batch_number  VARCHAR(50) NOT NULL,
    expiry_date   DATE NOT NULL,                       -- RN02: caducidad obligatoria
    UNIQUE (item_code, batch_number)
);

CREATE TABLE serial_number (
    serial_id     BIGSERIAL PRIMARY KEY,
    item_code     VARCHAR(50) NOT NULL REFERENCES item(item_code),
    serial        VARCHAR(80) NOT NULL,
    status        serial_status NOT NULL DEFAULT 'EN_STOCK',
    warehouse_id  INT REFERENCES warehouse(warehouse_id),
    UNIQUE (item_code, serial)
);
