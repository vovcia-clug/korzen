#!/usr/bin/env python3
"""Check if parent relationships are in the database."""

import sys
sys.path.insert(0, 'src')

from app import create_app
from app.extensions import db
from app.models import Person

app = create_app()

with app.app_context():
    # Count persons with parents
    total = Person.query.count()
    with_father = Person.query.filter(Person.father_id.isnot(None)).count()
    with_mother = Person.query.filter(Person.mother_id.isnot(None)).count()
    
    print(f"Total persons: {total}")
    print(f"Persons with father_id: {with_father}")
    print(f"Persons with mother_id: {with_mother}")
    print()
    
    if with_father > 0:
        # Show a sample
        sample = Person.query.filter(Person.father_id.isnot(None)).first()
        print(f"Sample person: {sample.first_name} {sample.last_name}")
        print(f"  Father ID: {sample.father_id}")
        print(f"  Mother ID: {sample.mother_id}")
        
        if sample.father:
            print(f"  Father: {sample.father.first_name} {sample.father.last_name}")
        if sample.mother:
            print(f"  Mother: {sample.mother.first_name} {sample.mother.last_name}")
    else:
        print("NO PARENT RELATIONSHIPS FOUND!")
        print("\nChecking first 5 persons:")
        for p in Person.query.limit(5).all():
            print(f"  {p.first_name} {p.last_name} - father_id: {p.father_id}, mother_id: {p.mother_id}")
