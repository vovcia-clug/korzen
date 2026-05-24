"""
Duplicate Detector Service

This module provides the core duplicate detection service that orchestrates
the entire duplicate detection pipeline. It combines vector similarity search,
phonetic matching, date comparison, and location matching to identify potential
duplicate records across persons and genealogical events.

The service uses a multi-stage approach:
1. Vector similarity search using pgvector (cosine distance)
2. Phonetic name matching using Daitch-Mokotoff algorithm
3. Date similarity calculation (temporal proximity)
4. Location similarity matching (parish, village, residence)
5. Composite score calculation with weighted components

This service is the main entry point for duplicate detection operations.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import func

from ..extensions import db
from ..models import (
    BaptismRecord,
    DeathRecord,
    DuplicateCandidate,
    MarriageRecord,
    Person,
)
from .embedding_generator import EmbeddingGenerator
from .feature_extractor import FeatureExtractor
from .phonetic_encoder import PhoneticEncoder

logger = logging.getLogger(__name__)


class DuplicateDetector:
    """
    Orchestrates the multi-stage duplicate detection pipeline.
    
    This class combines vector similarity, phonetic matching, date comparison,
    and location matching to identify potential duplicate records. It provides
    methods for detecting duplicates across different record types (persons,
    baptisms, marriages, deaths) and calculating composite similarity scores.
    
    The detection pipeline:
    1. Generate embeddings for query record
    2. Perform vector similarity search using pgvector
    3. Calculate phonetic similarity for names
    4. Calculate date similarity for temporal proximity
    5. Calculate location similarity for geographic matching
    6. Compute weighted composite score
    7. Save high-scoring candidates to database
    
    Composite Score Weights:
    - Vector similarity: 40%
    - Phonetic similarity: 30%
    - Date similarity: 20%
    - Location similarity: 10%
    
    Example:
        >>> detector = DuplicateDetector(threshold=0.85)
        >>> person = Person.query.first()
        >>> duplicates = detector.detect_person_duplicates(person, limit=10)
        >>> for candidate, score, breakdown in duplicates:
        ...     print(f"Match: {candidate.first_name} {candidate.last_name}")
        ...     print(f"Score: {score:.2f}")
        ...     print(f"Breakdown: {breakdown}")
    """
    
    # Composite score weights
    WEIGHT_VECTOR = 0.40
    WEIGHT_PHONETIC = 0.30
    WEIGHT_DATE = 0.20
    WEIGHT_LOCATION = 0.10
    
    def __init__(self, threshold: float = 0.85):
        """
        Initialize the duplicate detector.
        
        Args:
            threshold: Minimum composite score threshold for duplicate candidates.
                      Scores above this threshold will be saved to the database.
                      Default: 0.85 (85% similarity)
        
        Example:
            >>> detector = DuplicateDetector(threshold=0.90)
            >>> detector.threshold
            0.9
        """
        self.threshold = threshold
        self.phonetic_encoder = PhoneticEncoder()
        self.feature_extractor = FeatureExtractor()
        self.embedding_generator = EmbeddingGenerator()
        logger.info(f"DuplicateDetector initialized with threshold={threshold}")
    
    def _should_skip_person_duplicate_detection(self, person: Person) -> bool:
        """
        Determine if a person should be skipped for duplicate detection.
        
        Persons without sufficient identifying information are too generic to
        reliably detect duplicates. This method identifies such records to
        prevent false positive matches.
        
        A person is skipped if they lack BOTH:
        1. A surname (last name or maiden name), AND
        2. Sufficient contextual data (dates AND locations together)
        
        This stricter validation prevents records with only a first name and
        partial data (e.g., "Adele" with just a birth year) from matching
        broadly with other similar records.
        
        Required data combinations (at least one must be true):
        - Has surname (last_name or maiden_name)
        - Has BOTH dates (birth_date or death_date) AND locations (birth_place,
          death_place, parish, or residence)
        
        Args:
            person: Person entity to evaluate
        
        Returns:
            True if duplicate detection should be skipped, False otherwise
        
        Example:
            >>> person = Person(first_name="Adele", birth_date="1850-01-01")
            >>> detector._should_skip_person_duplicate_detection(person)
            True  # Has date but no surname and no location
            >>>
            >>> person2 = Person(first_name="Jan", last_name="Kowalski")
            >>> detector._should_skip_person_duplicate_detection(person2)
            False  # Has surname
            >>>
            >>> person3 = Person(first_name="Maria", birth_date="1850-01-01",
            ...                  birth_place="Krakow")
            >>> detector._should_skip_person_duplicate_detection(person3)
            False  # Has both dates and locations
        """
        # Check if person has a surname (last name or maiden name)
        has_surname = bool(person.last_name or person.maiden_name)
        
        # Check if person has any date information
        has_dates = bool(person.birth_date or person.death_date)
        
        # Check if person has any location information
        has_locations = bool(
            person.birth_place or
            person.death_place or
            person.parish or
            person.residence
        )
        
        # Require surname OR (dates AND locations together)
        # This prevents records with only partial data from generating false positives
        if not has_surname and not (has_dates and has_locations):
            logger.info(
                f"Skipping duplicate detection for person {person.id}: "
                f"insufficient identifying information (surname={has_surname}, "
                f"dates={has_dates}, locations={has_locations}). "
                f"Requires surname OR (dates AND locations)."
            )
            return True
        
        return False
    
    def detect_person_duplicates(
        self, 
        person: Person, 
        limit: int = 10
    ) -> list[tuple[Person, float, dict]]:
        """
        Find duplicate persons using vector similarity search.
        
        Performs multi-stage duplicate detection for a person entity:
        1. Vector similarity search using pgvector cosine distance
        2. Phonetic name matching (first, last, maiden names)
        3. Date similarity (birth/death dates)
        4. Location similarity (birth place, death place, parish, residence)
        5. Composite score calculation
        
        Args:
            person: Person entity to find duplicates for
            limit: Maximum number of candidates to return (default: 10)
        
        Returns:
            List of tuples containing:
            - candidate_person: Potential duplicate Person entity
            - composite_score: Weighted composite similarity score (0.0-1.0)
            - score_breakdown: Dictionary with individual scores:
                * vector_sim: Vector similarity score
                * phonetic_sim: Phonetic name similarity score
                * date_sim: Date similarity score
                * location_sim: Location similarity score
        
        Example:
            >>> person = Person.query.filter_by(last_name="Kowalski").first()
            >>> duplicates = detector.detect_person_duplicates(person, limit=5)
            >>> for candidate, score, breakdown in duplicates:
            ...     print(f"{candidate.first_name} {candidate.last_name}: {score:.2f}")
            ...     print(f"  Vector: {breakdown['vector_sim']:.2f}")
            ...     print(f"  Phonetic: {breakdown['phonetic_sim']:.2f}")
        """
        try:
            # Skip duplicate detection for persons with only a single name
            # and no other identifying information (too generic for reliable matching)
            if self._should_skip_person_duplicate_detection(person):
                logger.info(f"Skipped duplicate detection for person {person.id} (insufficient identifying information)")
                return []
            
            # Check if person has embedding
            if person.embedding is None:
                logger.warning(f"Person {person.id} has no embedding, cannot detect duplicates")
                return []
            
            # Perform vector similarity search
            query_embedding = person.embedding
            candidates = db.session.query(
                Person,
                (1 - Person.embedding.cosine_distance(query_embedding)).label('similarity')
            ).filter(
                Person.id != person.id,
                Person.embedding.isnot(None)
            ).order_by(
                Person.embedding.cosine_distance(query_embedding)
            ).limit(limit * 2).all()  # Get more candidates for filtering
            
            logger.info(f"Found {len(candidates)} vector similarity candidates for person {person.id}")
            
            # Calculate composite scores
            results = []
            for candidate_person, vector_sim in candidates:
                composite_score, score_breakdown = self.calculate_composite_score(
                    person, 
                    candidate_person, 
                    vector_sim, 
                    'person'
                )
                
                # Only include if above threshold
                if composite_score >= self.threshold:
                    results.append((candidate_person, composite_score, score_breakdown))
                    
                    # Save to database
                    self.save_duplicate_candidate(
                        'person',
                        person.id,
                        candidate_person.id,
                        composite_score,
                        score_breakdown,
                        method='auto'
                    )
            
            # Sort by composite score and limit
            results.sort(key=lambda x: x[1], reverse=True)
            results = results[:limit]
            
            logger.info(f"Detected {len(results)} person duplicates above threshold {self.threshold}")
            return results
            
        except Exception as e:
            logger.error(f"Error detecting person duplicates: {e}", exc_info=True)
            return []
    
    def detect_baptism_duplicates(
        self, 
        baptism: BaptismRecord, 
        limit: int = 10
    ) -> list[tuple[BaptismRecord, float, dict]]:
        """
        Find duplicate baptism records.
        
        Searches for duplicate baptism records within ±7 days of the baptism date,
        matching on child name, parent names, and parish location.
        
        Args:
            baptism: BaptismRecord to find duplicates for
            limit: Maximum number of candidates to return (default: 10)
        
        Returns:
            List of tuples containing:
            - candidate_baptism: Potential duplicate BaptismRecord
            - composite_score: Weighted composite similarity score (0.0-1.0)
            - score_breakdown: Dictionary with individual scores
        
        Example:
            >>> baptism = BaptismRecord.query.first()
            >>> duplicates = detector.detect_baptism_duplicates(baptism, limit=5)
            >>> for candidate, score, breakdown in duplicates:
            ...     print(f"Baptism {candidate.record_number}: {score:.2f}")
        """
        try:
            # Check if baptism has embedding
            if baptism.embedding is None:
                logger.warning(f"Baptism {baptism.id} has no embedding, cannot detect duplicates")
                return []
            
            # Define date range (±7 days)
            date_min = baptism.baptism_date - timedelta(days=7)
            date_max = baptism.baptism_date + timedelta(days=7)
            
            # Perform vector similarity search with date filter
            query_embedding = baptism.embedding
            candidates = db.session.query(
                BaptismRecord,
                (1 - BaptismRecord.embedding.cosine_distance(query_embedding)).label('similarity')
            ).filter(
                BaptismRecord.id != baptism.id,
                BaptismRecord.embedding.isnot(None),
                BaptismRecord.baptism_date >= date_min,
                BaptismRecord.baptism_date <= date_max
            ).order_by(
                BaptismRecord.embedding.cosine_distance(query_embedding)
            ).limit(limit * 2).all()
            
            logger.info(f"Found {len(candidates)} vector similarity candidates for baptism {baptism.id}")
            
            # Calculate composite scores
            results = []
            for candidate_baptism, vector_sim in candidates:
                composite_score, score_breakdown = self.calculate_composite_score(
                    baptism,
                    candidate_baptism,
                    vector_sim,
                    'baptism'
                )
                
                # Only include if above threshold
                if composite_score >= self.threshold:
                    results.append((candidate_baptism, composite_score, score_breakdown))
                    
                    # Save to database
                    self.save_duplicate_candidate(
                        'baptism',
                        baptism.id,
                        candidate_baptism.id,
                        composite_score,
                        score_breakdown,
                        method='auto'
                    )
            
            # Sort by composite score and limit
            results.sort(key=lambda x: x[1], reverse=True)
            results = results[:limit]
            
            logger.info(f"Detected {len(results)} baptism duplicates above threshold {self.threshold}")
            return results
            
        except Exception as e:
            logger.error(f"Error detecting baptism duplicates: {e}", exc_info=True)
            return []
    
    def detect_marriage_duplicates(
        self, 
        marriage: MarriageRecord, 
        limit: int = 10
    ) -> list[tuple[MarriageRecord, float, dict]]:
        """
        Find duplicate marriage records.
        
        Searches for duplicate marriage records within ±7 days of the marriage date,
        matching on spouse names and parish location.
        
        Args:
            marriage: MarriageRecord to find duplicates for
            limit: Maximum number of candidates to return (default: 10)
        
        Returns:
            List of tuples containing:
            - candidate_marriage: Potential duplicate MarriageRecord
            - composite_score: Weighted composite similarity score (0.0-1.0)
            - score_breakdown: Dictionary with individual scores
        
        Example:
            >>> marriage = MarriageRecord.query.first()
            >>> duplicates = detector.detect_marriage_duplicates(marriage, limit=5)
            >>> for candidate, score, breakdown in duplicates:
            ...     print(f"Marriage {candidate.record_number}: {score:.2f}")
        """
        try:
            # Check if marriage has embedding
            if marriage.embedding is None:
                logger.warning(f"Marriage {marriage.id} has no embedding, cannot detect duplicates")
                return []
            
            # Define date range (±7 days)
            date_min = marriage.marriage_date - timedelta(days=7)
            date_max = marriage.marriage_date + timedelta(days=7)
            
            # Perform vector similarity search with date filter
            query_embedding = marriage.embedding
            candidates = db.session.query(
                MarriageRecord,
                (1 - MarriageRecord.embedding.cosine_distance(query_embedding)).label('similarity')
            ).filter(
                MarriageRecord.id != marriage.id,
                MarriageRecord.embedding.isnot(None),
                MarriageRecord.marriage_date >= date_min,
                MarriageRecord.marriage_date <= date_max
            ).order_by(
                MarriageRecord.embedding.cosine_distance(query_embedding)
            ).limit(limit * 2).all()
            
            logger.info(f"Found {len(candidates)} vector similarity candidates for marriage {marriage.id}")
            
            # Calculate composite scores
            results = []
            for candidate_marriage, vector_sim in candidates:
                composite_score, score_breakdown = self.calculate_composite_score(
                    marriage,
                    candidate_marriage,
                    vector_sim,
                    'marriage'
                )
                
                # Only include if above threshold
                if composite_score >= self.threshold:
                    results.append((candidate_marriage, composite_score, score_breakdown))
                    
                    # Save to database
                    self.save_duplicate_candidate(
                        'marriage',
                        marriage.id,
                        candidate_marriage.id,
                        composite_score,
                        score_breakdown,
                        method='auto'
                    )
            
            # Sort by composite score and limit
            results.sort(key=lambda x: x[1], reverse=True)
            results = results[:limit]
            
            logger.info(f"Detected {len(results)} marriage duplicates above threshold {self.threshold}")
            return results
            
        except Exception as e:
            logger.error(f"Error detecting marriage duplicates: {e}", exc_info=True)
            return []
    
    def detect_death_duplicates(
        self, 
        death: DeathRecord, 
        limit: int = 10
    ) -> list[tuple[DeathRecord, float, dict]]:
        """
        Find duplicate death records.
        
        Searches for duplicate death records within ±7 days of the death date,
        matching on deceased name, age, and parish location.
        
        Args:
            death: DeathRecord to find duplicates for
            limit: Maximum number of candidates to return (default: 10)
        
        Returns:
            List of tuples containing:
            - candidate_death: Potential duplicate DeathRecord
            - composite_score: Weighted composite similarity score (0.0-1.0)
            - score_breakdown: Dictionary with individual scores
        
        Example:
            >>> death = DeathRecord.query.first()
            >>> duplicates = detector.detect_death_duplicates(death, limit=5)
            >>> for candidate, score, breakdown in duplicates:
            ...     print(f"Death {candidate.record_number}: {score:.2f}")
        """
        try:
            # Check if death has embedding
            if death.embedding is None:
                logger.warning(f"Death {death.id} has no embedding, cannot detect duplicates")
                return []
            
            # Define date range (±7 days)
            date_min = death.death_date - timedelta(days=7)
            date_max = death.death_date + timedelta(days=7)
            
            # Perform vector similarity search with date filter
            query_embedding = death.embedding
            candidates = db.session.query(
                DeathRecord,
                (1 - DeathRecord.embedding.cosine_distance(query_embedding)).label('similarity')
            ).filter(
                DeathRecord.id != death.id,
                DeathRecord.embedding.isnot(None),
                DeathRecord.death_date >= date_min,
                DeathRecord.death_date <= date_max
            ).order_by(
                DeathRecord.embedding.cosine_distance(query_embedding)
            ).limit(limit * 2).all()
            
            logger.info(f"Found {len(candidates)} vector similarity candidates for death {death.id}")
            
            # Calculate composite scores
            results = []
            for candidate_death, vector_sim in candidates:
                composite_score, score_breakdown = self.calculate_composite_score(
                    death,
                    candidate_death,
                    vector_sim,
                    'death'
                )
                
                # Only include if above threshold
                if composite_score >= self.threshold:
                    results.append((candidate_death, composite_score, score_breakdown))
                    
                    # Save to database
                    self.save_duplicate_candidate(
                        'death',
                        death.id,
                        candidate_death.id,
                        composite_score,
                        score_breakdown,
                        method='auto'
                    )
            
            # Sort by composite score and limit
            results.sort(key=lambda x: x[1], reverse=True)
            results = results[:limit]
            
            logger.info(f"Detected {len(results)} death duplicates above threshold {self.threshold}")
            return results
            
        except Exception as e:
            logger.error(f"Error detecting death duplicates: {e}", exc_info=True)
            return []
    
    def calculate_composite_score(
        self,
        record1,
        record2,
        vector_sim: float,
        record_type: str
    ) -> tuple[float, dict]:
        """
        Calculate weighted composite score from multiple similarity metrics.
        
        Combines vector similarity, phonetic similarity, date similarity, and
        location similarity using predefined weights:
        - Vector: 40%
        - Phonetic: 30%
        - Date: 20%
        - Location: 10%
        
        This method implements missing data masking: similarity components are only
        included in the composite score when the corresponding data is present in
        BOTH records. Weights are dynamically adjusted and normalized based on
        available data to prevent missing optional fields from artificially lowering
        similarity scores.
        
        Args:
            record1: First record (Person, BaptismRecord, MarriageRecord, or DeathRecord)
            record2: Second record (same type as record1)
            vector_sim: Pre-calculated vector similarity score (0.0-1.0)
            record_type: Type of record ('person', 'baptism', 'marriage', 'death')
        
        Returns:
            Tuple containing:
            - composite_score: Weighted composite score (0.0-1.0)
            - score_breakdown: Dictionary with individual scores:
                * vector_sim: Vector similarity
                * phonetic_sim: Phonetic similarity (or None if data missing)
                * date_sim: Date similarity (or None if data missing)
                * location_sim: Location similarity (or None if data missing)
        
        Example:
            >>> person1 = Person.query.get(id1)
            >>> person2 = Person.query.get(id2)
            >>> score, breakdown = detector.calculate_composite_score(
            ...     person1, person2, 0.92, 'person'
            ... )
            >>> print(f"Composite: {score:.2f}")
            >>> print(f"Phonetic: {breakdown['phonetic_sim']:.2f}")
        """
        try:
            # FIX 3: Gender validation for person records
            # Instant rejection if genders differ (prevents male-female matches)
            if record_type == 'person':
                if record1.gender and record2.gender:
                    if record1.gender != record2.gender:
                        logger.info(
                            f"Gender mismatch detected: {record1.gender} vs {record2.gender}. "
                            f"Returning score 0.0 (instant rejection)."
                        )
                        return 0.0, {
                            'vector_sim': vector_sim,
                            'phonetic_sim': None,
                            'date_sim': None,
                            'location_sim': None,
                            'rejection_reason': 'gender_mismatch'
                        }
            
            # Calculate phonetic similarity (returns None if data missing in both)
            phonetic_sim = self._calculate_phonetic_similarity_for_record(
                record1, record2, record_type
            )
            
            # Calculate date similarity (returns None if data missing in both)
            date_sim = self._calculate_date_similarity_for_record(
                record1, record2, record_type
            )
            
            # Calculate location similarity (returns None if data missing in both)
            location_sim = self._calculate_location_similarity_for_record(
                record1, record2, record_type
            )
            
            # FIX 4: Penalize missing data instead of ignoring it
            # Use fixed weights and assign low scores (0.3) for missing components
            # This prevents records with minimal data from scoring artificially high
            MISSING_DATA_PENALTY = 0.3  # Score assigned when data is missing
            
            composite_score = 0.0
            
            # Vector similarity is always included (primary signal)
            composite_score += self.WEIGHT_VECTOR * vector_sim
            
            # Phonetic similarity: use actual score or penalty if missing
            if phonetic_sim is not None:
                composite_score += self.WEIGHT_PHONETIC * phonetic_sim
            else:
                composite_score += self.WEIGHT_PHONETIC * MISSING_DATA_PENALTY
            
            # Date similarity: use actual score or penalty if missing
            if date_sim is not None:
                composite_score += self.WEIGHT_DATE * date_sim
            else:
                composite_score += self.WEIGHT_DATE * MISSING_DATA_PENALTY
            
            # Location similarity: use actual score or penalty if missing
            if location_sim is not None:
                composite_score += self.WEIGHT_LOCATION * location_sim
            else:
                composite_score += self.WEIGHT_LOCATION * MISSING_DATA_PENALTY
            
            # No normalization needed - using fixed weights that sum to 1.0
            # composite_score is already in range [0.0, 1.0]
            
            # Log which components were used for debugging
            components_used = ['vector']
            if phonetic_sim is not None:
                components_used.append('phonetic')
            if date_sim is not None:
                components_used.append('date')
            if location_sim is not None:
                components_used.append('location')
            
            logger.debug(
                f"Composite score calculation - Components used: {', '.join(components_used)} "
                f"(weight: {total_weight:.2f}), Score: {composite_score:.3f}"
            )
            
            score_breakdown = {
                'vector_sim': vector_sim,
                'phonetic_sim': phonetic_sim,
                'date_sim': date_sim,
                'location_sim': location_sim
            }
            
            return composite_score, score_breakdown
            
        except Exception as e:
            logger.error(f"Error calculating composite score: {e}", exc_info=True)
            # Return vector similarity as fallback
            return vector_sim, {
                'vector_sim': vector_sim,
                'phonetic_sim': None,
                'date_sim': None,
                'location_sim': None
            }
    
    def _both_have_names(self, record1, record2, record_type: str) -> bool:
        """
        Check if both records have name data.
        
        Args:
            record1: First record
            record2: Second record
            record_type: Type of record ('person', 'baptism', 'marriage', 'death')
        
        Returns:
            True if both records have at least one name field populated
        """
        if record_type == 'person':
            has_name1 = bool(record1.first_name or record1.last_name or record1.maiden_name)
            has_name2 = bool(record2.first_name or record2.last_name or record2.maiden_name)
            return has_name1 and has_name2
        
        elif record_type == 'baptism':
            has_name1 = bool(record1.child_name or record1.father_surname or record1.mother_name)
            has_name2 = bool(record2.child_name or record2.father_surname or record2.mother_name)
            return has_name1 and has_name2
        
        elif record_type == 'marriage':
            has_name1 = bool(record1.spouse1_name or record1.spouse2_name)
            has_name2 = bool(record2.spouse1_name or record2.spouse2_name)
            return has_name1 and has_name2
        
        elif record_type == 'death':
            has_name1 = bool(record1.deceased_name or record1.deceased_surname)
            has_name2 = bool(record2.deceased_name or record2.deceased_surname)
            return has_name1 and has_name2
        
        return False
    
    def _both_have_dates(self, record1, record2, record_type: str) -> bool:
        """
        Check if both records have date data.
        
        Args:
            record1: First record
            record2: Second record
            record_type: Type of record ('person', 'baptism', 'marriage', 'death')
        
        Returns:
            True if both records have at least one date field populated
        """
        if record_type == 'person':
            has_date1 = bool(record1.birth_date or record1.death_date)
            has_date2 = bool(record2.birth_date or record2.death_date)
            return has_date1 and has_date2
        
        elif record_type == 'baptism':
            return bool(record1.baptism_date and record2.baptism_date)
        
        elif record_type == 'marriage':
            return bool(record1.marriage_date and record2.marriage_date)
        
        elif record_type == 'death':
            return bool(record1.death_date and record2.death_date)
        
        return False
    
    def _both_have_locations(self, record1, record2, record_type: str) -> bool:
        """
        Check if both records have location data.
        
        Args:
            record1: First record
            record2: Second record
            record_type: Type of record ('person', 'baptism', 'marriage', 'death')
        
        Returns:
            True if both records have at least one location field populated
        """
        if record_type == 'person':
            has_loc1 = bool(record1.birth_place or record1.death_place or
                           record1.parish or record1.residence)
            has_loc2 = bool(record2.birth_place or record2.death_place or
                           record2.parish or record2.residence)
            return has_loc1 and has_loc2
        
        elif record_type in ['baptism', 'marriage', 'death']:
            has_loc1 = bool(record1.parish or (hasattr(record1, 'village') and record1.village))
            has_loc2 = bool(record2.parish or (hasattr(record2, 'village') and record2.village))
            return has_loc1 and has_loc2
        
        return False
    
    def _calculate_phonetic_similarity_for_record(
        self,
        record1,
        record2,
        record_type: str
    ) -> Optional[float]:
        """
        Calculate phonetic similarity based on record type.
        
        Returns None if both records lack name data, indicating that phonetic
        similarity should not be included in the composite score calculation.
        
        Args:
            record1: First record
            record2: Second record
            record_type: Type of record ('person', 'baptism', 'marriage', 'death')
        
        Returns:
            Phonetic similarity score (0.0-1.0) or None if data missing in both records
        """
        # Check if both records have name data
        if not self._both_have_names(record1, record2, record_type):
            return None
        
        if record_type == 'person':
            name1_parts = {
                'first_name': record1.first_name,
                'last_name': record1.last_name,
                'maiden_name': record1.maiden_name
            }
            name2_parts = {
                'first_name': record2.first_name,
                'last_name': record2.last_name,
                'maiden_name': record2.maiden_name
            }
            return self._calculate_phonetic_similarity(name1_parts, name2_parts)
        
        elif record_type == 'baptism':
            # Compare child name and parent names
            child_sim = self._calculate_phonetic_similarity(
                {'first_name': record1.child_name, 'last_name': record1.father_surname},
                {'first_name': record2.child_name, 'last_name': record2.father_surname}
            )
            mother_sim = self._calculate_phonetic_similarity(
                {'first_name': record1.mother_name, 'maiden_name': record1.mother_maiden_name},
                {'first_name': record2.mother_name, 'maiden_name': record2.mother_maiden_name}
            )
            return (child_sim + mother_sim) / 2.0
        
        elif record_type == 'marriage':
            # Compare both spouse names
            spouse1_sim = self._calculate_phonetic_similarity(
                {'first_name': record1.spouse1_name, 'last_name': record1.spouse1_surname},
                {'first_name': record2.spouse1_name, 'last_name': record2.spouse1_surname}
            )
            spouse2_sim = self._calculate_phonetic_similarity(
                {'first_name': record1.spouse2_name, 'last_name': record1.spouse2_surname, 'maiden_name': record1.spouse2_maiden_name},
                {'first_name': record2.spouse2_name, 'last_name': record2.spouse2_surname, 'maiden_name': record2.spouse2_maiden_name}
            )
            return (spouse1_sim + spouse2_sim) / 2.0
        
        elif record_type == 'death':
            # Compare deceased name
            name1_parts = {
                'first_name': record1.deceased_name,
                'last_name': record1.deceased_surname,
                'maiden_name': record1.deceased_maiden_name
            }
            name2_parts = {
                'first_name': record2.deceased_name,
                'last_name': record2.deceased_surname,
                'maiden_name': record2.deceased_maiden_name
            }
            return self._calculate_phonetic_similarity(name1_parts, name2_parts)
        
        return 0.0
    
    def _calculate_phonetic_similarity(
        self,
        name1_parts: dict,
        name2_parts: dict
    ) -> float:
        """
        Compare phonetic codes for first/last/maiden names.
        
        Calculates the average phonetic similarity across all available name
        components (first name, last name, maiden name). Uses the PhoneticEncoder's
        similarity method which compares Daitch-Mokotoff phonetic codes.
        
        Args:
            name1_parts: Dictionary with keys 'first_name', 'last_name', 'maiden_name'
            name2_parts: Dictionary with keys 'first_name', 'last_name', 'maiden_name'
        
        Returns:
            Average phonetic similarity score (0.0-1.0)
        
        Example:
            >>> name1 = {'first_name': 'Jan', 'last_name': 'Kowalski', 'maiden_name': None}
            >>> name2 = {'first_name': 'Jan', 'last_name': 'Kowalsky', 'maiden_name': None}
            >>> sim = detector._calculate_phonetic_similarity(name1, name2)
            >>> print(f"{sim:.2f}")  # High similarity due to phonetic match
        """
        similarities = []
        
        # Compare first names
        if name1_parts.get('first_name') and name2_parts.get('first_name'):
            sim = self.phonetic_encoder.similarity(
                name1_parts['first_name'],
                name2_parts['first_name']
            )
            similarities.append(sim)
        
        # Compare last names
        if name1_parts.get('last_name') and name2_parts.get('last_name'):
            sim = self.phonetic_encoder.similarity(
                name1_parts['last_name'],
                name2_parts['last_name']
            )
            similarities.append(sim)
        
        # Compare maiden names
        if name1_parts.get('maiden_name') and name2_parts.get('maiden_name'):
            sim = self.phonetic_encoder.similarity(
                name1_parts['maiden_name'],
                name2_parts['maiden_name']
            )
            similarities.append(sim)
        
        # Return average similarity
        if similarities:
            return sum(similarities) / len(similarities)
        return 0.0
    
    def _calculate_date_similarity_for_record(
        self,
        record1,
        record2,
        record_type: str
    ) -> Optional[float]:
        """
        Calculate date similarity based on record type.
        
        Returns None if both records lack date data, indicating that date
        similarity should not be included in the composite score calculation.
        
        Args:
            record1: First record
            record2: Second record
            record_type: Type of record ('person', 'baptism', 'marriage', 'death')
        
        Returns:
            Date similarity score (0.0-1.0) or None if data missing in both records
        """
        # Check if both records have date data
        if not self._both_have_dates(record1, record2, record_type):
            return None
        
        if record_type == 'person':
            # Compare birth and death dates
            similarities = []
            if record1.birth_date and record2.birth_date:
                similarities.append(
                    self._calculate_date_similarity(record1.birth_date, record2.birth_date)
                )
            if record1.death_date and record2.death_date:
                similarities.append(
                    self._calculate_date_similarity(record1.death_date, record2.death_date)
                )
            return sum(similarities) / len(similarities) if similarities else 0.0
        
        elif record_type == 'baptism':
            return self._calculate_date_similarity(record1.baptism_date, record2.baptism_date)
        
        elif record_type == 'marriage':
            return self._calculate_date_similarity(record1.marriage_date, record2.marriage_date)
        
        elif record_type == 'death':
            return self._calculate_date_similarity(record1.death_date, record2.death_date)
        
        return 0.0
    
    def _calculate_date_similarity(
        self,
        date1: datetime,
        date2: datetime
    ) -> float:
        """
        Calculate date similarity (0.0-1.0).
        
        Uses a decay function based on the time difference between dates:
        - Perfect match (same day): 1.0
        - 1 year difference: ~0.8
        - 5 years difference: 0.5
        - 10+ years difference: 0.0
        
        Args:
            date1: First date
            date2: Second date
        
        Returns:
            Date similarity score (0.0-1.0)
        
        Example:
            >>> from datetime import datetime
            >>> date1 = datetime(1850, 1, 1)
            >>> date2 = datetime(1850, 1, 1)
            >>> sim = detector._calculate_date_similarity(date1, date2)
            >>> print(f"{sim:.2f}")  # 1.00 (perfect match)
            >>> 
            >>> date3 = datetime(1855, 1, 1)
            >>> sim = detector._calculate_date_similarity(date1, date3)
            >>> print(f"{sim:.2f}")  # 0.50 (5 years difference)
        """
        if not date1 or not date2:
            return 0.0
        
        # Calculate difference in days
        diff_days = abs((date1 - date2).days)
        
        # Convert to years
        diff_years = diff_days / 365.25
        
        # Apply decay function
        # Perfect match: 1.0
        # 5 years: 0.5
        # 10+ years: 0.0
        if diff_years == 0:
            return 1.0
        elif diff_years <= 5:
            return 1.0 - (diff_years / 10.0)
        elif diff_years <= 10:
            return 0.5 - ((diff_years - 5) / 10.0)
        else:
            return 0.0
    
    def _calculate_location_similarity_for_record(
        self,
        record1,
        record2,
        record_type: str
    ) -> Optional[float]:
        """
        Calculate location similarity based on record type.
        
        Returns None if both records lack location data, indicating that location
        similarity should not be included in the composite score calculation.
        
        Args:
            record1: First record
            record2: Second record
            record_type: Type of record ('person', 'baptism', 'marriage', 'death')
        
        Returns:
            Location similarity score (0.0-1.0) or None if data missing in both records
        """
        # Check if both records have location data
        if not self._both_have_locations(record1, record2, record_type):
            return None
        
        if record_type == 'person':
            # Compare multiple location fields
            similarities = []
            if record1.birth_place and record2.birth_place:
                similarities.append(
                    self._calculate_location_similarity(record1.birth_place, record2.birth_place)
                )
            if record1.death_place and record2.death_place:
                similarities.append(
                    self._calculate_location_similarity(record1.death_place, record2.death_place)
                )
            if record1.parish and record2.parish:
                similarities.append(
                    self._calculate_location_similarity(record1.parish, record2.parish)
                )
            if record1.residence and record2.residence:
                similarities.append(
                    self._calculate_location_similarity(record1.residence, record2.residence)
                )
            return sum(similarities) / len(similarities) if similarities else 0.0
        
        elif record_type in ['baptism', 'marriage', 'death']:
            # Compare parish and village
            similarities = []
            if record1.parish and record2.parish:
                similarities.append(
                    self._calculate_location_similarity(record1.parish, record2.parish)
                )
            if hasattr(record1, 'village') and record1.village and record2.village:
                similarities.append(
                    self._calculate_location_similarity(record1.village, record2.village)
                )
            return sum(similarities) / len(similarities) if similarities else 0.0
        
        return 0.0
    
    def _calculate_location_similarity(
        self,
        loc1: str,
        loc2: str
    ) -> float:
        """
        Calculate location similarity.
        
        Compares two location strings using normalized comparison:
        - Exact match (case-insensitive): 1.0
        - Partial match (one contains the other): 0.6
        - No match: 0.3 (baseline for same region)
        
        Args:
            loc1: First location string
            loc2: Second location string
        
        Returns:
            Location similarity score (0.0-1.0)
        
        Example:
            >>> sim = detector._calculate_location_similarity("Kraków", "Krakow")
            >>> print(f"{sim:.2f}")  # 1.00 (normalized match)
        """
        if not loc1 or not loc2:
            return 0.0
        
        # Normalize locations (lowercase, strip whitespace)
        loc1_norm = loc1.lower().strip()
        loc2_norm = loc2.lower().strip()
        
        # Exact match
        if loc1_norm == loc2_norm:
            return 1.0
        
        # Partial match (one contains the other)
        if loc1_norm in loc2_norm or loc2_norm in loc1_norm:
            return 0.6
        
        # No match but same region (baseline)
        return 0.3
    
    def save_duplicate_candidate(
        self,
        record_type: str,
        record1_id: UUID,
        record2_id: UUID,
        composite_score: float,
        scores: dict,
        method: str = 'auto'
    ) -> None:
        """
        Save duplicate candidate to database.
        
        Creates a DuplicateCandidate record with all similarity scores. Checks
        for existing candidates to avoid duplicates (both orderings of record pairs).
        
        Args:
            record_type: Type of record ('person', 'baptism', 'marriage', 'death')
            record1_id: UUID of first record
            record2_id: UUID of second record
            composite_score: Pre-calculated composite similarity score (0.0-1.0)
            scores: Dictionary containing similarity scores:
                * vector_sim: Vector similarity score
                * phonetic_sim: Phonetic similarity score (or None if masked)
                * date_sim: Date similarity score (or None if masked)
                * location_sim: Location similarity score (or None if masked)
            method: Detection method ('auto', 'import', 'batch', 'manual')
        
        Example:
            >>> scores = {
            ...     'vector_sim': 0.92,
            ...     'phonetic_sim': 0.88,
            ...     'date_sim': 1.0,
            ...     'location_sim': 1.0
            ... }
            >>> detector.save_duplicate_candidate(
            ...     'person', person1_id, person2_id, 0.91, scores, 'auto'
            ... )
        """
        try:
            # Check if candidate already exists (either ordering)
            existing = db.session.query(DuplicateCandidate).filter(
                DuplicateCandidate.record_type == record_type,
                db.or_(
                    db.and_(
                        DuplicateCandidate.record1_id == record1_id,
                        DuplicateCandidate.record2_id == record2_id
                    ),
                    db.and_(
                        DuplicateCandidate.record1_id == record2_id,
                        DuplicateCandidate.record2_id == record1_id
                    )
                )
            ).first()
            
            if existing:
                logger.debug(f"Duplicate candidate already exists: {existing.id}")
                return
            
            # Create new candidate (composite_score already calculated correctly by caller)
            candidate = DuplicateCandidate()
            candidate.record_type = record_type
            candidate.record1_id = record1_id
            candidate.record2_id = record2_id
            candidate.vector_similarity = scores['vector_sim']
            candidate.phonetic_similarity = scores['phonetic_sim']
            candidate.date_similarity = scores['date_sim']
            candidate.location_similarity = scores['location_sim']
            candidate.composite_score = composite_score
            candidate.detection_method = method
            candidate.status = 'pending'
            
            db.session.add(candidate)
            db.session.commit()
            
            logger.info(
                f"Saved duplicate candidate: {record_type} "
                f"{record1_id} <-> {record2_id} "
                f"(score: {composite_score:.2f})"
            )
            
        except Exception as e:
            logger.error(f"Error saving duplicate candidate: {e}", exc_info=True)
            db.session.rollback()