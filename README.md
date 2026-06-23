# Spot On Appliance Cleaning

Django booking website for Spot On Appliance Cleaning.

## Run with Docker (recommended)

Uses **PostgreSQL** by default.

### Ubuntu server setup

```bash
# Install Docker
sudo apt update
sudo apt install -y git docker.io docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
# Log out and back in so docker group applies

# Clone and configure
git clone https://github.com/pcmodder2001/spotoncleaning.git
cd spotoncleaning
cp .env.example .env
nano .env   # set DJANGO_SECRET_KEY, DB_PASSWORD, and your domain(s)

# Build and start (web + postgres)
docker compose up -d --build

# Load services, time slots, and sample data (first time only)
docker compose exec web python manage.py setup_initial_data

# Create an admin user
docker compose exec web python manage.py createsuperuser
```

Open `http://192.168.0.50:8999` (or your domain if proxied).

### Useful commands

```bash
docker compose logs -f web          # View app logs
docker compose logs -f db           # View postgres logs
docker compose restart web          # Restart app
docker compose down                 # Stop containers
docker compose up -d --build        # Rebuild after git pull
docker compose exec web python manage.py migrate
```

## Local development (Windows / without Docker)

Connect to PostgreSQL on the Ubuntu server:

**PowerShell:**

```powershell
$env:DB_ENGINE = 'postgresql'
$env:DB_NAME = 'spotoncleaning'
$env:DB_USER = 'spoton'
$env:DB_PASSWORD = 'your-password'
$env:DB_HOST = '192.168.0.50'
$env:DB_PORT = '5432'

python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py setup_initial_data
python manage.py runserver 192.168.0.93:8999
```

Or use SQLite locally (no postgres env vars):

```bash
python manage.py migrate
python manage.py runserver 8999
```

## Environment variables

See `.env.example` for all supported settings.

**Docker note:** use `DB_HOST=db` (the docker service name).  
**Local dev note:** use `DB_HOST=192.168.0.50` (the server IP).

### Postgres: `no pg_hba.conf entry` from your dev PC

Your Windows machine (`192.168.0.93`) is blocked by PostgreSQL on the server. After pulling latest code, on **Ubuntu**:

```bash
cd ~/spotoncleaning
git pull
docker compose down
docker compose up -d --build
```

This repo configures Docker Postgres to allow `192.168.0.0/24` (your LAN).

If you use **system Postgres** (same server as Vehiclecare), add these lines to `/etc/postgresql/*/main/pg_hba.conf`:

```
host    spotoncleaning    spoton    192.168.0.0/24    md5
host    spotoncleaning    spoton    172.19.0.0/16     md5
```

Create the database and user if needed:

```bash
sudo -u postgres psql
```

```sql
CREATE USER spoton WITH PASSWORD 'your-password';
CREATE DATABASE spotoncleaning OWNER spoton;
\c spotoncleaning
ALTER SCHEMA public OWNER TO spoton;
GRANT ALL ON SCHEMA public TO spoton;
GRANT CREATE ON SCHEMA public TO spoton;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO spoton;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO spoton;
\q
```

### Postgres: `permission denied for schema public`

If migrate connects but fails with this error (PostgreSQL 15+), the user needs ownership of the `public` schema:

```bash
sudo -u postgres psql -d spotoncleaning
```

```sql
ALTER DATABASE spotoncleaning OWNER TO spoton;
ALTER SCHEMA public OWNER TO spoton;
GRANT ALL ON SCHEMA public TO spoton;
GRANT CREATE ON SCHEMA public TO spoton;
\q
```

Then on Windows run `python manage.py migrate` again.

Then restart Postgres:

```bash
sudo systemctl restart postgresql
```

For Docker-only Postgres, pull latest and `docker compose up -d --build` (uses `docker/postgres/pg_hba.conf`).
