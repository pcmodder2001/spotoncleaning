# Spot On Appliance Cleaning

Django booking website for Spot On Appliance Cleaning.

## Run with Docker (recommended)

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
nano .env   # set DJANGO_SECRET_KEY and your domain(s)

# Build and start
docker compose up -d --build

# Load services, time slots, and sample data (first time only)
docker compose exec web python manage.py setup_initial_data

# Create an admin user
docker compose exec web python manage.py createsuperuser
```

Open `http://YOUR_SERVER_IP:8000` (or your domain if proxied).

### Useful commands

```bash
docker compose logs -f web          # View logs
docker compose restart web          # Restart app
docker compose down                 # Stop containers
docker compose up -d --build        # Rebuild after git pull
docker compose exec web python manage.py migrate
```

### PostgreSQL (optional)

Edit `.env` and uncomment the `DB_ENGINE=postgresql` settings, then:

```bash
docker compose --profile postgres up -d --build
```

## Local development (without Docker)

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py setup_initial_data
python manage.py runserver
```

## Environment variables

See `.env.example` for all supported settings.
