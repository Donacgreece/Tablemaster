CREATE TABLE IF NOT EXISTS tables (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_number INTEGER NOT NULL,
    capacity INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'free',
    space TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reservations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_name TEXT NOT NULL,
    date TEXT NOT NULL,
    time TEXT NOT NULL,
    guests INTEGER NOT NULL,
    table_id INTEGER,
    FOREIGN KEY (table_id) REFERENCES tables(id)
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_id INTEGER,
    table_name TEXT, 
    status TEXT NOT NULL DEFAULT 'pending',
    order_date TEXT NOT NULL,
    user_id INTEGER,  
    receipt_number INTEGER,  
    FOREIGN KEY (table_id) REFERENCES tables(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER,
    product_id INTEGER,
    price REAL NOT NULL,
    quantity INTEGER NOT NULL,
    paid_quantity INTEGER DEFAULT 0,
    printed INTEGER DEFAULT 0,
    comments TEXT,
    subcategory_id INTEGER,  -- Νέο πεδίο
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (product_id) REFERENCES products(id)
);

CREATE TABLE IF NOT EXISTS bills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER,  
    table_id INTEGER,  
    total_amount REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'unpaid',
    receipt_number INTEGER,  
    payment_method TEXT NOT NULL DEFAULT 'Μετρητά',  
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (table_id) REFERENCES tables(id)
);

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    vat_rate REAL NOT NULL DEFAULT 24.0,
    is_active INTEGER NOT NULL DEFAULT 1  
);

CREATE TABLE IF NOT EXISTS subcategories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category_id INTEGER, 
    FOREIGN KEY (category_id) REFERENCES categories(id)
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    price REAL NOT NULL,
    category_id INTEGER,
    subcategory_id INTEGER,
    is_active INTEGER NOT NULL DEFAULT 1,  
    FOREIGN KEY (category_id) REFERENCES categories(id),
    FOREIGN KEY (subcategory_id) REFERENCES subcategories(id)
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    pin TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL DEFAULT 'user'
);

CREATE TABLE IF NOT EXISTS printers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    ip_address TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS company_info (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name TEXT NOT NULL,
    company_address TEXT NOT NULL,
    company_tax_id TEXT NOT NULL,  
    company_tax_office TEXT NOT NULL,  
    company_phone TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS receipts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_number INTEGER NOT NULL UNIQUE,  
    issue_date TEXT NOT NULL,  
    order_id INTEGER NOT NULL,  
    FOREIGN KEY (order_id) REFERENCES orders(id)
);

CREATE TABLE IF NOT EXISTS printer_categories (
    printer_id INTEGER,
    category_id INTEGER,
    FOREIGN KEY (printer_id) REFERENCES printers(id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE,
    PRIMARY KEY (printer_id, category_id)
);

CREATE TABLE IF NOT EXISTS settings (
    name TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pending_prints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    printer_id INTEGER,
    order_data TEXT,
    table_number INTEGER,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_receipt BOOLEAN
);

CREATE TABLE IF NOT EXISTS pending_receipts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    printer_id INTEGER,
    receipt_data TEXT,
    table_number TEXT,
    receipt_number INTEGER,
    payment_method TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (printer_id) REFERENCES printers(id)
);
