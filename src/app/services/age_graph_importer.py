"""
AGE Graph Importer Service

This module provides functionality to import genealogical data
into Apache AGE graph database.
"""

import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from psycopg import Connection

logger = logging.getLogger(__name__)


class AgeGraphImporter:
    """
    Service for importing genealogical data into Apache AGE graph.
    
    This class handles the creation of vertices (Person, Event, Source)
    and edges (PARENT_OF, MARRIED_TO, etc.) in the AGE graph.
    """
    
    def __init__(self, connection: Connection):
        """
        Initialize the importer with a database connection.
        
        Args:
            connection: psycopg Connection object (raw connection, not SQLAlchemy)
        """
        self.conn = connection
        self.graph_name = 'genealogy'
        self._setup_search_path()
    
    def _setup_search_path(self):
        """Set the search path to include ag_catalog."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("SET search_path = ag_catalog, '$user', public;")
                self.conn.commit()
        except Exception as e:
            logger.warning(f"Could not set search path: {e}")
            self.conn.rollback()
    
    def create_graph_if_not_exists(self):
        """
        Create the genealogy graph if it doesn't exist.
        
        This is idempotent - safe to call multiple times.
        """
        try:
            with self.conn.cursor() as cur:
                # Check if graph exists
                cur.execute("""
                    SELECT * FROM ag_catalog.ag_graph 
                    WHERE name = %s;
                """, (self.graph_name,))
                
                if cur.fetchone() is None:
                    # Graph doesn't exist, create it
                    cur.execute("""
                        SELECT create_graph(%s);
                    """, (self.graph_name,))
                    self.conn.commit()
                    logger.info(f"Created graph: {self.graph_name}")
                else:
                    logger.info(f"Graph already exists: {self.graph_name}")
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error creating graph: {e}")
            raise
    
    def vertex_exists(self, label: str, uuid: str) -> bool:
        """
        Check if a vertex with given label and UUID exists.
        
        Args:
            label: Vertex label (e.g., 'Person', 'Event')
            uuid: UUID to check
            
        Returns:
            True if vertex exists, False otherwise
        """
        try:
            with self.conn.cursor() as cur:
                query = f"""
                    SELECT * FROM cypher('{self.graph_name}', $$
                        MATCH (n:{label} {{uuid: $uuid}})
                        RETURN n
                    $$, %s) AS (vertex agtype);
                """
                params = json.dumps({'uuid': uuid})
                cur.execute(query, (params,))
                result = cur.fetchone()
                return result is not None
        except Exception as e:
            logger.warning(f"Error checking vertex existence: {e}")
            return False
    
    def create_person_vertex(self, uuid: str, properties: Dict[str, Any]) -> bool:
        """
        Create a Person vertex in the graph.
        
        Args:
            uuid: Person UUID from relational database
            properties: Dictionary of person properties
            
        Returns:
            True if created successfully, False if already exists or error
        """
        # Check if vertex already exists
        if self.vertex_exists('Person', uuid):
            logger.debug(f"Person vertex already exists: {uuid}")
            return False
        
        try:
            with self.conn.cursor() as cur:
                # Build Cypher query
                query = f"""
                    SELECT * FROM cypher('{self.graph_name}', $$
                        CREATE (p:Person {{
                            uuid: $uuid,
                            gedcom_id: $gedcom_id,
                            first_name: $first_name,
                            last_name: $last_name,
                            maiden_name: $maiden_name,
                            gender: $gender,
                            birth_date: $birth_date,
                            death_date: $death_date,
                            birth_place: $birth_place,
                            death_place: $death_place,
                            occupation: $occupation
                        }})
                        RETURN p
                    $$, %s) AS (person agtype);
                """
                
                # Prepare parameters (convert None to null, dates to strings)
                params = {
                    'uuid': uuid,
                    'gedcom_id': properties.get('gedcom_id'),
                    'first_name': properties.get('first_name'),
                    'last_name': properties.get('last_name'),
                    'maiden_name': properties.get('maiden_name'),
                    'gender': properties.get('gender'),
                    'birth_date': str(properties['birth_date']) if properties.get('birth_date') else None,
                    'death_date': str(properties['death_date']) if properties.get('death_date') else None,
                    'birth_place': properties.get('birth_place'),
                    'death_place': properties.get('death_place'),
                    'occupation': properties.get('occupation')
                }
                
                cur.execute(query, (json.dumps(params),))
                self.conn.commit()
                logger.debug(f"Created Person vertex: {uuid}")
                return True
                
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error creating Person vertex {uuid}: {e}")
            return False
    
    def create_event_vertex(self, uuid: str, properties: Dict[str, Any]) -> bool:
        """
        Create an Event vertex in the graph.
        
        Args:
            uuid: Event UUID
            properties: Dictionary of event properties
            
        Returns:
            True if created successfully, False otherwise
        """
        if self.vertex_exists('Event', uuid):
            logger.debug(f"Event vertex already exists: {uuid}")
            return False
        
        try:
            with self.conn.cursor() as cur:
                query = f"""
                    SELECT * FROM cypher('{self.graph_name}', $$
                        CREATE (e:Event {{
                            uuid: $uuid,
                            gedcom_id: $gedcom_id,
                            event_type: $event_type,
                            date: $date,
                            place: $place,
                            parish: $parish
                        }})
                        RETURN e
                    $$, %s) AS (event agtype);
                """
                
                params = {
                    'uuid': uuid,
                    'gedcom_id': properties.get('gedcom_id'),
                    'event_type': properties.get('event_type'),
                    'date': str(properties['date']) if properties.get('date') else None,
                    'place': properties.get('place'),
                    'parish': properties.get('parish')
                }
                
                cur.execute(query, (json.dumps(params),))
                self.conn.commit()
                logger.debug(f"Created Event vertex: {uuid}")
                return True
                
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error creating Event vertex {uuid}: {e}")
            return False
    
    def create_source_vertex(self, uuid: str, properties: Dict[str, Any]) -> bool:
        """
        Create a Source vertex in the graph.
        
        Args:
            uuid: Source UUID (batch_id)
            properties: Dictionary of source properties
            
        Returns:
            True if created successfully, False otherwise
        """
        if self.vertex_exists('Source', uuid):
            logger.debug(f"Source vertex already exists: {uuid}")
            return False
        
        try:
            with self.conn.cursor() as cur:
                query = f"""
                    SELECT * FROM cypher('{self.graph_name}', $$
                        CREATE (s:Source {{
                            uuid: $uuid,
                            source_name: $source_name,
                            import_date: $import_date,
                            description: $description
                        }})
                        RETURN s
                    $$, %s) AS (source agtype);
                """
                
                params = {
                    'uuid': uuid,
                    'source_name': properties.get('source_name'),
                    'import_date': properties.get('import_date', datetime.utcnow().isoformat()),
                    'description': properties.get('description')
                }
                
                cur.execute(query, (json.dumps(params),))
                self.conn.commit()
                logger.debug(f"Created Source vertex: {uuid}")
                return True
                
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error creating Source vertex {uuid}: {e}")
            return False
    
    def edge_exists(self, edge_type: str, from_uuid: str, to_uuid: str) -> bool:
        """
        Check if an edge exists between two vertices.
        
        Args:
            edge_type: Edge type (e.g., 'PARENT_OF', 'MARRIED_TO')
            from_uuid: Source vertex UUID
            to_uuid: Target vertex UUID
            
        Returns:
            True if edge exists, False otherwise
        """
        try:
            with self.conn.cursor() as cur:
                query = f"""
                    SELECT * FROM cypher('{self.graph_name}', $$
                        MATCH (a {{uuid: $from_uuid}})-[r:{edge_type}]->(b {{uuid: $to_uuid}})
                        RETURN r
                    $$, %s) AS (edge agtype);
                """
                params = json.dumps({'from_uuid': from_uuid, 'to_uuid': to_uuid})
                cur.execute(query, (params,))
                result = cur.fetchone()
                return result is not None
        except Exception as e:
            logger.warning(f"Error checking edge existence: {e}")
            return False
    
    def create_parent_child_edge(
        self, 
        parent_uuid: str, 
        child_uuid: str, 
        parent_type: str
    ) -> bool:
        """
        Create a PARENT_OF edge between parent and child.
        
        Args:
            parent_uuid: Parent person UUID
            child_uuid: Child person UUID
            parent_type: 'father' or 'mother'
            
        Returns:
            True if created successfully, False otherwise
        """
        if self.edge_exists('PARENT_OF', parent_uuid, child_uuid):
            logger.debug(f"PARENT_OF edge already exists: {parent_uuid} -> {child_uuid}")
            return False
        
        try:
            with self.conn.cursor() as cur:
                query = f"""
                    SELECT * FROM cypher('{self.graph_name}', $$
                        MATCH (parent:Person {{uuid: $parent_uuid}})
                        MATCH (child:Person {{uuid: $child_uuid}})
                        CREATE (parent)-[r:PARENT_OF {{type: $parent_type}}]->(child)
                        RETURN r
                    $$, %s) AS (edge agtype);
                """
                
                params = {
                    'parent_uuid': parent_uuid,
                    'child_uuid': child_uuid,
                    'parent_type': parent_type
                }
                
                cur.execute(query, (json.dumps(params),))
                self.conn.commit()
                logger.debug(f"Created PARENT_OF edge: {parent_uuid} -> {child_uuid} ({parent_type})")
                return True
                
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error creating PARENT_OF edge: {e}")
            return False
    
    def create_marriage_edge(
        self, 
        spouse1_uuid: str, 
        spouse2_uuid: str, 
        marriage_date: Optional[str] = None,
        marriage_place: Optional[str] = None,
        gedcom_id: Optional[str] = None
    ) -> bool:
        """
        Create bidirectional MARRIED_TO edges between spouses.
        
        Args:
            spouse1_uuid: First spouse UUID
            spouse2_uuid: Second spouse UUID
            marriage_date: Marriage date (ISO format string)
            marriage_place: Marriage location
            gedcom_id: GEDCOM family ID
            
        Returns:
            True if created successfully, False otherwise
        """
        # Check if either direction exists
        if (self.edge_exists('MARRIED_TO', spouse1_uuid, spouse2_uuid) or
            self.edge_exists('MARRIED_TO', spouse2_uuid, spouse1_uuid)):
            logger.debug(f"MARRIED_TO edge already exists: {spouse1_uuid} <-> {spouse2_uuid}")
            return False
        
        try:
            with self.conn.cursor() as cur:
                query = f"""
                    SELECT * FROM cypher('{self.graph_name}', $$
                        MATCH (s1:Person {{uuid: $spouse1_uuid}})
                        MATCH (s2:Person {{uuid: $spouse2_uuid}})
                        CREATE (s1)-[r1:MARRIED_TO {{
                            date: $marriage_date,
                            place: $marriage_place,
                            gedcom_id: $gedcom_id
                        }}]->(s2)
                        CREATE (s2)-[r2:MARRIED_TO {{
                            date: $marriage_date,
                            place: $marriage_place,
                            gedcom_id: $gedcom_id
                        }}]->(s1)
                        RETURN r1, r2
                    $$, %s) AS (edge1 agtype, edge2 agtype);
                """
                
                params = {
                    'spouse1_uuid': spouse1_uuid,
                    'spouse2_uuid': spouse2_uuid,
                    'marriage_date': marriage_date,
                    'marriage_place': marriage_place,
                    'gedcom_id': gedcom_id
                }
                
                cur.execute(query, (json.dumps(params),))
                self.conn.commit()
                logger.debug(f"Created MARRIED_TO edges: {spouse1_uuid} <-> {spouse2_uuid}")
                return True
                
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error creating MARRIED_TO edges: {e}")
            return False
    
    def create_baptized_in_edge(
        self, 
        person_uuid: str, 
        event_uuid: str,
        date: Optional[str] = None
    ) -> bool:
        """
        Create a BAPTIZED_IN edge from person to baptism event.
        
        Args:
            person_uuid: Person UUID
            event_uuid: Baptism event UUID
            date: Baptism date
            
        Returns:
            True if created successfully, False otherwise
        """
        if self.edge_exists('BAPTIZED_IN', person_uuid, event_uuid):
            logger.debug(f"BAPTIZED_IN edge already exists: {person_uuid} -> {event_uuid}")
            return False
        
        try:
            with self.conn.cursor() as cur:
                query = f"""
                    SELECT * FROM cypher('{self.graph_name}', $$
                        MATCH (person:Person {{uuid: $person_uuid}})
                        MATCH (event:Event {{uuid: $event_uuid}})
                        CREATE (person)-[r:BAPTIZED_IN {{date: $date}}]->(event)
                        RETURN r
                    $$, %s) AS (edge agtype);
                """
                
                params = {
                    'person_uuid': person_uuid,
                    'event_uuid': event_uuid,
                    'date': date
                }
                
                cur.execute(query, (json.dumps(params),))
                self.conn.commit()
                logger.debug(f"Created BAPTIZED_IN edge: {person_uuid} -> {event_uuid}")
                return True
                
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error creating BAPTIZED_IN edge: {e}")
            return False
    
    def create_died_in_edge(
        self, 
        person_uuid: str, 
        event_uuid: str,
        date: Optional[str] = None
    ) -> bool:
        """
        Create a DIED_IN edge from person to death event.
        
        Args:
            person_uuid: Person UUID
            event_uuid: Death event UUID
            date: Death date
            
        Returns:
            True if created successfully, False otherwise
        """
        if self.edge_exists('DIED_IN', person_uuid, event_uuid):
            logger.debug(f"DIED_IN edge already exists: {person_uuid} -> {event_uuid}")
            return False
        
        try:
            with self.conn.cursor() as cur:
                query = f"""
                    SELECT * FROM cypher('{self.graph_name}', $$
                        MATCH (person:Person {{uuid: $person_uuid}})
                        MATCH (event:Event {{uuid: $event_uuid}})
                        CREATE (person)-[r:DIED_IN {{date: $date}}]->(event)
                        RETURN r
                    $$, %s) AS (edge agtype);
                """
                
                params = {
                    'person_uuid': person_uuid,
                    'event_uuid': event_uuid,
                    'date': date
                }
                
                cur.execute(query, (json.dumps(params),))
                self.conn.commit()
                logger.debug(f"Created DIED_IN edge: {person_uuid} -> {event_uuid}")
                return True
                
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error creating DIED_IN edge: {e}")
            return False
    
    def create_godparent_edge(
        self, 
        godparent_uuid: str, 
        child_uuid: str,
        godparent_type: str
    ) -> bool:
        """
        Create a GODPARENT_OF edge from godparent to child.
        
        Args:
            godparent_uuid: Godparent person UUID
            child_uuid: Child person UUID
            godparent_type: 'godfather' or 'godmother'
            
        Returns:
            True if created successfully, False otherwise
        """
        if self.edge_exists('GODPARENT_OF', godparent_uuid, child_uuid):
            logger.debug(f"GODPARENT_OF edge already exists: {godparent_uuid} -> {child_uuid}")
            return False
        
        try:
            with self.conn.cursor() as cur:
                query = f"""
                    SELECT * FROM cypher('{self.graph_name}', $$
                        MATCH (godparent:Person {{uuid: $godparent_uuid}})
                        MATCH (child:Person {{uuid: $child_uuid}})
                        CREATE (godparent)-[r:GODPARENT_OF {{type: $godparent_type}}]->(child)
                        RETURN r
                    $$, %s) AS (edge agtype);
                """
                
                params = {
                    'godparent_uuid': godparent_uuid,
                    'child_uuid': child_uuid,
                    'godparent_type': godparent_type
                }
                
                cur.execute(query, (json.dumps(params),))
                self.conn.commit()
                logger.debug(f"Created GODPARENT_OF edge: {godparent_uuid} -> {child_uuid}")
                return True
                
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error creating GODPARENT_OF edge: {e}")
            return False
    
    def create_from_source_edge(
        self, 
        entity_uuid: str, 
        source_uuid: str
    ) -> bool:
        """
        Create a FROM_SOURCE edge from any entity to source.
        
        Args:
            entity_uuid: Entity UUID (person, event, etc.)
            source_uuid: Source UUID (batch_id)
            
        Returns:
            True if created successfully, False otherwise
        """
        if self.edge_exists('FROM_SOURCE', entity_uuid, source_uuid):
            logger.debug(f"FROM_SOURCE edge already exists: {entity_uuid} -> {source_uuid}")
            return False
        
        try:
            with self.conn.cursor() as cur:
                query = f"""
                    SELECT * FROM cypher('{self.graph_name}', $$
                        MATCH (entity {{uuid: $entity_uuid}})
                        MATCH (source:Source {{uuid: $source_uuid}})
                        CREATE (entity)-[r:FROM_SOURCE]->(source)
                        RETURN r
                    $$, %s) AS (edge agtype);
                """
                
                params = {
                    'entity_uuid': entity_uuid,
                    'source_uuid': source_uuid
                }
                
                cur.execute(query, (json.dumps(params),))
                self.conn.commit()
                logger.debug(f"Created FROM_SOURCE edge: {entity_uuid} -> {source_uuid}")
                return True
                
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error creating FROM_SOURCE edge: {e}")
            return False
    
    def get_statistics(self) -> Dict[str, int]:
        """
        Get graph statistics (vertex and edge counts).
        
        Returns:
            Dictionary with counts for each vertex and edge type
        """
        stats = {}
        
        try:
            with self.conn.cursor() as cur:
                # Count Person vertices
                cur.execute(f"""
                    SELECT count(*) FROM cypher('{self.graph_name}', $$
                        MATCH (p:Person)
                        RETURN count(p)
                    $$) AS (count agtype);
                """)
                result = cur.fetchone()
                stats['persons'] = int(str(result[0])) if result else 0
                
                # Count Event vertices
                cur.execute(f"""
                    SELECT count(*) FROM cypher('{self.graph_name}', $$
                        MATCH (e:Event)
                        RETURN count(e)
                    $$) AS (count agtype);
                """)
                result = cur.fetchone()
                stats['events'] = int(str(result[0])) if result else 0
                
                # Count Source vertices
                cur.execute(f"""
                    SELECT count(*) FROM cypher('{self.graph_name}', $$
                        MATCH (s:Source)
                        RETURN count(s)
                    $$) AS (count agtype);
                """)
                result = cur.fetchone()
                stats['sources'] = int(str(result[0])) if result else 0
                
                # Count PARENT_OF edges
                cur.execute(f"""
                    SELECT count(*) FROM cypher('{self.graph_name}', $$
                        MATCH ()-[r:PARENT_OF]->()
                        RETURN count(r)
                    $$) AS (count agtype);
                """)
                result = cur.fetchone()
                stats['parent_of_edges'] = int(str(result[0])) if result else 0
                
                # Count MARRIED_TO edges
                cur.execute(f"""
                    SELECT count(*) FROM cypher('{self.graph_name}', $$
                        MATCH ()-[r:MARRIED_TO]->()
                        RETURN count(r)
                    $$) AS (count agtype);
                """)
                result = cur.fetchone()
                stats['married_to_edges'] = int(str(result[0])) if result else 0
                
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
        
        return stats
