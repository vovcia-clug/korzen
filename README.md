# korzen

Scaffold for a genealogical records ingestion/processing system using Flask + PostgreSQL.

## Structure

- [`src/main.py`](src/main.py:1): entrypoint that creates the Flask app.
- [`src/app/__init__.py`](src/app/__init__.py:1): app factory + extension setup.
- [`src/app/models.py`](src/app/models.py:1): database models (schema only).
- [`src/app/routes/health.py`](src/app/routes/health.py:1): health check endpoint.

## Quick start (Docker)

1. Copy env file:

   ```bash
   cp .env.example .env
   ```

2. Build and run:

   ```bash
   docker compose up --build
   ```

3. Check health:

   ```bash
   curl http://localhost:5000/health
   ```

## Database models

- `RecordBatch` — groups ingested records by source.
- `GenealogicalRecord` — raw record payloads with type + optional external id.

## Environment variables

- `DATABASE_URL` — SQLAlchemy connection string.
- `FLASK_DEBUG` — set to `1` for debug.
- `PORT` — app port (default `5000`).
