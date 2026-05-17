#!/usr/bin/env python3
"""
Fix pgvector extension installation issues.
This script will:
1. Drop and recreate the vector extension
2. Verify the vector type is available
3. Test creating a table with vector columns
"""
import os
import sys
import psycopg

# Get database URL from environment
database_url = os.getenv('DATABASE_URL', 'postgresql+psycopg://postgres:postgres@localhost:5432/korzen')

# Convert SQLAlchemy URL to psycopg connection string
if database_url.startswith('postgresql+psycopg://'):
    conn_string = database_url.replace('postgresql+psycopg://', 'postgresql://')
else:
    conn_string = database_url

print(f"Connecting to database...")
print(f"URL: {conn_string.replace('postgres:postgres', 'postgres:***')}")

try:
    # Connect with autocommit
    conn = psycopg.connect(conn_string, autocommit=True)
    cursor = conn.cursor()
    
    print("\n=== Step 1: Check current extensions ===")
    cursor.execute("SELECT extname, extversion FROM pg_extension ORDER BY extname;")
    extensions = cursor.fetchall()
    print("Installed extensions:")
    for ext in extensions:
        print(f"  - {ext[0]} (version {ext[1]})")
    
    print("\n=== Step 2: Check if vector extension is available ===")
    cursor.execute("""
        SELECT name, default_version, installed_version
        FROM pg_available_extensions 
        WHERE name = 'vector';
    """)
    result = cursor.fetchone()
    if result:
        print(f"Vector extension: name={result[0]}, default_version={result[1]}, installed_version={result[2]}")
    else:
        print("ERROR: Vector extension is NOT available in pg_available_extensions!")
        print("This means pgvector is not properly installed in PostgreSQL.")
        print("\nTo fix this, you need to:")
        print("1. Install pgvector in the PostgreSQL server")
        print("2. Rebuild the database Docker container if using Docker")
        sys.exit(1)
    
    print("\n=== Step 3: Drop existing vector extension (if any) ===")
    try:
        cursor.execute("DROP EXTENSION IF EXISTS vector CASCADE;")
        print("✓ Dropped existing vector extension")
    except Exception as e:
        print(f"Note: {e}")
    
    print("\n=== Step 4: Create vector extension ===")
    try:
        cursor.execute("CREATE EXTENSION vector;")
        print("✓ Created vector extension")
    except Exception as e:
        print(f"ERROR creating extension: {e}")
        sys.exit(1)
    
    print("\n=== Step 5: Verify vector type exists ===")
    cursor.execute("""
        SELECT typname, typnamespace::regnamespace 
        FROM pg_type 
        WHERE typname = 'vector';
    """)
    result = cursor.fetchone()
    if result:
        print(f"✓ Vector type found: {result[0]} in schema {result[1]}")
    else:
        print("ERROR: Vector type not found after extension creation!")
        sys.exit(1)
    
    print("\n=== Step 6: Test creating table with vector column ===")
    try:
        cursor.execute("DROP TABLE IF EXISTS test_vector_table;")
        cursor.execute("""
            CREATE TABLE test_vector_table (
                id SERIAL PRIMARY KEY,
                embedding VECTOR(128)
            );
        """)
        print("✓ Successfully created test table with VECTOR(128) column")
        
        # Insert test data
        test_vector = '[' + ','.join(str(i) for i in range(128)) + ']'
        cursor.execute(
            "INSERT INTO test_vector_table (embedding) VALUES (%s);",
            (test_vector,)
        )
        print("✓ Successfully inserted test vector data")
        
        # Query test data
        cursor.execute("SELECT id, embedding FROM test_vector_table;")
        result = cursor.fetchone()
        if result:
            print(f"✓ Successfully queried vector data: id={result[0]}")
        
        # Clean up
        cursor.execute("DROP TABLE test_vector_table;")
        print("✓ Cleaned up test table")
        
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    
    print("\n=== Step 7: Check search_path ===")
    cursor.execute("SHOW search_path;")
    result = cursor.fetchone()
    if result:
        print(f"Current search_path: {result[0]}")
    
    cursor.close()
    conn.close()
    
    print("\n" + "="*60)
    print("SUCCESS! pgvector extension is properly installed and working.")
    print("="*60)
    print("\nYou can now restart your application.")
    
except Exception as e:
    print(f"\nFATAL ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
