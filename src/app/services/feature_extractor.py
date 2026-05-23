"""
Feature Extractor Service

This module provides feature extraction functionality for duplicate detection.
It extracts relevant features from Person, BaptismRecord, MarriageRecord, and
DeathRecord models, preparing them for embedding generation.

Features extracted include:
- Phonetic codes (using Daitch-Mokotoff for Slavic names)
- Normalized text fields
- Temporal features (years, ages)
- Location features (parishes, villages, residences)
- Categorical features (gender, marital status)
- Relationship flags

This service is used as the first step in the duplicate detection pipeline.
"""

import logging
import re
from datetime import datetime
from typing import Optional

from ..models import BaptismRecord, DeathRecord, MarriageRecord, Person
from .phonetic_encoder import PhoneticEncoder

logger = logging.getLogger(__name__)


class FeatureExtractor:
    """
    Extracts features from genealogical records for duplicate detection.
    
    This class provides methods to extract and normalize features from Person
    entities and event records (baptisms, marriages, deaths). Features include
    phonetic codes, normalized text, temporal data, and location information.
    
    Features:
    - Phonetic encoding using Daitch-Mokotoff algorithm
    - Text normalization (lowercase, whitespace cleanup)
    - Location normalization (standardized format)
    - Temporal feature extraction (years from dates)
    - Relationship flag extraction
    
    Example:
        >>> extractor = FeatureExtractor()
        >>> person = Person.query.first()
        >>> features = extractor.extract_person_features(person)
        >>> print(features.keys())
        dict_keys(['phonetic_first_name', 'phonetic_last_name', 'normalized_first_name', ...])
        >>> 
        >>> baptism = BaptismRecord.query.first()
        >>> features = extractor.extract_baptism_features(baptism)
        >>> print(features['baptism_year'])
        1850
    """
    
    def __init__(self):
        """Initialize the feature extractor with a phonetic encoder."""
        self.phonetic_encoder = PhoneticEncoder()
        logger.info("FeatureExtractor initialized")
    
    def extract_person_features(self, person: Person) -> dict:
        """
        Extract all relevant features from a Person entity.
        
        Extracts phonetic codes, normalized text, temporal features, location
        features, categorical features, and relationship flags.
        
        Args:
            person: Person entity to extract features from
            
        Returns:
            Dictionary containing extracted features:
            - phonetic_first_name: List of phonetic codes for first name
            - phonetic_last_name: List of phonetic codes for last name
            - phonetic_maiden_name: List of phonetic codes for maiden name
            - normalized_first_name: Normalized first name text
            - normalized_last_name: Normalized last name text
            - normalized_maiden_name: Normalized maiden name text
            - birth_year: Year of birth (or None)
            - death_year: Year of death (or None)
            - age: Calculated age (or None)
            - birth_place: Normalized birth place
            - death_place: Normalized death place
            - parish: Normalized parish
            - residence: Normalized residence
            - gender: Gender code (M/F/Unknown)
            - has_father: Boolean flag
            - has_mother: Boolean flag
            
        Example:
            >>> person = Person(first_name="Jan", last_name="Kowalski", 
            ...                 birth_date=datetime(1850, 1, 1))
            >>> features = extractor.extract_person_features(person)
            >>> features['phonetic_first_name']
            ['160000']
            >>> features['birth_year']
            1850
        """
        features = {}
        
        # Phonetic codes for names
        if person.first_name:
            features['phonetic_first_name'] = self.phonetic_encoder.encode(person.first_name)
        else:
            features['phonetic_first_name'] = []
        
        if person.last_name:
            features['phonetic_last_name'] = self.phonetic_encoder.encode(person.last_name)
        else:
            features['phonetic_last_name'] = []
        
        if person.maiden_name:
            features['phonetic_maiden_name'] = self.phonetic_encoder.encode(person.maiden_name)
        else:
            features['phonetic_maiden_name'] = []
        
        # Normalized text fields
        features['normalized_first_name'] = self.normalize_text(person.first_name)
        features['normalized_last_name'] = self.normalize_text(person.last_name)
        features['normalized_maiden_name'] = self.normalize_text(person.maiden_name)
        
        # Temporal features
        features['birth_year'] = self.extract_year(person.birth_date)
        features['death_year'] = self.extract_year(person.death_date)
        
        # Calculate age if both dates available
        if features['birth_year'] and features['death_year']:
            features['age'] = features['death_year'] - features['birth_year']
        else:
            features['age'] = None
        
        # Location features
        features['birth_place'] = self.normalize_location(person.birth_place)
        features['death_place'] = self.normalize_location(person.death_place)
        features['parish'] = self.normalize_location(person.parish)
        features['residence'] = self.normalize_location(person.residence)
        
        # Categorical features
        features['gender'] = person.gender if person.gender else 'Unknown'
        
        # Relationship flags
        features['has_father'] = person.father_id is not None
        features['has_mother'] = person.mother_id is not None
        
        logger.debug(f"Extracted features for person {person.id}: {len(features)} features")
        return features
    
    def extract_baptism_features(self, baptism: BaptismRecord) -> dict:
        """
        Extract features from a BaptismRecord.
        
        Extracts event date, participant names (with phonetic codes), location
        information, and baptism-specific attributes.
        
        Args:
            baptism: BaptismRecord entity to extract features from
            
        Returns:
            Dictionary containing extracted features:
            - baptism_year: Year of baptism
            - birth_year: Year of birth (if available)
            - parish: Normalized parish name
            - village: Normalized village name
            - child_name: Normalized child name
            - child_gender: Gender code
            - phonetic_father_name: Phonetic codes for father's name
            - phonetic_father_surname: Phonetic codes for father's surname
            - phonetic_mother_name: Phonetic codes for mother's name
            - phonetic_mother_maiden_name: Phonetic codes for mother's maiden name
            - legitimate: Legitimacy flag
            - has_godparents: Boolean flag
            
        Example:
            >>> baptism = BaptismRecord(baptism_date=datetime(1850, 3, 15),
            ...                         father_surname="Kowalski")
            >>> features = extractor.extract_baptism_features(baptism)
            >>> features['baptism_year']
            1850
        """
        features = {}
        
        # Temporal features
        features['baptism_year'] = self.extract_year(baptism.baptism_date)
        features['birth_year'] = self.extract_year(baptism.birth_date)
        
        # Location features
        features['parish'] = self.normalize_location(baptism.parish)
        features['village'] = self.normalize_location(baptism.village)
        
        # Child information
        features['child_name'] = self.normalize_text(baptism.child_name)
        features['child_gender'] = baptism.child_gender if baptism.child_gender else 'Unknown'
        
        # Parent phonetic codes
        if baptism.father_name:
            features['phonetic_father_name'] = self.phonetic_encoder.encode(baptism.father_name)
        else:
            features['phonetic_father_name'] = []
        
        if baptism.father_surname:
            features['phonetic_father_surname'] = self.phonetic_encoder.encode(baptism.father_surname)
        else:
            features['phonetic_father_surname'] = []
        
        if baptism.mother_name:
            features['phonetic_mother_name'] = self.phonetic_encoder.encode(baptism.mother_name)
        else:
            features['phonetic_mother_name'] = []
        
        if baptism.mother_maiden_name:
            features['phonetic_mother_maiden_name'] = self.phonetic_encoder.encode(baptism.mother_maiden_name)
        else:
            features['phonetic_mother_maiden_name'] = []
        
        # Baptism-specific attributes
        features['legitimate'] = baptism.legitimate if baptism.legitimate is not None else False
        features['has_godparents'] = bool(baptism.godfather_name or baptism.godmother_name)
        
        logger.debug(f"Extracted features for baptism {baptism.id}: {len(features)} features")
        return features
    
    def extract_marriage_features(self, marriage: MarriageRecord) -> dict:
        """
        Extract features from a MarriageRecord.
        
        Extracts event date, spouse information (with phonetic codes), location
        information, and marriage-specific attributes.
        
        Args:
            marriage: MarriageRecord entity to extract features from
            
        Returns:
            Dictionary containing extracted features:
            - marriage_year: Year of marriage
            - parish: Normalized parish name
            - village: Normalized village name
            - phonetic_spouse1_name: Phonetic codes for spouse 1 name
            - phonetic_spouse1_surname: Phonetic codes for spouse 1 surname
            - phonetic_spouse2_name: Phonetic codes for spouse 2 name
            - phonetic_spouse2_surname: Phonetic codes for spouse 2 surname
            - phonetic_spouse2_maiden_name: Phonetic codes for spouse 2 maiden name
            - spouse1_status: Marital status of spouse 1
            - spouse2_status: Marital status of spouse 2
            - spouse1_age: Age of spouse 1
            - spouse2_age: Age of spouse 2
            - has_witnesses: Boolean flag
            
        Example:
            >>> marriage = MarriageRecord(marriage_date=datetime(1875, 6, 20),
            ...                           spouse1_surname="Nowak")
            >>> features = extractor.extract_marriage_features(marriage)
            >>> features['marriage_year']
            1875
        """
        features = {}
        
        # Temporal features
        features['marriage_year'] = self.extract_year(marriage.marriage_date)
        
        # Location features
        features['parish'] = self.normalize_location(marriage.parish)
        features['village'] = self.normalize_location(marriage.village)
        
        # Spouse 1 phonetic codes
        if marriage.spouse1_name:
            features['phonetic_spouse1_name'] = self.phonetic_encoder.encode(marriage.spouse1_name)
        else:
            features['phonetic_spouse1_name'] = []
        
        if marriage.spouse1_surname:
            features['phonetic_spouse1_surname'] = self.phonetic_encoder.encode(marriage.spouse1_surname)
        else:
            features['phonetic_spouse1_surname'] = []
        
        # Spouse 2 phonetic codes
        if marriage.spouse2_name:
            features['phonetic_spouse2_name'] = self.phonetic_encoder.encode(marriage.spouse2_name)
        else:
            features['phonetic_spouse2_name'] = []
        
        if marriage.spouse2_surname:
            features['phonetic_spouse2_surname'] = self.phonetic_encoder.encode(marriage.spouse2_surname)
        else:
            features['phonetic_spouse2_surname'] = []
        
        if marriage.spouse2_maiden_name:
            features['phonetic_spouse2_maiden_name'] = self.phonetic_encoder.encode(marriage.spouse2_maiden_name)
        else:
            features['phonetic_spouse2_maiden_name'] = []
        
        # Marriage-specific attributes
        features['spouse1_status'] = self.normalize_text(marriage.spouse1_status)
        features['spouse2_status'] = self.normalize_text(marriage.spouse2_status)
        features['spouse1_age'] = marriage.spouse1_age
        features['spouse2_age'] = marriage.spouse2_age
        features['has_witnesses'] = bool(marriage.witnesses)
        
        logger.debug(f"Extracted features for marriage {marriage.id}: {len(features)} features")
        return features
    
    def extract_death_features(self, death: DeathRecord) -> dict:
        """
        Extract features from a DeathRecord.
        
        Extracts event date, deceased person information (with phonetic codes),
        location information, and death-specific attributes.
        
        Args:
            death: DeathRecord entity to extract features from
            
        Returns:
            Dictionary containing extracted features:
            - death_year: Year of death
            - burial_year: Year of burial (if available)
            - parish: Normalized parish name
            - village: Normalized village name
            - cemetery: Normalized cemetery name
            - phonetic_deceased_name: Phonetic codes for deceased name
            - phonetic_deceased_surname: Phonetic codes for deceased surname
            - phonetic_deceased_maiden_name: Phonetic codes for deceased maiden name
            - marital_status: Marital status
            - age_years: Age at death
            - has_cause_of_death: Boolean flag
            - sacraments_received: Boolean flag
            
        Example:
            >>> death = DeathRecord(death_date=datetime(1900, 12, 25),
            ...                     deceased_surname="Wiśniewski", age_years=75)
            >>> features = extractor.extract_death_features(death)
            >>> features['death_year']
            1900
            >>> features['age_years']
            75
        """
        features = {}
        
        # Temporal features
        features['death_year'] = self.extract_year(death.death_date)
        features['burial_year'] = self.extract_year(death.burial_date)
        
        # Location features
        features['parish'] = self.normalize_location(death.parish)
        features['village'] = self.normalize_location(death.village)
        features['cemetery'] = self.normalize_location(death.cemetery)
        
        # Deceased person phonetic codes
        if death.deceased_name:
            features['phonetic_deceased_name'] = self.phonetic_encoder.encode(death.deceased_name)
        else:
            features['phonetic_deceased_name'] = []
        
        if death.deceased_surname:
            features['phonetic_deceased_surname'] = self.phonetic_encoder.encode(death.deceased_surname)
        else:
            features['phonetic_deceased_surname'] = []
        
        if death.deceased_maiden_name:
            features['phonetic_deceased_maiden_name'] = self.phonetic_encoder.encode(death.deceased_maiden_name)
        else:
            features['phonetic_deceased_maiden_name'] = []
        
        # Death-specific attributes
        features['marital_status'] = self.normalize_text(death.marital_status)
        features['age_years'] = death.age_years
        features['has_cause_of_death'] = bool(death.cause_of_death)
        features['sacraments_received'] = death.sacraments_received if death.sacraments_received is not None else False
        
        logger.debug(f"Extracted features for death {death.id}: {len(features)} features")
        return features
    
    def normalize_text(self, text: Optional[str]) -> str:
        """
        Normalize text for comparison.
        
        Performs basic text normalization including:
        - Converting to lowercase
        - Stripping leading/trailing whitespace
        - Collapsing multiple spaces to single space
        - Removing special characters (keeping letters, numbers, spaces)
        
        Args:
            text: Text to normalize (can be None)
            
        Returns:
            Normalized text string (empty string if input is None)
            
        Example:
            >>> extractor.normalize_text("  Jan   Kowalski  ")
            'jan kowalski'
            >>> extractor.normalize_text("O'Brien")
            'obrien'
            >>> extractor.normalize_text(None)
            ''
        """
        if not text:
            return ''
        
        # Convert to lowercase
        normalized = text.lower()
        
        # Remove special characters (keep letters, numbers, spaces)
        normalized = re.sub(r'[^a-z0-9\s]', '', normalized)
        
        # Collapse multiple spaces to single space
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # Strip leading/trailing whitespace
        normalized = normalized.strip()
        
        return normalized
    
    def normalize_location(self, location: Optional[str]) -> str:
        """
        Normalize location names for comparison.
        
        Performs location-specific normalization including:
        - Basic text normalization (lowercase, whitespace)
        - Removing common prefixes/suffixes (e.g., "parish of", "village of")
        - Standardizing abbreviations
        
        Args:
            location: Location name to normalize (can be None)
            
        Returns:
            Normalized location string (empty string if input is None)
            
        Example:
            >>> extractor.normalize_location("Parish of Kraków")
            'krakow'
            >>> extractor.normalize_location("St. Mary's Church")
            'st marys church'
            >>> extractor.normalize_location(None)
            ''
        """
        if not location:
            return ''
        
        # Start with basic text normalization
        normalized = self.normalize_text(location)
        
        # Remove common location prefixes/suffixes
        prefixes = ['parish of', 'village of', 'town of', 'city of']
        for prefix in prefixes:
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):].strip()
        
        return normalized
    
    def extract_year(self, date: Optional[datetime]) -> Optional[int]:
        """
        Extract year from a datetime object.
        
        Args:
            date: Datetime object (can be None)
            
        Returns:
            Year as integer, or None if date is None
            
        Example:
            >>> from datetime import datetime
            >>> extractor.extract_year(datetime(1850, 3, 15))
            1850
            >>> extractor.extract_year(None)
            None
        """
        if date is None:
            return None
        
        return date.year
