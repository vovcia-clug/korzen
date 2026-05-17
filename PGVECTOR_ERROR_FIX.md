# pgvector "type does not exist" Error - Fix Summary

## Problem

The application was failing on startup with the error:

```
ERROR in __init__: Error creating database tables: (psycopg.errors.UndefinedObject) type "vector" does not exist
LINE 26:  embedding VECTOR(128),
```

Even though the logs showed:
```
INFO in __init__: ✓ pgvector extension already exists
INFO in __init__: ✓ Vector type is available
```

## Root Cause

The issue was caused by **calling `db.create_all()` before running migrations**. Here's what was happening:

1. **First worker startup:**
   - pgvector extension check passes ✓
   - `db.create_all()` tries to create tables with VECTOR columns
   - **FAILS** because the extension wasn't properly committed in the same transaction
   - Migrations run afterward (but tables already partially created)

2. **Second worker startup (after restart):**
   - pgvector extension now works ✓
   - `db.create_all()` tries to create tables again
   - **FAILS** with duplicate key error because tables already exist from migrations

## Solution

**Removed the `db.create_all()` call** and let Flask-Migrate handle all table creation through migrations.

### Changes Made to `src/app/__init__.py`

**Before:**
```python
with app.app_context():
    # Step 0: Initialize pgvector extension
    initialize_pgvector_extension(app)
    
    # Step 1: Create all tables (PROBLEMATIC!)
    db.create_all()
    
    # Step 2: Run migrations
    upgrade()
    
    # Step 3: Initialize AGE
    initialize_age_database(db)
```

**After:**
```python
with app.app_context():
    # Step 1: Initialize pgvector extension
    initialize_pgvector_extension(app)
    
    # Step 2: Run migrations (creates/updates all tables)
    upgrade()
    
    # Step 3: Initialize AGE
    initialize_age_database(db)
```

## Why This Works

1. **pgvector extension is created first** with proper commit
2. **Migrations handle all table creation** in a controlled, transactional manner
3. **No race conditions** between `db.create_all()` and migrations
4. **Idempotent** - migrations can be run multiple times safely

## Verification

After this fix, the application should start successfully with logs showing:

```
INFO in __init__: ✓ pgvector extension already exists
INFO in __init__: ✓ Vector type is available
INFO in __init__: Database migrations applied successfully
INFO in __init__: AGE database initialized successfully
```

## Best Practices

### ✅ DO:
- Use Flask-Migrate for all schema changes
- Initialize extensions before running migrations
- Let migrations handle table creation

### ❌ DON'T:
- Mix `db.create_all()` with Flask-Migrate
- Create tables before extensions are committed
- Assume extension creation is immediately visible in the same transaction

## Related Files

- [`src/app/__init__.py`](src/app/__init__.py) - Application initialization (FIXED)
- [`src/migrations/versions/001_initial_schema.py`](src/migrations/versions/001_initial_schema.py) - Initial schema migration
- [`src/migrations/versions/002_add_vector_embeddings.py`](src/migrations/versions/002_add_vector_embeddings.py) - Vector embeddings migration
- [`docker/initdb/01-init-extensions.sql`](docker/initdb/01-init-extensions.sql) - Database initialization script

## Additional Notes

The pgvector extension must be created with `autocommit` or in a separate transaction before it can be used. The `initialize_pgvector_extension()` function handles this correctly, but `db.create_all()` was bypassing the migration system and causing conflicts.

By removing `db.create_all()` and relying solely on Flask-Migrate, we ensure:
- Proper transaction handling
- Version control for schema changes
- Consistent database state across environments
- No race conditions between workers
