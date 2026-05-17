#!/usr/bin/env python3
"""
Script to run the CASCADE DELETE migration.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from app import create_app
from flask_migrate import upgrade

# Create app
app = create_app()

with app.app_context():
    print("Running migration to add CASCADE DELETE to person foreign keys...")
    try:
        upgrade()
        print("✓ Migration completed successfully!")
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        raise
