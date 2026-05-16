-- AGE Genealogy Graph Initialization Script
-- This script creates the genealogy graph and helper functions

-- Set search path to include ag_catalog
SET search_path = ag_catalog, "$user", public;

-- Create the genealogy graph
-- Use DO block to handle "already exists" error gracefully
DO $$
BEGIN
    PERFORM create_graph('genealogy');
    RAISE NOTICE 'Created genealogy graph';
EXCEPTION
    WHEN duplicate_object THEN
        RAISE NOTICE 'Genealogy graph already exists, skipping creation';
    WHEN OTHERS THEN
        RAISE NOTICE 'Error creating graph: %', SQLERRM;
END
$$;

-- Verify graph was created
SELECT * FROM ag_catalog.ag_graph WHERE name = 'genealogy';

-- Create helper function to safely execute Cypher queries
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

-- Create helper function to get vertex by UUID
CREATE OR REPLACE FUNCTION get_person_vertex(person_uuid text)
RETURNS TABLE(vertex agtype) AS $$
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
$$ LANGUAGE plpgsql;

-- Create helper function to count vertices by label
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

-- Create helper function to count edges by type
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

-- Create helper function to get graph statistics
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

-- Log completion
DO $$
BEGIN
    RAISE NOTICE 'AGE genealogy graph initialization complete';
    RAISE NOTICE 'Graph name: genealogy';
    RAISE NOTICE 'Helper functions created: execute_cypher, get_person_vertex, count_vertices, count_edges, get_graph_statistics';
END
$$;
