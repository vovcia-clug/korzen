#!/usr/bin/env python3
"""
Script to verify CASCADE DELETE constraints were applied correctly.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from app import create_app
from app.extensions import db

# Create app
app = create_app()

with app.app_context():
    print("Verifying CASCADE DELETE constraints on person foreign keys...\n")
    
    # Query to check foreign key constraints
    query = """
    SELECT 
        tc.table_name, 
        kcu.column_name,
        rc.delete_rule
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu 
        ON tc.constraint_name = kcu.constraint_name
    JOIN information_schema.referential_constraints rc
        ON tc.constraint_name = rc.constraint_name
    WHERE tc.constraint_type = 'FOREIGN KEY'
        AND kcu.column_name IN ('child_id', 'father_id', 'mother_id', 'spouse1_id', 'spouse2_id', 'deceased_id', 'godparent_id', 'witness_id')
        AND tc.table_schema = 'public'
    ORDER BY tc.table_name, kcu.column_name;
    """
    
    result = db.session.execute(db.text(query))
    rows = result.fetchall()
    
    print(f"{'Table':<30} {'Column':<20} {'Delete Rule':<15}")
    print("-" * 65)
    
    cascade_count = 0
    no_action_count = 0
    
    for row in rows:
        table_name, column_name, delete_rule = row
        print(f"{table_name:<30} {column_name:<20} {delete_rule:<15}")
        
        if delete_rule == 'CASCADE':
            cascade_count += 1
        elif delete_rule == 'NO ACTION':
            no_action_count += 1
    
    print("\n" + "=" * 65)
    print(f"Summary:")
    print(f"  ✓ CASCADE DELETE: {cascade_count} foreign keys")
    print(f"  ✗ NO ACTION: {no_action_count} foreign keys")
    
    if no_action_count == 0:
        print("\n✓ All person foreign keys now have CASCADE DELETE enabled!")
    else:
        print("\n✗ Some foreign keys still have NO ACTION. Migration may need adjustment.")
