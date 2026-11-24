PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS commercial_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    salt TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('administrador', 'compras', 'ventas', 'almacen')),
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS commercial_products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL CHECK (length(trim(name)) > 0),
    price_cents INTEGER NOT NULL CHECK (price_cents > 0),
    cost_cents INTEGER NOT NULL CHECK (cost_cents >= 0),
    stock INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0),
    minimum_stock INTEGER NOT NULL DEFAULT 0 CHECK (minimum_stock >= 0),
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS commercial_suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL CHECK (length(trim(name)) > 0),
    email TEXT,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS commercial_customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL CHECK (length(trim(name)) > 0),
    email TEXT,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS commercial_purchases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id INTEGER NOT NULL REFERENCES commercial_suppliers(id) ON DELETE RESTRICT,
    user_id INTEGER NOT NULL REFERENCES commercial_users(id) ON DELETE RESTRICT,
    status TEXT NOT NULL DEFAULT 'Borrador' CHECK (status IN ('Borrador', 'Confirmada')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    confirmed_at TEXT
);

CREATE TABLE IF NOT EXISTS commercial_purchase_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_id INTEGER NOT NULL REFERENCES commercial_purchases(id) ON DELETE RESTRICT,
    product_id INTEGER NOT NULL REFERENCES commercial_products(id) ON DELETE RESTRICT,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_cost_cents INTEGER NOT NULL CHECK (unit_cost_cents >= 0)
);

CREATE TABLE IF NOT EXISTS commercial_sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES commercial_customers(id) ON DELETE RESTRICT,
    user_id INTEGER NOT NULL REFERENCES commercial_users(id) ON DELETE RESTRICT,
    status TEXT NOT NULL DEFAULT 'Borrador' CHECK (status IN ('Borrador', 'Confirmada', 'Cancelada')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    confirmed_at TEXT,
    cancelled_at TEXT,
    cancellation_reason TEXT
);

CREATE TABLE IF NOT EXISTS commercial_sale_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL REFERENCES commercial_sales(id) ON DELETE RESTRICT,
    product_id INTEGER NOT NULL REFERENCES commercial_products(id) ON DELETE RESTRICT,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price_cents INTEGER NOT NULL CHECK (unit_price_cents > 0)
);

CREATE TABLE IF NOT EXISTS commercial_movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES commercial_products(id) ON DELETE RESTRICT,
    user_id INTEGER NOT NULL REFERENCES commercial_users(id) ON DELETE RESTRICT,
    movement_type TEXT NOT NULL CHECK (movement_type IN ('ALTA', 'RECEPCION', 'VENTA', 'CANCELACION', 'AJUSTE')),
    quantity_delta INTEGER NOT NULL CHECK (quantity_delta <> 0),
    document_type TEXT NOT NULL,
    document_id INTEGER,
    reason TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS commercial_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES commercial_users(id) ON DELETE RESTRICT,
    action TEXT NOT NULL,
    entity TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    details TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_commercial_movements_product ON commercial_movements(product_id, created_at);
CREATE INDEX IF NOT EXISTS idx_commercial_sale_lines_sale ON commercial_sale_lines(sale_id);
CREATE INDEX IF NOT EXISTS idx_commercial_purchase_lines_purchase ON commercial_purchase_lines(purchase_id);
