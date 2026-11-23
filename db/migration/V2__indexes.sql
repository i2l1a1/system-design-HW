CREATE INDEX orders_closed_finish_time_idx ON orders (finish_time)
    WHERE status IN ('finished', 'cancelled');

CREATE INDEX debts_unpaid_user_id_idx ON debts (user_id) WHERE status = 'unpaid';
CREATE INDEX debts_order_id_idx ON debts (order_id);
CREATE INDEX idempotency_keys_order_id_idx ON idempotency_keys (order_id);
CREATE INDEX payment_operations_order_id_idx ON payment_operations (order_id);
