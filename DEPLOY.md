# Deploying ShelfSync to PythonAnywhere (Free Plan)

This step-by-step guide explains how to host ShelfSync on PythonAnywhere using their free tier.

---

## 1. Sign Up and Open Bash Console
1. Create a free account at [pythonanywhere.com](https://www.pythonanywhere.com).
2. Go to the **Consoles** tab and click **Bash** to open an online shell.

---

## 2. Clone Repository and Set Up Virtual Environment

In the Bash console, run:

```bash
# Clone the repository
git clone https://github.com/Nid-build01it/ShelfSync.git
cd ShelfSync

# Create a virtual environment using Python 3.10+
python3 -m venv venv
source venv/bin/activate

# Install required packages
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 3. Initialize Database and Load Sample Data

Run the seed script inside the virtual environment:

```bash
python seed.py
```

This creates the SQLite database file at `/home/<your-username>/ShelfSync/shelf_sync.db` and populates the sample stationery products, customers, and initial invoices for Shree Mart.

---

## 4. Configure Web App in PythonAnywhere Dashboard

1. Navigate to the **Web** tab in the PythonAnywhere dashboard.
2. Click **Add a new web app**.
3. Select **Manual configuration** and choose **Python 3.10** (or your preferred Python 3 version).
4. Under the **Virtualenv** section, enter the path to your created virtual environment:
   ```
   /home/<your-username>/ShelfSync/venv
   ```
5. Under the **Code** section, set the **Source code** and **Working directory** to:
   ```
   /home/<your-username>/ShelfSync
   ```

---

## 5. Configure WSGI Configuration File

Click the link to edit the **WSGI configuration file** (e.g., `/var/www/<your-username>_pythonanywhere_com_wsgi.py`).

Replace the contents of the file with the following clean configuration:

```python
import os
import sys

# Path to ShelfSync repository
project_home = '/home/<your-username>/ShelfSync'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Set production environment variables
os.environ['SECRET_KEY'] = 'replace-with-a-secure-random-secret-key'
os.environ['SHELF_SYNC_DB'] = os.path.join(project_home, 'shelf_sync.db')
os.environ['FLASK_DEBUG'] = '0'

# Import the Flask application instance
from app import app as application
```
*(Make sure to replace `<your-username>` with your actual PythonAnywhere username!)*

Save the WSGI file.

---

## 6. Configure Static Files

In the **Web** tab under **Static files**, configure the mapping so your CSS and JS load properly:

| URL | Directory |
|---|---|
| `/static/` | `/home/<your-username>/ShelfSync/static` |

---

## 7. Reload and Visit the Site

1. Click the green **Reload <your-username>.pythonanywhere.com** button at the top of the **Web** tab.
2. Open your live site: `https://<your-username>.pythonanywhere.com`

---

## 8. Common Errors and Troubleshooting

1. **`ModuleNotFoundError: No module named 'flask'`**
   - **Cause**: The web app is not pointing to the correct virtual environment path.
   - **Fix**: Check the **Virtualenv** setting in the Web tab. It must be `/home/<your-username>/ShelfSync/venv`.

2. **Missing Styling or CSS/JS not loading**
   - **Cause**: Static file mapping is missing or incorrect in the Web tab.
   - **Fix**: Ensure `/static/` maps directly to `/home/<your-username>/ShelfSync/static`.

3. **`sqlite3.OperationalError: attempt to write a readonly database`**
   - **Cause**: Permissions issue or wrong database path.
   - **Fix**: Ensure the database path in `SHELF_SYNC_DB` is inside your project directory (`/home/<your-username>/ShelfSync/shelf_sync.db`) and that the directory is writable.

4. **CSRF Validation Failed (400 Bad Request)**
   - **Cause**: Missing `SECRET_KEY` causes session invalidation between worker restarts.
   - **Fix**: Set a persistent `SECRET_KEY` in your WSGI file as shown in Step 5.
