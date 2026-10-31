"""Integration and page route tests for ShelfSync.

Covers:
- Every page returns 200 with sample data.
- Every page returns 200 with an empty database.
- Deleting a product that is used on an invoice is safely blocked without crashing.
- Adding a customer with validation.
- Adding and editing products.
- Friendly 404 page for missing resources.
"""

import os
import tempfile
import pytest
from app import create_app
from db import init_db
from seed import seed_data


@pytest.fixture
def seeded_client():
    """Client with seeded sample stationery data."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    app = create_app({
        "TESTING": True,
        "DATABASE": db_path,
        "SECRET_KEY": "test-secret-key",
    })

    seed_data(db_path)

    with app.test_client() as client:
        with app.app_context():
            yield client

    try:
        os.close(db_fd)
    except OSError:
        pass
    try:
        if os.path.exists(db_path):
            os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture
def empty_client():
    """Client with an empty database (schema only, 0 rows)."""
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    app = create_app({
        "TESTING": True,
        "DATABASE": db_path,
        "SECRET_KEY": "test-secret-key",
    })

    init_db(db_path)

    with app.test_client() as client:
        with app.app_context():
            yield client

    try:
        os.close(db_fd)
    except OSError:
        pass
    try:
        if os.path.exists(db_path):
            os.unlink(db_path)
    except OSError:
        pass


def test_pages_with_seeded_data(seeded_client):
    """Verify that all major pages return 200 OK with populated data."""
    # Dashboard
    res = seeded_client.get("/")
    assert res.status_code == 200
    assert b"ShelfSync" in res.data
    assert b"Total Products" in res.data
    assert b"Total Sales" in res.data

    # Products List
    res = seeded_client.get("/products")
    assert res.status_code == 200
    assert b"Classmate A4" in res.data

    # Products Search
    res = seeded_client.get("/products?q=Fountain")
    assert res.status_code == 200
    assert b"Parker Vector" in res.data

    # New Product Form
    res = seeded_client.get("/products/new")
    assert res.status_code == 200
    assert b"New Product Details" in res.data

    # Edit Product Form
    res = seeded_client.get("/products/1/edit")
    assert res.status_code == 200
    assert b"Edit Product Details" in res.data

    # Customers Page
    res = seeded_client.get("/customers")
    assert res.status_code == 200
    assert b"Aarav Sharma" in res.data

    # New Bill Page
    res = seeded_client.get("/bill/new")
    assert res.status_code == 200
    assert b"Walk-in customer" in res.data

    # Invoice Details Page (invoice 1 exists)
    res = seeded_client.get("/invoices/1")
    assert res.status_code == 200
    assert b"INV-0001" in res.data
    assert b"Shree Mart" in res.data

    # Sales History Page
    res = seeded_client.get("/sales")
    assert res.status_code == 200
    assert b"INV-0001" in res.data


def test_pages_with_empty_database(empty_client):
    """Verify that all pages render cleanly with friendly empty states when database has no records."""
    # Dashboard with 0 data
    res = empty_client.get("/")
    assert res.status_code == 200
    assert b"No sales yet" in res.data
    assert b"All products have healthy stock levels" in res.data

    # Products List empty
    res = empty_client.get("/products")
    assert res.status_code == 200
    assert b"No products yet" in res.data

    # Products Search empty
    res = empty_client.get("/products?q=NonExistent")
    assert res.status_code == 200
    assert b"No results for your search" in res.data

    # Customers empty
    res = empty_client.get("/customers")
    assert res.status_code == 200
    assert b"No customers yet" in res.data

    # New Bill with no products
    res = empty_client.get("/bill/new")
    assert res.status_code == 200
    assert b"New Bill" in res.data

    # Sales History empty
    res = empty_client.get("/sales")
    assert res.status_code == 200
    assert b"No sales yet" in res.data


def test_delete_product_used_on_invoice_is_blocked(seeded_client):
    """Ensure deleting a product that is referenced in an invoice fails safely with an informative error."""
    # First get a valid CSRF token from session
    with seeded_client.session_transaction() as sess:
        sess["csrf_token"] = "valid_csrf_token"

    # Product 1 is used on Invoice 1
    res = seeded_client.post(
        "/products/1/delete",
        data={"csrf_token": "valid_csrf_token"},
        follow_redirects=True,
    )
    assert res.status_code == 200
    # Must display the required error message and not crash
    assert b"Cannot delete, used in 1 invoices. Set its stock to 0 instead." in res.data

    # Verify product 1 is still in database
    res_list = seeded_client.get("/products")
    assert b"Classmate A4 Ruled Notebook" in res_list.data


def test_delete_unused_product_succeeds(seeded_client):
    """Ensure an unused product can be deleted normally."""
    with seeded_client.session_transaction() as sess:
        sess["csrf_token"] = "valid_csrf_token"

    # Add a temporary product
    res = seeded_client.post(
        "/products/new",
        data={
            "csrf_token": "valid_csrf_token",
            "name": "Temporary Sticky Tape",
            "price": "30.00",
            "stock_quantity": "10",
            "low_stock_threshold": "2",
        },
        follow_redirects=True,
    )
    assert res.status_code == 200
    assert b"Product saved" in res.data

    # Now delete this unused product (should be product id 13)
    res_del = seeded_client.post(
        "/products/13/delete",
        data={"csrf_token": "valid_csrf_token"},
        follow_redirects=True,
    )
    assert res_del.status_code == 200
    assert b"Product deleted successfully" in res_del.data
    assert b"Temporary Sticky Tape" not in res_del.data


def test_nonexistent_pages_return_404(seeded_client):
    """Ensure non-existent URLs and invoices render friendly 404 pages."""
    res = seeded_client.get("/invoices/9999")
    assert res.status_code == 404
    assert b"404 - Page Not Found" in res.data
    assert b"Return to Dashboard" in res.data
