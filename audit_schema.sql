CREATE TABLE IF NOT EXISTS deletion_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_item_id INTEGER NOT NULL,
    product_name TEXT NOT NULL,
    table_number TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    user_name TEXT NOT NULL,
    deletion_time TEXT NOT NULL
);