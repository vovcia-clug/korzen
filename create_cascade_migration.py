#!/usr/bin/env python3
"""
Script to create a Flask-Migrate migration for adding CASCADE DELETE to person foreign keys.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from app import create_app
from app.extensions import db
from flask_migrate import migrate as flask_migrate_cmd

# Create app
app = create_app()

with app.app_context():
    # Generate migration
    flask_migrate_cmd(message="add_cascade_delete_to_person_fks")
    print("Migration created successfully!")
