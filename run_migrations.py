#!/usr/bin/env python3
"""
Script to run database migrations directly.
This creates all tables defined in the migration files.
"""
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get database URL
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql+psycopg://postgres:postgres@localhost:5432/korzen')

print(f"Connecting to database: {DATABASE_URL}")

# Create engine
engine = create_engine(DATABASE_URL)

# Import the migration upgrade function
sys.path.insert(0, str(Path(__file__).parent / 'src' / 'migrations' / 'versions'))

from versions import initial_schema as migration_001

print("Running migration 001: initial_schema")
migration_001.upgrade()

print("Checking if migration 002 exists...")
try:
    from versions import add_vector_embeddings as migration_002
    print("Running migration 002: add_vector_embeddings")
    migration_002.upgrade()
except ImportError:
    print("Migration 002 not found, skipping")

print("\nMigrations completed successfully!")
print("\nVerifying tables...")

with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT tablename 
        FROM pg_tables 
        WHERE schemaname = 'public' 
        ORDER BY tablename
    """))
    tables = [row[0] for row in result]
    print(f"Found {len(tables)} tables:")
    for table in tables:
        print(f"  - {table}")
