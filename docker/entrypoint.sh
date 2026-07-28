#!/bin/sh
set -e

mkdir -p /app/media /app/staticfiles

echo "Waiting for PostgreSQL at ${DB_HOST:-host.docker.internal}:${DB_PORT:-5432}..."
python <<'PY'
import os
import sys
import time

import psycopg2

host = os.environ.get("DB_HOST", "host.docker.internal")
port = int(os.environ.get("DB_PORT", "5432"))
name = os.environ.get("DB_NAME", "spotoncleaning")
user = os.environ.get("DB_USER", "spoton")
password = os.environ.get("DB_PASSWORD", "")

for attempt in range(60):
    try:
        psycopg2.connect(
            dbname=name,
            user=user,
            password=password,
            host=host,
            port=port,
            connect_timeout=3,
        ).close()
        print("PostgreSQL is ready.")
        break
    except Exception as exc:
        if attempt == 59:
            print(f"PostgreSQL not ready: {exc}", file=sys.stderr)
            sys.exit(1)
        time.sleep(1)
PY

python manage.py migrate --noinput
python manage.py collectstatic --noinput --clear

exec gunicorn config.wsgi:application \
    --bind "0.0.0.0:${APP_PORT:-8999}" \
    --workers "${GUNICORN_WORKERS:-3}" \
    --timeout "${GUNICORN_TIMEOUT:-120}" \
    --access-logfile - \
    --error-logfile - \
    --log-level info
