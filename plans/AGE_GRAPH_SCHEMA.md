# AGE Graph Schema Specification

## Overview

This document defines the complete graph schema for storing GEDCOM genealogical data in Apache AGE (A Graph Extension for PostgreSQL).

## Graph Name

```
genealogy
```

## Vertex Types (Labels)

### :Person

Represents an individual person in the genealogical database.

**Properties:**

| Property | Type | Required | Description | Example |
|----------|------|----------|-------------|---------|
| `uuid` | string | Yes | UUID from Person table | "550e8400-e29b-41d4-a716-446655440000" |
| `gedcom_id` | string | No | GEDCOM identifier | "I123" |
| `first_name` | string | No | Given name | "John" |
| `last_name` | string | No | Surname | "Smith" |
| `maiden_name` | string | No | Maiden name (if applicable) | "Johnson" |
| `gender` | string | No | Gender | "M", "F", "Unknown" |
| `birth_date` | string | No | Birth date (ISO format) | "1850-03-15" |
| `death_date` | string | No | Death date (ISO format) | "1920-11-22" |
| `birth_place` | string | No | Place of birth | "Warsaw, Poland" |
| `death_place` | string | No | Place of death | "Krakow, Poland" |
| `occupation` | string | No | Occupation | "Farmer" |

**Cypher Creation Example:**
```cypher
CREATE (p:Person {
    uuid: '550e8400-e29b-41d4-a716-446655440000',
    gedcom_id: 'I123',
    first_name: 'John',
    last_name: 'Smith',
    gender: 'M',
    birth_date: '1850-03-15',
    death_date: '1920-11-22',
    birth_place: 'Warsaw, Poland'
})
```

### :Event

Represents a life event (baptism, death, etc.).

**Properties:**

| Property | Type | Required | Description | Example |
|----------|------|----------|-------------|---------|
| `uuid` | string | Yes | UUID from event table | "660e8400-e29b-41d4-a716-446655440001" |
| `gedcom_id` | string | No | GEDCOM identifier | "I123_BAPM" |
| `event_type` | string | Yes | Type of event | "baptism", "death", "marriage" |
| `date` | string | No | Event date (ISO format) | "1850-04-01" |
| `place` | string | No | Event location | "St. Mary's Church, Warsaw" |
| `parish` | string | No | Parish name | "St. Mary's Parish" |

**Cypher Creation Example:**
```cypher
CREATE (e:Event {
    uuid: '660e8400-e29b-41d4-a716-446655440001',
    gedcom_id: 'I123_BAPM',
    event_type: 'baptism',
    date: '1850-04-01',
    place: 'St. Mary\'s Church, Warsaw',
    parish: 'St. Mary\'s Parish'
})
```

### :Place

Represents a geographic location.

**Properties:**

| Property | Type | Required | Description | Example |
|----------|------|----------|-------------|---------|
| `uuid` | string | Yes | Generated UUID | "770e8400-e29b-41d4-a716-446655440002" |
| `name` | string | Yes | Place name | "Warsaw, Poland" |
| `normalized_name` | string | No | Standardized name | "warsaw_poland" |
| `latitude` | float | No | Latitude | 52.2297 |
| `longitude` | float | No | Longitude | 21.0122 |
| `place_type` | string | No | Type of place | "city", "parish", "village" |

**Cypher Creation Example:**
```cypher
CREATE (pl:Place {
    uuid: '770e8400-e29b-41d4-a716-446655440002',
    name: 'Warsaw, Poland',
    normalized_name: 'warsaw_poland',
    latitude: 52.2297,
    longitude: 21.0122,
    place_type: 'city'
})
```

### :Source

Represents a data source (GEDCOM file, batch import).

**Properties:**

| Property | Type | Required | Description | Example |
|----------|------|----------|-------------|---------|
| `uuid` | string | Yes | UUID from RecordBatch table | "880e8400-e29b-41d4-a716-446655440003" |
| `source_name` | string | Yes | Source identifier | "Habsburg.ged" |
| `import_date` | string | Yes | Import timestamp | "2026-05-16T17:00:00Z" |
| `description` | string | No | Source description | "Habsburg family tree" |

**Cypher Creation Example:**
```cypher
CREATE (s:Source {
    uuid: '880e8400-e29b-41d4-a716-446655440003',
    source_name: 'Habsburg.ged',
    import_date: '2026-05-16T17:00:00Z',
    description: 'Habsburg family tree'
})
```

## Edge Types (Relationships)

### :PARENT_OF

Represents a parent-child biological relationship.

**Direction:** Parent → Child

**Properties:**

| Property | Type | Required | Description | Example |
|----------|------|----------|-------------|---------|
| `type` | string | Yes | Parent type | "father", "mother" |
| `confidence` | string | No | Confidence level | "certain", "probable", "possible" |

**Cypher Creation Example:**
```cypher
MATCH (parent:Person {uuid: 'parent-uuid'})
MATCH (child:Person {uuid: 'child-uuid'})
CREATE (parent)-[r:PARENT_OF {type: 'father'}]->(child)
```

**Query Examples:**
```cypher
// Find all children of a person
MATCH (parent:Person {uuid: $parent_id})-[:PARENT_OF]->(child:Person)
RETURN child

// Find all parents of a person
MATCH (parent:Person)-[:PARENT_OF]->(child:Person {uuid: $child_id})
RETURN parent

// Find all ancestors (up to 5 generations)
MATCH path = (descendant:Person {uuid: $person_id})<-[:PARENT_OF*1..5]-(ancestor:Person)
RETURN ancestor, length(path) as generation
```

### :CHILD_OF

Reverse relationship for bidirectional queries (optional, for optimization).

**Direction:** Child → Parent

**Properties:**

| Property | Type | Required | Description | Example |
|----------|------|----------|-------------|---------|
| `type` | string | Yes | Parent type | "father", "mother" |

**Note:** This is redundant with PARENT_OF but can improve query performance for certain patterns.

### :MARRIED_TO

Represents a marriage relationship (bidirectional).

**Direction:** Spouse ↔ Spouse (create both directions)

**Properties:**

| Property | Type | Required | Description | Example |
|----------|------|----------|-------------|---------|
| `date` | string | No | Marriage date | "1875-06-20" |
| `place` | string | No | Marriage location | "Warsaw Cathedral" |
| `gedcom_id` | string | No | GEDCOM family ID | "F123" |
| `end_date` | string | No | End date (divorce/death) | "1920-11-22" |
| `end_reason` | string | No | Reason for end | "death", "divorce" |

**Cypher Creation Example:**
```cypher
MATCH (spouse1:Person {uuid: 'spouse1-uuid'})
MATCH (spouse2:Person {uuid: 'spouse2-uuid'})
CREATE (spouse1)-[r1:MARRIED_TO {date: '1875-06-20', place: 'Warsaw Cathedral'}]->(spouse2)
CREATE (spouse2)-[r2:MARRIED_TO {date: '1875-06-20', place: 'Warsaw Cathedral'}]->(spouse1)
```

**Query Examples:**
```cypher
// Find all spouses of a person
MATCH (person:Person {uuid: $person_id})-[:MARRIED_TO]->(spouse:Person)
RETURN spouse

// Find all marriages with dates
MATCH (p1:Person)-[m:MARRIED_TO]->(p2:Person)
WHERE m.date IS NOT NULL
RETURN p1, p2, m.date
```

### :BAPTIZED_IN

Links a person to their baptism event.

**Direction:** Person → Event

**Properties:**

| Property | Type | Required | Description | Example |
|----------|------|----------|-------------|---------|
| `date` | string | No | Baptism date | "1850-04-01" |

**Cypher Creation Example:**
```cypher
MATCH (person:Person {uuid: 'person-uuid'})
MATCH (event:Event {uuid: 'event-uuid', event_type: 'baptism'})
CREATE (person)-[r:BAPTIZED_IN {date: '1850-04-01'}]->(event)
```

### :DIED_IN

Links a person to their death event.

**Direction:** Person → Event

**Properties:**

| Property | Type | Required | Description | Example |
|----------|------|----------|-------------|---------|
| `date` | string | No | Death date | "1920-11-22" |

**Cypher Creation Example:**
```cypher
MATCH (person:Person {uuid: 'person-uuid'})
MATCH (event:Event {uuid: 'event-uuid', event_type: 'death'})
CREATE (person)-[r:DIED_IN {date: '1920-11-22'}]->(event)
```

### :GODPARENT_OF

Represents a godparent relationship.

**Direction:** Godparent → Child

**Properties:**

| Property | Type | Required | Description | Example |
|----------|------|----------|-------------|---------|
| `type` | string | Yes | Godparent type | "godfather", "godmother" |
| `baptism_event_id` | string | No | Related baptism event UUID | "event-uuid" |

**Cypher Creation Example:**
```cypher
MATCH (godparent:Person {uuid: 'godparent-uuid'})
MATCH (child:Person {uuid: 'child-uuid'})
CREATE (godparent)-[r:GODPARENT_OF {type: 'godfather'}]->(child)
```

**Query Examples:**
```cypher
// Find all godchildren of a person
MATCH (godparent:Person {uuid: $person_id})-[:GODPARENT_OF]->(godchild:Person)
RETURN godchild

// Find all godparents of a person
MATCH (godparent:Person)-[:GODPARENT_OF]->(person:Person {uuid: $person_id})
RETURN godparent
```

### :WITNESSED

Represents a witness at an event (typically marriage).

**Direction:** Witness → Event

**Properties:**

| Property | Type | Required | Description | Example |
|----------|------|----------|-------------|---------|
| `order` | integer | No | Order in witness list | 1, 2 |
| `role` | string | No | Witness role | "witness", "best_man", "maid_of_honor" |

**Cypher Creation Example:**
```cypher
MATCH (witness:Person {uuid: 'witness-uuid'})
MATCH (event:Event {uuid: 'event-uuid', event_type: 'marriage'})
CREATE (witness)-[r:WITNESSED {order: 1}]->(event)
```

### :LOCATED_AT

Links an event to a place.

**Direction:** Event → Place

**Properties:** None

**Cypher Creation Example:**
```cypher
MATCH (event:Event {uuid: 'event-uuid'})
MATCH (place:Place {name: 'Warsaw, Poland'})
CREATE (event)-[r:LOCATED_AT]->(place)
```

### :FROM_SOURCE

Links any entity to its source.

**Direction:** Entity → Source

**Properties:**

| Property | Type | Required | Description | Example |
|----------|------|----------|-------------|---------|
| `import_date` | string | No | When imported | "2026-05-16T17:00:00Z" |

**Cypher Creation Example:**
```cypher
MATCH (person:Person {uuid: 'person-uuid'})
MATCH (source:Source {uuid: 'source-uuid'})
CREATE (person)-[r:FROM_SOURCE]->(source)
```

## Complete Graph Example

```cypher
// Create persons
CREATE (john:Person {
    uuid: 'john-uuid',
    gedcom_id: 'I1',
    first_name: 'John',
    last_name: 'Smith',
    gender: 'M',
    birth_date: '1820-01-15',
    death_date: '1890-05-20'
})

CREATE (mary:Person {
    uuid: 'mary-uuid',
    gedcom_id: 'I2',
    first_name: 'Mary',
    last_name: 'Smith',
    maiden_name: 'Johnson',
    gender: 'F',
    birth_date: '1825-03-10',
    death_date: '1895-08-15'
})

CREATE (robert:Person {
    uuid: 'robert-uuid',
    gedcom_id: 'I3',
    first_name: 'Robert',
    last_name: 'Smith',
    gender: 'M',
    birth_date: '1850-06-20'
})

// Create relationships
CREATE (john)-[:PARENT_OF {type: 'father'}]->(robert)
CREATE (mary)-[:PARENT_OF {type: 'mother'}]->(robert)
CREATE (john)-[:MARRIED_TO {date: '1845-05-10'}]->(mary)
CREATE (mary)-[:MARRIED_TO {date: '1845-05-10'}]->(john)

// Create baptism event
CREATE (baptism:Event {
    uuid: 'baptism-uuid',
    gedcom_id: 'I3_BAPM',
    event_type: 'baptism',
    date: '1850-07-01',
    parish: 'St. Mary\'s Parish'
})

CREATE (robert)-[:BAPTIZED_IN]->(baptism)

// Create source
CREATE (source:Source {
    uuid: 'source-uuid',
    source_name: 'Smith_Family.ged',
    import_date: '2026-05-16T17:00:00Z'
})

CREATE (john)-[:FROM_SOURCE]->(source)
CREATE (mary)-[:FROM_SOURCE]->(source)
CREATE (robert)-[:FROM_SOURCE]->(source)
```

## Common Query Patterns

### 1. Find All Ancestors

```cypher
MATCH path = (person:Person {uuid: $person_id})<-[:PARENT_OF*1..10]-(ancestor:Person)
RETURN ancestor, length(path) as generation
ORDER BY generation
```

### 2. Find All Descendants

```cypher
MATCH (ancestor:Person {uuid: $person_id})-[:PARENT_OF*1..10]->(descendant:Person)
RETURN descendant
```

### 3. Find Siblings

```cypher
MATCH (person:Person {uuid: $person_id})<-[:PARENT_OF]-(parent:Person)-[:PARENT_OF]->(sibling:Person)
WHERE person.uuid <> sibling.uuid
RETURN DISTINCT sibling
```

### 4. Find Common Ancestors

```cypher
MATCH (p1:Person {uuid: $person1_id})<-[:PARENT_OF*]-(ancestor:Person)
MATCH (p2:Person {uuid: $person2_id})<-[:PARENT_OF*]-(ancestor)
RETURN DISTINCT ancestor
```

### 5. Find Relationship Path

```cypher
MATCH path = shortestPath(
    (p1:Person {uuid: $person1_id})-[*..15]-(p2:Person {uuid: $person2_id})
)
RETURN path
```

### 6. Find All Marriages in a Family

```cypher
MATCH (ancestor:Person {uuid: $person_id})-[:PARENT_OF*0..5]->(descendant:Person)
MATCH (descendant)-[m:MARRIED_TO]->(spouse:Person)
RETURN descendant, spouse, m.date
```

### 7. Find Godparent Network

```cypher
MATCH (person:Person {uuid: $person_id})-[:GODPARENT_OF*1..3]->(godchild:Person)
RETURN godchild
```

### 8. Find All Events for a Person

```cypher
MATCH (person:Person {uuid: $person_id})-[r]->(event:Event)
RETURN event, type(r) as relationship_type
```

### 9. Find People Born in a Place

```cypher
MATCH (person:Person)
WHERE person.birth_place CONTAINS $place_name
RETURN person
```

### 10. Find Family Tree (Complete Subgraph)

```cypher
MATCH path = (root:Person {uuid: $person_id})-[:PARENT_OF|MARRIED_TO*0..5]-(related:Person)
RETURN path
```

## Index Strategy

While AGE doesn't support traditional indexes in the same way as relational databases, we can optimize queries by:

1. **Property Indexing**: AGE internally indexes properties used in WHERE clauses
2. **Label Indexing**: Vertex labels are automatically indexed
3. **Query Optimization**: Use specific labels and properties in MATCH clauses

**Recommended Query Patterns:**
```cypher
// Good: Specific label and property
MATCH (p:Person {uuid: $id})

// Good: Label with WHERE clause
MATCH (p:Person)
WHERE p.birth_date > '1900-01-01'

// Avoid: No label (scans all vertices)
MATCH (n {uuid: $id})
```

## Data Validation Rules

### Person Vertices
- `uuid` must be unique
- `gedcom_id` should be unique within a source
- `gender` must be one of: "M", "F", "Unknown", or null
- Dates must be in ISO format (YYYY-MM-DD)

### Event Vertices
- `uuid` must be unique
- `event_type` must be one of: "baptism", "death", "marriage", "birth"
- `date` must be in ISO format

### Relationships
- `PARENT_OF.type` must be "father" or "mother"
- `MARRIED_TO` should be bidirectional
- No self-relationships (person cannot be parent of themselves)

## Migration from Relational Model

### Mapping Strategy

1. **Person Table → Person Vertex**: Direct 1:1 mapping
2. **BaptismRecord → Event Vertex + Edges**: Create Event vertex, link with BAPTIZED_IN
3. **MarriageRecord → MARRIED_TO Edge**: Create bidirectional edges between spouses
4. **DeathRecord → Event Vertex + Edges**: Create Event vertex, link with DIED_IN
5. **RecordBatch → Source Vertex**: Create Source vertex, link all entities with FROM_SOURCE

### Data Integrity

- Maintain foreign key relationships as edges
- Preserve all relational data (no data loss)
- Graph is additive (doesn't replace relational model)

## Performance Considerations

### Query Complexity Limits

- **Max Path Length**: Limit to 15 hops to prevent infinite loops
- **Result Set Size**: Paginate results for large families
- **Timeout**: Set query timeout to 30 seconds

### Optimization Tips

1. **Use Specific Labels**: Always specify vertex labels in MATCH
2. **Limit Path Length**: Use `*1..N` instead of `*` for variable-length paths
3. **Filter Early**: Apply WHERE clauses as early as possible
4. **Use LIMIT**: Always limit result sets for exploratory queries
5. **Batch Operations**: Import vertices before edges

## Schema Evolution

### Adding New Vertex Types

```cypher
// Example: Add Occupation vertex
CREATE (occ:Occupation {
    uuid: 'occ-uuid',
    name: 'Farmer',
    category: 'Agriculture'
})

// Link to person
MATCH (person:Person {uuid: 'person-uuid'})
MATCH (occ:Occupation {name: 'Farmer'})
CREATE (person)-[:HAS_OCCUPATION]->(occ)
```

### Adding New Edge Types

```cypher
// Example: Add SIBLING relationship
MATCH (p1:Person {uuid: 'person1-uuid'})
MATCH (p2:Person {uuid: 'person2-uuid'})
CREATE (p1)-[:SIBLING {type: 'full'}]->(p2)
CREATE (p2)-[:SIBLING {type: 'full'}]->(p1)
```

## Conclusion

This schema provides a flexible, performant foundation for storing and querying genealogical data. The graph structure naturally represents family relationships and enables powerful traversal queries that would be complex or impossible in a pure relational model.
