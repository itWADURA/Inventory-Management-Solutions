# Backup & Disaster Recovery Guide

Protecting inventory data is critical for small businesses. This guide outlines how to create and restore complete backups of your PostgreSQL database and uploads.

---

## 1. Creating a Database Backup

### Docker-based Deployment
To create a timestamped SQL backup from the running database container:

```bash
# Set timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Dump PostgreSQL database
docker compose exec -T db pg_dump -U itwadura_user -d itwadura_inventory -F c -b -v > backup_itwadura_${TIMESTAMP}.dump
```

### Standalone PostgreSQL Host
```bash
pg_dump -U itwadura_user -h 127.0.0.1 -d itwadura_inventory -F c -b -v -f backup_itwadura.dump
```

---

## 2. Restoring a Database Backup

### Step 1: Stop the Web Application
Stop incoming web requests while restoring database state:
```bash
docker compose stop web
```

### Step 2: Restore from Dump File
```bash
# Drop and recreate clean target schema
docker compose exec -T db psql -U itwadura_user -d itwadura_inventory -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

# Restore dump
cat backup_itwadura_20261113.dump | docker compose exec -T db pg_restore -U itwadura_user -d itwadura_inventory --clean --if-exists
```

### Step 3: Restart Web Application
```bash
docker compose start web
```

---

## 3. Automated Daily Backup Script (Cron Example)

Save this script as `/opt/itwadura/scripts/backup.sh` and make it executable (`chmod +x`):

```bash
#!/bin/bash
BACKUP_DIR="/var/backups/itwadura"
mkdir -p "$BACKUP_DIR"

DATE=$(date +"%Y%m%d_%H%M%S")
cd /opt/itwadura || exit 1

# Execute dump
docker compose exec -T db pg_dump -U itwadura_user -d itwadura_inventory -F c > "${BACKUP_DIR}/itwadura_${DATE}.dump"

# Retain backups for 14 days, delete older files
find "$BACKUP_DIR" -type f -name "*.dump" -mtime +14 -delete
```

Add to system cron with `crontab -e`:
```cron
0 2 * * * /opt/itwadura/scripts/backup.sh > /dev/null 2>&1
```

