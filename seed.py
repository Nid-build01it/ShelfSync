"""Seed sample data for ShelfSync (Shree Mart Stationery Shop).

Loads:
- 12 realistic stationery products (with several low stock and one out of stock)
- 4 customers
- 3 invoices (with items and totals matching database records, consistent stock)
"""

import sys
from db import get_db, init_db


def seed_data(db_path=None):
    """Reset schema and load sample records."""
    # Ensure fresh schema
    conn = init_db(db_path)
    cur = conn.cursor()

    # Clear any existing rows
    cur.execute("DELETE FROM invoice_items;")
    cur.execute("DELETE FROM invoices;")
    cur.execute("DELETE FROM customers;")
    cur.execute("DELETE FROM products;")

    # 1. Seed Products (12 items)
    products = [
        # (id, name, price_paise, stock_quantity, low_stock_threshold)
        (1, "Classmate A4 Ruled Notebook (160 pgs)", 6500, 42, 10),
        (2, "Reynolds 045 Fine Carbure Ball Pen (Blue)", 1000, 150, 25),
        (3, "Parker Vector Standard Fountain Pen", 35000, 8, 5),
        (4, "Camlin Kokuyo Triangular Pencils (Pack of 10)", 5000, 28, 10),
        (5, "Faber-Castell Connector Pen Set (15 Shades)", 12000, 14, 5),
        (6, "Camlin Scholar Mathematical Geometry Box", 14000, 0, 5),  # Out of stock
        (7, "Kangaro Stapler No. 10 with Pins", 8500, 4, 5),         # Low stock (4 <= 5)
        (8, "Fevicol MR Squeezy Bottle (100g)", 4500, 3, 5),         # Low stock (3 <= 5)
        (9, "Post-it Canary Yellow Sticky Notes (3x3 in)", 5500, 2, 5), # Low stock (2 <= 5)
        (10, "Apsara Non-Dust Jumbo Eraser (Pack of 5)", 2500, 35, 10),
        (11, "Doms Pastel Highlighters (Pack of 5)", 9000, 5, 5),     # Low stock (5 <= 5)
        (12, "Solo Executive Display Folder (20 Pockets)", 16000, 12, 5),
    ]

    cur.executemany(
        """
        INSERT INTO products (id, name, price_paise, stock_quantity, low_stock_threshold)
        VALUES (?, ?, ?, ?, ?)
        """,
        products,
    )

    # 2. Seed Customers (4 customers)
    customers = [
        (1, "Aarav Sharma", "+91 98765 43210", "aarav.sharma@example.com"),
        (2, "Priya Patel", "+91 98234 56789", "priya.patel@example.com"),
        (3, "Rohan Gupta", "+91 91234 56780", None),
        (4, "Ananya Iyer", None, "ananya.iyer@example.com"),
    ]

    cur.executemany(
        """
        INSERT INTO customers (id, name, phone, email)
        VALUES (?, ?, ?, ?)
        """,
        customers,
    )

    # 3. Seed Invoices (3 invoices)
    invoices = [
        # (id, customer_id, created_at, total_paise)
        (1, 1, "2026-10-28 10:30:00", 24500),  # ₹245.00 - Aarav Sharma
        (2, 2, "2026-10-29 14:15:00", 69500),  # ₹695.00 - Priya Patel
        (3, None, "2026-10-30 17:45:00", 45000), # ₹450.00 - Walk-in customer
    ]

    cur.executemany(
        """
        INSERT INTO invoices (id, customer_id, created_at, total_paise)
        VALUES (?, ?, ?, ?)
        """,
        invoices,
    )

    # 4. Seed Invoice Items
    # Note: unit_price and product_name copied onto items so old invoices never change
    items = [
        # Invoice 1 items
        (1, 1, "Classmate A4 Ruled Notebook (160 pgs)", 3, 6500, 19500),
        (1, 2, "Reynolds 045 Fine Carbure Ball Pen (Blue)", 5, 1000, 5000),

        # Invoice 2 items
        (2, 3, "Parker Vector Standard Fountain Pen", 1, 35000, 35000),
        (2, 11, "Doms Pastel Highlighters (Pack of 5)", 2, 9000, 18000),
        (2, 9, "Post-it Canary Yellow Sticky Notes (3x3 in)", 3, 5500, 16500),

        # Invoice 3 items (Walk-in)
        (3, 5, "Faber-Castell Connector Pen Set (15 Shades)", 2, 12000, 24000),
        (3, 12, "Solo Executive Display Folder (20 Pockets)", 1, 16000, 16000),
        (3, 10, "Apsara Non-Dust Jumbo Eraser (Pack of 5)", 2, 2500, 5000),
    ]

    cur.executemany(
        """
        INSERT INTO invoice_items (invoice_id, product_id, product_name, quantity, unit_price_paise, line_total_paise)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        items,
    )

    conn.commit()
    conn.close()
    print("Database initialized and sample data seeded successfully for Shree Mart!")


if __name__ == "__main__":
    db_file = sys.argv[1] if len(sys.argv) > 1 else None
    seed_data(db_file)
