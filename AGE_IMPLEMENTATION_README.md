# PostgreSQL AGE Implementation for GEDCOM Data

## Overview

This implementation adds Apache AGE (A Graph Extension) graph database capabilities to the Korzen genealogy application, enabling powerful relationship queries while maintaining the existing relational database structure.

## What Has Been Implemented

### ✅ Completed Components

1. **Database Initialization Script**
   - File: [`docker/initdb/002-create-genealogy-graph.sql`](docker/initdb/002-create-genealogy-graph.sql)
   - Creates the `genealogy` graph
   - Provides helper functions for graph operations
   - Automatically runs when database container starts

2. **AGE Graph Importer Service**
   - File: [`src/app/services/age_graph_importer.py`](src/app/services/age_graph_importer.py)
   - Imports genealogical data into AGE graph
   - Creates Person, Event, and Source vertices
   - Creates relationship edges (PARENT_OF, MARRIED_TO, etc.)
   - Idempotent operations with duplicate detection

3. **Services Package**
   - File: [`src/app/services/__init__.py`](src/app/services/__init__.py)
   - Package initialization for service layer

4. **Comprehensive Documentation**
   - [`plans/AGE_IMPLEMENTATION_PLAN.md`](plans/AGE_IMPLEMENTATION_PLAN.md) - Overall strategy
   - [`plans/AGE_GRAPH_SCHEMA.md`](plans/AGE_GRAPH_SCHEMA.md) - Complete graph schema
   - [`plans/AGE_IMPLEMENTATION_GUIDE.md`](plans/AGE_IMPLEMENTATION_GUIDE.md) - Implementation steps
   - [`plans/AGE_QUERY_SERVICE_SPEC.md`](plans/AGE_QUERY_SERVICE_SPEC.md) - Query service specification
   - [`plans/AGE_API_ENDPOINTS_SPEC.md`](plans/AGE_API_ENDPOINTS_SPEC.md) - REST API specification
   - [`plans/AGE_TESTING_SPEC.md`](plans/AGE_TESTING_SPEC.md) - Testing strategy
   - [`plans/AGE_IMPLEMENTATION_SUMMARY.md`](plans/AGE_IMPLEMENTATION_SUMMARY.md) - Executive summary

### 📋 Remaining Components (Specifications Complete)

The following components have complete specifications and are ready to be implemented:

1. **Graph Query Service** - [`src/app/services/genealogy_graph_service.py`](plans/AGE_QUERY_SERVICE_SPEC.md)
2. **GEDCOM Parser Integration** - Extend [`src/app/gedcom_parser.py`](src/app/gedcom_parser.py)
3. **Graph API Routes** - [`src/app/routes/graph.py`](plans/AGE_API_ENDPOINTS_SPEC.md)
4. **Test Suite** - Multiple test files (see [testing spec](plans/AGE_TESTING_SPEC.md))

## Architecture

### Hybrid Data Model

```
┌─────────────────────────────────────────────────────────┐
│                    Application Layer                     │
│  (Flask Routes, Business Logic, GEDCOM Parser)          │
└────────────────┬────────────────────────────────────────┘
                 │
        ┌────────┴────────┐
        │                 │
┌───────▼──────┐  ┌──────▼────────┐
│  Relational  │  │  Graph Layer  │
│   Database   │  │  (AGE Graph)  │
│              │  │               │
│ • Person     │  │ • :Person     │
│ • Baptism    │  │ • :Event      │
│ • Marriage   │  │ • :PARENT_OF  │
│ • Death      │  │ • :MARRIED_TO │
└──────────────┘  └───────────────┘
        │                 │
        └────────┬────────┘
                 │
        ┌────────▼────────┐
        │   PostgreSQL    │
        │   with AGE      │
        └─────────────────┘
```

## Graph Schema

### Vertices

- **:Person** - Individual people (uuid, gedcom_id, first_name, last_name, birth_date, death_date, etc.)
- **:Event** - Life events (uuid, event_type, date, place, parish)
- **:Source** - Data sources (uuid, source_name, import_date, description)

### Edges

- **:PARENT_OF** - Parent → Child (type: father/mother)
- **:MARRIED_TO** - Spouse ↔ Spouse (bidirectional, date, place)
- **:BAPTIZED_IN** - Person → Event (date)
- **:DIED_IN** - Person → Event (date)
- **:GODPARENT_OF** - Godparent → Child (type: godfather/godmother)
- **:FROM_SOURCE** - Entity → Source (source tracking)

## Using the AGE Graph Importer

### Basic Usage

```python
from app.extensions import db
from app.services import AgeGraphImporter

# Get raw psycopg connection
raw_conn = db.engine.raw_connection()

# Create importer
importer = AgeGraphImporter(raw_conn)

# Ensure graph exists
importer.create_graph_if_not_exists()

# Create a person vertex
importer.create_person_vertex(
    'person-uuid',
    {
        'gedcom_id': 'I123',
        'first_name': 'John',
        'last_name': 'Smith',
        'gender': 'M',
        'birth_date': datetime(1850, 1, 1).date(),
        'death_date': datetime(1920, 1, 1).date()
    }
)

# Create parent-child relationship
importer.create_parent_child_edge(
    'parent-uuid',
    'child-uuid',
    'father'
)

# Create marriage relationship
importer.create_marriage_edge(
    'spouse1-uuid',
    'spouse2-uuid',
    '1875-06-20',
    'Warsaw Cathedral'
)

# Get statistics
stats = importer.get_statistics()
print(f"Persons: {stats['persons']}")
print(f"Parent-child relationships: {stats['parent_of_edges']}")

# Close connection
raw_conn.close()
```

### Integration with GEDCOM Parser

The importer is designed to be called after successful GEDCOM import to the relational database. See [`plans/AGE_IMPLEMENTATION_GUIDE.md`](plans/AGE_IMPLEMENTATION_GUIDE.md) for the complete integration pattern.

## Query Examples

Once the graph query service is implemented, you'll be able to run queries like:

```cypher
-- Find all ancestors (up to 5 generations)
MATCH path = (person:Person {uuid: $person_id})<-[:PARENT_OF*1..5]-(ancestor:Person)
RETURN ancestor, length(path) as generation
ORDER BY generation

-- Find siblings
MATCH (person:Person {uuid: $person_id})<-[:PARENT_OF]-(parent:Person)-[:PARENT_OF]->(sibling:Person)
WHERE person.uuid <> sibling.uuid
RETURN DISTINCT sibling

-- Find relationship path between two people
MATCH path = shortestPath(
    (p1:Person {uuid: $person1_id})-[*..15]-(p2:Person {uuid: $person2_id})
)
RETURN path
```

## API Endpoints (Planned)

Once implemented, the following REST API endpoints will be available:

- `GET /api/graph/person/<uuid>/ancestors` - Get ancestors
- `GET /api/graph/person/<uuid>/descendants` - Get descendants
- `GET /api/graph/person/<uuid>/siblings` - Get siblings
- `GET /api/graph/person/<uuid>/parents` - Get parents
- `GET /api/graph/person/<uuid>/children` - Get children
- `GET /api/graph/person/<uuid>/spouses` - Get spouses
- `GET /api/graph/relationship/<uuid1>/<uuid2>` - Find relationship path
- `GET /api/graph/common-ancestors/<uuid1>/<uuid2>` - Find common ancestors
- `GET /api/graph/person/<uuid>/tree` - Get complete family tree
- `GET /api/graph/statistics` - Get graph statistics
- `GET /api/graph/health` - Health check

## Testing the Implementation

### Verify Database Initialization

After starting the Docker containers:

```bash
# Check if graph was created
docker exec -it db psql -U postgres -d korzen -c "SELECT * FROM ag_catalog.ag_graph WHERE name = 'genealogy';"

# Test helper functions
docker exec -it db psql -U postgres -d korzen -c "SELECT * FROM get_graph_statistics();"
```

### Test the Importer Service

```python
# Run Python tests (once test files are created)
pytest tests/test_age_graph_importer.py -v
```

## Next Steps for Complete Implementation

1. **Implement Graph Query Service**
   - Create `src/app/services/genealogy_graph_service.py`
   - Follow specification in [`plans/AGE_QUERY_SERVICE_SPEC.md`](plans/AGE_QUERY_SERVICE_SPEC.md)

2. **Integrate with GEDCOM Parser**
   - Modify `src/app/gedcom_parser.py`
   - Add `_import_to_age_graph()` method
   - Call after successful relational import

3. **Create API Routes**
   - Create `src/app/routes/graph.py`
   - Follow specification in [`plans/AGE_API_ENDPOINTS_SPEC.md`](plans/AGE_API_ENDPOINTS_SPEC.md)
   - Register blueprint in `src/app/__init__.py`

4. **Add Tests**
   - Create test files as specified in [`plans/AGE_TESTING_SPEC.md`](plans/AGE_TESTING_SPEC.md)
   - Run tests to verify functionality

5. **Deploy and Test**
   - Restart Docker containers to run initialization script
   - Import a GEDCOM file
   - Verify graph population
   - Test API endpoints

## Benefits

### Performance
- **O(1) Relationship Traversal**: Direct edge following vs expensive joins
- **Efficient Path Finding**: Built-in shortest path algorithms
- **Scalability**: Handles large family trees efficiently

### Expressiveness
- **Natural Representation**: Family relationships are inherently graph-structured
- **Complex Queries**: Multi-hop relationships in single queries
- **Flexible Schema**: Easy to add new relationship types

### Functionality
- **Ancestor/Descendant Queries**: Any number of generations
- **Relationship Discovery**: How are two people related?
- **Common Ancestors**: Find shared ancestry
- **Family Tree Visualization**: Complete subgraph extraction

## Troubleshooting

### Graph Not Created

If the graph doesn't exist after container startup:

```bash
# Manually create the graph
docker exec -it db psql -U postgres -d korzen -c "SELECT create_graph('genealogy');"
```

### Import Errors

Check logs for detailed error messages:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Connection Issues

Ensure you're using a raw psycopg connection, not a SQLAlchemy session:

```python
# Correct
raw_conn = db.engine.raw_connection()

# Incorrect
conn = db.session  # This won't work with AGE
```

## Performance Considerations

- **Batch Operations**: Import vertices before edges for better performance
- **Connection Pooling**: Reuse database connections when possible
- **Query Limits**: Always limit path length and result sets
- **Indexing**: AGE automatically indexes properties used in WHERE clauses

## Security

- **Input Validation**: All UUIDs are validated
- **Parameter Limits**: Enforce reasonable limits on generations/hops
- **Query Timeouts**: Prevent long-running queries
- **Duplicate Detection**: Prevents duplicate vertices and edges

## Documentation

For detailed information, see the `plans/` directory:

1. **[AGE_IMPLEMENTATION_PLAN.md](plans/AGE_IMPLEMENTATION_PLAN.md)** - Overall implementation strategy
2. **[AGE_GRAPH_SCHEMA.md](plans/AGE_GRAPH_SCHEMA.md)** - Complete graph schema specification
3. **[AGE_IMPLEMENTATION_GUIDE.md](plans/AGE_IMPLEMENTATION_GUIDE.md)** - Step-by-step implementation guide
4. **[AGE_QUERY_SERVICE_SPEC.md](plans/AGE_QUERY_SERVICE_SPEC.md)** - Query service specification
5. **[AGE_API_ENDPOINTS_SPEC.md](plans/AGE_API_ENDPOINTS_SPEC.md)** - REST API specification
6. **[AGE_TESTING_SPEC.md](plans/AGE_TESTING_SPEC.md)** - Testing strategy
7. **[AGE_IMPLEMENTATION_SUMMARY.md](plans/AGE_IMPLEMENTATION_SUMMARY.md)** - Executive summary

## Support

For questions or issues:
- Review the detailed specification documents
- Check Apache AGE documentation: https://age.apache.org/
- Examine the existing GEDCOM parser implementation

## License

This implementation follows the same license as the Korzen project.

---

**Status**: Core components implemented, ready for integration and testing  
**Last Updated**: 2026-05-16  
**Version**: 1.0
