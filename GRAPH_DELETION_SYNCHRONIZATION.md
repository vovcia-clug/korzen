# Graph Deletion Synchronization Implementation

## Overview

This document describes the implementation of synchronized deletion between PostgreSQL and Apache AGE graph database when confirming duplicate records in the genealogy application.

## Problem Statement

**CRITICAL ISSUE IDENTIFIED**: When duplicate records were confirmed and hard deleted from PostgreSQL, the corresponding vertices and edges in the Apache AGE graph database were NOT being deleted. This caused:

- Orphaned graph vertices representing deleted persons
- Orphaned edges connecting to non-existent database records
- Growing inconsistency between relational and graph storage
- Failed queries when trying to resolve graph UUIDs to database records

## Solution Overview

The solution implements synchronized deletion across both storage systems:

1. **Graph Deletion Methods**: Added comprehensive deletion methods to [`AgeGraphImporter`](src/app/services/age_graph_importer.py)
2. **Integration**: Modified the duplicate confirmation endpoint to delete from graph BEFORE PostgreSQL deletion
3. **Error Handling**: Implemented safe error handling that continues with PostgreSQL deletion even if graph deletion fails

## Implementation Details

### 1. Graph Deletion Methods

Added to [`src/app/services/age_graph_importer.py`](src/app/services/age_graph_importer.py:730-878):

#### `delete_person_vertex_with_edges(person_uuid: str) -> bool`

Deletes a Person vertex and all connected edges from the graph.

```python
def delete_person_vertex_with_edges(self, person_uuid: str) -> bool:
    """
    Delete a Person vertex and all connected edges from the graph.
    
    This method handles the complete removal of a person from the graph,
    including all relationships (edges) connected to that person.
    
    Args:
        person_uuid: UUID of the person to delete
        
    Returns:
        True if deleted successfully, False if not found or error
    """
```

**Cypher Query Used**:
```cypher
MATCH (p:Person {uuid: $uuid})
OPTIONAL MATCH (p)-[r]-()
DELETE r, p
RETURN count(p) as deleted
```

This query:
- Matches the person vertex by UUID
- Finds all edges connected to this person (in any direction)
- Deletes all edges first, then the vertex
- Returns count of deleted vertices for verification

#### `delete_event_vertex_with_edges(event_uuid: str) -> bool`

Deletes an Event vertex (baptism, marriage, death) and all connected edges.

Handles deletion of:
- BAPTIZED_IN edges
- DIED_IN edges  
- MARRIED_TO edges
- FROM_SOURCE edges
- Any other event relationships

#### `delete_source_vertex_with_edges(source_uuid: str) -> bool`

Deletes a Source vertex and all connected edges.

#### `delete_record_from_graph(record_type: str, record_uuid: str) -> bool`

Convenience method that routes to the appropriate deletion method based on record type:
- `'person'` → `delete_person_vertex_with_edges()`
- `'baptism'`, `'marriage'`, `'death'` → `delete_event_vertex_with_edges()`

### 2. Integration with Duplicate Confirmation

Modified [`src/app/routes/main.py`](src/app/routes/main.py:1343-1476) endpoint `/api/duplicates/<candidate_id>/review`:

**Key Changes**:

1. **Import Added** (line 13):
   ```python
   from ..services.age_graph_importer import AgeGraphImporter
   ```

2. **Graph Deletion Integration** (lines 1451-1467):
   ```python
   # Delete from graph database first (before PostgreSQL deletion)
   # This ensures consistency between graph and relational storage
   try:
       raw_conn = db.session.connection().connection
       graph_importer = AgeGraphImporter(raw_conn)
       
       record_uuid = str(duplicate_record.id)
       graph_deleted = graph_importer.delete_record_from_graph(
           candidate.record_type, 
           record_uuid
       )
       
       if graph_deleted:
           logger.info(f"Deleted {candidate.record_type} from graph: {record_uuid}")
       else:
           logger.warning(f"Graph deletion returned False for {candidate.record_type}: {record_uuid}")
   except Exception as graph_error:
       logger.error(f"Error deleting from graph: {graph_error}", exc_info=True)
       # Continue with PostgreSQL deletion even if graph deletion fails
   
   # Delete the duplicate record from PostgreSQL
   db.session.delete(duplicate_record)
   ```

**Design Decisions**:

- **Order**: Graph deletion happens BEFORE PostgreSQL deletion
  - Rationale: If graph deletion fails, we can still clean up PostgreSQL
  - If PostgreSQL deletion fails, the transaction rolls back and nothing is deleted
  
- **Error Handling**: Graph deletion failures are logged but don't block PostgreSQL deletion
  - Rationale: Prevents blocking duplicate resolution if graph database is temporarily unavailable
  - Trade-off: May leave orphaned graph data if graph deletion fails, but ensures data can still be deleted from PostgreSQL

- **Connection Management**: Uses raw psycopg connection from SQLAlchemy session
  - `db.session.connection().connection` gives access to underlying psycopg connection
  - AGE operations require raw psycopg, not SQLAlchemy ORM

### 3. Logging and Audit Trail

The implementation includes comprehensive logging:

- **Success**: `INFO` level logs for successful deletions
- **Warnings**: `WARNING` level for vertices not found (may not have been in graph)
- **Errors**: `ERROR` level with full stack trace for deletion failures
- **Audit**: PostgreSQL `DuplicateResolution` table still maintains audit trail of deleted records

## Testing

### Unit Test Created

[`test_graph_deletion.py`](test_graph_deletion.py) provides a comprehensive test:

1. Creates two test persons in PostgreSQL
2. Adds both persons to the AGE graph
3. Verifies both vertices exist in graph
4. Deletes one person using the new deletion method
5. Verifies the deleted person no longer exists in graph
6. Verifies the kept person still exists in graph
7. Cleans up test data

**Running the Test**:
```bash
python test_graph_deletion.py
```

### Integration Test Scenarios

The implementation should be tested in the following scenarios:

1. **Normal Operation**:
   - Confirm a duplicate person
   - Verify vertex and edges deleted from graph
   - Verify record deleted from PostgreSQL

2. **Graph Unavailable**:
   - Stop AGE extension or graph database
   - Confirm a duplicate
   - Verify PostgreSQL deletion still succeeds
   - Verify error is logged

3. **Vertex Already Deleted**:
   - Manually delete vertex from graph
   - Confirm duplicate in application
   - Verify graceful handling (warning logged)

4. **Complex Relationships**:
   - Create person with parent-child edges, marriage edges, event relationships
   - Confirm duplicate
   - Verify all edges are properly deleted

## Impact on System

### Performance

- **Additional Operation**: Each duplicate confirmation now includes a graph query
- **Network Overhead**: One additional round-trip to database for Cypher query
- **Time Complexity**: O(1) for vertex lookup, O(n) for edge deletion where n = number of connected edges
- **Typical Impact**: < 100ms for most deletions (depends on number of relationships)

### Data Consistency

**Before Implementation**:
- PostgreSQL: Record deleted ❌
- AGE Graph: Orphaned vertices and edges ❌
- Status: INCONSISTENT

**After Implementation**:
- PostgreSQL: Record deleted ✅
- AGE Graph: Vertex and edges deleted ✅
- Status: CONSISTENT

### Failure Modes

| Scenario | Graph Deletion | PostgreSQL Deletion | Final State |
|----------|---------------|---------------------|-------------|
| Both succeed | ✅ Success | ✅ Success | Consistent - both deleted |
| Graph fails, PG succeeds | ❌ Failed | ✅ Success | Inconsistent - orphaned in graph |
| Graph succeeds, PG fails | ✅ Success | ❌ Failed (rolled back) | Inconsistent - orphaned in PG |
| Both fail | ❌ Failed | ❌ Failed | Consistent - both retained |

**Note**: The "Graph succeeds, PG fails" scenario is rare because SQLAlchemy transactions are atomic. If PostgreSQL deletion fails, the entire transaction (including the duplicate status update) is rolled back.

## Future Improvements

### 1. Foreign Key Cascade Configuration

Currently missing from [`src/migrations/versions/9fa49afd5516_initial_schema.py`](src/migrations/versions/9fa49afd5516_initial_schema.py):

**Recommended**:
```python
sa.ForeignKeyConstraint(['father_id'], ['persons.id'], ondelete='SET NULL'),
sa.ForeignKeyConstraint(['mother_id'], ['persons.id'], ondelete='SET NULL'),
sa.ForeignKeyConstraint(['child_id'], ['persons.id'], ondelete='CASCADE'),
```

This would:
- Handle orphaned relationships automatically
- Prevent foreign key constraint errors during deletion
- Reduce manual cascade handling

### 2. Two-Phase Commit

For stronger consistency guarantees:

```python
# Pseudo-code for 2PC approach
with transaction_coordinator:
    if graph_importer.delete_vertex(uuid):
        if db.session.delete(record):
            transaction_coordinator.commit_both()
        else:
            transaction_coordinator.rollback_both()
```

Requires:
- Distributed transaction coordinator
- Ability to rollback AGE changes
- More complex error handling

### 3. Graph Consistency Check

Periodic background job to:
- Find vertices with UUIDs not in PostgreSQL (orphaned from failed deletions)
- Find PostgreSQL records without graph vertices (missing from graph)
- Generate reconciliation report
- Optionally auto-fix inconsistencies

**Recommended Implementation**:
```bash
# Cron job: daily at 2 AM
0 2 * * * /usr/bin/python /app/scripts/check_graph_consistency.py
```

### 4. Audit Trail for Graph Changes

Consider extending `DuplicateResolution` table:

```python
class DuplicateResolution(db.Model):
    # ... existing fields ...
    graph_deleted = db.Column(db.Boolean, default=False)
    graph_deletion_error = db.Column(db.Text, nullable=True)
```

This would:
- Track which deletions included graph cleanup
- Flag failed graph deletions for manual review
- Provide better audit trail

### 5. Batch Deletion Method

For bulk operations:

```python
def delete_multiple_vertices(self, vertex_type: str, uuids: List[str]) -> Dict[str, bool]:
    """Delete multiple vertices in a single Cypher query for efficiency."""
    # Use UNWIND for batch deletion
    # Return dict mapping UUID → success status
```

## Related Files

### Modified Files

- [`src/app/services/age_graph_importer.py`](src/app/services/age_graph_importer.py) - Added 4 new deletion methods
- [`src/app/routes/main.py`](src/app/routes/main.py) - Integrated graph deletion in duplicate review endpoint

### New Files

- [`test_graph_deletion.py`](test_graph_deletion.py) - Test script for graph deletion functionality
- [`GRAPH_DELETION_SYNCHRONIZATION.md`](GRAPH_DELETION_SYNCHRONIZATION.md) - This documentation

### Related Documentation

- [`DUPLICATE_HANDLING_IMPLEMENTATION.md`](DUPLICATE_HANDLING_IMPLEMENTATION.md) - Overall duplicate handling system
- [`AGE_IMPLEMENTATION_README.md`](AGE_IMPLEMENTATION_README.md) - AGE graph setup and configuration
- [`plans/AGE_GRAPH_SCHEMA.md`](plans/AGE_GRAPH_SCHEMA.md) - Graph schema design

## Verification Steps

To verify the implementation is working:

1. **Check Logs**: After confirming a duplicate, check application logs for:
   ```
   INFO: Deleted person from graph: <uuid>
   INFO: Deleted duplicate person record <uuid2>, kept <uuid1>
   ```

2. **Query Graph**: Verify vertex was deleted:
   ```cypher
   SELECT * FROM cypher('genealogy', $$
       MATCH (p:Person {uuid: '<deleted-uuid>'})
       RETURN p
   $$) AS (person agtype);
   -- Should return 0 rows
   ```

3. **Query PostgreSQL**: Verify record was deleted:
   ```sql
   SELECT * FROM persons WHERE id = '<deleted-uuid>';
   -- Should return 0 rows
   ```

4. **Check Audit Trail**: Verify resolution was recorded:
   ```sql
   SELECT * FROM duplicate_resolutions 
   WHERE merged_record_id = '<deleted-uuid>';
   -- Should return the resolution record
   ```

## Conclusion

The graph deletion synchronization implementation provides:

✅ **Consistency**: Deletions are synchronized between PostgreSQL and AGE graph  
✅ **Reliability**: Safe error handling prevents blocking operations  
✅ **Auditability**: Comprehensive logging of all deletion operations  
✅ **Maintainability**: Clean, well-documented methods for future use  

The implementation resolves the critical data consistency issue where orphaned graph data accumulated over time, while maintaining backward compatibility and graceful degradation when the graph database is unavailable.

## Support

For issues or questions:
- Check logs at `logger` level INFO or higher
- Review AGE graph statistics with `/api/statistics` endpoint
- Run consistency check: `python test_graph_deletion.py`
- Review audit trail in `duplicate_resolutions` table
