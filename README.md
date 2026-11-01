
# ShelfSync

> A clean, responsive Mini Inventory & Billing Management System for a retail shop ("Shree Mart"). Built for the PentaForge Software Developer Internship assignment.

| | |
|---|---|
| **Live demo** | https://nidwpy.pythonanywhere.com |
| **Source code** | https://github.com/Nid-build01it/ShelfSync |

**Tech stack:** Python Flask, SQLite (plain SQL), Bootstrap 5, plain JavaScript.

---

## What it does

ShelfSync lets a shop counter manage products and customers, create bills with several items, and look back at past sales. When a bill is created, stock goes down automatically, and the app refuses to sell more than what is in stock.

### The seven assignment requirements

| # | Requirement | Where to find it |
|---|---|---|
| 1 | Dashboard with basic statistics | Dashboard: total products, customers, sales, low-stock items, recent sales |
| 2 | Product management (add, edit, delete, search) | Products |
| 3 | Customer management | Customers |
| 4 | Billing with multiple products and automatic totals | New Bill |
| 5 | Automatic inventory update after a sale | Billing logic in `billing.py` |
| 6 | Sales history with invoice details | Sales History and Invoice pages |
| 7 | Responsive user interface | Works on phone, tablet and desktop |

### Try it in 2 minutes (live demo)

1. Open **Products** and search for an item.
2. Open **New Bill**, add 2-3 items, and watch the total update.
3. Click **Generate Invoice** and check that the stock went down on **Products**.
4. Try to sell more than the available stock and see the "Only N left" message.
5. Open **Sales History** and view the invoice you just made.

> **About the live demo:** it runs on a free PythonAnywhere account, so it may be slow if many people use it at once. There is no login, so anyone with the link can add or change data. This is a demo, not a production system.

---

## Screenshots

*These screenshots were taken before the final blue colour theme was applied. The live app uses the blue theme.*

### Desktop (1440 px)

#### Dashboard
![ShelfSync Dashboard](screenshots/dashboard.png)

#### Products and search
![ShelfSync Products](screenshots/products.png)

#### New Bill with live totals
![ShelfSync New Bill](screenshots/new_bill.png)

#### Invoice details and print view
![ShelfSync Invoice](screenshots/invoice.png)

### Mobile (390 px)

#### New Bill on a phone, with a sticky total bar
<p align="center">
  <img src="screenshots/new_bill_phone.png" alt="ShelfSync Mobile Bill" width="390" />
</p>

---

## Features

- **Dashboard:** Total Products, Total Customers and Total Sales (with the number of invoices), a Recent Sales list, and a Low Stock list for items that are running out.
- **Product management:** search by name, add, edit and delete products, and set a low-stock alert level for each. Stock status shows as In stock, Low or Out of stock.
- **Safe deleting:** a product that appears on any invoice cannot be deleted. The app shows a friendly message and suggests setting its stock to 0 instead.
- **Customers:** add and view customers (name, phone, email) with email validation on the server.
- **Billing:** several items per bill, live totals in JavaScript, and a walk-in option so no customer has to be saved.
- **Safe billing:** stock is checked on the server and the whole sale is saved all-or-nothing (see below).
- **Tamper-proof prices:** the server ignores any price or total sent by the browser and reads prices from the database.
- **Invoices:** each invoice keeps the product name and price from the time of sale, so later price changes never alter old invoices. Invoices are print-ready.
- **Sales history:** all past invoices, newest first, with a View button.
- **Responsive design:** a sidebar on desktop that becomes a menu button on phones, tables that scroll inside their own box, and a sticky total bar on phones.
- **Custom design:** a blue colour theme (deep navy `#1A2B63`, royal blue `#28459D` and `#425DAE`, light blue `#B6C5F0`) with Lexend and Alegreya fonts and rounded cards.

---

## Tech stack

- **Backend:** Python 3, Flask 3.x
- **Database:** SQLite, using Python's built-in `sqlite3` with plain parameterised SQL (no ORM)
- **Templates:** Jinja2 with automatic HTML escaping
- **Frontend:** Bootstrap 5 (grid and utilities via CDN), Bootstrap Icons, custom CSS in `static/style.css`, and plain JavaScript in `static/bill.js`
- **Testing:** pytest
- **Hosting:** PythonAnywhere (free plan)

---

## Project structure

```
app.py            all pages (routes)
billing.py        the invoice-creation logic (stock check and all-or-nothing save)
db.py             database connection helpers
schema.sql        the 4 database tables
seed.py           creates the database and loads sample data
templates/        the HTML pages
static/           style.css, bill.js, logo
tests/            automated tests for billing and pages
screenshots/      images used in this README
DEPLOY.md         notes for hosting on PythonAnywhere
```

---

## Setup steps

### 1. Clone the repository
```bash
git clone https://github.com/Nid-build01it/ShelfSync.git
cd ShelfSync
```

### 2. Create and activate a virtual environment
```bash
# Linux / macOS
python3 -m venv venv
source venv/bin/activate

# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Install the packages
```bash
pip install -r requirements.txt
```

### 4. Create the database and load sample data
```bash
python seed.py
```

### 5. Run the app
```bash
python app.py
```
Open **http://127.0.0.1:5000** in your browser.

### 6. Run the tests
```bash
pytest
```

---

## How billing and stock updates work

1. **The server is the authority.** The browser calculates totals only to give instant feedback. When you click Generate Invoice, the server ignores every price and total sent by the browser and reads the real prices and stock from the database.
2. **Duplicate rows are merged.** If the same product is on two rows, `billing.py` adds the quantities together before checking stock. For example, 2 + 3 = 5 notebooks are checked against the stock, and the bill is refused with "Only 4 left of ..." if only 4 exist.
3. **All-or-nothing save.** The whole sale runs inside one database transaction (`BEGIN IMMEDIATE`). It creates the invoice, creates its items, reduces the stock and saves the total. If any check fails, everything is undone: nothing is saved, no stock changes, and the user sees a clear message with their input kept.
4. **Prices are copied onto the invoice.** Each invoice item stores the product name and price at the time of sale. If a product's price changes later, old invoices keep the original price.
5. **Money is exact.** All amounts are stored as whole paise (1 rupee = 100 paise), never as decimals that can drift. The Indian number format (for example 1,51,060.00) is applied only when displaying.
6. **Stock can never go negative.** The server checks it, and the database also rejects negative stock.

---

## Database design (4 tables)

```
customers 1 --- many invoices 1 --- many invoice_items many --- 1 products
```

| Table | Main columns |
|---|---|
| `products` | id, name, price_paise, stock_quantity, low_stock_threshold, created_at |
| `customers` | id, name, phone, email, created_at |
| `invoices` | id, customer_id (empty for a walk-in sale), created_at, total_paise |
| `invoice_items` | id, invoice_id, product_id, product_name, quantity, unit_price_paise, line_total_paise |

Foreign keys are switched on. A product used on an invoice cannot be deleted, and invoice items are removed together with their invoice.

---

## Assumptions

1. All prices are in Indian rupees, stored as integer paise.
2. A walk-in bill stores no customer, and the invoice shows "Walk-in customer".
3. Products with 0 stock cannot be added to a bill.
4. A product that has been sold cannot be deleted (set its stock to 0 instead).
5. Forms are protected with a simple CSRF token using Python's built-in `secrets` module.
6. No tax or discounts, because the assignment does not ask for them.

---

## Limitations and future improvements

- **Login:** the app has no user accounts. A real shop would add roles (admin and cashier).
- **Database:** SQLite suits a demo or a single counter. A busy shop would move to PostgreSQL.
- **PDF invoices:** invoices print from the browser, and direct PDF download could be added.
- **Tax and discounts:** GST and discounts are not included.
- **Returns:** refunds and returned items are not handled yet.
- **Search:** search covers products only, not sales history.

---

## AI usage disclosure

Planning was done with Claude (Anthropic) and implementation with Google Antigravity. I reviewed and tested the code and I can explain how it works.
