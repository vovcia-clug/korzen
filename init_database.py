#!/usr/bin/env python3
"""
Script to initialize the database by creating all tables.
This uses SQLAlchemy's create_all() method to create tables from models.
"""
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from sqlalchemy import create_engine, text, inspect
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get database URL - use localhost when running from host machine
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql+psycopg://postgres:postgres@localhost:5432/korzen')
# Override if using docker internal hostname
if 'db:5432' in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace('db:5432', 'localhost:5432')

print(f"Connecting to database: {DATABASE_URL}")

# Create engine
engine = create_engine(DATABASE_URL)

# First, ensure the vector extension is installed
print("\nEnsuring pgvector extension is installed...")
with engine.connect() as conn:
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
    conn.commit()
    print("✓ pgvector extension ready")

# Import models to register them with SQLAlchemy
from app.extensions import db
from app import models

print("\nCreating all tables from models...")

# Get metadata from models
from sqlalchemy import MetaData
metadata = MetaData()

# Reflect existing tables
inspector = inspect(engine)
existing_tables = inspector.get_table_names()
print(f"\nExisting tables: {existing_tables}")

# Import all model classes to ensure they're registered
from app.models import (
    RecordBatch, GenealogicalRecord, UploadedFile, SocialStatus,
    Person, BaptismRecord, MarriageRecord, DeathRecord,
    GodparentRelationship, WitnessRelationship,
    DuplicateCandidate, DuplicateResolution
)

# Create tables using the db.Model.metadata
print("\nCreating tables...")
db.Model.metadata.create_all(bind=engine)

print("\nVerifying tables...")
with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT tablename 
        FROM pg_tables 
        WHERE schemaname = 'public' 
        ORDER BY tablename
    """))
    tables = [row[0] for row in result]
    print(f"\nFound {len(tables)} tables:")
    for table in tables:
        print(f"  ✓ {table}")

print("\n✅ Database initialization completed successfully!")
