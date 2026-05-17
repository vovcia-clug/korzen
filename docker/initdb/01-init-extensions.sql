-- Initialize required PostgreSQL extensions

-- Create AGE extension
CREATE EXTENSION IF NOT EXISTS age;

-- Load AGE into search path
LOAD 'age';
SET search_path = ag_catalog, "$user", public;

-- Create pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;
