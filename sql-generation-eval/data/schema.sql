PRAGMA foreign_keys = ON;

CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    country TEXT NOT NULL,
    registered_at TEXT NOT NULL
) STRICT;

CREATE TABLE addresses (
    address_id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    city TEXT NOT NULL,
    country TEXT NOT NULL,
    line1 TEXT NOT NULL,
    UNIQUE(address_id, customer_id)
) STRICT;

CREATE TABLE categories (
    category_id INTEGER PRIMARY KEY,
    parent_category_id INTEGER REFERENCES categories(category_id),
    category_name TEXT NOT NULL UNIQUE,
    CHECK(parent_category_id IS NULL OR parent_category_id <> category_id)
) STRICT;

CREATE TABLE suppliers (
    supplier_id INTEGER PRIMARY KEY,
    supplier_name TEXT NOT NULL,
    country TEXT NOT NULL
) STRICT;

CREATE TABLE products (
    product_id INTEGER PRIMARY KEY,
    category_id INTEGER NOT NULL REFERENCES categories(category_id),
    sku TEXT NOT NULL UNIQUE,
    product_name TEXT NOT NULL,
    current_price_cents INTEGER NOT NULL CHECK(current_price_cents >= 0),
    active INTEGER NOT NULL CHECK(active IN (0, 1))
) STRICT;

CREATE TABLE product_suppliers (
    product_id INTEGER NOT NULL REFERENCES products(product_id),
    supplier_id INTEGER NOT NULL REFERENCES suppliers(supplier_id),
    supply_cost_cents INTEGER NOT NULL CHECK(supply_cost_cents >= 0),
    lead_time_days INTEGER NOT NULL CHECK(lead_time_days >= 0),
    PRIMARY KEY(product_id, supplier_id)
) STRICT;

CREATE TABLE orders (
    order_id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    shipping_address_id INTEGER NOT NULL,
    ordered_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('completed', 'processing', 'cancelled')),
    shipping_fee_cents INTEGER NOT NULL CHECK(shipping_fee_cents >= 0),
    FOREIGN KEY(shipping_address_id, customer_id) REFERENCES addresses(address_id, customer_id)
) STRICT;

CREATE TABLE order_items (
    order_item_id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(order_id),
    product_id INTEGER NOT NULL REFERENCES products(product_id),
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    unit_price_cents INTEGER NOT NULL CHECK(unit_price_cents >= 0),
    discount_cents INTEGER NOT NULL CHECK(discount_cents >= 0 AND discount_cents <= quantity * unit_price_cents),
    UNIQUE(order_item_id, order_id)
) STRICT;

CREATE TABLE payments (
    payment_id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(order_id),
    paid_at TEXT NOT NULL,
    amount_cents INTEGER NOT NULL CHECK(amount_cents >= 0),
    method TEXT NOT NULL CHECK(method IN ('card', 'transfer', 'cash')),
    status TEXT NOT NULL CHECK(status IN ('succeeded', 'failed', 'pending'))
) STRICT;

CREATE TABLE shipments (
    shipment_id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(order_id),
    shipped_at TEXT NOT NULL,
    promised_at TEXT NOT NULL,
    delivered_at TEXT,
    carrier TEXT NOT NULL,
    CHECK(promised_at >= shipped_at),
    CHECK(delivered_at IS NULL OR delivered_at >= shipped_at)
) STRICT;

CREATE TABLE returns (
    return_id INTEGER PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(order_id),
    requested_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('approved', 'rejected', 'pending')),
    UNIQUE(return_id, order_id)
) STRICT;

CREATE TABLE return_items (
    return_item_id INTEGER PRIMARY KEY,
    return_id INTEGER NOT NULL,
    order_id INTEGER NOT NULL,
    order_item_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    refund_cents INTEGER NOT NULL CHECK(refund_cents >= 0),
    FOREIGN KEY(return_id, order_id) REFERENCES returns(return_id, order_id),
    FOREIGN KEY(order_item_id, order_id) REFERENCES order_items(order_item_id, order_id)
) STRICT;

CREATE INDEX idx_orders_customer_date ON orders(customer_id, ordered_at);
CREATE INDEX idx_orders_status_date ON orders(status, ordered_at);
CREATE INDEX idx_items_order ON order_items(order_id);
CREATE INDEX idx_items_product ON order_items(product_id);
CREATE INDEX idx_payments_order ON payments(order_id);
CREATE INDEX idx_shipments_order ON shipments(order_id);
CREATE INDEX idx_returns_order ON returns(order_id);
CREATE INDEX idx_return_items_item ON return_items(order_item_id);
CREATE INDEX idx_product_category ON products(category_id);
CREATE INDEX idx_supplier_products ON product_suppliers(supplier_id);
CREATE INDEX idx_category_parent ON categories(parent_category_id);
