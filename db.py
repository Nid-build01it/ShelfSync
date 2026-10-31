"""Database connection and initialization helpers for ShelfSync."""

import os
import sqlite3
from flask import current_app, g

DATABASE_FILENAME = "shelf_sync.db"


def get_db_path():
    """Get the database path from app config, env, or default."""
    try:
        if current_app and "DATABASE" in current_app.config:
            return current_app.config["DATABASE"]
    except RuntimeError:
        pass
    return os.environ.get("SHELF_SYNC_DB", os.path.join(os.path.dirname(__file__), DATABASE_FILENAME))


def get_db(db_path=None):
    """Open a new database connection if there is none yet for the current app context."""
    if db_path is None:
        db_path = get_db_path()

    # If within a Flask request context, reuse connection on g
    try:
        if current_app:
            if "db" not in g:
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA foreign_keys = ON;")
                g.db = conn
            return g.db
    except RuntimeError:
        pass

    # Outside request context (e.g., seeding, tests, CLI)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def close_db(e=None):
    """Close the database connection at the end of the request."""
    db = g.pop("db", None) if "db" in g else None
    if db is not None:
        db.close()


def init_db(db_path=None):
    """Create all database tables using schema.sql."""
    if db_path is None:
        db_path = get_db_path()
    conn = get_db(db_path)
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    return conn


def format_inr(paise, show_decimals=True):
    """Format paise amount into Indian currency format with ₹ sign.

    Example: 15106000 paise -> ₹1,51,060.00
    """
    if paise is None:
        return "₹0.00" if show_decimals else "₹0"

    is_negative = paise < 0
    paise = abs(int(paise))

    rupees = paise // 100
    sub_paise = paise % 100

    rupees_str = str(rupees)
    if len(rupees_str) <= 3:
        formatted_rupees = rupees_str
    else:
        last3 = rupees_str[-3:]
        remaining = rupees_str[:-3]
        chunks = []
        while len(remaining) > 2:
            chunks.insert(0, remaining[-2:])
            remaining = remaining[:-2]
        if remaining:
            chunks.insert(0, remaining)
        formatted_rupees = ",".join(chunks) + "," + last3

    sign = "-" if is_negative else ""
    if show_decimals:
        return f"{sign}₹{formatted_rupees}.{sub_paise:02d}"
    return f"{sign}₹{formatted_rupees}"
