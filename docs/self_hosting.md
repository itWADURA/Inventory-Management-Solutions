# Self-Hosting Guide

This guide describes how to deploy **Itwadura Inventory** on your own server or virtual machine using Docker Compose and Caddy.

---

## 1. Prerequisites

- A Linux server (Ubuntu 22.04+ or Debian 12 recommended) with at least 1 GB RAM and 1 CPU core.
- Docker and Docker Compose installed.
- A registered domain name pointing to your server's public IP address (for automated HTTPS certificates).

---

## 2. Quick Production Deployment with Docker Compose

### Step 1: Clone Repository
```bash
git clone https://github.com/itwadura/inventory-management-solutions.git /opt/itwadura
cd /opt/itwadura
```

### Step 2: Configure Environment Variables
Copy the template and generate a strong secret key:
```bash
cp .env.example .env
```

Edit `.env` using your text editor:
```ini
DEBUG=False
SECRET_KEY=generate_a_cryptographically_secure_random_string_here
ALLOWED_HOSTS=inventory.yourdomain.com,web
CSRF_TRUSTED_ORIGINS=https://inventory.yourdomain.com

DB_ENGINE=postgresql
DB_NAME=itwadura_inventory
DB_USER=itwadura_user
DB_PASSWORD=choose_a_strong_database_password
DB_HOST=db
DB_PORT=5432

SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```

### Step 3: Configure Caddy Reverse Proxy
In `Caddyfile`, set your public domain:
```caddy
inventory.yourdomain.com {
    encode gzip zstd

    handle_path /static/* {
        root * /var/www/static
        file_server
    }

    handle {
        reverse_proxy web:8000 {
            header_up X-Forwarded-Proto {scheme}
            header_up X-Forwarded-Host {host}
            header_up Host {host}
        }
    }
}
```
Caddy will automatically issue and renew a free Let's Encrypt TLS certificate.

### Step 4: Launch Containers
```bash
docker compose up -d --build
```

### Step 5: Create Initial Administrator Account
```bash
docker compose exec web python manage.py createsuperuser
```

Your inventory system is now live at `https://inventory.yourdomain.com`!

---

## 3. Container Services Summary

| Service | Container Name | Description |
|---|---|---|
| `db` | `itwadura_db` | PostgreSQL 16 database |
| `web` | `itwadura_web` | Gunicorn WSGI server running Django |
| `caddy` | `itwadura_proxy` | Automatic HTTPS reverse proxy & static asset server |

