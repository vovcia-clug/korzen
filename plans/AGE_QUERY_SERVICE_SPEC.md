# AGE Graph Query Service Specification

## Overview

This document specifies the graph query service for performing genealogical queries using Apache AGE.

## Service Architecture

```
API Endpoints → GenealogyGraphService → AGE Database
                        ↓
                  Result Formatting
                        ↓
                   JSON Response
```

## File Structure

```
src/app/services/
├── age_graph_importer.py      # Import service (already specified)
├── genealogy_graph_service.py # Query service (this spec)
└── __init__.py                # Package initialization
```

## Implementation

**File:** `src/app/services/genealogy_graph_service.py`

```python
"""
Genealogy Graph Query Service

This module provides high-level query operations for genealogical
data stored in Apache AGE graph database.
"""

import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from psycopg import Connection
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)


class GenealogyGraphService:
    """
    Service for querying genealogical data from AGE graph.
    
    This class provides methods for common genealogical queries such as
    finding ancestors, descendants, siblings, and relationship paths.
    """
    
    def __init__(self, connection: Connection):
        """
        Initialize the service with a database connection.
        
        Args:
            connection: psycopg Connection object (raw connection)
        """
        self.conn = connection
        self.graph_name = 'genealogy'
        self._setup_search_path()
    
    def _setup_search_path(self):
        """Set the search path to include ag_catalog."""
        with self.conn.cursor() as cur:
            cur.execute("SET search_path = ag_catalog, '$user', public;")
            self.conn.commit()
    
    def _parse_agtype_result(self, agtype_value: Any) -> Dict[str, Any]:
        """
        Parse AGE agtype result to Python dictionary.
        
        Args:
            agtype_value: AGE agtype value
            
        Returns:
            Parsed dictionary
        """
        if agtype_value is None:
            return {}
        
        # Convert agtype to string and parse as JSON
        try:
            result_str = str(agtype_value)
            # AGE returns results in a specific format, parse accordingly
            if result_str.startswith('{') or result_str.startswith('['):
                return json.loads(result_str)
            return {'value': result_str}
        except Exception as e:
            logger.warning(f"Error parsing agtype: {e}")
            return {'raw': str(agtype_value)}
    
    def find_ancestors(
        self, 
        person_uuid: str, 
        max_generations: int = 10,
        include_details: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Find all ancestors of a person up to max_generations.
        
        Args:
            person_uuid: UUID of the person
            max_generations: Maximum number of generations to traverse
            include_details: Include full person details or just names
            
        Returns:
            List of ancestor dictionaries with generation information
            
        Example:
            >>> service.find_ancestors('person-uuid', max_generations=5)
            [
                {
                    'uuid': 'parent-uuid',
                    'first_name': 'John',
                    'last_name': 'Smith',
                    'generation': 1,
                    'relationship': 'father'
                },
                ...
            ]
        """
        try:
            with self.conn.cursor() as cur:
                query = f"""
                    SELECT * FROM cypher('{self.graph_name}', $$
                        MATCH path = (descendant:Person {{uuid: $person_uuid}})
                                     <-[r:PARENT_OF*1..{max_generations}]-(ancestor:Person)
                        RETURN ancestor, length(path) as generation, 
                               [rel in relationships(path) | rel.type] as relationship_chain
                        ORDER BY generation
                    $$, %s) AS (ancestor agtype, generation agtype, relationship_chain agtype);
                """
                
                params = json.dumps({'person_uuid': person_uuid})
                cur.execute(query, (params,))
                
                results = []
                for row in cur.fetchall():
                    ancestor_data = self._parse_agtype_result(row[0])
                    generation = int(str(row[1]))
                    rel_chain = self._parse_agtype_result(row[2])
                    
                    result = {
                        'uuid': ancestor_data.get('uuid'),
                        'gedcom_id': ancestor_data.get('gedcom_id'),
                        'first_name': ancestor_data.get('first_name'),
                        'last_name': ancestor_data.get('last_name'),
                        'gender': ancestor_data.get('gender'),
                        'generation': generation,
                        'relationship_chain': rel_chain
                    }
                    
                    if include_details:
                        result.update({
                            'birth_date': ancestor_data.get('birth_date'),
                            'death_date': ancestor_data.get('death_date'),
                            'birth_place': ancestor_data.get('birth_place'),
                            'death_place': ancestor_data.get('death_place')
                        })
                    
                    results.append(result)
                
                return results
                
        except Exception as e:
            logger.error(f"Error finding ancestors for {person_uuid}: {e}")
            return []
    
    def find_descendants(
        self, 
        person_uuid: str, 
        max_generations: int = 10,
        include_details: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Find all descendants of a person up to max_generations.
        
        Args:
            person_uuid: UUID of the person
            max_generations: Maximum number of generations to traverse
            include_details: Include full person details or just names
            
        Returns:
            List of descendant dictionaries with generation information
        """
        try:
            with self.conn.cursor() as cur:
                query = f"""
                    SELECT * FROM cypher('{self.graph_name}', $$
                        MATCH path = (ancestor:Person {{uuid: $person_uuid}})
                                     -[r:PARENT_OF*1..{max_generations}]->(descendant:Person)
                        RETURN descendant, length(path) as generation,
                               [rel in relationships(path) | rel.type] as relationship_chain
                        ORDER BY generation
                    $$, %s) AS (descendant agtype, generation agtype, relationship_chain agtype);
                """
                
                params = json.dumps({'person_uuid': person_uuid})
                cur.execute(query, (params,))
                
                results = []
                for row in cur.fetchall():
                    descendant_data = self._parse_agtype_result(row[0])
                    generation = int(str(row[1]))
                    rel_chain = self._parse_agtype_result(row[2])
                    
                    result = {
                        'uuid': descendant_data.get('uuid'),
                        'gedcom_id': descendant_data.get('gedcom_id'),
                        'first_name': descendant_data.get('first_name'),
                        'last_name': descendant_data.get('last_name'),
                        'gender': descendant_data.get('gender'),
                        'generation': generation,
                        'relationship_chain': rel_chain
                    }
                    
                    if include_details:
                        result.update({
                            'birth_date': descendant_data.get('birth_date'),
                            'death_date': descendant_data.get('death_date'),
                            'birth_place': descendant_data.get('birth_place'),
                            'death_place': descendant_data.get('death_place')
                        })
                    
                    results.append(result)
                
                return results
                
        except Exception as e:
            logger.error(f"Error finding descendants for {person_uuid}: {e}")
            return []
    
    def find_siblings(
        self, 
        person_uuid: str,
        include_half_siblings: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Find all siblings of a person.
        
        Args:
            person_uuid: UUID of the person
            include_half_siblings: Include half-siblings (one shared parent)
            
        Returns:
            List of sibling dictionaries with relationship type
        """
        try:
            with self.conn.cursor() as cur:
                query = f"""
                    SELECT * FROM cypher('{self.graph_name}', $$
                        MATCH (person:Person {{uuid: $person_uuid}})
                              <-[r1:PARENT_OF]-(parent:Person)
                              -[r2:PARENT_OF]->(sibling:Person)
                        WHERE person.uuid <> sibling.uuid
                        RETURN DISTINCT sibling, 
                               collect(DISTINCT parent.uuid) as shared_parents,
                               collect(DISTINCT r1.type) as parent_types
                    $$, %s) AS (sibling agtype, shared_parents agtype, parent_types agtype);
                """
                
                params = json.dumps({'person_uuid': person_uuid})
                cur.execute(query, (params,))
                
                results = []
                for row in cur.fetchall():
                    sibling_data = self._parse_agtype_result(row[0])
                    shared_parents = self._parse_agtype_result(row[1])
                    parent_types = self._parse_agtype_result(row[2])
                    
                    # Determine sibling type
                    num_shared_parents = len(shared_parents) if isinstance(shared_parents, list) else 0
                    sibling_type = 'full' if num_shared_parents >= 2 else 'half'
                    
                    if not include_half_siblings and sibling_type == 'half':
                        continue
                    
                    result = {
                        'uuid': sibling_data.get('uuid'),
                        'gedcom_id': sibling_data.get('gedcom_id'),
                        'first_name': sibling_data.get('first_name'),
                        'last_name': sibling_data.get('last_name'),
                        'gender': sibling_data.get('gender'),
                        'birth_date': sibling_data.get('birth_date'),
                        'sibling_type': sibling_type,
                        'shared_parent_count': num_shared_parents
                    }
                    
                    results.append(result)
                
                return results
                
        except Exception as e:
            logger.error(f"Error finding siblings for {person_uuid}: {e}")
            return []
    
    def find_common_ancestors(
        self, 
        person1_uuid: str, 
        person2_uuid: str,
        max_generations: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Find common ancestors between two people.
        
        Args:
            person1_uuid: UUID of first person
            person2_uuid: UUID of second person
            max_generations: Maximum generations to search
            
        Returns:
            List of common ancestor dictionaries
        """
        try:
            with self.conn.cursor() as cur:
                query = f"""
                    SELECT * FROM cypher('{self.graph_name}', $$
                        MATCH path1 = (p1:Person {{uuid: $person1_uuid}})
                                      <-[:PARENT_OF*1..{max_generations}]-(ancestor:Person)
                        MATCH path2 = (p2:Person {{uuid: $person2_uuid}})
                                      <-[:PARENT_OF*1..{max_generations}]-(ancestor)
                        RETURN DISTINCT ancestor,
                               length(path1) as gen_to_person1,
                               length(path2) as gen_to_person2
                        ORDER BY (length(path1) + length(path2))
                    $$, %s) AS (ancestor agtype, gen1 agtype, gen2 agtype);
                """
                
                params = json.dumps({
                    'person1_uuid': person1_uuid,
                    'person2_uuid': person2_uuid
                })
                cur.execute(query, (params,))
                
                results = []
                for row in cur.fetchall():
                    ancestor_data = self._parse_agtype_result(row[0])
                    gen1 = int(str(row[1]))
                    gen2 = int(str(row[2]))
                    
                    result = {
                        'uuid': ancestor_data.get('uuid'),
                        'gedcom_id': ancestor_data.get('gedcom_id'),
                        'first_name': ancestor_data.get('first_name'),
                        'last_name': ancestor_data.get('last_name'),
                        'gender': ancestor_data.get('gender'),
                        'birth_date': ancestor_data.get('birth_date'),
                        'death_date': ancestor_data.get('death_date'),
                        'generations_to_person1': gen1,
                        'generations_to_person2': gen2,
                        'total_distance': gen1 + gen2
                    }
                    
                    results.append(result)
                
                return results
                
        except Exception as e:
            logger.error(f"Error finding common ancestors: {e}")
            return []
    
    def find_relationship_path(
        self, 
        person1_uuid: str, 
        person2_uuid: str,
        max_hops: int = 15
    ) -> Optional[Dict[str, Any]]:
        """
        Find the shortest relationship path between two people.
        
        Args:
            person1_uuid: UUID of first person
            person2_uuid: UUID of second person
            max_hops: Maximum path length to search
            
        Returns:
            Dictionary with path information or None if no path found
        """
        try:
            with self.conn.cursor() as cur:
                query = f"""
                    SELECT * FROM cypher('{self.graph_name}', $$
                        MATCH path = shortestPath(
                            (p1:Person {{uuid: $person1_uuid}})
                            -[*1..{max_hops}]-
                            (p2:Person {{uuid: $person2_uuid}})
                        )
                        RETURN path, length(path) as path_length,
                               [node in nodes(path) | node.uuid] as node_uuids,
                               [rel in relationships(path) | type(rel)] as relationship_types
                    $$, %s) AS (path agtype, path_length agtype, node_uuids agtype, rel_types agtype);
                """
                
                params = json.dumps({
                    'person1_uuid': person1_uuid,
                    'person2_uuid': person2_uuid
                })
                cur.execute(query, (params,))
                
                row = cur.fetchone()
                if not row:
                    return None
                
                path_length = int(str(row[1]))
                node_uuids = self._parse_agtype_result(row[2])
                rel_types = self._parse_agtype_result(row[3])
                
                return {
                    'path_length': path_length,
                    'node_uuids': node_uuids,
                    'relationship_types': rel_types,
                    'relationship_description': self._describe_relationship(rel_types)
                }
                
        except Exception as e:
            logger.error(f"Error finding relationship path: {e}")
            return None
    
    def _describe_relationship(self, rel_types: List[str]) -> str:
        """
        Generate human-readable relationship description.
        
        Args:
            rel_types: List of relationship types in path
            
        Returns:
            Human-readable description
        """
        if not rel_types:
            return "No relationship"
        
        # Simple descriptions for common patterns
        if len(rel_types) == 1:
            if rel_types[0] == 'PARENT_OF':
                return "Parent-child"
            elif rel_types[0] == 'MARRIED_TO':
                return "Spouse"
            elif rel_types[0] == 'GODPARENT_OF':
                return "Godparent-godchild"
        
        # Count parent relationships
        parent_count = sum(1 for r in rel_types if r == 'PARENT_OF')
        if parent_count == len(rel_types):
            if parent_count == 2:
                return "Grandparent-grandchild"
            elif parent_count == 3:
                return "Great-grandparent-great-grandchild"
            else:
                return f"{parent_count} generations apart"
        
        return f"Related through {len(rel_types)} connections"
    
    def find_spouses(self, person_uuid: str) -> List[Dict[str, Any]]:
        """
        Find all spouses of a person.
        
        Args:
            person_uuid: UUID of the person
            
        Returns:
            List of spouse dictionaries with marriage information
        """
        try:
            with self.conn.cursor() as cur:
                query = f"""
                    SELECT * FROM cypher('{self.graph_name}', $$
                        MATCH (person:Person {{uuid: $person_uuid}})
                              -[m:MARRIED_TO]->(spouse:Person)
                        RETURN spouse, m.date as marriage_date, 
                               m.place as marriage_place, m.gedcom_id as family_id
                    $$, %s) AS (spouse agtype, marriage_date agtype, 
                                marriage_place agtype, family_id agtype);
                """
                
                params = json.dumps({'person_uuid': person_uuid})
                cur.execute(query, (params,))
                
                results = []
                for row in cur.fetchall():
                    spouse_data = self._parse_agtype_result(row[0])
                    marriage_date = str(row[1]) if row[1] else None
                    marriage_place = str(row[2]) if row[2] else None
                    family_id = str(row[3]) if row[3] else None
                    
                    result = {
                        'uuid': spouse_data.get('uuid'),
                        'gedcom_id': spouse_data.get('gedcom_id'),
                        'first_name': spouse_data.get('first_name'),
                        'last_name': spouse_data.get('last_name'),
                        'maiden_name': spouse_data.get('maiden_name'),
                        'gender': spouse_data.get('gender'),
                        'marriage_date': marriage_date,
                        'marriage_place': marriage_place,
                        'family_id': family_id
                    }
                    
                    results.append(result)
                
                return results
                
        except Exception as e:
            logger.error(f"Error finding spouses for {person_uuid}: {e}")
            return []
    
    def find_children(self, person_uuid: str) -> List[Dict[str, Any]]:
        """
        Find all children of a person.
        
        Args:
            person_uuid: UUID of the person
            
        Returns:
            List of child dictionaries
        """
        try:
            with self.conn.cursor() as cur:
                query = f"""
                    SELECT * FROM cypher('{self.graph_name}', $$
                        MATCH (parent:Person {{uuid: $person_uuid}})
                              -[r:PARENT_OF]->(child:Person)
                        RETURN child, r.type as parent_type
                        ORDER BY child.birth_date
                    $$, %s) AS (child agtype, parent_type agtype);
                """
                
                params = json.dumps({'person_uuid': person_uuid})
                cur.execute(query, (params,))
                
                results = []
                for row in cur.fetchall():
                    child_data = self._parse_agtype_result(row[0])
                    parent_type = str(row[1]) if row[1] else None
                    
                    result = {
                        'uuid': child_data.get('uuid'),
                        'gedcom_id': child_data.get('gedcom_id'),
                        'first_name': child_data.get('first_name'),
                        'last_name': child_data.get('last_name'),
                        'gender': child_data.get('gender'),
                        'birth_date': child_data.get('birth_date'),
                        'parent_type': parent_type
                    }
                    
                    results.append(result)
                
                return results
                
        except Exception as e:
            logger.error(f"Error finding children for {person_uuid}: {e}")
            return []
    
    def find_parents(self, person_uuid: str) -> List[Dict[str, Any]]:
        """
        Find parents of a person.
        
        Args:
            person_uuid: UUID of the person
            
        Returns:
            List of parent dictionaries
        """
        try:
            with self.conn.cursor() as cur:
                query = f"""
                    SELECT * FROM cypher('{self.graph_name}', $$
                        MATCH (parent:Person)-[r:PARENT_OF]->(child:Person {{uuid: $person_uuid}})
                        RETURN parent, r.type as parent_type
                    $$, %s) AS (parent agtype, parent_type agtype);
                """
                
                params = json.dumps({'person_uuid': person_uuid})
                cur.execute(query, (params,))
                
                results = []
                for row in cur.fetchall():
                    parent_data = self._parse_agtype_result(row[0])
                    parent_type = str(row[1]) if row[1] else None
                    
                    result = {
                        'uuid': parent_data.get('uuid'),
                        'gedcom_id': parent_data.get('gedcom_id'),
                        'first_name': parent_data.get('first_name'),
                        'last_name': parent_data.get('last_name'),
                        'gender': parent_data.get('gender'),
                        'birth_date': parent_data.get('birth_date'),
                        'death_date': parent_data.get('death_date'),
                        'parent_type': parent_type
                    }
                    
                    results.append(result)
                
                return results
                
        except Exception as e:
            logger.error(f"Error finding parents for {person_uuid}: {e}")
            return []
    
    def get_family_tree(
        self, 
        person_uuid: str,
        generations_up: int = 3,
        generations_down: int = 3
    ) -> Dict[str, Any]:
        """
        Get complete family tree for a person (ancestors and descendants).
        
        Args:
            person_uuid: UUID of the root person
            generations_up: Number of ancestor generations
            generations_down: Number of descendant generations
            
        Returns:
            Dictionary with nodes and edges for visualization
        """
        try:
            # Get ancestors
            ancestors = self.find_ancestors(person_uuid, generations_up, include_details=True)
            
            # Get descendants
            descendants = self.find_descendants(person_uuid, generations_down, include_details=True)
            
            # Get root person
            with self.conn.cursor() as cur:
                query = f"""
                    SELECT * FROM cypher('{self.graph_name}', $$
                        MATCH (p:Person {{uuid: $person_uuid}})
                        RETURN p
                    $$, %s) AS (person agtype);
                """
                params = json.dumps({'person_uuid': person_uuid})
                cur.execute(query, (params,))
                row = cur.fetchone()
                root_person = self._parse_agtype_result(row[0]) if row else {}
            
            # Combine all nodes
            all_nodes = [root_person] + ancestors + descendants
            
            # Get all edges between these nodes
            node_uuids = [n.get('uuid') for n in all_nodes if n.get('uuid')]
            
            edges = []
            with self.conn.cursor() as cur:
                query = f"""
                    SELECT * FROM cypher('{self.graph_name}', $$
                        MATCH (a)-[r]->(b)
                        WHERE a.uuid IN $node_uuids AND b.uuid IN $node_uuids
                        RETURN a.uuid, type(r), b.uuid, properties(r)
                    $$, %s) AS (from_uuid agtype, rel_type agtype, 
                                to_uuid agtype, properties agtype);
                """
                params = json.dumps({'node_uuids': node_uuids})
                cur.execute(query, (params,))
                
                for row in cur.fetchall():
                    edges.append({
                        'from': str(row[0]),
                        'to': str(row[2]),
                        'type': str(row[1]),
                        'properties': self._parse_agtype_result(row[3])
                    })
            
            return {
                'root_person': root_person,
                'nodes': all_nodes,
                'edges': edges,
                'statistics': {
                    'total_nodes': len(all_nodes),
                    'total_edges': len(edges),
                    'ancestor_count': len(ancestors),
                    'descendant_count': len(descendants)
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting family tree for {person_uuid}: {e}")
            return {
                'root_person': {},
                'nodes': [],
                'edges': [],
                'statistics': {}
            }
    
    def get_graph_statistics(self) -> Dict[str, Any]:
        """
        Get overall graph statistics.
        
        Returns:
            Dictionary with various graph metrics
        """
        stats = {}
        
        try:
            with self.conn.cursor() as cur:
                # Total persons
                cur.execute(f"""
                    SELECT count(*) FROM cypher('{self.graph_name}', $$
                        MATCH (p:Person)
                        RETURN count(p)
                    $$) AS (count agtype);
                """)
                stats['total_persons'] = int(str(cur.fetchone()[0]))
                
                # Total relationships
                cur.execute(f"""
                    SELECT count(*) FROM cypher('{self.graph_name}', $$
                        MATCH ()-[r]->()
                        RETURN count(r)
                    $$) AS (count agtype);
                """)
                stats['total_relationships'] = int(str(cur.fetchone()[0]))
                
                # Parent-child relationships
                cur.execute(f"""
                    SELECT count(*) FROM cypher('{self.graph_name}', $$
                        MATCH ()-[r:PARENT_OF]->()
                        RETURN count(r)
                    $$) AS (count agtype);
                """)
                stats['parent_child_relationships'] = int(str(cur.fetchone()[0]))
                
                # Marriages
                cur.execute(f"""
                    SELECT count(*) FROM cypher('{self.graph_name}', $$
                        MATCH ()-[r:MARRIED_TO]->()
                        RETURN count(r)
                    $$) AS (count agtype);
                """)
                stats['marriages'] = int(str(cur.fetchone()[0])) // 2  # Divide by 2 (bidirectional)
                
                # Persons with known birth dates
                cur.execute(f"""
                    SELECT count(*) FROM cypher('{self.graph_name}', $$
                        MATCH (p:Person)
                        WHERE p.birth_date IS NOT NULL
                        RETURN count(p)
                    $$) AS (count agtype);
                """)
                stats['persons_with_birth_dates'] = int(str(cur.fetchone()[0]))
                
                # Persons with known death dates
                cur.execute(f"""
                    SELECT count(*) FROM cypher('{self.graph_name}', $$
                        MATCH (p:Person)
                        WHERE p.death_date IS NOT NULL
                        RETURN count(p)
                    $$) AS (count agtype);
                """)
                stats['persons_with_death_dates'] = int(str(cur.fetchone()[0]))
                
        except Exception as e:
            logger.error(f"Error getting graph statistics: {e}")
        
        return stats
```

## Query Performance Guidelines

### Optimization Tips

1. **Limit Path Length**: Always specify maximum path length
   ```cypher
   MATCH path = (a)-[*1..10]-(b)  // Good
   MATCH path = (a)-[*]-(b)       // Bad (unbounded)
   ```

2. **Use Specific Labels**: Always specify vertex labels
   ```cypher
   MATCH (p:Person {uuid: $id})   // Good
   MATCH (n {uuid: $id})          // Bad (scans all vertices)
   ```

3. **Filter Early**: Apply WHERE clauses early in the query
   ```cypher
   MATCH (p:Person)
   WHERE p.birth_date > '1900-01-01'
   RETURN p
   ```

4. **Use LIMIT**: Always limit result sets for large queries
   ```cypher
   MATCH (p:Person)
   RETURN p
   LIMIT 100
   ```

### Query Timeouts

Set reasonable timeouts for queries:
- Simple queries (ancestors, descendants): 5 seconds
- Complex queries (relationship paths): 30 seconds
- Statistics queries: 60 seconds

## Error Handling

All methods should:
1. Catch exceptions and log errors
2. Return empty results on error (not raise exceptions)
3. Log detailed error information for debugging
4. Return consistent data structures

## Testing Queries

Example test queries to verify functionality:

```python
# Test ancestors
ancestors = service.find_ancestors('person-uuid', max_generations=5)
assert len(ancestors) > 0
assert all('generation' in a for a in ancestors)

# Test descendants
descendants = service.find_descendants('person-uuid', max_generations=5)
assert isinstance(descendants, list)

# Test siblings
siblings = service.find_siblings('person-uuid')
assert isinstance(siblings, list)

# Test relationship path
path = service.find_relationship_path('person1-uuid', 'person2-uuid')
assert path is None or 'path_length' in path
```

## Integration with Flask

Example usage in Flask route:

```python
from flask import jsonify
from app.extensions import db

@app.route('/api/graph/person/<uuid>/ancestors')
def get_ancestors(uuid):
    raw_conn = db.engine.raw_connection()
    service = GenealogyGraphService(raw_conn)
    
    ancestors = service.find_ancestors(uuid, max_generations=10)
    raw_conn.close()
    
    return jsonify({
        'data': ancestors,
        'meta': {
            'count': len(