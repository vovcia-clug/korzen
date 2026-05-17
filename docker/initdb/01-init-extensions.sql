-- Initialize required PostgreSQL extensions

-- Create AGE extension
CREATE EXTENSION IF NOT EXISTS age;

-- Load AGE into search path
LOAD 'age';
SET search_path = ag_catalog, "$user", public;

-- Create pgvector extension in public schema (not ag_catalog)
CREATE EXTENSION IF NOT EXISTS vector SCHEMA public;
