-- ---------------------------------------------------------------------
-- 7. CONTABILIDAD (Asientos) - ID03
-- ---------------------------------------------------------------------
CREATE TABLE gl_account (
    account_code  VARCHAR(20) PRIMARY KEY,
    name          VARCHAR(120) NOT NULL
);

CREATE TABLE journal_entry (
    je_id         BIGSERIAL PRIMARY KEY,
    je_date       DATE NOT NULL DEFAULT CURRENT_DATE,
    memo          VARCHAR(255),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE journal_entry_line (
    je_id         BIGINT NOT NULL REFERENCES journal_entry(je_id),
    line_no       INT NOT NULL,
    account_code  VARCHAR(20) NOT NULL REFERENCES gl_account(account_code),
    debit         NUMERIC(19,6) NOT NULL DEFAULT 0 CHECK (debit >= 0),
    credit        NUMERIC(19,6) NOT NULL DEFAULT 0 CHECK (credit >= 0),
    PRIMARY KEY (je_id, line_no),
    CHECK ((debit = 0) <> (credit = 0))   -- una línea es débito O crédito
);

-- ---------------------------------------------------------------------
-- 8. DOCUMENTOS DE INVENTARIO (inmutables) - RN03
-- ---------------------------------------------------------------------
CREATE TABLE inventory_doc (
    doc_id        BIGSERIAL PRIMARY KEY,
    doc_type      inv_doc_type NOT NULL,
    doc_date      DATE NOT NULL DEFAULT CURRENT_DATE,
    status        inv_doc_status NOT NULL DEFAULT 'PUBLICADO',
    reversal_of_doc_id BIGINT REFERENCES inventory_doc(doc_id),  -- documento que revierte
    je_id         BIGINT NOT NULL REFERENCES journal_entry(je_id), -- ID03
    created_by    VARCHAR(60) NOT NULL DEFAULT current_user,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_reversal CHECK ((doc_type = 'REVERSION') = (reversal_of_doc_id IS NOT NULL))
);
CREATE UNIQUE INDEX ux_one_reversal_per_doc
    ON inventory_doc (reversal_of_doc_id) WHERE reversal_of_doc_id IS NOT NULL;

CREATE TABLE inventory_doc_line (
    line_id       BIGSERIAL PRIMARY KEY,
    doc_id        BIGINT NOT NULL REFERENCES inventory_doc(doc_id),
    line_no       INT NOT NULL,
    item_code     VARCHAR(50) NOT NULL REFERENCES item(item_code),   -- ID01
    warehouse_id  INT NOT NULL REFERENCES warehouse(warehouse_id),
    bin_id        INT REFERENCES bin_location(bin_id),
    batch_id      BIGINT REFERENCES batch(batch_id),
    uom_code      VARCHAR(20) NOT NULL,
    qty_entered   NUMERIC(19,6) NOT NULL CHECK (qty_entered > 0),    -- en la UoM capturada
    qty_base      NUMERIC(19,6) NOT NULL CHECK (qty_base <> 0),      -- + entrada / - salida
    unit_cost     NUMERIC(19,6) NOT NULL DEFAULT 0 CHECK (unit_cost >= 0),
    UNIQUE (doc_id, line_no)
);
CREATE INDEX ix_idl_item ON inventory_doc_line (item_code, warehouse_id);

-- Series asociadas a una línea (una fila por unidad serializada)
CREATE TABLE inventory_doc_line_serial (
    line_id       BIGINT NOT NULL REFERENCES inventory_doc_line(line_id),
    serial_id     BIGINT NOT NULL REFERENCES serial_number(serial_id),
    PRIMARY KEY (line_id, serial_id)
);

-- Capas de costo para FIFO
CREATE TABLE cost_layer (
    layer_id      BIGSERIAL PRIMARY KEY,
    item_code     VARCHAR(50) NOT NULL REFERENCES item(item_code),
    warehouse_id  INT NOT NULL REFERENCES warehouse(warehouse_id),
    source_line_id BIGINT NOT NULL REFERENCES inventory_doc_line(line_id),
    received_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    qty_initial   NUMERIC(19,6) NOT NULL CHECK (qty_initial > 0),
    qty_remaining NUMERIC(19,6) NOT NULL CHECK (qty_remaining >= 0),
    unit_cost     NUMERIC(19,6) NOT NULL CHECK (unit_cost >= 0),
    CHECK (qty_remaining <= qty_initial)
);
CREATE INDEX ix_cost_layer_fifo
    ON cost_layer (item_code, warehouse_id, received_at) WHERE qty_remaining > 0;
