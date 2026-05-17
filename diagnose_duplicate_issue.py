#!/usr/bin/env python3
"""
Comprehensive diagnostic script to investigate why duplicates still appear
after implementing CASCADE DELETE and auto-merge functionality.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from app import create_app
from app.extensions import db
from sqlalchemy import text

def main():
    app = create_app()
    
    with app.app_context():
        print("=" * 80)
        print("DUPLICATE DELETION DIAGNOSTIC REPORT")
        print("=" * 80)
        
        # 1. Check migration status
        print("\n1. MIGRATION STATUS")
        print("-" * 80)
        result = db.session.execute(text("SELECT version_num FROM alembic_version;"))
        version = result.fetchone()
        print(f"Current migration version: {version[0] if version else 'None'}")
        print(f"Expected version: ce299e9dbdee (CASCADE DELETE migration)")
        
        # 2. Check foreign key constraints
        print("\n2. FOREIGN KEY CONSTRAINTS (CASCADE DELETE)")
        print("-" * 80)
        result = db.session.execute(text("""
            SELECT 
                tc.table_name,
                kcu.column_name,
                tc.constraint_name,
                rc.delete_rule
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu 
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.referential_constraints rc 
                ON tc.constraint_name = rc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
            AND kcu.column_name = 'person_id'
            ORDER BY tc.table_name;
        """))
        constraints = result.fetchall()
        has_cascade = False
        for row in constraints:
            print(f"Table: {row[0]:20} Column: {row[1]:15} Delete Rule: {row[3]}")
            if row[3] == 'CASCADE':
                has_cascade = True
        
        if not has_cascade:
            print("\n⚠️  WARNING: No CASCADE DELETE constraints found!")
        else:
            print("\n✓ CASCADE DELETE constraints are present")
        
        # 3. Check for duplicate persons
        print("\n3. DUPLICATE PERSONS IN DATABASE")
        print("-" * 80)
        result = db.session.execute(text("""
            SELECT 
                given_name, 
                surname, 
                birth_date,
                COUNT(*) as count,
                STRING_AGG(id::text, ', ') as ids
            FROM persons
            WHERE surname LIKE '%Kennedy%' OR surname LIKE '%Fitzgerald%'
            GROUP BY given_name, surname, birth_date
            HAVING COUNT(*) > 1
            ORDER BY count DESC
            LIMIT 10;
        """))
        duplicates = result.fetchall()
        if duplicates:
            print(f"Found {len(duplicates)} sets of duplicates:")
            for row in duplicates:
                print(f"  {row[0]} {row[1]} (b. {row[2]}): {row[3]} records (IDs: {row[4]})")
        else:
            print("✓ No duplicates found")
        
        # 4. Check total persons
        print("\n4. PERSON COUNTS")
        print("-" * 80)
        result = db.session.execute(text("""
            SELECT COUNT(*) 
            FROM persons 
            WHERE surname LIKE '%Kennedy%' OR surname LIKE '%Fitzgerald%';
        """))
        kennedy_count = result.scalar()
        result = db.session.execute(text("SELECT COUNT(*) FROM persons;"))
        total_count = result.scalar()
        print(f"Kennedy/Fitzgerald persons: {kennedy_count}")
        print(f"Total persons: {total_count}")
        
        # 5. Check for orphaned records that should have been deleted
        print("\n5. ORPHANED RECORDS CHECK")
        print("-" * 80)
        
        # Check marriages with deleted persons
        result = db.session.execute(text("""
            SELECT COUNT(*) 
            FROM marriages m
            WHERE NOT EXISTS (SELECT 1 FROM persons p WHERE p.id = m.person_id);
        """))
        orphaned_marriages = result.scalar()
        print(f"Marriages with missing person_id: {orphaned_marriages}")
        
        # Check deaths with deleted persons
        result = db.session.execute(text("""
            SELECT COUNT(*) 
            FROM deaths d
            WHERE NOT EXISTS (SELECT 1 FROM persons p WHERE p.id = d.person_id);
        """))
        orphaned_deaths = result.scalar()
        print(f"Deaths with missing person_id: {orphaned_deaths}")
        
        # Check baptisms with deleted persons
        result = db.session.execute(text("""
            SELECT COUNT(*) 
            FROM baptisms b
            WHERE NOT EXISTS (SELECT 1 FROM persons p WHERE p.id = b.person_id);
        """))
        orphaned_baptisms = result.scalar()
        print(f"Baptisms with missing person_id: {orphaned_baptisms}")
        
        # 6. Check parent-child relationships
        print("\n6. PARENT-CHILD RELATIONSHIPS")
        print("-" * 80)
        result = db.session.execute(text("""
            SELECT COUNT(*) 
            FROM parent_child_relationships pcr
            WHERE NOT EXISTS (SELECT 1 FROM persons p WHERE p.id = pcr.parent_id)
               OR NOT EXISTS (SELECT 1 FROM persons p WHERE p.id = pcr.child_id);
        """))
        orphaned_relationships = result.scalar()
        print(f"Orphaned parent-child relationships: {orphaned_relationships}")
        
        # 7. Check if duplicate_groups table exists and has data
        print("\n7. DUPLICATE DETECTION DATA")
        print("-" * 80)
        try:
            result = db.session.execute(text("SELECT COUNT(*) FROM duplicate_groups;"))
            dup_groups = result.scalar()
            print(f"Duplicate groups: {dup_groups}")
            
            result = db.session.execute(text("SELECT COUNT(*) FROM duplicate_pairs;"))
            dup_pairs = result.scalar()
            print(f"Duplicate pairs: {dup_pairs}")
            
            # Check for high-confidence duplicates
            result = db.session.execute(text("""
                SELECT COUNT(*) 
                FROM duplicate_pairs 
                WHERE similarity_score >= 0.85;
            """))
            high_conf = result.scalar()
            print(f"High-confidence pairs (≥0.85): {high_conf}")
            
        except Exception as e:
            print(f"⚠️  Duplicate detection tables not found or error: {e}")
        
        # 8. Sample duplicate data for analysis
        if duplicates:
            print("\n8. SAMPLE DUPLICATE DETAILS")
            print("-" * 80)
            first_dup = duplicates[0]
            ids = first_dup[4].split(', ')
            print(f"Analyzing: {first_dup[0]} {first_dup[1]} (IDs: {first_dup[4]})")
            
            for person_id in ids[:2]:  # Check first 2 duplicates
                result = db.session.execute(text("""
                    SELECT id, given_name, surname, birth_date, birth_place, 
                           gedcom_id, gedcom_xref
                    FROM persons 
                    WHERE id = :person_id;
                """), {"person_id": int(person_id)})
                person = result.fetchone()
                if person:
                    print(f"\n  Person ID {person[0]}:")
                    print(f"    Name: {person[1]} {person[2]}")
                    print(f"    Birth: {person[3]} at {person[4]}")
                    print(f"    GEDCOM ID: {person[5]}, XREF: {person[6]}")
                    
                    # Check related records
                    result = db.session.execute(text("SELECT COUNT(*) FROM marriages WHERE person_id = :pid"), {"pid": int(person_id)})
                    marriages = result.scalar()
                    result = db.session.execute(text("SELECT COUNT(*) FROM deaths WHERE person_id = :pid"), {"pid": int(person_id)})
                    deaths = result.scalar()
                    result = db.session.execute(text("SELECT COUNT(*) FROM baptisms WHERE person_id = :pid"), {"pid": int(person_id)})
                    baptisms = result.scalar()
                    print(f"    Related records: {marriages} marriages, {deaths} deaths, {baptisms} baptisms")
        
        print("\n" + "=" * 80)
        print("DIAGNOSTIC COMPLETE")
        print("=" * 80)

if __name__ == "__main__":
    main()
