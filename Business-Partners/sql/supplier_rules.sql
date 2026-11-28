CREATE TABLE IF NOT EXISTS supplier_rules (
    id SERIAL PRIMARY KEY,
    material_id INTEGER NOT NULL
        REFERENCES materials(id),
    supplier_code VARCHAR(20) NOT NULL,
    preferred BOOLEAN NOT NULL DEFAULT FALSE,
    lead_time_days INTEGER NOT NULL
        CHECK (lead_time_days >= 0),
    moq INTEGER NOT NULL CHECK (moq > 0),
    order_multiple INTEGER NOT NULL DEFAULT 1
        CHECK (order_multiple > 0),
    UNIQUE (material_id, supplier_code)
);
