# Database Migration Reset

## What Was Done

All previous migration files have been removed and replaced with a single fresh initial migration that creates the complete database schema from scratch.

### Changes Made

1. **Deleted old migrations:**
   - `add_gedcom_id_tracking_to_persons.py`
   - `add_gedcom_id_tracking_to_records.py`
   - `add_parent_relationships_to_persons.py`

2. **Created new initial migration:**
   - [`src/migrations/versions/001_initial_schema.py`](src/migrations/versions/001_initial_schema.py)
   - This migration creates all tables with the current schema including:
     - `record_batches`
     - `genealogical_records`
     - `uploaded_files`
     - `social_statuses`
     - `persons` (with gedcom_id, parent relationships, etc.)
     - `baptism_records` (with gedcom_id)
     - `marriage_records` (with gedcom_id)
     - `death_records` (with gedcom_id)
     - `godparent_relationships`
     - `witness_relationships`

## How to Apply the Migration

### Prerequisites

Ensure your PostgreSQL database is running. If using Docker:

```bash
docker-compose up -d db
```

### Option 1: Automatic (Recommended)

The application automatically applies migrations on startup via [`src/app/__init__.py`](src/app/__init__.py:49). Simply start the application:

```bash
cd src
python main.py
```

The app will:
1. Create tables if they don't exist
2. Apply pending migrations
3. Initialize Apache AGE extension

### Option 2: Manual Migration

If you prefer to apply migrations manually:

```bash
cd src
flask db upgrade
```

Or using Alembic directly:

```bash
cd src
alembic upgrade head
```

### Option 3: Fresh Database Reset

To completely reset the database and apply the fresh schema:

```bash
# Drop all tables and recreate from scratch
cd src
python -c "from app.extensions import db; from app import create_app; app = create_app(); app.app_context().push(); db.drop_all(); db.create_all()"

# Then apply the migration to mark it as applied
flask db stamp head
```

## Database Schema

The new schema includes all features from previous migrations:

### Person Entity
- GEDCOM ID tracking (`gedcom_id` field with index)
- Parent-child relationships (`father_id`, `mother_id` foreign keys)
- Source batch tracking
- Complete biographical information

### Record Entities
All record types (Baptism, Marriage, Death) include:
- GEDCOM ID tracking (`gedcom_id` field with index)
- Source batch tracking
- Complete record-specific fields

### Relationship Tables
- `godparent_relationships` - Links persons as godparents to baptism records
- `witness_relationships` - Links persons as witnesses to marriage records

## Verification

After applying the migration, verify the schema:

```bash
# Connect to PostgreSQL
psql -U postgres -d korzen

# List all tables
\dt

# Check persons table structure
\d persons

# Check indexes
\di
```

You should see all tables created with proper foreign keys and indexes.

## Troubleshooting

### Migration Already Applied Error

If you get an error that the migration is already applied, you may need to clear the alembic version table:

```sql
DELETE FROM alembic_version;
```

Then reapply:

```bash
cd src
flask db upgrade
```

### Database Connection Issues

If you can't connect to the database:

1. Check if PostgreSQL is running: `docker-compose ps`
2. Verify connection string in `.env`: `DATABASE_URL=postgresql+psycopg://postgres:postgres@db:5432/korzen`
3. Check Docker network: `docker network ls`

### Schema Mismatch

If the schema doesn't match the models after migration:

```bash
# Generate a new migration to fix differences
cd src
flask db revision --autogenerate -m "fix_schema_differences"
flask db upgrade
```

## Next Steps

After successfully applying the migration:

1. Import GEDCOM files - duplicate detection will work correctly
2. Parent-child relationships will be properly tracked
3. All record types will have source tracking
4. Apache AGE graph features will be available

## Notes

- The migration is idempotent - it can be safely applied to an empty database
- All previous migration history has been consolidated into this single initial migration
- Future schema changes should be added as new migrations on top of this base
