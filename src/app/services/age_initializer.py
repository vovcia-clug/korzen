"""
AGE (Apache AGE) Database Initializer

This module handles the initialization of the Apache AGE extension and
the genealogy graph, including helper functions. This replaces the need
for Docker init SQL scripts.
"""

import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


class AGEInitializer:
    """Handles initialization of Apache AGE extension and genealogy graph."""

    def __init__(self, db_session):
        """
        Initialize the AGE initializer.

        Args:
            db_session: SQLAlchemy database session or engine
        """
        self.db = db_session

    def initialize_age_extension(self) -> bool:
        """
        Enable the Apache AGE extension and load it.

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info("Initializing Apache AGE extension...")

            # Create AGE extension if it doesn't exist
            self.db.session.execute(text("CREATE EXTENSION IF NOT EXISTS age"))
            logger.info("AGE extension created/verified")

            # Load AGE
            self.db.session.execute(text("LOAD 'age'"))
            logger.info("AGE extension loaded")

            # Set search path
            self.db.session.execute(
                text("SET search_path = ag_catalog, \"$user\", public")
            )
            logger.info("Search path configured for AGE")

            self.db.session.commit()
            return True

        except SQLAlchemyError as e:
            logger.error(f"Error initializing AGE extension: {e}")
            self.db.session.rollback()
            return False

    def create_genealogy_graph(self) -> bool:
        """
        Create the genealogy graph if it doesn't exist.

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info("Creating genealogy graph...")

            # Use DO block to handle "already exists" error gracefully
            sql = text("""
                DO $$
                BEGIN
                    PERFORM ag_catalog.create_graph('genealogy');
                    RAISE NOTICE 'Created genealogy graph';
                EXCEPTION
                    WHEN duplicate_object THEN
                        RAISE NOTICE 'Genealogy graph already exists, skipping creation';
                    WHEN OTHERS THEN
                        RAISE NOTICE 'Error creating graph: %', SQLERRM;
                END
                $$;
            """)

            self.db.session.execute(sql)
            self.db.session.commit()

            # Verify graph was created
            result = self.db.session.execute(
                text("SELECT * FROM ag_catalog.ag_graph WHERE name = 'genealogy'")
            )
            if result.fetchone():
                logger.info("Genealogy graph verified successfully")
                return True
            else:
                logger.warning("Genealogy graph not found after creation attempt")
                return False

        except SQLAlchemyError as e:
            logger.error(f"Error creating genealogy graph: {e}")
            self.db.session.rollback()
            return False

    def create_helper_functions(self) -> bool:
        """
        Create helper functions for working with the genealogy graph.

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info("Creating AGE helper functions...")

            # Helper function to safely execute Cypher queries
            self.db.session.execute(text("""
                CREATE OR REPLACE FUNCTION execute_cypher(
                    graph_name text,
                    query text,
                    params jsonb DEFAULT '{}'::jsonb
                )
                RETURNS TABLE(result agtype) AS $$
                BEGIN
                    RETURN QUERY EXECUTE format(
                        'SELECT * FROM cypher(%L, %L, %L) AS (result agtype)',
                        graph_name,
                        query,
                        params
                    );
                EXCEPTION
                    WHEN OTHERS THEN
                        RAISE NOTICE 'Error executing Cypher query: %', SQLERRM;
                        RETURN;
                END;
                $$ LANGUAGE plpgsql;
            """))

            # Helper function to get vertex by UUID
            self.db.session.execute(text("""
                CREATE OR REPLACE FUNCTION get_person_vertex(person_uuid text)
                RETURNS TABLE(vertex agtype) AS $func$
                BEGIN
                    RETURN QUERY
                    SELECT * FROM cypher('genealogy', $$
                        MATCH (p:Person {uuid: $uuid})
                        RETURN p
                    $$, jsonb_build_object('uuid', person_uuid)) AS (vertex agtype);
                EXCEPTION
                    WHEN OTHERS THEN
                        RAISE NOTICE 'Error getting person vertex: %', SQLERRM;
                        RETURN;
                END;
                $func$ LANGUAGE plpgsql;
            """))

            # Helper function to count vertices by label
            self.db.session.execute(text("""
                CREATE OR REPLACE FUNCTION count_vertices(label text)
                RETURNS bigint AS $$
                DECLARE
                    result bigint;
                BEGIN
                    EXECUTE format(
                        'SELECT count(*)::bigint FROM cypher(''genealogy'', $cypher$
                            MATCH (n:%I)
                            RETURN count(n)
                        $cypher$) AS (count agtype)',
                        label
                    ) INTO result;
                    RETURN result;
                EXCEPTION
                    WHEN OTHERS THEN
                        RAISE NOTICE 'Error counting vertices: %', SQLERRM;
                        RETURN 0;
                END;
                $$ LANGUAGE plpgsql;
            """))

            # Helper function to count edges by type
            self.db.session.execute(text("""
                CREATE OR REPLACE FUNCTION count_edges(edge_type text)
                RETURNS bigint AS $$
                DECLARE
                    result bigint;
                BEGIN
                    EXECUTE format(
                        'SELECT count(*)::bigint FROM cypher(''genealogy'', $cypher$
                            MATCH ()-[r:%I]->()
                            RETURN count(r)
                        $cypher$) AS (count agtype)',
                        edge_type
                    ) INTO result;
                    RETURN result;
                EXCEPTION
                    WHEN OTHERS THEN
                        RAISE NOTICE 'Error counting edges: %', SQLERRM;
                        RETURN 0;
                END;
                $$ LANGUAGE plpgsql;
            """))

            # Helper function to get graph statistics
            self.db.session.execute(text("""
                CREATE OR REPLACE FUNCTION get_graph_statistics()
                RETURNS TABLE(
                    metric text,
                    value bigint
                ) AS $$
                BEGIN
                    RETURN QUERY
                    SELECT 'total_persons'::text, count_vertices('Person');
                    
                    RETURN QUERY
                    SELECT 'total_events'::text, count_vertices('Event');
                    
                    RETURN QUERY
                    SELECT 'total_sources'::text, count_vertices('Source');
                    
                    RETURN QUERY
                    SELECT 'parent_of_edges'::text, count_edges('PARENT_OF');
                    
                    RETURN QUERY
                    SELECT 'married_to_edges'::text, count_edges('MARRIED_TO');
                    
                    RETURN QUERY
                    SELECT 'baptized_in_edges'::text, count_edges('BAPTIZED_IN');
                    
                    RETURN QUERY
                    SELECT 'died_in_edges'::text, count_edges('DIED_IN');
                EXCEPTION
                    WHEN OTHERS THEN
                        RAISE NOTICE 'Error getting graph statistics: %', SQLERRM;
                        RETURN;
                END;
                $$ LANGUAGE plpgsql;
            """))

            self.db.session.commit()
            logger.info("AGE helper functions created successfully")
            return True

        except SQLAlchemyError as e:
            logger.error(f"Error creating helper functions: {e}")
            self.db.session.rollback()
            return False

    def initialize_all(self) -> bool:
        """
        Run all initialization steps in order.

        Returns:
            bool: True if all steps successful, False otherwise
        """
        logger.info("Starting AGE database initialization...")

        steps = [
            ("AGE Extension", self.initialize_age_extension),
            ("Genealogy Graph", self.create_genealogy_graph),
            ("Helper Functions", self.create_helper_functions),
        ]

        for step_name, step_func in steps:
            if not step_func():
                logger.error(f"Failed to initialize {step_name}")
                return False

        logger.info("AGE database initialization completed successfully")
        logger.info("Graph name: genealogy")
        logger.info(
            "Helper functions created: execute_cypher, get_person_vertex, "
            "count_vertices, count_edges, get_graph_statistics"
        )
        return True


def initialize_age_database(db) -> bool:
    """
    Convenience function to initialize AGE database.

    Args:
        db: SQLAlchemy database instance

    Returns:
        bool: True if successful, False otherwise
    """
    initializer = AGEInitializer(db)
    return initializer.initialize_all()
