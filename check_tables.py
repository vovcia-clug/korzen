#!/usr/bin/env python3
"""Check if database tables exist."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from sqlalchemy import create_engine, text

# Get database URL
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql+psycopg://postgres:postgres@localhost:5432/korzen')
if 'db:5432' in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace('db:5432', 'localhost:5432')

print(f"Connecting to: {DATABASE_URL}\n")

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT tablename 
        FROM pg_tables 
        WHERE schemaname = 'public' 
        ORDER BY tablename
    """))
    tables = [row[0] for row in result]
    
    if tables:
        print(f"✓ Found {len(tables)} tables:")
        for table in tables:
            print(f"  - {table}")
    else:
        print("✗ No tables found in the database")
        sys.exit(1)
    
    # Check if persons table exists
    if 'persons' in tables:
        print("\n✓ 'persons' table exists!")
        
        # Check row count
        result = conn.execute(text("SELECT COUNT(*) FROM persons"))
        count = result.scalar()
        print(f"  Contains {count} records")
    else:
        print("\n✗ 'persons' table does NOT exist")
        sys.exit(1)
