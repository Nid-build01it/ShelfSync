"""Billing management logic for ShelfSync.

The server is the single source of truth for pricing, stock, and invoice calculations.
"""

import sqlite3


class BillingError(Exception):
    """Custom exception raised when invoice generation fails validation."""
    pass


def parse_and_validate_items(items_raw):
    """Parse raw form inputs and validate item structure.

    Rules:
    - At least one item is required.
    - Quantity must be an integer >= 1.
    - Duplicate product entries are merged by summing quantities BEFORE checking stock.
    """
    if not items_raw:
        raise BillingError("At least one item is required to create a bill.")

    merged_quantities = {}

    for item in items_raw:
        # Each item can be a dict or tuple with product_id and quantity
        p_id = item.get("product_id") if isinstance(item, dict) else item[0]
        qty = item.get("quantity") if isinstance(item, dict) else item[1]

        # Ignore empty row placeholders
        if (p_id is None or str(p_id).strip() == "") and (qty is None or str(qty).strip() == ""):
            continue

        if p_id is None or str(p_id).strip() == "":
            raise BillingError("Please select a product for each line item.")

        try:
            product_id = int(p_id)
            if product_id <= 0:
                raise ValueError
        except (ValueError, TypeError):
            raise BillingError("Invalid product selected.")

        try:
            quantity = int(qty)
            if quantity < 1:
                raise ValueError
        except (ValueError, TypeError):
            raise BillingError("Quantity must be a whole number of 1 or more.")

        # Merge duplicate product rows before checking stock
        merged_quantities[product_id] = merged_quantities.get(product_id, 0) + quantity

    if not merged_quantities:
        raise BillingError("At least one item is required to create a bill.")

    return merged_quantities


def create_invoice(conn, customer_id, items_raw):
    """Create a new invoice atomically inside a single BEGIN IMMEDIATE transaction.

    Steps:
    1. Validate customer (if provided; walk-in customer leaves customer_id as None).
    2. Parse and merge duplicate item rows.
    3. Start an IMMEDIATE database transaction so concurrent sales cannot oversell.
    4. Fetch fresh product details and verify stock from DB (ignoring browser prices).
    5. Deduct product stock.
    6. Insert the invoice and its line items (copying product name and price at sale time).
    7. Commit transaction and return invoice ID.
    8. Roll back on any error without changing anything.
    """
    # Normalize customer ID (walk-in customers have None)
    clean_customer_id = None
    if customer_id and str(customer_id).strip() and str(customer_id).strip().lower() != "walk-in":
        try:
            clean_customer_id = int(customer_id)
        except (ValueError, TypeError):
            raise BillingError("Invalid customer selected.")

    # Step 1: Validate and merge items
    merged_items = parse_and_validate_items(items_raw)

    # We manage transaction explicitly with BEGIN IMMEDIATE
    # Save original isolation level to restore after operation
    original_isolation_level = conn.isolation_level
    conn.isolation_level = None  # Enable manual transaction control in sqlite3
    cur = conn.cursor()

    try:
        cur.execute("BEGIN IMMEDIATE;")

        # Verify customer exists if specified
        if clean_customer_id is not None:
            cur.execute("SELECT id, name FROM customers WHERE id = ?", (clean_customer_id,))
            customer_row = cur.fetchone()
            if not customer_row:
                raise BillingError("Selected customer does not exist.")

        # Step 2: Validate stock and prepare line items
        items_to_insert = []
        total_paise = 0

        for product_id, quantity in merged_items.items():
            # Server is the single authority: fetch current price and stock from database
            cur.execute(
                "SELECT id, name, price_paise, stock_quantity FROM products WHERE id = ?",
                (product_id,),
            )
            product = cur.fetchone()

            if not product:
                raise BillingError(f"Product ID {product_id} was not found.")

            name = product["name"]
            price_paise = product["price_paise"]
            available_stock = product["stock_quantity"]

            # Stock check
            if available_stock <= 0:
                raise BillingError(f"{name} is out of stock.")
            if quantity > available_stock:
                raise BillingError(f"Only {available_stock} left of {name}.")

            line_total_paise = quantity * price_paise
            total_paise += line_total_paise

            items_to_insert.append({
                "product_id": product_id,
                "product_name": name,
                "quantity": quantity,
                "unit_price_paise": price_paise,
                "line_total_paise": line_total_paise,
            })

            # Reduce product stock
            cur.execute(
                "UPDATE products SET stock_quantity = stock_quantity - ? WHERE id = ?",
                (quantity, product_id),
            )

        # Step 3: Insert invoice
        cur.execute(
            "INSERT INTO invoices (customer_id, total_paise) VALUES (?, ?)",
            (clean_customer_id, total_paise),
        )
        invoice_id = cur.lastrowid

        # Step 4: Insert invoice line items
        # Product name and unit price are snapshotted so future price edits never affect this bill
        for item in items_to_insert:
            cur.execute(
                """
                INSERT INTO invoice_items
                (invoice_id, product_id, product_name, quantity, unit_price_paise, line_total_paise)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    invoice_id,
                    item["product_id"],
                    item["product_name"],
                    item["quantity"],
                    item["unit_price_paise"],
                    item["line_total_paise"],
                ),
            )

        cur.execute("COMMIT;")
        return invoice_id

    except Exception:
        try:
            cur.execute("ROLLBACK;")
        except Exception:
            pass
        raise
    finally:
        conn.isolation_level = original_isolation_level
