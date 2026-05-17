# Migration Reset Complete

## Summary

Successfully removed all migrations and started with fresh databases.

## What Was Done

### 1. Removed Old Migrations
- Deleted all migration version files from [`src/migrations/versions/`](src/migrations/versions/)
- Old migrations: `001_initial_schema.py` and `002_add_vector_embeddings.py`

### 2. Reset Databases
- Stopped Docker containers with `docker compose down -v`
- Removed all database volumes to ensure a clean slate
- Restarted containers with fresh databases

### 3. Created New Initial Migration
- Generated new migration using Flask-Migrate: [`9fa49afd5516_initial_schema.py`](src/migrations/versions/9fa49afd5516_initial_schema.py)
- Added `import pgvector.sqlalchemy` to fix vector type support
- Removed AGE-related table operations (these are managed by the AGE extension, not our migrations)

### 4. Fixed pgvector Extension Schema Issue
**Critical Fix:** The pgvector extension was being created in the `ag_catalog` schema instead of `public`, causing "type vector does not exist" errors.

**Solution:**
- Dropped and recreated vector extension in `public` schema
- Updated [`docker/initdb/01-init-extensions.sql`](docker/initdb/01-init-extensions.sql) to explicitly create vector in public schema:
  ```sql
  CREATE EXTENSION IF NOT EXISTS vector SCHEMA public;
  ```

### 5. Initialized Database
- Used [`init_database.py`](init_database.py) to create all tables from models
- Manually inserted migration version into `alembic_version` table

## Current State

### Database Tables (13 total)
✅ All tables created successfully:
- `alembic_version` - Migration tracking
- `baptism_records` - Baptism records with embeddings
- `death_records` - Death records with embeddings
- `duplicate_candidates` - Duplicate detection results
- `duplicate_resolutions` - Resolved duplicates
- `genealogical_records` - Raw genealogical data
- `godparent_relationships` - Godparent connections
- `marriage_records` - Marriage records with embeddings
- `persons` - Person entities with embeddings
- `record_batches` - Import batches
- `social_statuses` - Social status reference data
- `uploaded_files` - File upload tracking
- `witness_relationships` - Marriage witness connections

### Extensions
- ✅ **AGE** extension in `ag_catalog` schema
- ✅ **pgvector** extension in `public` schema (fixed!)

### Migration Status
- Current version: `9fa49afd5516` (Initial schema)
- All tables match the current models

## Next Steps

When you restart the containers in the future, the database will:
1. Automatically create extensions (AGE in ag_catalog, vector in public)
2. Run migrations via Flask app initialization
3. Be ready to use immediately

## Important Notes

- The vector extension **must** be in the `public` schema for SQLAlchemy models to work
- AGE tables (`ag_graph`, `ag_label`) are managed by the AGE extension, not our migrations
- The init script now ensures vector is always created in the correct schema
