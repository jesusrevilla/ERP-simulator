CREATE TABLE IF NOT EXISTS demand_forecasts (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL
        REFERENCES products(id),
    forecast_date DATE NOT NULL,
    quantity INTEGER NOT NULL
        CHECK (quantity > 0)
);
