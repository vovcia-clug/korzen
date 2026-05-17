# pgvector Column Missing Error - Fix Guide

## Problem

After fixing the initial pgvector extension issue, a new error appears:

```
sqlalchemy.exc.ProgrammingError: (psycopg.errors.UndefinedColumn) column persons.embedding does not exist
```

## Root Cause

The application models define `embedding` columns, but:
1. Migration 001 creates tables WITHOUT embedding columns
2. Migration 002 is supposed to ADD the embedding columns
3. The application tries to use the models BEFORE migration 002 completes

## Solution

The database needs migration 002 to be applied. Since you cannot run manual scripts on the remote server, here are the options:

### Option 1: Let the Application Apply Migrations (Recommended)

The application is configured to run migrations automatically on startup. The issue is that it's failing partway through. To fix this:

1. **Ensure the database is in a clean state** - The migrations should complete successfully
2. **Check the alembic_version table** to see which migration is currently applied
3. **The application will automatically apply migration 002** on next startup

### Option 2: Regenerate Migration 001 to Include Vector Columns

Since the models already have `embedding` columns defined, migration 001 should create them from the start. This would eliminate the need for migration 002.

**Steps:**
1. Delete migration 002 (or mark it as applied)
2. Regenerate migration 001 to match the current models
3. Reset the database and reapply migrations

### Option 3: Make Models Match Migration 001

Remove the `embedding` columns from the models temporarily, let migration 001 create the base tables, then add the columns back and let migration 002 add them.

## Recommended Fix: Update Migration 002 to be Idempotent

The safest fix is to make migration 002 check if columns exist before adding them:

```python
def upgrade():
    # Enable pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    
    # Check if embedding column exists before adding
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    # Add columns to persons table if they don't exist
    persons_columns = [c['name'] for c in inspector.get_columns('persons')]
    if 'embedding' not in persons_columns:
        op.add_column('persons', sa.Column('embedding', Vector(128), nullable=True))
    if 'first_name_phonetic' not in persons_columns:
        op.add_column('persons', sa.Column('first_name_phonetic', postgresql.JSONB(), nullable=True))
    # ... etc for other columns
```

## Current Status

Based on the logs:
- Migration 001 has been applied ✓
- Migration 002 is attempting to run
- The application is trying to use `embedding` columns before migration 002 completes

## Next Steps

1. **Check which migration is currently applied:**
   ```sql
   SELECT * FROM alembic_version;
   ```

2. **If it shows '001':** Migration 002 needs to be applied
   - The application should do this automatically on next startup
   - Make sure the application stays running long enough for migrations to complete

3. **If it shows '002':** The columns should exist
   - This might be a caching issue
   - Try restarting the application completely
   - Check if columns actually exist: `\d persons` in psql

4. **If migrations keep failing:** The database might be in an inconsistent state
   - You may need to reset the database and start fresh
   - Or manually apply the migration SQL commands

## Prevention

To avoid this issue in the future:
- Keep models and migrations in sync
- Don't define columns in models that don't exist in the initial migration
- Use `flask db migrate` to auto-generate migrations when models change
- Test migrations in a development environment before deploying

## Files Involved

- [`src/app/models.py`](src/app/models.py) - Defines models with `embedding` columns
- [`src/migrations/versions/001_initial_schema.py`](src/migrations/versions/001_initial_schema.py) - Creates tables WITHOUT embedding
- [`src/migrations/versions/002_add_vector_embeddings.py`](src/migrations/versions/002_add_vector_embeddings.py) - Adds embedding columns
- [`src/app/__init__.py`](src/app/__init__.py) - Runs migrations on startup
