"""Deterministic relational fixtures with deliberate join and boundary traps."""

from __future__ import annotations

import random
import sqlite3
from datetime import date, timedelta


def populate(connection: sqlite3.Connection, seed: int) -> None:
    rng = random.Random(seed)
    countries = ["TN", "FR", "DE", "IT"]
    # Repeated names, customers without orders, and multiple addresses are intentional.
    for customer in range(1, 81):
        country = countries[(customer + seed) % len(countries)]
        connection.execute("INSERT INTO customers VALUES (?, ?, ?, ?, ?)", (
            customer, f"Customer {customer % 67:02}", f"customer{customer}@example.test",
            country, f"2024-{1 + customer % 12:02}-01"))
        for offset in (() if customer == 80 else (0, 1)):
            connection.execute("INSERT INTO addresses VALUES (?, ?, ?, ?, ?)", (
                customer * 2 - offset, customer, f"City {customer % 9}", country,
                f"{customer + offset} Example Street"))
    categories = [
        (1, None, "Electronics"), (2, None, "Home"), (3, None, "Sports"),
        (4, 1, "Computers"), (5, 1, "Phones"), (6, 2, "Kitchen"),
        (7, 2, "Furniture"), (8, 3, "Outdoor"), (9, 3, "Fitness"),
        (10, 4, "Laptops"), (11, 4, "Accessories"), (12, 8, "Camping"),
    ]
    connection.executemany("INSERT INTO categories VALUES (?, ?, ?)", categories)
    for supplier in range(1, 13):
        connection.execute("INSERT INTO suppliers VALUES (?, ?, ?)", (
            supplier, f"Supplier {supplier:02}", countries[supplier % 4]))
    prices = {}
    leaves = [5, 6, 7, 9, 10, 11, 12]
    for product in range(1, 49):
        prices[product] = rng.choice([1500, 2500, 4000, 6000, 12000, 25000])
        connection.execute("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?)", (
            product, leaves[(product - 1) % len(leaves)], f"SKU-{product:04}",
            f"Product {product % 41:02}", prices[product], int(product % 11 != 0)))
        if product % 13 != 0:
            for supplier in rng.sample(range(1, 11), 1 + product % 3):
                connection.execute("INSERT INTO product_suppliers VALUES (?, ?, ?, ?)", (
                    product, supplier, prices[product] * rng.choice([5, 6, 7]) // 10,
                    rng.choice([2, 5, 10, 20])))

    # A supplier covering a whole category and another missing one product make
    # universal-quantification questions distinguish correct answers from empty sets.
    connection.execute("INSERT INTO product_suppliers SELECT product_id,11,current_price_cents/2,5 FROM products WHERE category_id=11 AND active=1")
    connection.execute("INSERT INTO product_suppliers SELECT product_id,12,current_price_cents/2,5 FROM products WHERE category_id=11 AND active=1 AND product_id<>(SELECT MIN(product_id) FROM products WHERE category_id=11 AND active=1)")

    item_id = payment_id = shipment_id = return_id = return_item_id = 0
    for order_id in range(1, 481):
        customer = 1 + ((order_id * 13 + seed) % 72)
        ordered = date(2025, 1, 1) + timedelta(days=rng.randrange(365))
        # Ensure every month is covered, including exact quarter boundaries.
        if order_id <= 24:
            ordered = date(2025, 1 + (order_id - 1) % 12, 1)
            customer = 1 + (order_id - 1) // 12
        status = "cancelled" if order_id % 11 == 0 else "processing" if order_id % 9 == 0 else "completed"
        shipping_fee = 0 if order_id % 3 == 0 else 500
        connection.execute("INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?)", (
            order_id, customer, customer * 2 - order_id % 2, ordered.isoformat(), status, shipping_fee))
        items = []
        for line in range(1 + order_id % 4):
            item_id += 1
            # Products 45-48 are deliberately never sold; repeated product lines are allowed.
            product = rng.randrange(1, 45)
            quantity = rng.randrange(1, 5)
            unit_price = prices[product] + rng.choice([-100, 0, 100])
            discount = (quantity * unit_price // 10) if (order_id + line) % 5 == 0 else 0
            amount = quantity * unit_price - discount
            connection.execute("INSERT INTO order_items VALUES (?, ?, ?, ?, ?, ?)", (
                item_id, order_id, product, quantity, unit_price, discount))
            items.append((item_id, quantity, amount))
        total = sum(item[2] for item in items) + shipping_fee
        if status == "completed":
            amounts = [total // 2, total - total // 2] if order_id % 3 == 0 else [total]
            payment_status = "succeeded"
        else:
            amounts = [total]
            payment_status = "failed" if status == "cancelled" else "pending"
        for amount in amounts:
            payment_id += 1
            connection.execute("INSERT INTO payments VALUES (?, ?, ?, ?, ?, ?)", (
                payment_id, order_id, (ordered + timedelta(days=1)).isoformat(), amount,
                rng.choice(["card", "transfer", "cash"]), payment_status))
        if order_id % 7 == 0:
            payment_id += 1
            connection.execute("INSERT INTO payments VALUES (?, ?, ?, ?, ?, ?)", (
                payment_id, order_id, ordered.isoformat(), total, "card", "failed"))

        if status != "cancelled" and (status == "completed" or order_id % 2 == 0):
            for part in range(2 if order_id % 4 == 0 else 1):
                shipment_id += 1
                shipped = ordered + timedelta(days=2 + part)
                promised = shipped + timedelta(days=4)
                delivered = promised + timedelta(days=2 if order_id % 5 == 0 else -1)
                connection.execute("INSERT INTO shipments VALUES (?, ?, ?, ?, ?, ?)", (
                    shipment_id, order_id, shipped.isoformat(), promised.isoformat(),
                    delivered.isoformat() if status == "completed" else None,
                    ["Atlas", "Express", "Parcel"][order_id % 3]))

        if status == "completed" and order_id % 6 == 0:
            return_id += 1
            return_status = ["approved", "approved", "pending", "rejected"][order_id // 6 % 4]
            connection.execute("INSERT INTO returns VALUES (?, ?, ?, ?)", (
                return_id, order_id, (ordered + timedelta(days=15)).isoformat(), return_status))
            for sold_id, sold_qty, sold_amount in items[:1 + (order_id // 6) % 2]:
                return_item_id += 1
                returned_qty = max(1, sold_qty // 2)
                connection.execute("INSERT INTO return_items VALUES (?, ?, ?, ?, ?, ?)", (
                    return_item_id, return_id, order_id, sold_id, returned_qty,
                    sold_amount * returned_qty // sold_qty))
    connection.commit()
