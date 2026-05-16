"""
GEDCOM parser module using ged4py to extract genealogical data.
"""
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging

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
        return 'utf-8'
        
    def parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """
        Parse GEDCOM date string to datetime object.
        
        Args:
            date_str: GEDCOM date string (e.g., "1 JAN 1900") or DateValue object
            
        Returns:
            datetime object or None if parsing fails
        """
        if not date_str:
            return None
            
        try:
            # Convert to string if it's a DateValue object or other type
            date_str = str(date_str) if not isinstance(date_str, str) else date_str
            original_date_str = date_str
            
            # Remove parentheses (used for BC dates and BET dates)
            date_str = date_str.strip().strip('()')
            
            # Handle BC dates and UNKNOWN - skip them
            if 'BC' in date_str.upper():
                logger.debug(f"Skipping BC date: {original_date_str}")
                return None
            
            if date_str.upper() in ('UNKNOWN', 'UNK', ''):
                logger.debug(f"Skipping unknown date: {original_date_str}")
                return None
            
            # Handle BETWEEN dates - extract first date
            # Examples: "BET 07 OCT AND 08 NOV 1260", "BET SEP AND NOV 1081", "BETWEEN 26 AND 27 NOV 1252"
            if 'BETWEEN' in date_str.upper() or date_str.upper().startswith('BET '):
                # Split by AND to get the two date parts
                and_parts = date_str.upper().split(' AND ')
                if len(and_parts) >= 2:
                    # Get first date part (preserve original case)
                    and_index = date_str.upper().index(' AND ')
                    first_part = date_str[:and_index].strip()
                    second_part = date_str[and_index + 5:].strip()
                    
                    # Remove BET/BETWEEN prefix from first part
                    for prefix in ['BETWEEN', 'BET']:
                        if first_part.upper().startswith(prefix):
                            first_part = first_part[len(prefix):].strip()
                            break
                    
                    # Parse the parts
                    first_parts = first_part.split()
                    second_parts = second_part.split()
                    
                    # Check if this is a year range format: "975 AND 1001"
                    if (len(first_parts) == 1 and first_parts[0].isdigit() and len(first_parts[0]) == 4 and
                        len(second_parts) == 1 and second_parts[0].isdigit() and len(second_parts[0]) == 4):
                        # This is a year range, use the first year
                        date_str = first_parts[0]
                    # Check if this is a day range format: "26 AND 27 NOV 1252"
                    elif len(first_parts) == 1 and first_parts[0].isdigit() and len(first_parts[0]) <= 2:
                        # This is a day range, use the day from first part with month/year from second part
                        # second_part should be like "27 NOV 1252" or just "NOV 1252"
                        if len(second_parts) >= 2:
                            # Skip the second day number if present
                            if second_parts[0].isdigit() and len(second_parts[0]) <= 2:
                                # Format: "day AND day MONTH YEAR"
                                date_str = first_parts[0] + ' ' + ' '.join(second_parts[1:])
                            else:
                                # Format: "day AND MONTH YEAR"
                                date_str = first_parts[0] + ' ' + ' '.join(second_parts)
                        else:
                            date_str = first_part
                    # Check if this is a month range: "25 SEP AND NOV 915" or "SEP AND NOV 915"
                    elif len(first_parts) <= 2 and len(second_parts) >= 2:
                        # Check if second part has a year at the end
                        if second_parts[-1].isdigit() and len(second_parts[-1]) == 4:
                            year = second_parts[-1]
                            # Use first part with year from second part
                            date_str = first_part + ' ' + year
                        else:
                            date_str = first_part
                    else:
                        # Normal BETWEEN format with full dates
                        # If first part doesn't end with a year (4 digits), append year from second part
                        if first_parts and not (first_parts[-1].isdigit() and len(first_parts[-1]) == 4):
                            # Look for year in second part
                            for part in reversed(second_parts):
                                if part.isdigit() and len(part) == 4:
                                    first_part = first_part + ' ' + part
                                    break
                        
                        date_str = first_part
            
            # Handle WEEN format (shortened BETWEEN)
            elif date_str.upper().startswith('WEEN'):
                and_parts = date_str.upper().split(' AND ')
                if len(and_parts) >= 2:
                    first_part = date_str[:date_str.upper().index(' AND ')].strip()
                    second_part = date_str[date_str.upper().index(' AND ') + 5:].strip()
                    
                    first_part = first_part.replace('WEEN', '').replace('ween', '').strip()
                    
                    # Check if first part has a year
                    first_parts = first_part.split()
                    second_parts = second_part.split()
                    
                    if first_parts and not (first_parts[-1].isdigit() and len(first_parts[-1]) == 4):
                        for part in reversed(second_parts):
                            if part.isdigit() and len(part) == 4:
                                first_part = first_part + ' ' + part
                                break
                    
                    date_str = first_part
            
            # Remove date modifiers (English and other languages)
            # Must check longer prefixes first to avoid partial matches
            prefixes_to_remove = [
                'ABOUT', 'BEFORE', 'AFTER', 'BETWEEN', 'ESTIMATED',
                'ABT', 'BEF', 'AFT', 'BET', 'CAL', 'EST',
                'ORE',  # Italian/Latin for "before"
                'ER',   # Italian/Latin for "after"
                'AND'
            ]
            
            for prefix in prefixes_to_remove:
                if date_str.upper().startswith(prefix + ' ') or date_str.upper() == prefix:
                    date_str = date_str[len(prefix):].strip()
                    break
            
            # Clean up any remaining text
            date_str = date_str.strip()
            
            # Try different date formats
            date_formats = [
                '%d %b %Y',      # 1 JAN 1900
                '%d %B %Y',      # 1 January 1900
                '%b %Y',         # JAN 1900
                '%B %Y',         # January 1900
                '%Y',            # 1900
            ]
            
            for fmt in date_formats:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
            
            # Try parsing just a year number (plain digits)
            if date_str.isdigit():
                year = int(date_str)
                if 1 <= year <= 9999:  # Valid year range
                    return datetime(year, 1, 1)
            
            # Try parsing month name + year without day
            try:
                # Handle cases like "DEC 894" or "MAY 936" or "APR 1646"
                parts = date_str.split()
                if len(parts) == 2:
                    month_str, year_str = parts
                    if year_str.isdigit():
                        year = int(year_str)
                        if 1 <= year <= 9999:
                            # Try to parse month (case-insensitive)
                            for month_fmt in ['%b', '%B']:
                                try:
                                    month_obj = datetime.strptime(month_str.upper(), month_fmt.upper())
                                    return datetime(year, month_obj.month, 1)
                                except ValueError:
                                    try:
                                        # Try with original case
                                        month_obj = datetime.strptime(month_str, month_fmt)
                                        return datetime(year, month_obj.month, 1)
                                    except ValueError:
                                        continue
            except Exception:
                pass
            
            # Try parsing full date with various separators
            try:
                parts = date_str.split()
                if len(parts) == 3:
                    day_str, month_str, year_str = parts
                    if day_str.isdigit() and year_str.isdigit():
                        day = int(day_str)
                        year = int(year_str)
                        if 1 <= year <= 9999 and 1 <= day <= 31:
                            # Try to parse month
                            for month_fmt in ['%b', '%B']:
                                try:
                                    month_obj = datetime.strptime(month_str.upper(), month_fmt.upper())
                                    return datetime(year, month_obj.month, day)
                                except ValueError:
                                    try:
                                        month_obj = datetime.strptime(month_str, month_fmt)
                                        return datetime(year, month_obj.month, day)
                                    except ValueError:
                                        continue
            except Exception:
                pass
                    
            logger.warning(f"Could not parse date: {original_date_str}")
            return None
        except Exception as e:
            logger.error(f"Error parsing date '{date_str}': {e}")
            return None
    
    def extract_name_parts(self, name: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract first name and last name from GEDCOM name format.
        
        GEDCOM format: "FirstName /LastName/"
        
        Args:
            name: GEDCOM name string or tuple
            
        Returns:
            Tuple of (first_name, last_name)
        """
        if not name:
            return None, None
        
        # Handle tuple (sometimes ged4py returns tuples)
        if isinstance(name, tuple):
            name = name[0] if name else None
            if not name:
                return None, None
        
        # Convert to string if needed
        name = str(name)
            
        # Remove slashes and split
        parts = name.replace('/', '').strip().split(None, 1)
        
        if len(parts) == 0:
            return None, None
        elif len(parts) == 1:
            return parts[0], None
        else:
            # Check if second part looks like a surname
            if parts[1]:
                return parts[0], parts[1]
            return parts[0], None
    
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
        
        return person
    
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
        
        for sub in family.sub_records:
            if sub.tag == 'HUSB' and sub.value:
                # Remove @ symbols from xref
                xref = sub.value.strip('@')
                if xref in self.person_map:
                    spouse1_id = self.person_map[xref]
            elif sub.tag == 'WIFE' and sub.value:
                xref = sub.value.strip('@')
                if xref in self.person_map:
                    spouse2_id = self.person_map[xref]
        
        # Create marriage record with GEDCOM ID tracking
        marriage_record = MarriageRecord(
            gedcom_id=marriage_gedcom_id,
            source_batch_id=self.batch.id,
            marriage_date=marriage_date.date(),
            parish=parish,
            spouse1_id=spouse1_id,
            spouse2_id=spouse2_id
        )
        
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
        
        return death_record
    
    def parse_and_import(self) -> Dict[str, int]:
        """
        Parse the GEDCOM file and import data into the database.
        
        Returns:
            Dictionary with import statistics
        """
        stats = {
            'persons': 0,
            'baptisms': 0,
            'marriages': 0,
            'deaths': 0,
            'errors': []
        }
        
        try:
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
            
            # Try different encodings
            encoding = self._detect_encoding()
            logger.info(f"Using encoding: {encoding}")
            
            with GedcomReader(self.filepath, encoding=encoding) as reader:
                # First pass: Create all Person records
                for individual in reader.records0('INDI'):
                    try:
                        person = self.create_person_from_individual(individual)
                        db.session.add(person)
                        db.session.flush()
                        
                        # Map GEDCOM ID to Person UUID
                        self.person_map[individual.xref_id] = str(person.id)
                        stats['persons'] += 1
                        
                        # Create genealogical record for raw data
                        # Extract name from sub_records
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
                        if not db.session.get(RecordBatch, self.batch.id):
                            db.session.add(self.batch)
                
                db.session.commit()
                logger.info(f"Created {stats['persons']} person records")
                
                # Second pass: Create baptism and death records
                with GedcomReader(self.filepath, encoding=encoding) as reader2:
                    for individual in reader2.records0('INDI'):
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
                                # Only add if it's a new record (not already in session)
                                if baptism not in db.session:
                                    db.session.add(baptism)
                                    stats['baptisms'] += 1
                            
                            # Create death record
                            death = self.create_death_record(individual, person)
                            if death:
                                # Only add if it's a new record (not already in session)
                                if death not in db.session:
                                    db.session.add(death)
                                    stats['deaths'] += 1
                                
                        except Exception as e:
                            error_msg = f"Error processing events for {individual.xref_id}: {str(e)}"
                            logger.error(error_msg)
                            stats['errors'].append(error_msg)
                
                db.session.commit()
                logger.info(f"Created {stats['baptisms']} baptism records and {stats['deaths']} death records")
                
                # Third pass: Create marriage records from families
                with GedcomReader(self.filepath, encoding=encoding) as reader3:
                    for family in reader3.records0('FAM'):
                        try:
                            marriage = self.create_marriage_record(family)
                            if marriage:
                                # Only add if it's a new record (not already in session)
                                if marriage not in db.session:
                                    db.session.add(marriage)
                                    stats['marriages'] += 1
                                
                                # Extract data from sub_records for raw data
                                husband_xref = None
                                wife_xref = None
                                marriage_date_value = None
                                
                                for sub in family.sub_records:
                                    if sub.tag == 'HUSB' and sub.value:
                                        husband_xref = sub.value.strip('@')
                                    elif sub.tag == 'WIFE' and sub.value:
                                        wife_xref = sub.value.strip('@')
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
                logger.info(f"Created {stats['marriages']} marriage records")
            
            # Import data into AGE graph
            try:
                logger.info("Starting AGE graph import...")
                self._import_to_age_graph(stats)
                logger.info("AGE graph import completed")
            except Exception as e:
                logger.error(f"AGE graph import failed: {e}")
                stats['errors'].append(f"AGE graph import failed: {str(e)}")
            
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
    
    def _import_to_age_graph(self, stats: Dict[str, int]):
        """
        Import the parsed data into Apache AGE graph database.
        
        Args:
            stats: Statistics dictionary to update with graph import info
        """
        try:
            # Get raw psycopg connection for AGE
            raw_conn = db.session.connection().connection
            
            # Create AGE importer
            importer = AgeGraphImporter(raw_conn)
            importer.create_graph_if_not_exists()
            
            # Create source vertex for this batch
            source_props = {
                'source_name': self.filepath,
                'import_date': datetime.utcnow().isoformat(),
                'description': f'GEDCOM import batch {self.batch.id}'
            }
            importer.create_source_vertex(str(self.batch.id), source_props)
            
            # Import all persons
            persons = Person.query.filter_by(source_batch_id=self.batch.id).all()
            for person in persons:
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
            
            # Import baptism events
            baptisms = BaptismRecord.query.filter_by(source_batch_id=self.batch.id).all()
            for baptism in baptisms:
                event_props = {
                    'gedcom_id': baptism.gedcom_id,
                    'event_type': 'baptism',
                    'date': baptism.baptism_date,
                    'place': baptism.baptism_place,
                    'parish': baptism.parish
                }
                importer.create_event_vertex(str(baptism.id), event_props)
                importer.create_baptized_in_edge(
                    str(baptism.person_id),
                    str(baptism.id),
                    str(baptism.baptism_date) if baptism.baptism_date else None
                )
                importer.create_from_source_edge(str(baptism.id), str(self.batch.id))
            
            # Import death events
            deaths = DeathRecord.query.filter_by(source_batch_id=self.batch.id).all()
            for death in deaths:
                event_props = {
                    'gedcom_id': death.gedcom_id,
                    'event_type': 'death',
                    'date': death.death_date,
                    'place': death.death_place,
                    'parish': death.parish
                }
                importer.create_event_vertex(str(death.id), event_props)
                importer.create_died_in_edge(
                    str(death.person_id),
                    str(death.id),
                    str(death.death_date) if death.death_date else None
                )
                importer.create_from_source_edge(str(death.id), str(self.batch.id))
            
            # Import marriages and create MARRIED_TO edges
            marriages = MarriageRecord.query.filter_by(source_batch_id=self.batch.id).all()
            for marriage in marriages:
                if marriage.husband_id and marriage.wife_id:
                    importer.create_marriage_edge(
                        str(marriage.husband_id),
                        str(marriage.wife_id),
                        str(marriage.marriage_date) if marriage.marriage_date else None,
                        marriage.marriage_place,
                        marriage.gedcom_id
                    )
            
            # Import parent-child relationships
            for person in persons:
                if person.father_id:
                    importer.create_parent_child_edge(
                        str(person.father_id),
                        str(person.id),
                        'father'
                    )
                if person.mother_id:
                    importer.create_parent_child_edge(
                        str(person.mother_id),
                        str(person.id),
                        'mother'
                    )
            
            # Get graph statistics
            graph_stats = importer.get_statistics()
            logger.info(f"AGE graph statistics: {graph_stats}")
            
        except Exception as e:
            logger.error(f"Error importing to AGE graph: {e}")
            raise
