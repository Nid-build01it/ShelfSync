"""Unit tests for billing logic in ShelfSync.

Covers:
- Overselling is refused with a clear message.
- Duplicate rows are merged before checking stock.
- Stock is reduced accurately upon successful bill.
- A failed bill saves nothing and leaves all stock unchanged (atomicity).
- Prices come from the database and snapshot onto invoice items.
- Walk-in bills work without a customer.
"""

import os
import sqlite3
import pytest
from billing import create_invoice, BillingError


@pytest.fixture
def db_conn():
    """Create an in-memory test database with fresh schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")

    # Read and apply schema
    schema_path = os.path.join(os.path.dirname(__file__), "..", "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())

    # Insert baseline products
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO products (id, name, price_paise, stock_quantity, low_stock_threshold)
        VALUES (1, 'A4 Ruled Notebook', 6500, 5, 5),
               (2, 'Blue Ballpoint Pen', 1000, 20, 5),
               (3, 'Geometry Box', 14000, 0, 5);
        """
    )
    # Insert baseline customer
    cur.execute(
        """
        INSERT INTO customers (id, name, phone, email)
        VALUES (1, 'Rohan Sharma', '9876543210', 'rohan@example.com');
        """
    )
    conn.commit()
    yield conn
    conn.close()


def test_overselling_is_refused(db_conn):
    """Ensure attempting to buy more than available stock fails and leaves stock unchanged."""
    # Product 1 has stock 5; requesting 6 must fail
    with pytest.raises(BillingError, match="Only 5 left of A4 Ruled Notebook"):
        create_invoice(db_conn, customer_id=1, items_raw=[{"product_id": 1, "quantity": 6}])

    # Verify stock remained untouched
    cur = db_conn.cursor()
    cur.execute("SELECT stock_quantity FROM products WHERE id = 1")
    assert cur.fetchone()["stock_quantity"] == 5

    # Verify no invoice was recorded
    cur.execute("SELECT COUNT(*) as cnt FROM invoices")
    assert cur.fetchone()["cnt"] == 0


def test_duplicate_rows_are_merged_and_checked(db_conn):
    """Ensure identical products on separate rows are combined before checking stock limits."""
    # Product 1 has stock 5; two rows of 3 items = 6 items total, which exceeds 5
    with pytest.raises(BillingError, match="Only 5 left of A4 Ruled Notebook"):
        create_invoice(
            db_conn,
            customer_id=1,
            items_raw=[
                {"product_id": 1, "quantity": 3},
                {"product_id": 1, "quantity": 3},
            ],
        )

    # When total quantity is within stock (e.g. 2 + 3 = 5), merging succeeds
    invoice_id = create_invoice(
        db_conn,
        customer_id=1,
        items_raw=[
            {"product_id": 1, "quantity": 2},
            {"product_id": 1, "quantity": 3},
        ],
    )
    assert invoice_id is not None

    # Stock should now be exactly 0
    cur = db_conn.cursor()
    cur.execute("SELECT stock_quantity FROM products WHERE id = 1")
    assert cur.fetchone()["stock_quantity"] == 0


def test_stock_reduced_correctly(db_conn):
    """Ensure stock is reduced accurately upon a successful invoice generation."""
    # Product 2 starts at 20 stock, buy 7
    invoice_id = create_invoice(
        db_conn,
        customer_id=1,
        items_raw=[{"product_id": 2, "quantity": 7}],
    )
    assert invoice_id is not None

    cur = db_conn.cursor()
    cur.execute("SELECT stock_quantity FROM products WHERE id = 2")
    assert cur.fetchone()["stock_quantity"] == 13

    # Check invoice total (7 * 1000 = 7000 paise)
    cur.execute("SELECT total_paise FROM invoices WHERE id = ?", (invoice_id,))
    assert cur.fetchone()["total_paise"] == 7000


def test_failed_bill_saves_nothing_and_leaves_stock_unchanged(db_conn):
    """Ensure transaction atomicity: failure on one item rolls back all changes."""
    # Buy 2 of Product 2 (valid) and 10 of Product 1 (invalid, stock is only 5)
    with pytest.raises(BillingError, match="Only 5 left of A4 Ruled Notebook"):
        create_invoice(
            db_conn,
            customer_id=1,
            items_raw=[
                {"product_id": 2, "quantity": 2},
                {"product_id": 1, "quantity": 10},
            ],
        )

    cur = db_conn.cursor()
    # Product 2 stock must still be 20
    cur.execute("SELECT stock_quantity FROM products WHERE id = 2")
    assert cur.fetchone()["stock_quantity"] == 20

    # No invoice or invoice items should exist
    cur.execute("SELECT COUNT(*) as cnt FROM invoices")
    assert cur.fetchone()["cnt"] == 0
    cur.execute("SELECT COUNT(*) as cnt FROM invoice_items")
    assert cur.fetchone()["cnt"] == 0


def test_prices_come_from_database_not_browser(db_conn):
    """Ensure any client-supplied prices are completely ignored and DB prices are used."""
    # Browser attempts to pass spoofed unit_price of 10 paise instead of real 6500 paise
    invoice_id = create_invoice(
        db_conn,
        customer_id=1,
        items_raw=[{"product_id": 1, "quantity": 2, "spoofed_price": 10}],
    )

    cur = db_conn.cursor()
    cur.execute("SELECT total_paise FROM invoices WHERE id = ?", (invoice_id,))
    # Total must be 2 * 6500 = 13000 paise
    assert cur.fetchone()["total_paise"] == 13000

    # If the product's price in DB is later changed, the historical invoice item stays unchanged
    cur.execute("UPDATE products SET price_paise = 9999 WHERE id = 1")
    db_conn.commit()

    cur.execute("SELECT unit_price_paise, line_total_paise FROM invoice_items WHERE invoice_id = ?", (invoice_id,))
    item = cur.fetchone()
    assert item["unit_price_paise"] == 6500
    assert item["line_total_paise"] == 13000


def test_walkin_bill_works(db_conn):
    """Ensure bills without a registered customer (walk-in) work and set customer_id to NULL."""
    invoice_id = create_invoice(
        db_conn,
        customer_id=None,
        items_raw=[{"product_id": 2, "quantity": 1}],
    )
    assert invoice_id is not None

    cur = db_conn.cursor()
    cur.execute("SELECT customer_id, total_paise FROM invoices WHERE id = ?", (invoice_id,))
    row = cur.fetchone()
    assert row["customer_id"] is None
    assert row["total_paise"] == 1000


def test_out_of_stock_product_refused(db_conn):
    """Ensure out-of-stock items (stock = 0) cannot be purchased."""
    with pytest.raises(BillingError, match="Geometry Box is out of stock"):
        create_invoice(
            db_conn,
            customer_id=None,
            items_raw=[{"product_id": 3, "quantity": 1}],
        )


def test_invalid_quantities_and_empty_items(db_conn):
    """Ensure invalid quantities or empty item lists raise clear errors."""
    with pytest.raises(BillingError, match="At least one item is required"):
        create_invoice(db_conn, customer_id=None, items_raw=[])

    with pytest.raises(BillingError, match="Quantity must be a whole number of 1 or more"):
        create_invoice(db_conn, customer_id=None, items_raw=[{"product_id": 1, "quantity": 0}])

    with pytest.raises(BillingError, match="Quantity must be a whole number of 1 or more"):
        create_invoice(db_conn, customer_id=None, items_raw=[{"product_id": 1, "quantity": -5}])
