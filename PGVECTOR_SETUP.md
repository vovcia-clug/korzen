# pgvector Setup for Docker

## Problem
The application was failing with the error:
```
column persons.embedding does not exist
extension "vector" is not available
```

## Solution
I've configured Docker to install the pgvector extension in your PostgreSQL database.

## Changes Made

### 1. Created Custom Database Dockerfile
**File:** `docker/Dockerfile.db`
- Extends the Apache AGE image
- Installs pgvector extension (v0.5.1)
- Compiles and installs pgvector into PostgreSQL

### 2. Created Database Initialization Script
**File:** `docker/initdb/01-init-extensions.sql`
- Creates the AGE extension
- Creates the pgvector extension
- Sets up the search path

### 3. Updated docker-compose.yml
- Changed from using `image: apache/age:latest` to building from custom Dockerfile
- The database will now be built with pgvector support

## Next Steps

### 1. Rebuild the Database Container
```bash
# Stop and remove existing containers
docker compose down

# Remove the database volume (WARNING: This will delete all data!)
docker volume rm korzen_korzen-db-data

# Rebuild and start containers
docker compose up --build -d
```

### 2. Run Database Migrations
After the containers are running, apply the migrations to create the embedding columns:

```bash
# Using your Flask migration commands
# (Replace with your actual migration command)
python -m flask db upgrade
# or
alembic upgrade head
```

### 3. Verify Installation
Connect to the database and verify the extensions:
```bash
docker compose exec db psql -U postgres -d korzen -c "SELECT * FROM pg_extension WHERE extname IN ('age', 'vector');"
```

You should see both extensions listed.

## What This Enables

Once setup is complete, the application will have:
- ✅ Vector embeddings for duplicate detection
- ✅ Similarity search using cosine distance
- ✅ Automatic duplicate checking during GEDCOM imports
- ✅ Phonetic matching with Daitch-Mokotoff encoding

## Troubleshooting

If you encounter issues:

1. **Build fails**: Check Docker logs with `docker compose logs db`
2. **Extension not found**: Ensure the init script ran with `docker compose exec db psql -U postgres -d korzen -c "\dx"`
3. **Migration fails**: Check that the database is fully initialized before running migrations

## Rollback (if needed)

If you need to revert to the original setup without pgvector:
1. Restore `docker-compose.yml` to use `image: apache/age:latest`
2. Comment out the embedding columns in `src/app/models.py`
3. Comment out embedding generation in `src/app/gedcom_parser.py`
