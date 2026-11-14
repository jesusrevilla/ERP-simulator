CREATE TABLE IF NOT EXISTS mrp_recommendations (
    id SERIAL PRIMARY KEY,
    material_id INTEGER NOT NULL
        REFERENCES materials(id),
    supplier_code VARCHAR(20) NOT NULL,
    suggested_quantity INTEGER NOT NULL
        CHECK (suggested_quantity > 0),
    planned_release_date DATE NOT NULL,
    status VARCHAR(12) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected')),
    unit_price NUMERIC(12,2)
        CHECK (unit_price >= 0),
    agreement_ref VARCHAR(50)
);
