FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY . .

RUN chmod +x docker/entrypoint.sh \
    && adduser --disabled-password --gecos "" appuser \
    && mkdir -p /app/data /app/media /app/staticfiles \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8999

ENTRYPOINT ["./docker/entrypoint.sh"]
