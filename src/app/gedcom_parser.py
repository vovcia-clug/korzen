"""
GEDCOM parser module using ged4py to extract genealogical data.

This module has been refactored to improve maintainability:
- Date parsing is delegated to DateParser utility class
- Name parsing is delegated to NameParser utility class
- Constants are centralized in gedcom_constants module
- Parsing passes are extracted into separate methods
"""
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging
import tempfile
import os

from ged4py import GedcomReader
from ged4py.model import Individual, Record

from .extensions import db
from .models import (
    RecordBatch,
    GenealogicalRecord,
    Person,
    BaptismRecord,
    MarriageRecord,
    DeathRecord,
    UploadedFile
)
from .services.age_graph_importer import AgeGraphImporter
from .services.phonetic_encoder import PhoneticEncoder
from .services.feature_extractor import FeatureExtractor
from .services.embedding_generator import EmbeddingGenerator
from .services.duplicate_detector import DuplicateDetector
from .utils.date_parser import DateParser
from .utils.name_parser import NameParser
from .gedcom_constants import (
    UNICODE_REPLACEMENTS,
    DEFAULT_ENCODING,
    DUPLICATE_THRESHOLD
)

logger = logging.getLogger(__name__)


class GedcomParser:
    """Parser for GEDCOM files using ged4py."""
    
    def __init__(self, filepath: str, uploaded_file_id: str):
        """
        Initialize the parser.
        
        Args:
            filepath: Path to the GEDCOM file
            uploaded_file_id: UUID of the UploadedFile record
        """
        self.filepath = filepath
        self.uploaded_file_id = uploaded_file_id
        self.batch = None
        self.person_map: Dict[str, str] = {}  # Maps GEDCOM ID to Person UUID
        
        # Initialize duplicate detection services
        self.phonetic_encoder = PhoneticEncoder()
        self.feature_extractor = FeatureExtractor()
        self.embedding_generator = EmbeddingGenerator()
        self.duplicate_detector = DuplicateDetector(threshold=DUPLICATE_THRESHOLD)
    
    def _detect_encoding(self) -> str:
        """
        Detect the encoding of the GEDCOM file.
        
        Returns:
            Encoding name (utf-8, latin-1, cp1252, etc.)
        """
        # Try to read the CHAR tag from GEDCOM header
        try:
            with open(self.filepath, 'rb') as f:
                # Read first 1000 bytes to find CHAR tag
                header = f.read(1000)
                
                # Try UTF-8 first
                try:
                    header_str = header.decode('utf-8')
                    if '1 CHAR UTF-8' in header_str or '1 CHAR UTF8' in header_str:
                        return 'utf-8'
                except UnicodeDecodeError:
                    pass
                
                # Try Latin-1 (ISO-8859-1)
                try:
                    header_str = header.decode('latin-1')
                    if '1 CHAR ANSEL' in header_str:
                        return 'ansel'
                    if '1 CHAR ASCII' in header_str:
                        return 'ascii'
                    # Default to latin-1 for older files
                    return 'latin-1'
                except UnicodeDecodeError:
                    pass
                
                # Try Windows-1252
                try:
                    header.decode('cp1252')
                    return 'cp1252'
                except UnicodeDecodeError:
                    pass
                
        except Exception as e:
            logger.warning(f"Could not detect encoding: {e}")
        
        # Default to UTF-8
        return DEFAULT_ENCODING
    
    def _normalize_unicode_characters(self, filepath: str) -> str:
        """
        Normalize Unicode characters and remove blank lines from GEDCOM file.
        
        This handles OCR artifacts like smart quotes and other Unicode characters
        that are not compatible with strict GEDCOM parsers. Also removes blank lines
        which violate the GEDCOM specification.
        
        Args:
            filepath: Path to the GEDCOM file to normalize
            
        Returns:
            Path to the temporary file with normalized content
        """
        logger.info("Normalizing GEDCOM file (Unicode characters and blank lines)...")
        
        try:
            # Read the file content with UTF-8 encoding
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            # Check if any replacements are needed
            needs_unicode_normalization = any(char in content for char in UNICODE_REPLACEMENTS.keys())
            
            # Check for blank lines (GEDCOM spec prohibits blank lines)
            lines = content.splitlines(keepends=True)
            blank_line_count = sum(1 for line in lines if not line.strip())
            needs_blank_line_removal = blank_line_count > 0
            
            if needs_unicode_normalization or needs_blank_line_removal:
                if needs_unicode_normalization:
                    logger.info("Found Unicode characters that need normalization")
                    
                    # Apply all character replacements
                    for unicode_char, ascii_char in UNICODE_REPLACEMENTS.items():
                        if unicode_char in content:
                            count = content.count(unicode_char)
                            content = content.replace(unicode_char, ascii_char)
                            logger.debug(f"Replaced {count} occurrence(s) of {repr(unicode_char)} with {repr(ascii_char)}")
                
                if needs_blank_line_removal:
                    logger.info(f"Found {blank_line_count} blank line(s) that need to be removed")
                    
                    # Remove blank lines while preserving line endings
                    lines = content.splitlines(keepends=True)
                    non_blank_lines = [line for line in lines if line.strip()]
                    content = ''.join(non_blank_lines)
                    
                    logger.debug(f"Removed {blank_line_count} blank line(s) from GEDCOM file")
                
                # Create a temporary file with the normalized content
                temp_file = tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                                                        suffix='.ged', delete=False)
                temp_file.write(content)
                temp_file.close()
                
                logger.info(f"Created normalized temporary file: {temp_file.name}")
                return temp_file.name
            else:
                logger.info("No normalization needed")
                return filepath
                
        except Exception as e:
            logger.warning(f"Error during normalization: {e}. Using original file.")
            return filepath
    
    def parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """
        Parse GEDCOM date string to datetime object.
        
        This method now delegates to the DateParser utility class.
        
        Args:
            date_str: GEDCOM date string (e.g., "1 JAN 1900") or DateValue object
            
        Returns:
            datetime object or None if parsing fails
        """
        return DateParser.parse(date_str)
    
    def extract_name_parts(self, name: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract first name and last name from GEDCOM name format.
        
        This method now delegates to the NameParser utility class.
        
        GEDCOM format: "FirstName /LastName/"
        
        Args:
            name: GEDCOM name string or tuple
            
        Returns:
            Tuple of (first_name, last_name)
        """
        return NameParser.extract_name_parts(name)
    
    def create_person_from_individual(self, individual: Individual) -> Person:
        """
        Create a Person record from a GEDCOM Individual.
        Checks for existing person by GEDCOM ID to prevent duplicates.
        
        Args:
            individual: ged4py Individual object
            
        Returns:
            Person database object (existing or newly created)
        """
        # Check if person already exists by GEDCOM ID
        existing_person = Person.query.filter_by(gedcom_id=individual.xref_id).first()
        
        if existing_person:
            logger.info(f"Found existing person with GEDCOM ID {individual.xref_id}: {existing_person.first_name} {existing_person.last_name}")
            return existing_person
        
        # Extract name from sub_records
        first_name, last_name = None, None
        for sub in individual.sub_records:
            if sub.tag == 'NAME' and sub.value:
                first_name, last_name = self.extract_name_parts(sub.value)
                break
        
        # Extract gender from sub_records
        gender = None
        for sub in individual.sub_records:
            if sub.tag == 'SEX' and sub.value:
                if sub.value in ['M', 'F']:
                    gender = sub.value
                break
        
        # Extract birth information from sub_records
        birth_date = None
        birth_place = None
        for sub in individual.sub_records:
            if sub.tag == 'BIRT':
                for subsub in sub.sub_records:
                    if subsub.tag == 'DATE' and subsub.value:
                        birth_date = self.parse_date(subsub.value)
                    elif subsub.tag == 'PLAC' and subsub.value:
                        birth_place = subsub.value
                break
        
        # Extract death information from sub_records
        death_date = None
        death_place = None
        for sub in individual.sub_records:
            if sub.tag == 'DEAT':
                for subsub in sub.sub_records:
                    if subsub.tag == 'DATE' and subsub.value:
                        death_date = self.parse_date(subsub.value)
                    elif subsub.tag == 'PLAC' and subsub.value:
                        death_place = subsub.value
                break
        
        # Extract occupation from sub_records
        occupation = None
        for sub in individual.sub_records:
            if sub.tag == 'OCCU' and sub.value:
                occupation = sub.value
                break
        
        # Truncate long names to fit database constraints
        if first_name and len(first_name) > 100:
            first_name = first_name[:100]
        if last_name and len(last_name) > 100:
            last_name = last_name[:100]
        if birth_place and len(birth_place) > 200:
            birth_place = birth_place[:200]
        if death_place and len(death_place) > 200:
            death_place = death_place[:200]
        if occupation and len(occupation) > 200:
            occupation = occupation[:200]
        
        # Create Person record with GEDCOM ID and source batch tracking
        person = Person(
            gedcom_id=individual.xref_id,
            source_batch_id=self.batch.id,
            first_name=first_name,
            last_name=last_name,
            gender=gender,
            birth_date=birth_date.date() if birth_date else None,
            birth_place=birth_place,
            death_date=death_date.date() if death_date else None,
            death_place=death_place,
            occupation=occupation
        )
        
        # Generate embedding and phonetic codes for duplicate detection
        self._generate_person_embedding(person)
        
        return person
    
    def _generate_person_embedding(self, person: Person) -> None:
        """Generate and store embedding and phonetic codes for a person."""
        try:
            # Extract features
            features = self.feature_extractor.extract_person_features(person)
            
            # Generate phonetic codes
            person.first_name_phonetic = self.phonetic_encoder.encode(person.first_name)
            person.last_name_phonetic = self.phonetic_encoder.encode(person.last_name)
            person.maiden_name_phonetic = self.phonetic_encoder.encode(person.maiden_name)
            
            # Generate embedding
            embedding = self.embedding_generator.generate_person_embedding(features)
            person.embedding = embedding.tolist()
            
            logger.debug(f"Generated embedding for person: {person.first_name} {person.last_name}")
        except Exception as e:
            logger.warning(f"Failed to generate embedding for person: {e}")
    
    def _generate_baptism_embedding(self, baptism: BaptismRecord) -> None:
        """Generate and store embedding and phonetic codes for a baptism record."""
        try:
            # Extract features
            features = self.feature_extractor.extract_baptism_features(baptism)
            
            # Generate phonetic codes
            if baptism.child_name:
                baptism.child_name_phonetic = self.phonetic_encoder.encode(baptism.child_name)
            if baptism.father_surname:
                baptism.father_surname_phonetic = self.phonetic_encoder.encode(baptism.father_surname)
            if baptism.mother_maiden_name:
                baptism.mother_maiden_name_phonetic = self.phonetic_encoder.encode(baptism.mother_maiden_name)
            
            # Generate embedding
            embedding = self.embedding_generator.generate_event_embedding(features, 'baptism')
            baptism.embedding = embedding.tolist()
            
            logger.debug(f"Generated embedding for baptism record: {baptism.gedcom_id}")
        except Exception as e:
            logger.warning(f"Failed to generate embedding for baptism: {e}")
    
    def _generate_marriage_embedding(self, marriage: MarriageRecord) -> None:
        """Generate and store embedding and phonetic codes for a marriage record."""
        try:
            # Extract features
            features = self.feature_extractor.extract_marriage_features(marriage)
            
            # Generate phonetic codes
            if marriage.spouse1_surname:
                marriage.spouse1_surname_phonetic = self.phonetic_encoder.encode(marriage.spouse1_surname)
            if marriage.spouse2_surname:
                marriage.spouse2_surname_phonetic = self.phonetic_encoder.encode(marriage.spouse2_surname)
            if marriage.spouse2_maiden_name:
                marriage.spouse2_maiden_name_phonetic = self.phonetic_encoder.encode(marriage.spouse2_maiden_name)
            
            # Generate embedding
            embedding = self.embedding_generator.generate_event_embedding(features, 'marriage')
            marriage.embedding = embedding.tolist()
            
            logger.debug(f"Generated embedding for marriage record: {marriage.gedcom_id}")
        except Exception as e:
            logger.warning(f"Failed to generate embedding for marriage: {e}")
    
    def _generate_death_embedding(self, death: DeathRecord) -> None:
        """Generate and store embedding and phonetic codes for a death record."""
        try:
            # Extract features
            features = self.feature_extractor.extract_death_features(death)
            
            # Generate phonetic codes
            if death.deceased_surname:
                death.deceased_surname_phonetic = self.phonetic_encoder.encode(death.deceased_surname)
            if death.deceased_maiden_name:
                death.deceased_maiden_name_phonetic = self.phonetic_encoder.encode(death.deceased_maiden_name)
            
            # Generate embedding
            embedding = self.embedding_generator.generate_event_embedding(features, 'death')
            death.embedding = embedding.tolist()
            
            logger.debug(f"Generated embedding for death record: {death.gedcom_id}")
        except Exception as e:
            logger.warning(f"Failed to generate embedding for death: {e}")
    
    def _check_for_duplicates(self, person: Person) -> None:
        """Check for potential duplicates and log warnings."""
        try:
            duplicates = self.duplicate_detector.detect_person_duplicates(person, limit=5)
            
            if duplicates:
                logger.warning(
                    f"Found {len(duplicates)} potential duplicate(s) for "
                    f"{person.first_name} {person.last_name} (GEDCOM ID: {person.gedcom_id})"
                )
                for candidate, score, breakdown in duplicates:
                    logger.warning(
                        f"  - Match: {candidate.first_name} {candidate.last_name} "
                        f"(ID: {candidate.id}, Score: {score:.2f}, "
                        f"Vector: {breakdown['vector']:.2f}, "
                        f"Phonetic: {breakdown['phonetic']:.2f})"
                    )
        except Exception as e:
            logger.warning(f"Failed to check for duplicates: {e}")
    
    def create_baptism_record(self, individual: Individual, person: Person) -> Optional[BaptismRecord]:
        """
        Create a BaptismRecord from an Individual's baptism event.
        Checks for existing baptism record by GEDCOM ID to prevent duplicates.
        
        Args:
            individual: ged4py Individual object
            person: Person database object
            
        Returns:
            BaptismRecord or None if no baptism event found
        """
        # Find BAPM or CHR sub-record
        baptism_event = None
        for sub in individual.sub_records:
            if sub.tag in ('BAPM', 'CHR'):
                baptism_event = sub
                break
        
        if not baptism_event:
            return None
        
        # Generate GEDCOM ID for baptism event (use individual's ID + event type)
        baptism_gedcom_id = f"{individual.xref_id}_BAPM"
        
        # Check if baptism record already exists
        existing_baptism = BaptismRecord.query.filter_by(gedcom_id=baptism_gedcom_id).first()
        if existing_baptism:
            logger.info(f"Found existing baptism record with GEDCOM ID {baptism_gedcom_id}")
            return existing_baptism
        
        # Extract baptism date and place
        baptism_date = None
        parish = None
        
        for sub in baptism_event.sub_records:
            if sub.tag == 'DATE' and sub.value:
                baptism_date = self.parse_date(sub.value)
            elif sub.tag == 'PLAC' and sub.value:
                parish = sub.value
        
        if not baptism_date:
            return None
        
        # Create baptism record with GEDCOM ID tracking
        baptism_record = BaptismRecord(
            gedcom_id=baptism_gedcom_id,
            source_batch_id=self.batch.id,
            child_id=person.id,
            child_name=person.first_name,
            child_gender=person.gender,
            baptism_date=baptism_date.date(),
            birth_date=person.birth_date,
            parish=parish
        )
        
        # Generate embedding and phonetic codes for duplicate detection
        self._generate_baptism_embedding(baptism_record)
        
        return baptism_record
    
    def create_marriage_record(self, family: Record) -> Optional[MarriageRecord]:
        """
        Create a MarriageRecord from a GEDCOM Family record.
        Checks for existing marriage record by GEDCOM ID to prevent duplicates.
        
        Args:
            family: ged4py Record object representing a family
            
        Returns:
            MarriageRecord or None if no marriage event found
        """
        # Check if marriage record already exists by family GEDCOM ID
        marriage_gedcom_id = f"{family.xref_id}_MARR"
        existing_marriage = MarriageRecord.query.filter_by(gedcom_id=marriage_gedcom_id).first()
        if existing_marriage:
            logger.info(f"Found existing marriage record with GEDCOM ID {marriage_gedcom_id}")
            return existing_marriage
        
        # Find MARR sub-record
        marriage_event = None
        for sub in family.sub_records:
            if sub.tag == 'MARR':
                marriage_event = sub
                break
        
        if not marriage_event:
            return None
        
        # Extract marriage date
        marriage_date = None
        parish = None
        
        for sub in marriage_event.sub_records:
            if sub.tag == 'DATE' and sub.value:
                marriage_date = self.parse_date(sub.value)
            elif sub.tag == 'PLAC' and sub.value:
                parish = sub.value
        
        if not marriage_date:
            return None
        
        # Get spouse IDs from HUSB and WIFE tags
        spouse1_id = None
        spouse2_id = None
        spouse1_name = None
        spouse1_surname = None
        spouse2_name = None
        spouse2_surname = None
        spouse2_maiden_name = None
        
        for sub in family.sub_records:
            if sub.tag == 'HUSB' and sub.value:
                # Keep xref as-is (with @ symbols) to match person_map keys
                xref = sub.value
                
                # Try to find person by xref in person_map first
                if xref in self.person_map:
                    spouse1_id = self.person_map[xref]
                    person = db.session.get(Person, spouse1_id)
                else:
                    # Fallback: try to find person by GEDCOM ID in database
                    # Person.gedcom_id is stored WITH @ symbols
                    person = Person.query.filter_by(gedcom_id=xref, source_batch_id=self.batch.id).first()
                    if person:
                        spouse1_id = person.id
                        # Update person_map for future lookups
                        self.person_map[xref] = str(person.id)
                
                if person:
                    spouse1_name = person.first_name
                    spouse1_surname = person.last_name
                    
            elif sub.tag == 'WIFE' and sub.value:
                # Keep xref as-is (with @ symbols) to match person_map keys
                xref = sub.value
                
                # Try to find person by xref in person_map first
                if xref in self.person_map:
                    spouse2_id = self.person_map[xref]
                    person = db.session.get(Person, spouse2_id)
                else:
                    # Fallback: try to find person by GEDCOM ID in database
                    # Person.gedcom_id is stored WITH @ symbols
                    person = Person.query.filter_by(gedcom_id=xref, source_batch_id=self.batch.id).first()
                    if person:
                        spouse2_id = person.id
                        # Update person_map for future lookups
                        self.person_map[xref] = str(person.id)
                
                if person:
                    spouse2_name = person.first_name
                    spouse2_surname = person.last_name
                    spouse2_maiden_name = person.maiden_name
        
        # Create marriage record with GEDCOM ID tracking
        marriage_record = MarriageRecord(
            gedcom_id=marriage_gedcom_id,
            source_batch_id=self.batch.id,
            marriage_date=marriage_date.date(),
            parish=parish,
            spouse1_id=spouse1_id,
            spouse2_id=spouse2_id,
            spouse1_name=spouse1_name,
            spouse1_surname=spouse1_surname,
            spouse2_name=spouse2_name,
            spouse2_surname=spouse2_surname,
            spouse2_maiden_name=spouse2_maiden_name
        )
        
        # Generate embedding and phonetic codes for duplicate detection
        self._generate_marriage_embedding(marriage_record)
        
        return marriage_record
    
    def create_death_record(self, individual: Individual, person: Person) -> Optional[DeathRecord]:
        """
        Create a DeathRecord from an Individual's death event.
        Checks for existing death record by GEDCOM ID to prevent duplicates.
        
        Args:
            individual: ged4py Individual object
            person: Person database object
            
        Returns:
            DeathRecord or None if no death event found
        """
        # Generate GEDCOM ID for death event
        death_gedcom_id = f"{individual.xref_id}_DEAT"
        
        # Check if death record already exists
        existing_death = DeathRecord.query.filter_by(gedcom_id=death_gedcom_id).first()
        if existing_death:
            logger.info(f"Found existing death record with GEDCOM ID {death_gedcom_id}")
            return existing_death
        
        # Find DEAT sub-record
        death_event = None
        for sub in individual.sub_records:
            if sub.tag == 'DEAT':
                death_event = sub
                break
        
        if not death_event:
            return None
        
        # Extract death date and place
        death_date = None
        parish = None
        
        for sub in death_event.sub_records:
            if sub.tag == 'DATE' and sub.value:
                death_date = self.parse_date(sub.value)
            elif sub.tag == 'PLAC' and sub.value:
                parish = sub.value
        
        if not death_date:
            return None
        
        # Create death record with GEDCOM ID tracking
        death_record = DeathRecord(
            gedcom_id=death_gedcom_id,
            source_batch_id=self.batch.id,
            deceased_id=person.id,
            deceased_name=person.first_name,
            deceased_surname=person.last_name,
            death_date=death_date.date(),
            parish=parish
        )
        
        # Generate embedding and phonetic codes for duplicate detection
        self._generate_death_embedding(death_record)
        
        return death_record
    
    def process_family_children(self, family: Record) -> int:
        """
        Process parent-child relationships from a GEDCOM Family record.
        Updates Person records with father_id and mother_id.
        
        Args:
            family: ged4py Record object representing a family
            
        Returns:
            Number of children processed
        """
        from uuid import UUID
        
        # Extract parent references - DON'T strip @ symbols, they're in person_map keys
        father_xref = None
        mother_xref = None
        
        for sub in family.sub_records:
            if sub.tag == 'HUSB' and sub.value:
                father_xref = sub.value  # Keep @ symbols
            elif sub.tag == 'WIFE' and sub.value:
                mother_xref = sub.value  # Keep @ symbols
        
        # Get parent UUIDs from person_map (stored as strings)
        father_uuid_str = self.person_map.get(father_xref) if father_xref else None
        mother_uuid_str = self.person_map.get(mother_xref) if mother_xref else None
        
        # Convert string UUIDs to UUID objects
        father_id = UUID(father_uuid_str) if father_uuid_str else None
        mother_id = UUID(mother_uuid_str) if mother_uuid_str else None
        
        # Process children
        children_count = 0
        for sub in family.sub_records:
            if sub.tag == 'CHIL' and sub.value:
                child_xref = sub.value  # Keep @ symbols
                child_uuid_str = self.person_map.get(child_xref)
                
                if child_uuid_str:
                    # Update person record with parent references
                    person = db.session.get(Person, child_uuid_str)
                    if person:
                        # Only set if not already set (handle multiple family references)
                        if father_id and not person.father_id:
                            person.father_id = father_id
                            logger.debug(f"Set father for {person.first_name} {person.last_name}")
                        if mother_id and not person.mother_id:
                            person.mother_id = mother_id
                            logger.debug(f"Set mother for {person.first_name} {person.last_name}")
                        children_count += 1
                else:
                    logger.warning(f"Child {child_xref} not found in person_map for family {family.xref_id}")
        
        return children_count
    
    def _first_pass_create_persons(self, reader: GedcomReader, stats: Dict[str, int]) -> None:
        """
        First pass: Create all Person records from GEDCOM individuals.
        
        Args:
            reader: GedcomReader instance
            stats: Statistics dictionary to update
        """
        logger.info("Starting first pass: Creating person records...")
        
        for individual in reader.records0('INDI'):
            try:
                person = self.create_person_from_individual(individual)
                db.session.add(person)
                db.session.flush()
                
                # Check for potential duplicates
                self._check_for_duplicates(person)
                
                # Map GEDCOM ID to Person UUID
                self.person_map[individual.xref_id] = str(person.id)
                stats['persons'] += 1
                
                # Create genealogical record for raw data
                name_value = None
                sex_value = None
                birth_value = None
                death_value = None
                
                for sub in individual.sub_records:
                    if sub.tag == 'NAME' and sub.value:
                        name_value = str(sub.value)
                    elif sub.tag == 'SEX' and sub.value:
                        sex_value = str(sub.value)
                    elif sub.tag == 'BIRT':
                        for subsub in sub.sub_records:
                            if subsub.tag == 'DATE' and subsub.value:
                                birth_value = str(subsub.value)
                                break
                    elif sub.tag == 'DEAT':
                        for subsub in sub.sub_records:
                            if subsub.tag == 'DATE' and subsub.value:
                                death_value = str(subsub.value)
                                break
                
                raw_data = {
                    'gedcom_id': individual.xref_id,
                    'name': name_value,
                    'sex': sex_value,
                    'birth': birth_value,
                    'death': death_value,
                }
                
                gen_record = GenealogicalRecord(
                    batch_id=self.batch.id,
                    record_type='INDIVIDUAL',
                    raw_payload=raw_data,
                    external_id=individual.xref_id
                )
                db.session.add(gen_record)
                
            except Exception as e:
                # Rollback this individual and continue
                db.session.rollback()
                error_msg = f"Error processing individual {individual.xref_id}: {str(e)}"
                logger.error(error_msg)
                stats['errors'].append(error_msg)
                # Recreate batch after rollback
                try:
                    db.session.merge(self.batch)
                except:
                    db.session.add(self.batch)
        
        db.session.commit()
        logger.info(f"Completed first pass: Created {stats['persons']} person records")
    
    def _second_pass_create_events(self, filepath: str, encoding: str, stats: Dict[str, int]) -> None:
        """
        Second pass: Create baptism and death records from GEDCOM individuals.
        
        Args:
            filepath: Path to the GEDCOM file
            encoding: File encoding
            stats: Statistics dictionary to update
        """
        logger.info("Starting second pass: Creating event records...")
        
        with GedcomReader(filepath, encoding=encoding) as reader:
            for individual in reader.records0('INDI'):
                try:
                    if individual.xref_id not in self.person_map:
                        continue
                    
                    person_id = self.person_map[individual.xref_id]
                    person = db.session.get(Person, person_id)
                    
                    if not person:
                        continue
                    
                    # Create baptism record
                    baptism = self.create_baptism_record(individual, person)
                    if baptism:
                        if baptism not in db.session:
                            db.session.add(baptism)
                            stats['baptisms'] += 1
                    
                    # Create death record
                    death = self.create_death_record(individual, person)
                    if death:
                        if death not in db.session:
                            db.session.add(death)
                            stats['deaths'] += 1
                        
                except Exception as e:
                    error_msg = f"Error processing events for {individual.xref_id}: {str(e)}"
                    logger.error(error_msg)
                    stats['errors'].append(error_msg)
        
        db.session.commit()
        logger.info(f"Completed second pass: Created {stats['baptisms']} baptism records and {stats['deaths']} death records")
    
    def _third_pass_create_marriages(self, filepath: str, encoding: str, stats: Dict[str, int]) -> None:
        """
        Third pass: Create marriage records from GEDCOM family records.
        
        Args:
            filepath: Path to the GEDCOM file
            encoding: File encoding
            stats: Statistics dictionary to update
        """
        logger.info("Starting third pass: Creating marriage records...")
        
        with GedcomReader(filepath, encoding=encoding) as reader:
            for family in reader.records0('FAM'):
                try:
                    marriage = self.create_marriage_record(family)
                    if marriage:
                        if marriage not in db.session:
                            db.session.add(marriage)
                            stats['marriages'] += 1
                        
                        # Extract data from sub_records for raw data
                        husband_xref = None
                        wife_xref = None
                        marriage_date_value = None
                        
                        for sub in family.sub_records:
                            if sub.tag == 'HUSB' and sub.value:
                                husband_xref = sub.value
                            elif sub.tag == 'WIFE' and sub.value:
                                wife_xref = sub.value
                            elif sub.tag == 'MARR':
                                for subsub in sub.sub_records:
                                    if subsub.tag == 'DATE' and subsub.value:
                                        marriage_date_value = str(subsub.value)
                                        break
                        
                        # Create genealogical record for raw data
                        raw_data = {
                            'gedcom_id': family.xref_id,
                            'husband': husband_xref,
                            'wife': wife_xref,
                            'marriage_date': marriage_date_value,
                        }
                        
                        gen_record = GenealogicalRecord(
                            batch_id=self.batch.id,
                            record_type='FAMILY',
                            raw_payload=raw_data,
                            external_id=family.xref_id
                        )
                        db.session.add(gen_record)
                        
                except Exception as e:
                    error_msg = f"Error processing family {family.xref_id}: {str(e)}"
                    logger.error(error_msg)
                    stats['errors'].append(error_msg)
        
        db.session.commit()
        logger.info(f"Completed third pass: Created {stats['marriages']} marriage records")
    
    def _fourth_pass_process_relationships(self, filepath: str, encoding: str, stats: Dict[str, int]) -> None:
        """
        Fourth pass: Process parent-child relationships from GEDCOM family records.
        
        Args:
            filepath: Path to the GEDCOM file
            encoding: File encoding
            stats: Statistics dictionary to update
        """
        print("\n" + "="*80)
        print("STARTING PARENT-CHILD RELATIONSHIP PROCESSING")
        print("="*80)
        logger.info("Processing parent-child relationships...")
        children_processed = 0
        
        with GedcomReader(filepath, encoding=encoding) as reader:
            families = list(reader.records0('FAM'))
            print(f"Found {len(families)} families to process")
            
            for family in families:
                try:
                    print(f"\nProcessing family {family.xref_id}")
                    count = self.process_family_children(family)
                    children_processed += count
                    print(f"  -> Processed {count} children")
                except Exception as e:
                    error_msg = f"Error processing family children {family.xref_id}: {str(e)}"
                    print(f"  -> ERROR: {error_msg}")
                    logger.error(error_msg)
                    stats['errors'].append(error_msg)
                    import traceback
                    traceback.print_exc()
        
        print(f"\nCommitting changes to database...")
        db.session.commit()
        print(f"TOTAL: Processed {children_processed} parent-child relationships")
        print("="*80 + "\n")
        logger.info(f"Processed {children_processed} parent-child relationships")
        stats['parent_child_relationships'] = children_processed
    
    def parse_and_import(self) -> Dict[str, int]:
        """
        Parse the GEDCOM file and import data into the database.
        
        This method coordinates the four-pass import process:
        1. Create person records
        2. Create event records (baptisms, deaths)
        3. Create marriage records
        4. Process parent-child relationships
        
        Returns:
            Dictionary with import statistics
        """
        stats = {
            'persons': 0,
            'baptisms': 0,
            'marriages': 0,
            'deaths': 0,
            'parent_child_relationships': 0,
            'errors': []
        }
        
        # Track temporary file for cleanup
        normalized_filepath = None
        temp_file_created = False
        
        try:
            # Ensure session is in a clean state before starting
            try:
                db.session.rollback()
            except:
                pass
            
            # Update uploaded file status
            uploaded_file = db.session.get(UploadedFile, self.uploaded_file_id)
            if uploaded_file:
                uploaded_file.processing_status = 'processing'
                db.session.commit()
            
            # Create a record batch
            self.batch = RecordBatch(
                source='GEDCOM Import',
                description=f'Imported from {self.filepath}'
            )
            db.session.add(self.batch)
            db.session.flush()
            
            # Link uploaded file to batch
            if uploaded_file:
                uploaded_file.batch_id = self.batch.id
            
            # Parse GEDCOM file
            logger.info(f"Parsing GEDCOM file: {self.filepath}")
            
            # Normalize Unicode characters that may cause parsing issues
            normalized_filepath = self._normalize_unicode_characters(self.filepath)
            temp_file_created = (normalized_filepath != self.filepath)
            
            if temp_file_created:
                logger.info("Using normalized GEDCOM file for parsing")
            
            # Try different encodings
            encoding = self._detect_encoding()
            logger.info(f"Using encoding: {encoding}")
            
            # Execute the four parsing passes
            with GedcomReader(normalized_filepath, encoding=encoding) as reader:
                self._first_pass_create_persons(reader, stats)
            
            self._second_pass_create_events(self.filepath, encoding, stats)
            self._third_pass_create_marriages(self.filepath, encoding, stats)
            self._fourth_pass_process_relationships(self.filepath, encoding, stats)
            
            # Import data into AGE graph
            try:
                print("\n" + "="*80)
                print("STARTING AGE GRAPH IMPORT")
                print("="*80)
                logger.info("Starting AGE graph import...")
                self._import_to_age_graph(stats)
                logger.info("AGE graph import completed")
                print("AGE GRAPH IMPORT COMPLETED SUCCESSFULLY")
                print("="*80 + "\n")
            except Exception as e:
                print(f"\n!!! AGE GRAPH IMPORT FAILED !!!")
                print(f"Error: {e}")
                print("="*80 + "\n")
                logger.error(f"AGE graph import failed: {e}")
                stats['errors'].append(f"AGE graph import failed: {str(e)}")
                import traceback
                traceback.print_exc()
            
            # Update uploaded file status
            if uploaded_file:
                uploaded_file.processing_status = 'completed'
                db.session.commit()
            
            logger.info(f"GEDCOM import completed: {stats}")
            return stats
            
        except Exception as e:
            db.session.rollback()
            error_msg = f"Fatal error during GEDCOM import: {str(e)}"
            logger.error(error_msg)
            stats['errors'].append(error_msg)
            
            # Update uploaded file status
            if uploaded_file:
                uploaded_file.processing_status = 'failed'
                db.session.commit()
            
            raise
        
        finally:
            # Clean up temporary normalized file if it was created
            if temp_file_created and normalized_filepath:
                try:
                    if os.path.exists(normalized_filepath):
                        os.unlink(normalized_filepath)
                        logger.info(f"Cleaned up temporary normalized file: {normalized_filepath}")
                except Exception as e:
                    logger.warning(f"Failed to clean up temporary file {normalized_filepath}: {e}")
    
    def _import_to_age_graph(self, stats: Dict[str, int]):
        """
        Import the parsed data into Apache AGE graph database with detailed progress tracking.
        
        Args:
            stats: Statistics dictionary to update with graph import info
        """
        try:
            logger.info("="*80)
            logger.info("STARTING AGE GRAPH IMPORT")
            logger.info("="*80)
            
            # Get raw psycopg connection for AGE
            raw_conn = db.session.connection().connection
            
            # Create AGE importer
            importer = AgeGraphImporter(raw_conn)
            importer.create_graph_if_not_exists()
            
            # Query all records to be imported
            persons = Person.query.filter_by(source_batch_id=self.batch.id).all()
            baptisms = BaptismRecord.query.filter_by(source_batch_id=self.batch.id).all()
            deaths = DeathRecord.query.filter_by(source_batch_id=self.batch.id).all()
            marriages = MarriageRecord.query.filter_by(source_batch_id=self.batch.id).all()
            
            # Calculate totals for progress tracking
            total_persons = len(persons)
            total_baptisms = len(baptisms)
            total_deaths = len(deaths)
            total_marriages = len(marriages)
            total_parent_edges = sum(1 for p in persons if p.father_id) + sum(1 for p in persons if p.mother_id)
            
            total_records = total_persons + total_baptisms + total_deaths + total_marriages
            
            logger.info(f"Records to import:")
            logger.info(f"  - Persons: {total_persons}")
            logger.info(f"  - Baptism events: {total_baptisms}")
            logger.info(f"  - Death events: {total_deaths}")
            logger.info(f"  - Marriage relationships: {total_marriages}")
            logger.info(f"  - Parent-child relationships: {total_parent_edges}")
            logger.info(f"Total entities: {total_records}")
            logger.info("")
            
            # Create source vertex for this batch
            logger.info("Creating source vertex...")
            source_props = {
                'source_name': self.filepath,
                'import_date': datetime.utcnow().isoformat(),
                'description': f'GEDCOM import batch {self.batch.id}'
            }
            importer.create_source_vertex(str(self.batch.id), source_props)
            logger.info(f"✓ Source vertex created for batch {self.batch.id}")
            logger.info("")
            
            # Import all persons
            logger.info(f"Importing {total_persons} person vertices...")
            processed = 0
            for i, person in enumerate(persons, 1):
                person_props = {
                    'gedcom_id': person.gedcom_id,
                    'first_name': person.first_name,
                    'last_name': person.last_name,
                    'maiden_name': person.maiden_name,
                    'gender': person.gender,
                    'birth_date': person.birth_date,
                    'death_date': person.death_date,
                    'birth_place': person.birth_place,
                    'death_place': person.death_place,
                    'occupation': person.occupation
                }
                importer.create_person_vertex(str(person.id), person_props)
                importer.create_from_source_edge(str(person.id), str(self.batch.id))
                processed += 1
                
                # Log progress every 10% or every 100 records
                if i % max(1, total_persons // 10) == 0 or i % 100 == 0:
                    percentage = (i / total_persons) * 100
                    logger.info(f"  Progress: {i}/{total_persons} persons ({percentage:.1f}%) - Elapsed: {importer.progress.elapsed_time_str()}")
            
            logger.info(f"✓ Completed person import: {importer.progress.vertices_created['Person']} created, {importer.progress.vertices_skipped['Person']} skipped")
            logger.info(f"  Time elapsed: {importer.progress.elapsed_time_str()}")
            logger.info("")
            
            # Import baptism events
            if total_baptisms > 0:
                logger.info(f"Importing {total_baptisms} baptism event vertices...")
                for i, baptism in enumerate(baptisms, 1):
                    event_props = {
                        'gedcom_id': baptism.gedcom_id,
                        'event_type': 'baptism',
                        'date': baptism.baptism_date,
                        'place': baptism.village,
                        'parish': baptism.parish
                    }
                    importer.create_event_vertex(str(baptism.id), event_props)
                    if baptism.child_id:
                        importer.create_baptized_in_edge(
                            str(baptism.child_id),
                            str(baptism.id),
                            str(baptism.baptism_date) if baptism.baptism_date else None
                        )
                    importer.create_from_source_edge(str(baptism.id), str(self.batch.id))
                    
                    # Log progress every 10% or every 50 records
                    if i % max(1, total_baptisms // 10) == 0 or i % 50 == 0:
                        percentage = (i / total_baptisms) * 100
                        logger.info(f"  Progress: {i}/{total_baptisms} baptisms ({percentage:.1f}%) - Elapsed: {importer.progress.elapsed_time_str()}")
                
                logger.info(f"✓ Completed baptism import: {importer.progress.edges_created['BAPTIZED_IN']} edges created")
                logger.info(f"  Time elapsed: {importer.progress.elapsed_time_str()}")
                logger.info("")
            
            # Import death events
            if total_deaths > 0:
                logger.info(f"Importing {total_deaths} death event vertices...")
                for i, death in enumerate(deaths, 1):
                    event_props = {
                        'gedcom_id': death.gedcom_id,
                        'event_type': 'death',
                        'date': death.death_date,
                        'place': death.village or death.cemetery,
                        'parish': death.parish
                    }
                    importer.create_event_vertex(str(death.id), event_props)
                    if death.deceased_id:
                        importer.create_died_in_edge(
                            str(death.deceased_id),
                            str(death.id),
                            str(death.death_date) if death.death_date else None
                        )
                    importer.create_from_source_edge(str(death.id), str(self.batch.id))
                    
                    # Log progress every 10% or every 50 records
                    if i % max(1, total_deaths // 10) == 0 or i % 50 == 0:
                        percentage = (i / total_deaths) * 100
                        logger.info(f"  Progress: {i}/{total_deaths} deaths ({percentage:.1f}%) - Elapsed: {importer.progress.elapsed_time_str()}")
                
                logger.info(f"✓ Completed death import: {importer.progress.edges_created['DIED_IN']} edges created")
                logger.info(f"  Time elapsed: {importer.progress.elapsed_time_str()}")
                logger.info("")
            
            # Import marriages and create MARRIED_TO edges
            if total_marriages > 0:
                logger.info(f"Importing {total_marriages} marriage relationships...")
                valid_marriages = 0
                for i, marriage in enumerate(marriages, 1):
                    if marriage.spouse1_id and marriage.spouse2_id:
                        importer.create_marriage_edge(
                            str(marriage.spouse1_id),
                            str(marriage.spouse2_id),
                            str(marriage.marriage_date) if marriage.marriage_date else None,
                            marriage.village or marriage.parish,
                            marriage.gedcom_id
                        )
                        valid_marriages += 1
                    
                    # Log progress every 10% or every 50 records
                    if i % max(1, total_marriages // 10) == 0 or i % 50 == 0:
                        percentage = (i / total_marriages) * 100
                        logger.info(f"  Progress: {i}/{total_marriages} marriages ({percentage:.1f}%) - Elapsed: {importer.progress.elapsed_time_str()}")
                
                logger.info(f"✓ Completed marriage import: {importer.progress.edges_created['MARRIED_TO']//2} marriages ({importer.progress.edges_created['MARRIED_TO']} bi-directional edges)")
                logger.info(f"  Marriages with both spouses: {valid_marriages}")
                logger.info(f"  Time elapsed: {importer.progress.elapsed_time_str()}")
                logger.info("")
            
            # Import parent-child relationships
            if total_parent_edges > 0:
                logger.info(f"Importing {total_parent_edges} parent-child relationships...")
                processed_edges = 0
                for person in persons:
                    if person.father_id:
                        result = importer.create_parent_child_edge(
                            str(person.father_id),
                            str(person.id),
                            'father'
                        )
                        processed_edges += 1
                        
                        # Log progress every 10% or every 100 edges
                        if processed_edges % max(1, total_parent_edges // 10) == 0 or processed_edges % 100 == 0:
                            percentage = (processed_edges / total_parent_edges) * 100
                            logger.info(f"  Progress: {processed_edges}/{total_parent_edges} parent edges ({percentage:.1f}%) - Elapsed: {importer.progress.elapsed_time_str()}")
                    
                    if person.mother_id:
                        result = importer.create_parent_child_edge(
                            str(person.mother_id),
                            str(person.id),
                            'mother'
                        )
                        processed_edges += 1
                        
                        # Log progress every 10% or every 100 edges
                        if processed_edges % max(1, total_parent_edges // 10) == 0 or processed_edges % 100 == 0:
                            percentage = (processed_edges / total_parent_edges) * 100
                            logger.info(f"  Progress: {processed_edges}/{total_parent_edges} parent edges ({percentage:.1f}%) - Elapsed: {importer.progress.elapsed_time_str()}")
                
                logger.info(f"✓ Completed parent-child import: {importer.progress.edges_created['PARENT_OF']} edges created, {importer.progress.edges_skipped['PARENT_OF']} skipped")
                logger.info(f"  Time elapsed: {importer.progress.elapsed_time_str()}")
                logger.info("")
            
            # Log final summary
            importer.progress.log_summary()
            
            # Get graph statistics
            graph_stats = importer.get_statistics()
            logger.info("")
            logger.info("Current AGE graph statistics:")
            logger.info(f"  - Total persons in graph: {graph_stats.get('persons', 0)}")
            logger.info(f"  - Total events in graph: {graph_stats.get('events', 0)}")
            logger.info(f"  - Total sources in graph: {graph_stats.get('sources', 0)}")
            logger.info(f"  - Total parent-child relationships: {graph_stats.get('parent_of_edges', 0)}")
            logger.info(f"  - Total marriage relationships: {graph_stats.get('married_to_edges', 0)}")
            
            # Update stats with import summary
            stats['age_import'] = importer.progress.get_summary()
            stats['age_graph_stats'] = graph_stats
            
        except Exception as e:
            logger.error(f"Error importing to AGE graph: {e}")
            raise
