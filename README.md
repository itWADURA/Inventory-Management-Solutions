# Itwadura Inventory

> **“Know what you have, where it is, and when to restock.”**

**Itwadura Inventory** is a simple, dependable, open-source inventory management system designed for small businesses—shops, workshops, cafés, schools, and offices—moving away from paper notebooks and spreadsheets.

It is built as a clean Django modular monolith with server-rendered HTML, HTMX for real-time reactivity, Tailwind CSS for accessible styling, and Progressive Web App (PWA) support for mobile and desktop devices.

---

## 🌟 Features & Supported Workflows

- **Multi-Tenant Business Workspaces:** Scoped by organization with role-based access control (`Owner`, `Manager`, `Staff`).
- **Catalog & Item Management:** Name, Item Code (SKU), barcode, categories, units of measure, cost/selling prices, and reorder levels.
- **Transactional Stock Movements:** All inventory balance changes are immutable events (`Stock Received`, `Stock Used / Sold`, `Count Adjustment`, `Opening Balance`).
- **Concurrency & Non-Negative Balance Guarantee:** Row-level locking prevents race conditions and ensures on-hand stock cannot drop below zero.
- **Low Stock Alerts & Dashboard:** Live metrics tracking active items, total physical quantity, and deficit items requiring replenishment.
- **Locations & Multi-Storage:** Support for multiple stock storage points (shelves, rooms, warehouses).
- **Data Portability:** Free CSV export for stock summaries, low-stock items, and movements; bulk CSV item import with validation and preview.
- **Audit Logging:** Immutable audit trail tracking membership modifications, item status toggles, stock adjustments, and settings updates.
- **Installable PWA:** Web App Manifest and Service Worker with safe caching of static assets.

---

## 🚀 Quick Start & Local Development

### 1. Requirements
- Python 3.12+
- Git

### 2. Clone and Setup Environment
```bash
git clone https://github.com/itwadura/inventory-management-solutions.git
cd inventory-management-solutions

# Copy example environment configuration
cp .env.example .env
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run Migrations & Create Superuser
```bash
python manage.py migrate
python manage.py createsuperuser
```

### 5. Start the Local Server
```bash
python manage.py runserver 127.0.0.1:8000
```
Visit **http://127.0.0.1:8000** in your browser.

---

## 🐳 Running with Docker Compose

For local testing with PostgreSQL or production self-hosting:

```bash
# 1. Build and start containers in the background
docker compose up -d --build

# 2. Apply database migrations
docker compose exec web python manage.py migrate

# 3. Create your initial admin account
docker compose exec web python manage.py createsuperuser
```
Open **http://localhost:8000** (or your reverse-proxied domain).

---

## 🧪 Running Quality & Verification Checks

```bash
# Run automated test suite (pytest)
python -m pytest

# Run code style and linting checks (Ruff)
python -m ruff check .

# Run code formatter check
python -m ruff format --check .

# Run Django system integrity check
python -m manage check
```

---

## ⚙️ Environment Variables Reference

| Variable | Default | Purpose |
|---|---|---|
| `DEBUG` | `True` | Toggle Django debugging mode |
| `SECRET_KEY` | *(dev key)* | Production cryptographic secret key |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated allowed host headers |
| `CSRF_TRUSTED_ORIGINS` | `http://localhost:8000` | Trusted origins for CSRF POST requests |
| `DB_ENGINE` | `sqlite` | Database engine: `sqlite` or `postgresql` |
| `DB_NAME` | `itwadura_inventory` | PostgreSQL database name |
| `DB_USER` | `itwadura_user` | PostgreSQL database username |
| `DB_PASSWORD` | *(placeholder)* | PostgreSQL database password |
| `DB_HOST` | `127.0.0.1` | PostgreSQL host |
| `DB_PORT` | `5432` | PostgreSQL port |
| `SECURE_SSL_REDIRECT` | `False` | Enforce HTTPS redirect in production |
| `SESSION_COOKIE_SECURE`| `False` | Require HTTPS for session cookie |
| `CSRF_COOKIE_SECURE` | `False` | Require HTTPS for CSRF cookie |

---

## 💾 Backup & Restore

To back up and restore your PostgreSQL database:

```bash
# Backup
docker compose exec -T db pg_dump -U itwadura_user -d itwadura_inventory -F c > backup.dump

# Restore
cat backup.dump | docker compose exec -T db pg_restore -U itwadura_user -d itwadura_inventory --clean
```
See [docs/backup_restore.md](file:///c:/Users/deegh/OneDrive/Desktop/DEE/ITwandura/Inventory-Management-Solutions/docs/backup_restore.md) for full instructions.

---

## 📚 Documentation Links

- [Architecture & Data Model](file:///c:/Users/deegh/OneDrive/Desktop/DEE/ITwandura/Inventory-Management-Solutions/docs/architecture.md)
- [Self-Hosting Guide](file:///c:/Users/deegh/OneDrive/Desktop/DEE/ITwandura/Inventory-Management-Solutions/docs/self_hosting.md)
- [Backup & Disaster Recovery](file:///c:/Users/deegh/OneDrive/Desktop/DEE/ITwandura/Inventory-Management-Solutions/docs/backup_restore.md)
- [User Guide](file:///c:/Users/deegh/OneDrive/Desktop/DEE/ITwandura/Inventory-Management-Solutions/docs/user_guide.md)

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:
1. Fork the repository and create a feature branch (`git checkout -b feature/my-feature`).
2. Ensure code is formatted and clean: `python -m ruff format . && python -m ruff check .`.
3. Ensure all tests pass: `python -m pytest`.
4. Submit a Pull Request.

---

## 📄 License

This program is free software: licensed under the **GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later)**. See the [LICENSE](file:///c:/Users/deegh/OneDrive/Desktop/DEE/ITwandura/Inventory-Management-Solutions/LICENSE) file for full details. Users should review licensing requirements before redistributing or hosting modified versions.
