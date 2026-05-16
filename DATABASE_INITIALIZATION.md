# Database Initialization

This document explains how database initialization works in the Korzen genealogy application.

## Overview

The application now handles all database initialization automatically on startup, eliminating the need for manual migration commands or Docker init scripts.

## Automatic Initialization Process

When the Flask application starts (via [`src/main.py`](src/main.py)), it automatically performs the following steps in order:

### 1. Flask-Migrate Migrations
- **What**: Applies all pending Alembic migrations to create/update database tables
- **Location**: [`src/app/__init__.py`](src/app/__init__.py) - `create_app()` function
- **Equivalent to**: Running `flask db upgrade` manually
- **Logs**: "Database migrations applied successfully"

### 2. Apache AGE Extension Initialization
- **What**: Enables the Apache AGE PostgreSQL extension for graph database functionality
- **Location**: [`src/app/services/age_initializer.py`](src/app/services/age_initializer.py) - `initialize_age_extension()`
- **Actions**:
  - Creates AGE extension if not exists
  - Loads AGE into PostgreSQL
  - Sets search path to include `ag_catalog`
- **Equivalent to**: Running [`docker/initdb/001-enable-age.sql`](docker/initdb/001-enable-age.sql)

### 3. Genealogy Graph Creation
- **What**: Creates the 'genealogy' graph in Apache AGE
- **Location**: [`src/app/services/age_initializer.py`](src/app/services/age_initializer.py) - `create_genealogy_graph()`
- **Actions**:
  - Creates the genealogy graph (idempotent - safe to run multiple times)
  - Verifies graph creation
- **Equivalent to**: Part of [`docker/initdb/002-create-genealogy-graph.sql`](docker/initdb/002-create-genealogy-graph.sql)

### 4. Helper Functions Creation
- **What**: Creates PostgreSQL helper functions for working with the graph
- **Location**: [`src/app/services/age_initializer.py`](src/app/services/age_initializer.py) - `create_helper_functions()`
- **Functions Created**:
  - `execute_cypher(graph_name, query, params)` - Execute Cypher queries safely
  - `get_person_vertex(person_uuid)` - Get a person vertex by UUID
  - `count_vertices(label)` - Count vertices by label
  - `count_edges(edge_type)` - Count edges by type
  - `get_graph_statistics()` - Get comprehensive graph statistics
- **Equivalent to**: Part of [`docker/initdb/002-create-genealogy-graph.sql`](docker/initdb/002-create-genealogy-graph.sql)

## Benefits

### 1. **No Manual Steps Required**
- No need to run `flask db upgrade` after deployment
- No need to manually execute SQL scripts
- Works in any environment (Docker, local, production)

### 2. **Idempotent Operations**
- Safe to restart the application multiple times
- All operations check if resources already exist
- No errors on subsequent runs

### 3. **Consistent Initialization**
- Same initialization process in all environments
- Reduces deployment complexity
- Eliminates "forgot to run migrations" errors

### 4. **Better Error Handling**
- Detailed logging for each initialization step
- Graceful handling of errors
- Application can continue even if AGE initialization fails (for non-graph features)

## Error Handling

### Migration Errors
If Flask-Migrate migrations fail:
- Error is logged: "Error applying database migrations: {error}"
- Application startup continues (can be changed to fatal by uncommenting `raise`)
- Check database connectivity and migration files

### AGE Initialization Errors
If AGE initialization fails:
- Error is logged: "Error initializing AGE database: {error}"
- Application startup continues (graph features may not work)
- Check that PostgreSQL has AGE extension installed
- Verify database user has necessary permissions

## Configuration

No additional configuration is required. The initialization uses the existing database connection from [`src/app/config.py`](src/app/config.py):

```python
SQLALCHEMY_DATABASE_URI = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@db:5432/korzen",
)
```

## Docker Considerations

### Old Approach (No Longer Needed)
Previously, Docker init scripts in [`docker/initdb/`](docker/initdb/) were used:
- `001-enable-age.sql` - Enable AGE extension
- `002-create-genealogy-graph.sql` - Create graph and helper functions

### New Approach
These scripts are now **deprecated** and can be removed. The application handles all initialization automatically.

**Note**: The Docker init scripts only run when the PostgreSQL container is first created. The application-based approach runs on every startup, making it more reliable for development and updates.

## Development Workflow

### Starting the Application
```bash
# Just start the application - initialization happens automatically
cd src
python main.py
```

Or with Docker:
```bash
docker-compose up
```

### Creating New Migrations
```bash
cd src
flask db migrate -m "Description of changes"
# The new migration will be applied automatically on next startup
```

### Verifying Initialization
Check the application logs on startup:
```
INFO: Database migrations applied successfully
INFO: Starting AGE database initialization...
INFO: AGE extension created/verified
INFO: AGE extension loaded
INFO: Search path configured for AGE
INFO: Creating genealogy graph...
INFO: Genealogy graph verified successfully
INFO: Creating AGE helper functions...
INFO: AGE helper functions created successfully
INFO: AGE database initialization completed successfully
INFO: AGE database initialized successfully
```

## Troubleshooting

### "AGE extension not found"
- Ensure PostgreSQL has the AGE extension installed
- For Docker: Use a PostgreSQL image with AGE pre-installed
- For local: Install AGE from https://age.apache.org/

### "Permission denied"
- Database user needs SUPERUSER privileges to create extensions
- Or grant specific permissions: `GRANT CREATE ON DATABASE korzen TO your_user;`

### "Graph already exists" warnings
- This is normal and expected on subsequent startups
- The initialization is idempotent and handles existing resources gracefully

## Migration from Docker Init Scripts

If you're migrating from the old Docker init script approach:

1. **No action required** - The application will handle initialization
2. **Optional**: Remove or archive the [`docker/initdb/`](docker/initdb/) directory
3. **Optional**: Update [`docker-compose.yml`](docker-compose.yml) to remove volume mount for init scripts

The application-based initialization is backward compatible and will work alongside existing Docker init scripts without conflicts.
