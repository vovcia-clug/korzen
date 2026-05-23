"""
Embedding Generator Service

This module provides embedding generation functionality for duplicate detection.
It converts extracted features into fixed-size 128-dimensional vector embeddings
suitable for similarity search using pgvector.

The embedding structure (128 dimensions total):
- Phonetic features: 32 dimensions (hash-based encoding of phonetic codes)
- Temporal features: 16 dimensions (normalized years, age, date ranges)
- Location features: 80 dimensions (hash-based encoding of locations)

The embeddings are L2-normalized for cosine similarity search.
"""

import hashlib
import logging
from typing import List, Optional

import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """
    Generates 128-dimensional vector embeddings from extracted features.
    
    This class converts feature dictionaries into fixed-size vector embeddings
    suitable for similarity search. It uses hash-based encoding for phonetic
    codes and locations, and normalized encoding for temporal features.
    
    Embedding Structure (128 dimensions):
    - Phonetic features: 32 dimensions
      * Hash-based encoding of phonetic codes
      * Captures name similarity
    - Temporal features: 16 dimensions
      * Normalized years (1600-2000 range)
      * Age encoding
      * Date range features
    - Location features: 80 dimensions
      * Hash-based encoding of location strings
      * Captures geographic similarity
    
    Features:
    - Hash-based encoding for categorical features
    - Normalized temporal encoding
    - L2 normalization for cosine similarity
    - Graceful handling of missing values
    - Support for both person and event embeddings
    
    Example:
        >>> generator = EmbeddingGenerator()
        >>> features = {
        ...     'phonetic_first_name': ['160000'],
        ...     'phonetic_last_name': ['584000'],
        ...     'birth_year': 1850,
        ...     'death_year': 1920,
        ...     'parish': 'krakow'
        ... }
        >>> embedding = generator.generate_person_embedding(features)
        >>> embedding.shape
        (128,)
        >>> np.linalg.norm(embedding)  # Should be ~1.0 (L2 normalized)
        1.0
    """
    
    # Dimension allocations
    PHONETIC_DIM = 32
    TEMPORAL_DIM = 16
    LOCATION_DIM = 80
    TOTAL_DIM = 128  # PHONETIC_DIM + TEMPORAL_DIM + LOCATION_DIM
    
    # Temporal normalization constants
    MIN_YEAR = 1600
    MAX_YEAR = 2000
    MAX_AGE = 120
    
    def __init__(self):
        """Initialize the embedding generator."""
        logger.info("EmbeddingGenerator initialized")
    
    def generate_person_embedding(self, features: dict) -> np.ndarray:
        """
        Generate a 128-dimensional embedding for a Person entity.
        
        Combines phonetic codes from names, temporal features from dates,
        and location features from places into a single normalized vector.
        
        Args:
            features: Dictionary of extracted features from FeatureExtractor
                Expected keys:
                - phonetic_first_name: List of phonetic codes
                - phonetic_last_name: List of phonetic codes
                - phonetic_maiden_name: List of phonetic codes
                - birth_year: Integer year or None
                - death_year: Integer year or None
                - age: Integer age or None
                - birth_place: Normalized location string
                - death_place: Normalized location string
                - parish: Normalized location string
                - residence: Normalized location string
                
        Returns:
            128-dimensional numpy array (L2 normalized)
            
        Example:
            >>> features = {
            ...     'phonetic_first_name': ['160000'],
            ...     'phonetic_last_name': ['584000', '585000'],
            ...     'phonetic_maiden_name': [],
            ...     'birth_year': 1850,
            ...     'death_year': 1920,
            ...     'age': 70,
            ...     'birth_place': 'krakow',
            ...     'death_place': 'krakow',
            ...     'parish': 'st mary',
            ...     'residence': 'krakow'
            ... }
            >>> embedding = generator.generate_person_embedding(features)
            >>> embedding.shape
            (128,)
        """
        # Collect phonetic codes
        phonetic_codes = []
        phonetic_codes.extend(features.get('phonetic_first_name', []))
        phonetic_codes.extend(features.get('phonetic_last_name', []))
        phonetic_codes.extend(features.get('phonetic_maiden_name', []))
        
        # Encode phonetic features (32 dimensions)
        phonetic_vector = self._encode_phonetic_features(phonetic_codes)
        
        # Encode temporal features (16 dimensions)
        temporal_vector = self._encode_temporal_features(
            birth_year=features.get('birth_year'),
            death_year=features.get('death_year'),
            age=features.get('age')
        )
        
        # Collect locations
        locations = []
        if features.get('birth_place'):
            locations.append(features['birth_place'])
        if features.get('death_place'):
            locations.append(features['death_place'])
        if features.get('parish'):
            locations.append(features['parish'])
        if features.get('residence'):
            locations.append(features['residence'])
        
        # Encode location features (80 dimensions)
        location_vector = self._encode_location_features(locations)
        
        # Concatenate all feature vectors
        embedding = np.concatenate([phonetic_vector, temporal_vector, location_vector])
        
        # L2 normalize
        embedding = self._normalize_vector(embedding)
        
        logger.debug(f"Generated person embedding: shape={embedding.shape}, norm={np.linalg.norm(embedding):.4f}")
        return embedding
    
    def generate_event_embedding(self, features: dict, event_type: str) -> np.ndarray:
        """
        Generate a 128-dimensional embedding for an event record.
        
        Combines phonetic codes from participant names, temporal features from
        event dates, and location features from event places into a single
        normalized vector. The encoding adapts based on event type.
        
        Args:
            features: Dictionary of extracted features from FeatureExtractor
            event_type: Type of event ('baptism', 'marriage', 'death')
                
        Returns:
            128-dimensional numpy array (L2 normalized)
            
        Example:
            >>> features = {
            ...     'baptism_year': 1850,
            ...     'birth_year': 1850,
            ...     'parish': 'st mary',
            ...     'village': 'krakow',
            ...     'phonetic_father_surname': ['584000'],
            ...     'phonetic_mother_maiden_name': ['693000']
            ... }
            >>> embedding = generator.generate_event_embedding(features, 'baptism')
            >>> embedding.shape
            (128,)
        """
        phonetic_codes = []
        locations = []
        birth_year = None
        death_year = None
        age = None
        
        if event_type == 'baptism':
            # Collect phonetic codes from parents
            phonetic_codes.extend(features.get('phonetic_father_name', []))
            phonetic_codes.extend(features.get('phonetic_father_surname', []))
            phonetic_codes.extend(features.get('phonetic_mother_name', []))
            phonetic_codes.extend(features.get('phonetic_mother_maiden_name', []))
            
            # Temporal features
            birth_year = features.get('baptism_year')  # Use baptism year as proxy
            if features.get('birth_year'):
                birth_year = features['birth_year']
            
            # Locations
            if features.get('parish'):
                locations.append(features['parish'])
            if features.get('village'):
                locations.append(features['village'])
        
        elif event_type == 'marriage':
            # Collect phonetic codes from spouses
            phonetic_codes.extend(features.get('phonetic_spouse1_name', []))
            phonetic_codes.extend(features.get('phonetic_spouse1_surname', []))
            phonetic_codes.extend(features.get('phonetic_spouse2_name', []))
            phonetic_codes.extend(features.get('phonetic_spouse2_surname', []))
            phonetic_codes.extend(features.get('phonetic_spouse2_maiden_name', []))
            
            # Temporal features
            birth_year = features.get('marriage_year')
            
            # Use spouse ages to estimate birth years if available
            if features.get('spouse1_age'):
                age = features['spouse1_age']
            elif features.get('spouse2_age'):
                age = features['spouse2_age']
            
            # Locations
            if features.get('parish'):
                locations.append(features['parish'])
            if features.get('village'):
                locations.append(features['village'])
        
        elif event_type == 'death':
            # Collect phonetic codes from deceased
            phonetic_codes.extend(features.get('phonetic_deceased_name', []))
            phonetic_codes.extend(features.get('phonetic_deceased_surname', []))
            phonetic_codes.extend(features.get('phonetic_deceased_maiden_name', []))
            
            # Temporal features
            death_year = features.get('death_year')
            age = features.get('age_years')
            
            # Calculate birth year from death year and age
            if death_year and age:
                birth_year = death_year - age
            
            # Locations
            if features.get('parish'):
                locations.append(features['parish'])
            if features.get('village'):
                locations.append(features['village'])
            if features.get('cemetery'):
                locations.append(features['cemetery'])
        
        # Encode phonetic features (32 dimensions)
        phonetic_vector = self._encode_phonetic_features(phonetic_codes)
        
        # Encode temporal features (16 dimensions)
        temporal_vector = self._encode_temporal_features(
            birth_year=birth_year,
            death_year=death_year,
            age=age
        )
        
        # Encode location features (80 dimensions)
        location_vector = self._encode_location_features(locations)
        
        # Concatenate all feature vectors
        embedding = np.concatenate([phonetic_vector, temporal_vector, location_vector])
        
        # L2 normalize
        embedding = self._normalize_vector(embedding)
        
        logger.debug(f"Generated {event_type} embedding: shape={embedding.shape}, norm={np.linalg.norm(embedding):.4f}")
        return embedding
    
    def _encode_phonetic_features(self, codes: List[str]) -> np.ndarray:
        """
        Encode phonetic codes into a 32-dimensional vector.
        
        Uses hash-based encoding to map phonetic codes to fixed dimensions.
        Multiple codes are aggregated by summing their hash vectors.
        
        Args:
            codes: List of phonetic code strings (e.g., ['584000', '585000'])
            
        Returns:
            32-dimensional numpy array
            
        Example:
            >>> codes = ['584000', '585000', '160000']
            >>> vector = generator._encode_phonetic_features(codes)
            >>> vector.shape
            (32,)
        """
        vector = np.zeros(self.PHONETIC_DIM, dtype=np.float32)
        
        if not codes:
            return vector
        
        # Hash each code and distribute across dimensions
        for code in codes:
            if not code:
                continue
            
            # Use MD5 hash for consistent distribution
            hash_obj = hashlib.md5(code.encode('utf-8'))
            hash_bytes = hash_obj.digest()
            
            # Convert hash bytes to indices (modulo dimension size)
            for i, byte in enumerate(hash_bytes[:self.PHONETIC_DIM]):
                idx = i % self.PHONETIC_DIM
                # Use byte value to create weighted contribution
                vector[idx] += byte / 255.0
        
        # Normalize by number of codes to prevent magnitude bias
        if len(codes) > 0:
            vector = vector / len(codes)
        
        return vector
    
    def _encode_temporal_features(
        self,
        birth_year: Optional[int] = None,
        death_year: Optional[int] = None,
        age: Optional[int] = None
    ) -> np.ndarray:
        """
        Encode temporal features into a 16-dimensional vector.
        
        Encodes years normalized to 1600-2000 range, age normalized to 0-120,
        and derived features like century and decade.
        
        Args:
            birth_year: Year of birth (or None)
            death_year: Year of death (or None)
            age: Age in years (or None)
            
        Returns:
            16-dimensional numpy array
            
        Example:
            >>> vector = generator._encode_temporal_features(
            ...     birth_year=1850, death_year=1920, age=70
            ... )
            >>> vector.shape
            (16,)
        """
        vector = np.zeros(self.TEMPORAL_DIM, dtype=np.float32)
        
        # Normalize birth year (dimensions 0-3)
        if birth_year is not None:
            normalized_birth = (birth_year - self.MIN_YEAR) / (self.MAX_YEAR - self.MIN_YEAR)
            normalized_birth = np.clip(normalized_birth, 0.0, 1.0)
            vector[0] = normalized_birth
            vector[1] = 1.0  # Flag indicating birth year is present
            
            # Century encoding (1600s=0, 1700s=1, 1800s=2, 1900s=3)
            century = (birth_year // 100) - 16
            if 0 <= century < 4:
                vector[2] = century / 3.0
            
            # Decade within century (0-9)
            decade = (birth_year % 100) // 10
            vector[3] = decade / 9.0
        
        # Normalize death year (dimensions 4-7)
        if death_year is not None:
            normalized_death = (death_year - self.MIN_YEAR) / (self.MAX_YEAR - self.MIN_YEAR)
            normalized_death = np.clip(normalized_death, 0.0, 1.0)
            vector[4] = normalized_death
            vector[5] = 1.0  # Flag indicating death year is present
            
            # Century encoding
            century = (death_year // 100) - 16
            if 0 <= century < 4:
                vector[6] = century / 3.0
            
            # Decade within century
            decade = (death_year % 100) // 10
            vector[7] = decade / 9.0
        
        # Normalize age (dimensions 8-11)
        if age is not None:
            normalized_age = age / self.MAX_AGE
            normalized_age = np.clip(normalized_age, 0.0, 1.0)
            vector[8] = normalized_age
            vector[9] = 1.0  # Flag indicating age is present
            
            # Age category encoding (child=0, adult=1, elderly=2)
            if age < 18:
                vector[10] = 0.0
            elif age < 60:
                vector[10] = 0.5
            else:
                vector[10] = 1.0
            
            # Age decade (0-12 for 0-120 years)
            age_decade = min(age // 10, 12)
            vector[11] = age_decade / 12.0
        
        # Lifespan features (dimensions 12-15)
        if birth_year is not None and death_year is not None:
            lifespan = death_year - birth_year
            normalized_lifespan = lifespan / self.MAX_AGE
            normalized_lifespan = np.clip(normalized_lifespan, 0.0, 1.0)
            vector[12] = normalized_lifespan
            vector[13] = 1.0  # Flag indicating lifespan is present
            
            # Mid-life year (useful for matching)
            mid_year = (birth_year + death_year) // 2
            normalized_mid = (mid_year - self.MIN_YEAR) / (self.MAX_YEAR - self.MIN_YEAR)
            normalized_mid = np.clip(normalized_mid, 0.0, 1.0)
            vector[14] = normalized_mid
            
            # Century span (did person live across century boundary?)
            century_span = 1.0 if (death_year // 100) > (birth_year // 100) else 0.0
            vector[15] = century_span
        
        return vector
    
    def _encode_location_features(self, locations: List[str]) -> np.ndarray:
        """
        Encode location strings into an 80-dimensional vector.
        
        Uses hash-based encoding to map location strings to fixed dimensions.
        Multiple locations are aggregated by summing their hash vectors.
        
        Args:
            locations: List of normalized location strings
            
        Returns:
            80-dimensional numpy array
            
        Example:
            >>> locations = ['krakow', 'st mary', 'malopolska']
            >>> vector = generator._encode_location_features(locations)
            >>> vector.shape
            (80,)
        """
        vector = np.zeros(self.LOCATION_DIM, dtype=np.float32)
        
        if not locations:
            return vector
        
        # Hash each location and distribute across dimensions
        for location in locations:
            if not location:
                continue
            
            # Use MD5 hash for consistent distribution
            hash_obj = hashlib.md5(location.encode('utf-8'))
            hash_bytes = hash_obj.digest()
            
            # Convert hash bytes to indices and values
            # Use multiple passes through hash bytes to fill 80 dimensions
            for pass_num in range(5):  # 5 passes * 16 bytes = 80 dimensions
                for i, byte in enumerate(hash_bytes):
                    idx = (pass_num * 16 + i) % self.LOCATION_DIM
                    # Use byte value to create weighted contribution
                    # Add rotation based on pass number for better distribution
                    rotated_byte = (byte + pass_num * 37) % 256
                    vector[idx] += rotated_byte / 255.0
        
        # Normalize by number of locations to prevent magnitude bias
        if len(locations) > 0:
            vector = vector / len(locations)
        
        return vector
    
    def _normalize_vector(self, vector: np.ndarray) -> np.ndarray:
        """
        Apply L2 normalization to a vector.
        
        L2 normalization ensures the vector has unit length, which is required
        for cosine similarity search with pgvector. Handles zero vectors by
        returning them unchanged.
        
        Args:
            vector: Input vector (any dimension)
            
        Returns:
            L2-normalized vector (same dimension as input)
            
        Example:
            >>> vector = np.array([3.0, 4.0])
            >>> normalized = generator._normalize_vector(vector)
            >>> np.linalg.norm(normalized)
            1.0
            >>> normalized
            array([0.6, 0.8])
        """
        norm = np.linalg.norm(vector)
        
        # Avoid division by zero
        if norm < 1e-10:
            logger.warning("Vector has near-zero norm, returning as-is")
            return vector
        
        return vector / norm
