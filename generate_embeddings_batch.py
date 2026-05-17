#!/usr/bin/env python3
"""
Batch processing utility for generating embeddings and detecting duplicates.

This script processes existing records in the database to:
1. Generate vector embeddings for records without embeddings
2. Generate phonetic codes for name matching
3. Detect duplicate records using multi-stage similarity detection

Usage:
    python generate_embeddings_batch.py --record-type all --batch-size 100
    python generate_embeddings_batch.py --record-type person --detect-duplicates
    python generate_embeddings_batch.py --record-type person --limit 1000
    python generate_embeddings_batch.py --record-type baptism --batch-size 50 --detect-duplicates
"""

import argparse
import logging
import sys
from typing import Optional

from tqdm import tqdm

# Add src to path
sys.path.insert(0, 'src')

from app import create_app
from app.extensions import db
from app.models import Person, BaptismRecord, MarriageRecord, DeathRecord
from app.services.phonetic_encoder import PhoneticEncoder
from app.services.feature_extractor import FeatureExtractor
from app.services.embedding_generator import EmbeddingGenerator
from app.services.duplicate_detector import DuplicateDetector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize services
phonetic_encoder = PhoneticEncoder()
feature_extractor = FeatureExtractor()
embedding_generator = EmbeddingGenerator()
duplicate_detector = DuplicateDetector()


def generate_person_embeddings(batch_size: int, limit: Optional[int] = None) -> int:
    """
    Generate embeddings for persons without embeddings.
    
    Args:
        batch_size: Number of records to process per batch
        limit: Maximum number of records to process (optional)
    
    Returns:
        Count of processed records
    """
    logger.info("Starting person embedding generation")
    
    # Query persons without embeddings
    query = Person.query.filter(Person.embedding.is_(None))
    
    if limit:
        query = query.limit(limit)
    
    total_count = query.count()
    logger.info(f"Found {total_count} persons without embeddings")
    
    if total_count == 0:
        return 0
    
    processed = 0
    errors = 0
    
    # Process in batches
    with tqdm(total=total_count, desc="Generating person embeddings") as pbar:
        offset = 0
        while offset < total_count:
            # Fetch batch
            batch = query.offset(offset).limit(batch_size).all()
            
            if not batch:
                break
            
            for person in batch:
                try:
                    # Extract features
                    features = feature_extractor.extract_person_features(person)
                    
                    # Generate embedding
                    embedding = embedding_generator.generate_person_embedding(features)
                    person.embedding = embedding.tolist()
                    
                    # Generate phonetic codes
                    if person.first_name:
                        person.first_name_phonetic = phonetic_encoder.encode(person.first_name)
                    if person.last_name:
                        person.last_name_phonetic = phonetic_encoder.encode(person.last_name)
                    if person.maiden_name:
                        person.maiden_name_phonetic = phonetic_encoder.encode(person.maiden_name)
                    
                    processed += 1
                    
                except Exception as e:
                    logger.error(f"Error processing person {person.id}: {e}")
                    db.session.rollback()
                    errors += 1
                
                pbar.update(1)
            
            # Commit batch
            try:
                db.session.commit()
                logger.debug(f"Committed batch at offset {offset}")
            except Exception as e:
                logger.error(f"Error committing batch: {e}")
                db.session.rollback()
            
            offset += batch_size
    
    logger.info(f"Person embedding generation complete: {processed} processed, {errors} errors")
    return processed


def generate_baptism_embeddings(batch_size: int, limit: Optional[int] = None) -> int:
    """
    Generate embeddings for baptism records without embeddings.
    
    Args:
        batch_size: Number of records to process per batch
        limit: Maximum number of records to process (optional)
    
    Returns:
        Count of processed records
    """
    logger.info("Starting baptism embedding generation")
    
    # Query baptism records without embeddings
    query = BaptismRecord.query.filter(BaptismRecord.embedding.is_(None))
    
    if limit:
        query = query.limit(limit)
    
    total_count = query.count()
    logger.info(f"Found {total_count} baptism records without embeddings")
    
    if total_count == 0:
        return 0
    
    processed = 0
    errors = 0
    
    # Process in batches
    with tqdm(total=total_count, desc="Generating baptism embeddings") as pbar:
        offset = 0
        while offset < total_count:
            # Fetch batch
            batch = query.offset(offset).limit(batch_size).all()
            
            if not batch:
                break
            
            for baptism in batch:
                try:
                    # Extract features
                    features = feature_extractor.extract_baptism_features(baptism)
                    
                    # Generate embedding
                    embedding = embedding_generator.generate_baptism_embedding(features)
                    baptism.embedding = embedding.tolist()
                    
                    # Generate phonetic codes
                    if baptism.child_name:
                        baptism.child_name_phonetic = phonetic_encoder.encode(baptism.child_name)
                    if baptism.father_surname:
                        baptism.father_surname_phonetic = phonetic_encoder.encode(baptism.father_surname)
                    if baptism.mother_maiden_name:
                        baptism.mother_maiden_name_phonetic = phonetic_encoder.encode(baptism.mother_maiden_name)
                    
                    processed += 1
                    
                except Exception as e:
                    logger.error(f"Error processing baptism {baptism.id}: {e}")
                    db.session.rollback()
                    errors += 1
                
                pbar.update(1)
            
            # Commit batch
            try:
                db.session.commit()
                logger.debug(f"Committed batch at offset {offset}")
            except Exception as e:
                logger.error(f"Error committing batch: {e}")
                db.session.rollback()
            
            offset += batch_size
    
    logger.info(f"Baptism embedding generation complete: {processed} processed, {errors} errors")
    return processed


def generate_marriage_embeddings(batch_size: int, limit: Optional[int] = None) -> int:
    """
    Generate embeddings for marriage records without embeddings.
    
    Args:
        batch_size: Number of records to process per batch
        limit: Maximum number of records to process (optional)
    
    Returns:
        Count of processed records
    """
    logger.info("Starting marriage embedding generation")
    
    # Query marriage records without embeddings
    query = MarriageRecord.query.filter(MarriageRecord.embedding.is_(None))
    
    if limit:
        query = query.limit(limit)
    
    total_count = query.count()
    logger.info(f"Found {total_count} marriage records without embeddings")
    
    if total_count == 0:
        return 0
    
    processed = 0
    errors = 0
    
    # Process in batches
    with tqdm(total=total_count, desc="Generating marriage embeddings") as pbar:
        offset = 0
        while offset < total_count:
            # Fetch batch
            batch = query.offset(offset).limit(batch_size).all()
            
            if not batch:
                break
            
            for marriage in batch:
                try:
                    # Extract features
                    features = feature_extractor.extract_marriage_features(marriage)
                    
                    # Generate embedding
                    embedding = embedding_generator.generate_marriage_embedding(features)
                    marriage.embedding = embedding.tolist()
                    
                    # Generate phonetic codes
                    if marriage.spouse1_surname:
                        marriage.spouse1_surname_phonetic = phonetic_encoder.encode(marriage.spouse1_surname)
                    if marriage.spouse2_surname:
                        marriage.spouse2_surname_phonetic = phonetic_encoder.encode(marriage.spouse2_surname)
                    
                    processed += 1
                    
                except Exception as e:
                    logger.error(f"Error processing marriage {marriage.id}: {e}")
                    db.session.rollback()
                    errors += 1
                
                pbar.update(1)
            
            # Commit batch
            try:
                db.session.commit()
                logger.debug(f"Committed batch at offset {offset}")
            except Exception as e:
                logger.error(f"Error committing batch: {e}")
                db.session.rollback()
            
            offset += batch_size
    
    logger.info(f"Marriage embedding generation complete: {processed} processed, {errors} errors")
    return processed


def generate_death_embeddings(batch_size: int, limit: Optional[int] = None) -> int:
    """
    Generate embeddings for death records without embeddings.
    
    Args:
        batch_size: Number of records to process per batch
        limit: Maximum number of records to process (optional)
    
    Returns:
        Count of processed records
    """
    logger.info("Starting death embedding generation")
    
    # Query death records without embeddings
    query = DeathRecord.query.filter(DeathRecord.embedding.is_(None))
    
    if limit:
        query = query.limit(limit)
    
    total_count = query.count()
    logger.info(f"Found {total_count} death records without embeddings")
    
    if total_count == 0:
        return 0
    
    processed = 0
    errors = 0
    
    # Process in batches
    with tqdm(total=total_count, desc="Generating death embeddings") as pbar:
        offset = 0
        while offset < total_count:
            # Fetch batch
            batch = query.offset(offset).limit(batch_size).all()
            
            if not batch:
                break
            
            for death in batch:
                try:
                    # Extract features
                    features = feature_extractor.extract_death_features(death)
                    
                    # Generate embedding
                    embedding = embedding_generator.generate_death_embedding(features)
                    death.embedding = embedding.tolist()
                    
                    # Generate phonetic codes
                    if death.deceased_surname:
                        death.deceased_surname_phonetic = phonetic_encoder.encode(death.deceased_surname)
                    if death.deceased_maiden_name:
                        death.deceased_maiden_name_phonetic = phonetic_encoder.encode(death.deceased_maiden_name)
                    
                    processed += 1
                    
                except Exception as e:
                    logger.error(f"Error processing death {death.id}: {e}")
                    db.session.rollback()
                    errors += 1
                
                pbar.update(1)
            
            # Commit batch
            try:
                db.session.commit()
                logger.debug(f"Committed batch at offset {offset}")
            except Exception as e:
                logger.error(f"Error committing batch: {e}")
                db.session.rollback()
            
            offset += batch_size
    
    logger.info(f"Death embedding generation complete: {processed} processed, {errors} errors")
    return processed


def detect_all_duplicates(record_type: str, batch_size: int, limit: Optional[int] = None) -> int:
    """
    Detect duplicates for all records of a given type.
    
    Args:
        record_type: Type of records ('person', 'baptism', 'marriage', 'death')
        batch_size: Number of records to process per batch
        limit: Maximum number of records to process (optional)
    
    Returns:
        Count of duplicate candidates found
    """
    logger.info(f"Starting duplicate detection for {record_type} records")
    
    # Select appropriate model and detection method
    if record_type == 'person':
        model = Person
        detect_method = duplicate_detector.detect_person_duplicates
    elif record_type == 'baptism':
        model = BaptismRecord
        detect_method = duplicate_detector.detect_baptism_duplicates
    elif record_type == 'marriage':
        model = MarriageRecord
        detect_method = duplicate_detector.detect_marriage_duplicates
    elif record_type == 'death':
        model = DeathRecord
        detect_method = duplicate_detector.detect_death_duplicates
    else:
        logger.error(f"Unknown record type: {record_type}")
        return 0
    
    # Query records with embeddings
    query = model.query.filter(model.embedding.isnot(None))
    
    if limit:
        query = query.limit(limit)
    
    total_count = query.count()
    logger.info(f"Found {total_count} {record_type} records with embeddings")
    
    if total_count == 0:
        return 0
    
    processed = 0
    duplicates_found = 0
    errors = 0
    
    # Process in batches
    with tqdm(total=total_count, desc=f"Detecting {record_type} duplicates") as pbar:
        offset = 0
        while offset < total_count:
            # Fetch batch
            batch = query.offset(offset).limit(batch_size).all()
            
            if not batch:
                break
            
            for record in batch:
                try:
                    # Detect duplicates for this record
                    duplicates = detect_method(record, limit=10)
                    
                    if duplicates:
                        duplicates_found += len(duplicates)
                        logger.debug(f"Found {len(duplicates)} duplicates for {record_type} {record.id}")
                    
                    processed += 1
                    
                except Exception as e:
                    logger.error(f"Error detecting duplicates for {record_type} {record.id}: {e}")
                    db.session.rollback()
                    errors += 1
                
                pbar.update(1)
            
            # Commit batch (duplicate candidates are saved within detect methods)
            try:
                db.session.commit()
                logger.debug(f"Committed batch at offset {offset}")
            except Exception as e:
                logger.error(f"Error committing batch: {e}")
                db.session.rollback()
            
            offset += batch_size
    
    logger.info(f"Duplicate detection complete: {processed} records processed, {duplicates_found} candidates found, {errors} errors")
    return duplicates_found


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Generate embeddings and detect duplicates in batch',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate embeddings for all record types
  python generate_embeddings_batch.py --record-type all
  
  # Generate embeddings for persons only
  python generate_embeddings_batch.py --record-type person --batch-size 50
  
  # Generate embeddings and detect duplicates
  python generate_embeddings_batch.py --record-type person --detect-duplicates
  
  # Process limited number of records (for testing)
  python generate_embeddings_batch.py --record-type baptism --limit 100
  
  # Detect duplicates only (assumes embeddings already exist)
  python generate_embeddings_batch.py --record-type all --detect-duplicates --batch-size 50
        """
    )
    
    parser.add_argument(
        '--record-type',
        choices=['person', 'baptism', 'marriage', 'death', 'all'],
        default='all',
        help='Type of records to process (default: all)'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=100,
        help='Number of records to process per batch (default: 100)'
    )
    parser.add_argument(
        '--detect-duplicates',
        action='store_true',
        help='Run duplicate detection after generating embeddings'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Maximum number of records to process (optional, for testing)'
    )
    parser.add_argument(
        '--skip-embeddings',
        action='store_true',
        help='Skip embedding generation, only detect duplicates'
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.batch_size < 1:
        parser.error("Batch size must be at least 1")
    
    if args.limit and args.limit < 1:
        parser.error("Limit must be at least 1")
    
    # Create Flask app context
    app = create_app()
    
    with app.app_context():
        print("=" * 80)
        print("Batch Processing Utility for Embeddings and Duplicate Detection")
        print("=" * 80)
        print(f"Record type: {args.record_type}")
        print(f"Batch size: {args.batch_size}")
        print(f"Limit: {args.limit if args.limit else 'None (process all)'}")
        print(f"Detect duplicates: {args.detect_duplicates}")
        print(f"Skip embeddings: {args.skip_embeddings}")
        print("=" * 80)
        print()
        
        total_processed = 0
        total_duplicates = 0
        
        # Determine which record types to process
        if args.record_type == 'all':
            record_types = ['person', 'baptism', 'marriage', 'death']
        else:
            record_types = [args.record_type]
        
        # Generate embeddings (unless skipped)
        if not args.skip_embeddings:
            print("\n" + "=" * 80)
            print("PHASE 1: GENERATING EMBEDDINGS")
            print("=" * 80 + "\n")
            
            for record_type in record_types:
                print(f"\n--- Processing {record_type} records ---\n")
                
                if record_type == 'person':
                    count = generate_person_embeddings(args.batch_size, args.limit)
                elif record_type == 'baptism':
                    count = generate_baptism_embeddings(args.batch_size, args.limit)
                elif record_type == 'marriage':
                    count = generate_marriage_embeddings(args.batch_size, args.limit)
                elif record_type == 'death':
                    count = generate_death_embeddings(args.batch_size, args.limit)
                
                total_processed += count
                print(f"✓ Processed {count} {record_type} records\n")
        
        # Detect duplicates (if requested)
        if args.detect_duplicates:
            print("\n" + "=" * 80)
            print("PHASE 2: DETECTING DUPLICATES")
            print("=" * 80 + "\n")
            
            for record_type in record_types:
                print(f"\n--- Detecting duplicates for {record_type} records ---\n")
                
                count = detect_all_duplicates(record_type, args.batch_size, args.limit)
                total_duplicates += count
                print(f"✓ Found {count} duplicate candidates for {record_type} records\n")
        
        # Print summary
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        if not args.skip_embeddings:
            print(f"Total embeddings generated: {total_processed}")
        if args.detect_duplicates:
            print(f"Total duplicate candidates found: {total_duplicates}")
        print("=" * 80)
        print("\n✓ Batch processing complete!\n")


if __name__ == '__main__':
    main()
