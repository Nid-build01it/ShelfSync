"""ShelfSync - Mini Inventory & Billing Management System for Shree Mart.

Built with Python Flask, SQLite3, Jinja, and plain JavaScript.
"""

import os
import re
import secrets
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    abort,
)
from db import get_db, close_db, format_inr
from billing import create_invoice, BillingError


def create_app(test_config=None):
    """Application factory for ShelfSync."""
    app = Flask(__name__)

    # Configuration
    secret_key = os.environ.get("SECRET_KEY", "shelf-sync-dev-secret-key-shree-mart")
    app.config["SECRET_KEY"] = secret_key
    app.config["DATABASE"] = os.environ.get(
        "SHELF_SYNC_DB",
        os.path.join(os.path.dirname(__file__), "shelf_sync.db"),
    )

    if test_config:
        app.config.update(test_config)

    # Register DB teardown
    app.teardown_appcontext(close_db)

    # Custom Jinja Filter for Indian Rupee Formatting
    @app.template_filter("inr")
    def inr_filter(paise):
        return format_inr(paise, show_decimals=True)

    # CSRF Protection via session tokens
    @app.before_request
    def check_csrf():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_hex(16)

        if request.method == "POST":
            submitted_token = request.form.get("csrf_token")
            session_token = session.get("csrf_token")
            if not submitted_token or submitted_token != session_token:
                abort(400, description="CSRF token validation failed.")

    @app.context_processor
    def inject_csrf_token():
        return dict(csrf_token=lambda: session.get("csrf_token", ""))

    # Helper: parse rupee decimal string to integer paise without float inaccuracy
    def parse_rupees_to_paise(val_str):
        if not val_str:
            raise ValueError("Price is required.")
        val_str = str(val_str).strip()
        # Must be valid non-negative number with at most 2 decimals
        if not re.match(r"^\d+(\.\d{1,2})?$", val_str):
            raise ValueError("Price must be a valid positive amount with up to 2 decimal places.")
        if "." in val_str:
            rupees_part, paise_part = val_str.split(".")
            paise_part = (paise_part + "00")[:2]
            return int(rupees_part) * 100 + int(paise_part)
        return int(val_str) * 100

    # 1. Dashboard Route
    @app.route("/")
    def dashboard():
        conn = get_db()
        cur = conn.cursor()

        # Stat 1: Total Products
        cur.execute("SELECT COUNT(*) AS total FROM products;")
        total_products = cur.fetchone()["total"]

        # Stat 2: Total Customers
        cur.execute("SELECT COUNT(*) AS total FROM customers;")
        total_customers = cur.fetchone()["total"]

        # Stat 3: Total Sales & Invoice Count
        cur.execute("SELECT COALESCE(SUM(total_paise), 0) AS total_sales, COUNT(*) AS total_invoices FROM invoices;")
        sales_row = cur.fetchone()
        total_sales_paise = sales_row["total_sales"]
        total_invoices = sales_row["total_invoices"]

        # Recent Sales (Last 5)
        cur.execute(
            """
            SELECT i.id, i.total_paise, i.created_at, c.name AS customer_name
            FROM invoices i
            LEFT JOIN customers c ON i.customer_id = c.id
            ORDER BY i.created_at DESC, i.id DESC
            LIMIT 5;
            """
        )
        recent_sales = cur.fetchall()

        # Low Stock Count (stock <= low_stock_threshold, includes stock == 0)
        cur.execute(
            """
            SELECT COUNT(*) AS total
            FROM products
            WHERE stock_quantity <= low_stock_threshold;
            """
        )
        low_stock_count = cur.fetchone()["total"]

        # Low Stock Top 5 Items
        cur.execute(
            """
            SELECT id, name, stock_quantity, low_stock_threshold
            FROM products
            WHERE stock_quantity <= low_stock_threshold
            ORDER BY stock_quantity ASC, name ASC
            LIMIT 5;
            """
        )
        low_stock_items = cur.fetchall()

        return render_template(
            "dashboard.html",
            active_page="dashboard",
            total_products=total_products,
            total_customers=total_customers,
            total_sales_paise=total_sales_paise,
            total_invoices=total_invoices,
            recent_sales=recent_sales,
            low_stock_count=low_stock_count,
            low_stock_items=low_stock_items,
        )

    # 2. Products List and Search
    @app.route("/products")
    def products():
        conn = get_db()
        cur = conn.cursor()
        query = request.args.get("q", "").strip()

        if query:
            cur.execute(
                """
                SELECT * FROM products
                WHERE name LIKE ?
                ORDER BY name ASC;
                """,
                (f"%{query}%",),
            )
        else:
            cur.execute("SELECT * FROM products ORDER BY name ASC;")

        products_list = cur.fetchall()

        return render_template(
            "products.html",
            active_page="products",
            products=products_list,
            query=query,
        )

    # 3. Add Product
    @app.route("/products/new", methods=["GET", "POST"])
    def new_product():
        conn = get_db()
        errors = {}
        form_data = {}

        if request.method == "POST":
            name = request.form.get("name", "").strip()
            price_raw = request.form.get("price", "").strip()
            stock_raw = request.form.get("stock_quantity", "").strip()
            threshold_raw = request.form.get("low_stock_threshold", "5").strip()

            form_data = {
                "name": name,
                "price": price_raw,
                "stock_quantity": stock_raw,
                "low_stock_threshold": threshold_raw,
            }

            # Validation
            if not name:
                errors["name"] = "Product name is required."
            elif len(name) > 100:
                errors["name"] = "Product name must be 100 characters or fewer."

            price_paise = None
            try:
                price_paise = parse_rupees_to_paise(price_raw)
            except ValueError as e:
                errors["price"] = str(e)

            stock_quantity = None
            try:
                stock_quantity = int(stock_raw)
                if stock_quantity < 0:
                    raise ValueError
            except (ValueError, TypeError):
                errors["stock_quantity"] = "Stock quantity must be a non-negative whole number."

            low_stock_threshold = 5
            try:
                if threshold_raw:
                    low_stock_threshold = int(threshold_raw)
                    if low_stock_threshold < 0:
                        raise ValueError
            except (ValueError, TypeError):
                errors["low_stock_threshold"] = "Alert level must be a non-negative whole number."

            if not errors:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO products (name, price_paise, stock_quantity, low_stock_threshold)
                    VALUES (?, ?, ?, ?);
                    """,
                    (name, price_paise, stock_quantity, low_stock_threshold),
                )
                conn.commit()
                flash("Product saved", "success")
                return redirect(url_for("products"))

        return render_template(
            "product_form.html",
            active_page="products",
            is_edit=False,
            action_url=url_for("new_product"),
            form_data=form_data,
            errors=errors,
        )

    # 4. Edit Product
    @app.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
    def edit_product(product_id):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM products WHERE id = ?;", (product_id,))
        product = cur.fetchone()

        if not product:
            abort(404)

        errors = {}
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            price_raw = request.form.get("price", "").strip()
            stock_raw = request.form.get("stock_quantity", "").strip()
            threshold_raw = request.form.get("low_stock_threshold", "5").strip()

            form_data = {
                "name": name,
                "price": price_raw,
                "stock_quantity": stock_raw,
                "low_stock_threshold": threshold_raw,
            }

            # Validation
            if not name:
                errors["name"] = "Product name is required."
            elif len(name) > 100:
                errors["name"] = "Product name must be 100 characters or fewer."

            price_paise = None
            try:
                price_paise = parse_rupees_to_paise(price_raw)
            except ValueError as e:
                errors["price"] = str(e)

            stock_quantity = None
            try:
                stock_quantity = int(stock_raw)
                if stock_quantity < 0:
                    raise ValueError
            except (ValueError, TypeError):
                errors["stock_quantity"] = "Stock quantity must be a non-negative whole number."

            low_stock_threshold = 5
            try:
                if threshold_raw:
                    low_stock_threshold = int(threshold_raw)
                    if low_stock_threshold < 0:
                        raise ValueError
            except (ValueError, TypeError):
                errors["low_stock_threshold"] = "Alert level must be a non-negative whole number."

            if not errors:
                cur.execute(
                    """
                    UPDATE products
                    SET name = ?, price_paise = ?, stock_quantity = ?, low_stock_threshold = ?
                    WHERE id = ?;
                    """,
                    (name, price_paise, stock_quantity, low_stock_threshold, product_id),
                )
                conn.commit()
                flash("Product saved", "success")
                return redirect(url_for("products"))
        else:
            # Prefill from existing DB product
            rupees_val = f"{product['price_paise'] / 100:.2f}"
            form_data = {
                "name": product["name"],
                "price": rupees_val,
                "stock_quantity": product["stock_quantity"],
                "low_stock_threshold": product["low_stock_threshold"],
            }

        return render_template(
            "product_form.html",
            active_page="products",
            is_edit=True,
            action_url=url_for("edit_product", product_id=product_id),
            form_data=form_data,
            errors=errors,
        )

    # 5. Delete Product
    @app.route("/products/<int:product_id>/delete", methods=["POST"])
    def delete_product(product_id):
        conn = get_db()
        cur = conn.cursor()

        # Check if product is referenced in any invoice
        cur.execute(
            "SELECT COUNT(*) AS invoice_count FROM invoice_items WHERE product_id = ?;",
            (product_id,),
        )
        count = cur.fetchone()["invoice_count"]

        if count > 0:
            flash(f"Cannot delete, used in {count} invoices. Set its stock to 0 instead.", "error")
            return redirect(url_for("products"))

        cur.execute("DELETE FROM products WHERE id = ?;", (product_id,))
        conn.commit()
        flash("Product deleted successfully", "success")
        return redirect(url_for("products"))

    # 6. Customers Page
    @app.route("/customers", methods=["GET", "POST"])
    def customers():
        conn = get_db()
        cur = conn.cursor()
        errors = {}
        form_data = {}

        if request.method == "POST":
            name = request.form.get("name", "").strip()
            phone = request.form.get("phone", "").strip()
            email = request.form.get("email", "").strip()

            form_data = {"name": name, "phone": phone, "email": email}

            if not name:
                errors["name"] = "Customer name is required."

            if email:
                email_regex = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
                if not re.match(email_regex, email):
                    errors["email"] = "Please enter a valid email address."

            if not errors:
                cur.execute(
                    """
                    INSERT INTO customers (name, phone, email)
                    VALUES (?, ?, ?);
                    """,
                    (name, phone or None, email or None),
                )
                conn.commit()
                flash("Customer added successfully", "success")
                return redirect(url_for("customers"))

        cur.execute("SELECT * FROM customers ORDER BY name ASC;")
        customers_list = cur.fetchall()

        return render_template(
            "customers.html",
            active_page="customers",
            customers=customers_list,
            form_data=form_data,
            errors=errors,
        )

    # 7. New Bill
    @app.route("/bill/new", methods=["GET", "POST"])
    def new_bill():
        conn = get_db()
        cur = conn.cursor()

        # Fetch catalog and customers
        cur.execute("SELECT * FROM products ORDER BY name ASC;")
        products_list = cur.fetchall()

        cur.execute("SELECT * FROM customers ORDER BY name ASC;")
        customers_list = cur.fetchall()

        # Recent bills (last 3 invoices)
        cur.execute(
            """
            SELECT id, total_paise, created_at
            FROM invoices
            ORDER BY created_at DESC, id DESC
            LIMIT 3;
            """
        )
        recent_bills = cur.fetchall()

        if request.method == "POST":
            walkin = request.form.get("walkin_customer")
            customer_id = None if walkin else request.form.get("customer_id")

            # Collect dynamic item rows
            product_ids = request.form.getlist("product_id[]")
            quantities = request.form.getlist("quantity[]")

            raw_items = []
            form_items = []
            for p_id, q_val in zip(product_ids, quantities):
                # Save raw values so form stays filled if validation fails
                try:
                    parsed_pid = int(p_id) if p_id else None
                except ValueError:
                    parsed_pid = None
                raw_items.append({"product_id": p_id, "quantity": q_val})
                form_items.append({"product_id": parsed_pid, "quantity": q_val})

            try:
                invoice_id = create_invoice(conn, customer_id, raw_items)
                flash("Invoice generated successfully", "success")
                return redirect(url_for("invoice_view", invoice_id=invoice_id))
            except BillingError as err:
                flash(str(err), "error")
                return render_template(
                    "new_bill.html",
                    active_page="new_bill",
                    products=products_list,
                    customers=customers_list,
                    recent_bills=recent_bills,
                    is_walkin=bool(walkin),
                    selected_customer_id=int(customer_id) if (customer_id and customer_id.isdigit()) else None,
                    form_items=form_items if form_items else [{"product_id": None, "quantity": 1}],
                )

        # GET: Start with one empty row and walkin checked
        return render_template(
            "new_bill.html",
            active_page="new_bill",
            products=products_list,
            customers=customers_list,
            recent_bills=recent_bills,
            is_walkin=True,
            selected_customer_id=None,
            form_items=[{"product_id": None, "quantity": 1}],
        )

    # 8. Invoice View
    @app.route("/invoices/<int:invoice_id>")
    def invoice_view(invoice_id):
        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT i.*, c.name AS customer_name, c.phone AS customer_phone, c.email AS customer_email
            FROM invoices i
            LEFT JOIN customers c ON i.customer_id = c.id
            WHERE i.id = ?;
            """,
            (invoice_id,),
        )
        invoice = cur.fetchone()

        if not invoice:
            abort(404)

        cur.execute(
            """
            SELECT * FROM invoice_items
            WHERE invoice_id = ?
            ORDER BY id ASC;
            """,
            (invoice_id,),
        )
        items = cur.fetchall()

        total_units = sum(item["quantity"] for item in items)
        customer = None
        if invoice["customer_id"]:
            customer = {
                "name": invoice["customer_name"],
                "phone": invoice["customer_phone"],
                "email": invoice["customer_email"],
            }

        return render_template(
            "invoice.html",
            active_page="sales",
            invoice=invoice,
            customer=customer,
            items=items,
            total_units=total_units,
        )

    # 9. Sales History
    @app.route("/sales")
    def sales_history():
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT i.id, i.total_paise, i.created_at, c.name AS customer_name
            FROM invoices i
            LEFT JOIN customers c ON i.customer_id = c.id
            ORDER BY i.created_at DESC, i.id DESC;
            """
        )
        sales = cur.fetchall()

        return render_template(
            "sales.html",
            active_page="sales",
            sales=sales,
        )

    # Error Handlers
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template("404.html", active_page=""), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template("500.html", active_page=""), 500

    return app


# WSGI application instance for gunicorn / PythonAnywhere
app = create_app()

if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "0") in ("1", "true", "True")
    app.run(host="0.0.0.0", port=5000, debug=debug_mode)
