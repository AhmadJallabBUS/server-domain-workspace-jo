# System Flow: iRedMail REST API

## Overview

Build a production-ready REST API for iRedMail database operations with Python, FastAPI, and PostgreSQL.

## Project Goals

- Develop RESTful endpoints for iRedMail database operations (DDL, DML, DQL)
- Serve endpoints via Nginx with Gunicorn/Uvicorn as WSGI server
- Implement automated API logic generation using Windsurf MCP schema
- Ensure production-grade security and performance

## Development Environment

### Database Connection

- Utilize Windsurf as MCP schema for automated API logic generation
- AI-assisted database schema awareness

### Technology Stack

- **API Framework**: FastAPI
- **Database**: PostgreSQL with SQLAlchemy 2.0 (async) + asyncpg
- **Migrations**: Alembic
- **Validation**: Pydantic v2
- **Production Server**: Uvicorn with Gunicorn
- **Web Server**: Nginx (reverse proxy)
- **Process Management**: systemd
- **Backup**: Daily pg_dump

## 1. Server Setup

### 1.1 System Requirements

- Ubuntu/Debian Linux with iRedMail installed
- Python 3.12+
- Existing PostgreSQL server (managed by iRedMail)

### 1.2 Install System Dependencies

```bash
# Update package lists
sudo apt update

# Install required packages
sudo apt install -y \
    python3.12-venv \
    python3-pip \
    build-essential \
    libpq-dev
```

### 1.3 Verify Database Connection

Ensure you have the following database connection details from your iRedMail installation:
- Database host
- Database port (default: 5432)
- Database name (e.g., iredadmin, vmail, etc.)
- Database user with appropriate permissions
- Database password

> Note: The database user should have the necessary permissions for the tables you need to access.

---

2. Project scaffold

```bash
mkdir -p /srv/myapi && cd /srv/myapi
python3 -m venv .venv
source .venv/bin/activate
```

### 2.1 Requirements

Create `requirements.txt`:

```
fastapi==0.115.5
uvicorn[standard]==0.32.0
gunicorn==23.0.0
SQLAlchemy==2.0.36
asyncpg==0.30.0
alembic==1.13.3
pydantic==2.9.2
python-dotenv==1.0.1
```

Install:

```bash
pip install -r requirements.txt
```

### 2.2 Environment variables

Create `.env` (do **not** commit):

```
APP_ENV=prod
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=app_db
DB_USER=app_user
DB_PASS=STRONG_PASSWORD_HERE
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
```

> If you prefer Unix socket (often faster/simpler on same server), set `DB_HOST=/var/run/postgresql` and keep `DB_PORT` empty.

### 2.3 Project Structure

#### Goal
Connect to an existing PostgreSQL (vmail) database and perform basic CRUD operations using psycopg2-binary, without relying on advanced ORM tools.

#### Project Structure
```
/srv/myapi
  ├── .env                    # Environment variables
  ├── requirements.txt        # Python dependencies
  ├── config.py               # Configuration settings
  ├── database.py             # Database connection and utilities
  ├── models/                 # Database models
  │   └── __init__.py
  ├── crud/                  # Database operations
  │   └── __init__.py
  └── main.py                # FastAPI application
```

#### Dependencies
Update `requirements.txt` to include:
```
fastapi==0.115.5
uvicorn[standard]==0.32.0
psycopg2-binary==2.9.9
python-dotenv==1.0.1
```

#### Configuration
Update `.env` with PostgreSQL connection details:
```
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=vmail
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_POOL_SIZE=5
```
> For Unix socket connections, set `DB_HOST=/var/run/postgresql` and leave `DB_PORT` empty.

#### Implementation Notes
- Uses raw SQL with psycopg2 for direct database access
- Implements connection pooling for better performance
- Environment-based configuration
- No ORM or migration tools required

---

6. Production Deployment

### 6.1 Gunicorn (with Uvicorn workers)

```bash
pip install gunicorn uvicorn
```

Create a **systemd** service `/etc/systemd/system/myapi.service`:

```ini
[Unit]
Description=My FastAPI service
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/srv/myapi
Environment="PATH=/srv/myapi/.venv/bin"
EnvironmentFile=/srv/myapi/.env
ExecStart=/srv/myapi/.venv/bin/gunicorn -k uvicorn.workers.UvicornWorker \
  -w 2 -b 127.0.0.1:8000 app.main:app
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Enable & start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable myapi
sudo systemctl start myapi
sudo systemctl status myapi
```

* **Why**: Keeps the API running on boot and auto-restarts on failure.

### 6.2 (Optional) Nginx reverse proxy with TLS

```bash
sudo apt install -y nginx
sudo tee /etc/nginx/sites-available/myapi <<'EOF'
server {
    listen 80;
    server_name _;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 300;
    }
}
EOF
sudo ln -s /etc/nginx/sites-available/myapi /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

* Add **Let’s Encrypt** later for HTTPS.

---

7. PostgreSQL Tuning

* **Local-only access**: keep `listen_addresses='localhost'` and ensure OS firewall blocks external access.
* **Indexes**: add based on queries. Example:

  ```sql
  CREATE INDEX IF NOT EXISTS idx_items_name_trgm ON items USING gin (name gin_trgm_ops);
  ```

  (requires `CREATE EXTENSION IF NOT EXISTS pg_trgm;`)
* **Backups**:

  ```bash
  sudo -u postgres mkdir -p /var/backups/postgres
  echo '0 3 * * * postgres pg_dump -Fc app_db > /var/backups/postgres/app_db-$(date +\%F).dump' | sudo tee /etc/cron.d/pgbackup
  sudo systemctl restart cron
  ```
* **Migrations on deploy**: `alembic upgrade head` in your CI/CD or pre-start hook.

---

8. Security Best Practices

* **Secrets** only in `.env` or systemd `EnvironmentFile`, never in Git.
* **DB user**: only needed privileges (you already granted on `app_db`).
* **Firewall** (allow HTTP only if using Nginx; Postgres stays local):

  ```bash
  sudo ufw allow 'Nginx Full'
  sudo ufw enable
  sudo ufw status
  ```
* **Health**: add a health endpoint if you want:

  ```python
  # in main.py, after app = FastAPI(...)
  @app.get("/healthz")
  async def healthz():
      return {"ok": True}
  ```

---

9. Common Operations

* **Create migration after model change**

  ```bash
  alembic revision --autogenerate -m "change xyz"
  alembic upgrade head
  ```

* **Connect to Postgres quickly**

  ```bash
  sudo -u postgres psql -d app_db
  ```

* **Check open sockets/ports**

  ```bash
  ss -lntp | grep -E "8000|5432"
  ```

* **Tail logs**

  ```bash
  journalctl -u myapi -f
  sudo tail -f /var/log/nginx/access.log /var/log/nginx/error.log
  ```

---

10. Unix Socket Configuration

* In `.env`:

  ```
  DB_HOST=/var/run/postgresql
  DB_PORT=
  ```
* Postgres already creates the socket there; permissions usually fine for local client. Faster and never exposed to network.

---

## Done ✅

You now have:

1. A production-grade FastAPI API,
2. Async SQLAlchemy with PostgreSQL on the **same server**,
3. Migrations, systemd service, (optional) Nginx, and backups.

If you want, tell me your OS (Ubuntu/Debian/AlmaLinux) and I can adapt commands, or I can add JWT auth, role-based endpoints, and a proper test suite (pytest + httpx + test DB) next.




## file syetem flow 
endpoint_serve_python -> server-domain-workspace-jo