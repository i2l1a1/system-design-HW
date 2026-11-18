CREATE TABLE offers (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    scooter_id TEXT NOT NULL,
    zone_id TEXT NOT NULL,
    price_per_minute INTEGER NOT NULL,
    price_unlock INTEGER NOT NULL,
    deposit INTEGER NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE orders (
    id TEXT PRIMARY KEY,
    offer_id TEXT NOT NULL UNIQUE,
    user_id TEXT NOT NULL,
    scooter_id TEXT NOT NULL,
    price_per_minute INTEGER NOT NULL,
    price_unlock INTEGER NOT NULL,
    deposit INTEGER NOT NULL,
    total_amount INTEGER,
    status TEXT NOT NULL,
    start_time TIMESTAMPTZ,
    finish_time TIMESTAMPTZ,
    CONSTRAINT orders_offer_id_fkey FOREIGN KEY (offer_id) REFERENCES offers (id)
);

CREATE TABLE debts (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    order_id TEXT NOT NULL,
    amount INTEGER NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    repaid_at TIMESTAMPTZ,
    CONSTRAINT debts_order_id_fkey FOREIGN KEY (order_id) REFERENCES orders (id)
);

CREATE TABLE user_reliability (
    user_id TEXT PRIMARY KEY,
    score INTEGER NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE idempotency_keys (
    "key" TEXT PRIMARY KEY,
    order_id TEXT NOT NULL,
    result TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT idempotency_keys_order_id_fkey FOREIGN KEY (order_id) REFERENCES orders (id)
);

CREATE TABLE payment_operations (
    payment_key TEXT PRIMARY KEY,
    order_id TEXT NOT NULL,
    type TEXT NOT NULL,
    status TEXT NOT NULL,
    amount INTEGER NOT NULL,
    CONSTRAINT payment_operations_order_id_fkey FOREIGN KEY (order_id) REFERENCES orders (id)
);
