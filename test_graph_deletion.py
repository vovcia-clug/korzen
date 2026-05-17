"""
Test script to verify graph deletion when confirming duplicates.

This script tests that when a duplicate is confirmed and hard deleted,
the corresponding vertex and edges are also removed from the Apache AGE graph.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from app import create_app
from app.extensions import db
from app.models import Person, DuplicateCandidate
from app.services.age_graph_importer import AgeGraphImporter
from datetime import datetime, date
import uuid
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_graph_deletion():
    """Test that duplicate deletion removes records from both PostgreSQL and AGE graph."""
    
    app = create_app()
    
    with app.app_context():
        try:
            # Create two test persons
            person1_id = uuid.uuid4()
            person2_id = uuid.uuid4()
            
            person1 = Person(
                id=person1_id,
                first_name="Jan",
                last_name="Kowalski",
                gender="M",
                birth_date=date(1850, 1, 15),
                birth_place="Kraków"
            )
            
            person2 = Person(
                id=person2_id,
                first_name="Jan",
                last_name="Kowalski",
                gender="M",
                birth_date=date(1850, 1, 15),
                birth_place="Krakow"  # Slightly different spelling
            )
            
            db.session.add(person1)
            db.session.add(person2)
            db.session.commit()
            
            logger.info(f"Created test persons: {person1_id} and {person2_id}")
            
            # Add both persons to the graph
            raw_conn = db.session.connection().connection
            graph_importer = AgeGraphImporter(raw_conn)
            
            # Ensure graph exists
            graph_importer.create_graph_if_not_exists()
            
            # Create vertices for both persons
            person1_props = {
                'uuid': str(person1_id),
                'first_name': person1.first_name,
                'last_name': person1.last_name,
                'gender': person1.gender,
                'birth_date': person1.birth_date.isoformat() if person1.birth_date else None
            }
            
            person2_props = {
                'uuid': str(person2_id),
                'first_name': person2.first_name,
                'last_name': person2.last_name,
                'gender': person2.gender,
                'birth_date': person2.birth_date.isoformat() if person2.birth_date else None
            }
            
            created1 = graph_importer.create_person_vertex(str(person1_id), person1_props)
            created2 = graph_importer.create_person_vertex(str(person2_id), person2_props)
            
            if not created1 or not created2:
                logger.error("Failed to create person vertices in graph")
                return False
            
            logger.info("Created vertices in graph for both persons")
            
            # Verify both persons exist in graph
            exists1_before = graph_importer.vertex_exists('Person', str(person1_id))
            exists2_before = graph_importer.vertex_exists('Person', str(person2_id))
            
            logger.info(f"Person 1 exists in graph before deletion: {exists1_before}")
            logger.info(f"Person 2 exists in graph before deletion: {exists2_before}")
            
            if not exists1_before or not exists2_before:
                logger.error("Persons not found in graph after creation!")
                return False
            
            # Now test deletion using the delete method
            logger.info(f"\nDeleting person 2 (duplicate) from graph...")
            deleted = graph_importer.delete_person_vertex_with_edges(str(person2_id))
            
            if not deleted:
                logger.error("Graph deletion returned False")
                return False
            
            logger.info("Graph deletion succeeded")
            
            # Verify person2 no longer exists in graph
            exists1_after = graph_importer.vertex_exists('Person', str(person1_id))
            exists2_after = graph_importer.vertex_exists('Person', str(person2_id))
            
            logger.info(f"Person 1 exists in graph after deletion: {exists1_after}")
            logger.info(f"Person 2 exists in graph after deletion: {exists2_after}")
            
            # Clean up: delete from PostgreSQL
            db.session.delete(person1)
            db.session.delete(person2)
            db.session.commit()
            
            # Delete person1 from graph too
            graph_importer.delete_person_vertex_with_edges(str(person1_id))
            
            # Verify results
            if exists1_after and not exists2_after:
                logger.info("\n✅ SUCCESS: Person 1 still exists, Person 2 was deleted from graph")
                return True
            else:
                logger.error("\n❌ FAILED: Graph deletion did not work as expected")
                return False
                
        except Exception as e:
            logger.error(f"Test failed with error: {e}", exc_info=True)
            db.session.rollback()
            return False


if __name__ == "__main__":
    logger.info("Testing graph deletion functionality...\n")
    success = test_graph_deletion()
    
    if success:
        logger.info("\n" + "="*60)
        logger.info("Graph deletion test PASSED")
        logger.info("="*60)
        sys.exit(0)
    else:
        logger.error("\n" + "="*60)
        logger.error("Graph deletion test FAILED")
        logger.error("="*60)
        sys.exit(1)
