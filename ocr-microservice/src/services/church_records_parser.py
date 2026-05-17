"""
Church records parser service for normalizing and preparing genealogical data.

This service takes structured church records from OpenRouter and prepares them
for GEDCOM generation by normalizing dates, names, and extracting relationships.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Union
from unidecode import unidecode

from ..models import ChurchRecordsDocument, EventRecord, PersonRecord, ParentRecord, WitnessRecord


@dataclass
class ParsedPerson:
    """Normalized individual data ready for GEDCOM generation."""
    person_id: str  # Unique ID for this person
    given_names: str
    surname: str
    gender: Optional[str] = None
    birth_date: Optional[str] = None  # GEDCOM format date
    birth_place: Optional[str] = None
    baptism_date: Optional[str] = None
    baptism_place: Optional[str] = None
    death_date: Optional[str] = None
    death_place: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class ParsedFamily:
    """Family relationship data."""
    family_id: str  # Unique ID for this family
    husband_id: Optional[str] = None
    wife_id: Optional[str] = None
    children_ids: List[str] = field(default_factory=list)
    marriage_date: Optional[str] = None
    marriage_place: Optional[str] = None


@dataclass
class ParsedSource:
    """Source citation data."""
    source_id: str
    title: str
    text: Optional[str] = None
    date: Optional[str] = None


@dataclass
class ParsedGenealogyData:
    """Complete parsed genealogy data ready for GEDCOM generation."""
    persons: List[ParsedPerson] = field(default_factory=list)
    families: List[ParsedFamily] = field(default_factory=list)
    sources: List[ParsedSource] = field(default_factory=list)
    person_to_families: Dict[str, List[str]] = field(default_factory=dict)  # Map person to their families


class ChurchRecordsParser:
    """Parser for church records that normalizes data for GEDCOM generation."""
    
    # Latin month names mapping
    LATIN_MONTHS = {
        'januarius': '01', 'januarii': '01', 'januar': '01',
        'februarius': '02', 'februarii': '02', 'februar': '02',
        'martius': '03', 'martii': '03', 'mart': '03',
        'aprilis': '04', 'aprili': '04', 'april': '04',
        'maius': '05', 'maii': '05', 'mai': '05',
        'junius': '06', 'junii': '06', 'juni': '06',
        'julius': '07', 'julii': '07', 'juli': '07',
        'augustus': '08', 'augusti': '08', 'august': '08',
        'september': '09', '7ber': '09', 'septembris': '09',
        'october': '10', '8ber': '10', 'octobris': '10',
        'november': '11', '9ber': '11', 'novembris': '11',
        'december': '12', '10ber': '12', 'decembris': '12',
    }
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize parser.
        
        Args:
            logger: Logger instance for logging operations
        """
        self.logger = logger or logging.getLogger(__name__)
        self._person_counter = 0
        self._family_counter = 0
        self._source_counter = 0
        self._person_cache: Dict[str, str] = {}  # Cache to avoid duplicate persons
    
    def parse(
        self,
        church_records: ChurchRecordsDocument,
        source_metadata: Optional[dict] = None
    ) -> ParsedGenealogyData:
        """
        Parse church records into normalized genealogy data.
        
        Args:
            church_records: Structured church records from OpenRouter
            source_metadata: Metadata about the source document
            
        Returns:
            ParsedGenealogyData ready for GEDCOM generation
        """
        self.logger.info(f"Parsing {len(church_records.records)} church records")
        
        # Reset counters for new parse
        self._person_counter = 0
        self._family_counter = 0
        self._source_counter = 0
        self._person_cache = {}
        
        result = ParsedGenealogyData()
        
        # Create source citation
        source = self._create_source(church_records, source_metadata)
        result.sources.append(source)
        
        # Process each event record
        for event in church_records.records:
            try:
                self._process_event(event, result, source.source_id)
            except Exception as e:
                self.logger.error(f"Error processing event {event.record_type}: {str(e)}")
                continue
        
        self.logger.info(
            f"Parsed {len(result.persons)} persons, "
            f"{len(result.families)} families"
        )
        
        return result
    
    def _create_source(
        self,
        church_records: ChurchRecordsDocument,
        metadata: Optional[dict]
    ) -> ParsedSource:
        """Create source citation from church records."""
        self._source_counter += 1
        source_id = f"S{self._source_counter}"
        
        title = "Church Records"
        if metadata:
            if 'filename' in metadata:
                title = f"Church Records - {metadata['filename']}"
            elif 'title' in metadata:
                title = metadata['title']
        
        date = None
        if church_records.document_metadata and 'date' in church_records.document_metadata:
            date = church_records.document_metadata['date']
        
        return ParsedSource(source_id=source_id, title=title, date=date)
    
    def _process_event(
        self,
        event: EventRecord,
        result: ParsedGenealogyData,
        source_id: str
    ) -> None:
        """Process a single event record."""
        if event.record_type == "baptism":
            self._process_baptism(event, result, source_id)
        elif event.record_type == "marriage":
            self._process_marriage(event, result, source_id)
        elif event.record_type == "death":
            self._process_death(event, result, source_id)
    
    def _process_baptism(
        self,
        event: EventRecord,
        result: ParsedGenealogyData,
        source_id: str
    ) -> None:
        """Process a baptism record."""
        # Create person for the child
        given_names, surname = self._normalize_name(event.person)
        person_id = self._get_or_create_person_id(given_names, surname, event.person.birth_date)
        
        child = ParsedPerson(
            person_id=person_id,
            given_names=given_names,
            surname=surname,
            gender=event.person.gender,
            birth_date=self._parse_date(event.person.birth_date),
            birth_place=event.person.birth_place,
            baptism_date=self._parse_date(event.event_date),
            baptism_place=event.event_place,
            notes=event.notes
        )
        result.persons.append(child)
        
        # Process parents if present
        if event.parents:
            father_id = None
            mother_id = None
            
            for parent in event.parents:
                parent_given, parent_surname = self._normalize_name(parent)
                parent_id = self._get_or_create_person_id(parent_given, parent_surname)
                
                gender = "M" if parent.role.lower() == "father" else "F"
                parent_person = ParsedPerson(
                    person_id=parent_id,
                    given_names=parent_given,
                    surname=parent_surname,
                    gender=gender
                )
                result.persons.append(parent_person)
                
                if parent.role.lower() == "father":
                    father_id = parent_id
                else:
                    mother_id = parent_id
            
            # Create family if we have parents
            if father_id or mother_id:
                family_id = self._create_family_id()
                family = ParsedFamily(
                    family_id=family_id,
                    husband_id=father_id,
                    wife_id=mother_id,
                    children_ids=[child.person_id]
                )
                result.families.append(family)
                
                # Update person-to-families mapping
                if father_id:
                    result.person_to_families.setdefault(father_id, []).append(family_id)
                if mother_id:
                    result.person_to_families.setdefault(mother_id, []).append(family_id)
    
    def _process_marriage(
        self,
        event: EventRecord,
        result: ParsedGenealogyData,
        source_id: str
    ) -> None:
        """Process a marriage record."""
        # Create groom
        groom_given, groom_surname = self._normalize_name(event.person)
        groom_id = self._get_or_create_person_id(groom_given, groom_surname, event.person.birth_date)
        
        groom = ParsedPerson(
            person_id=groom_id,
            given_names=groom_given,
            surname=groom_surname,
            gender=event.person.gender or "M",
            birth_date=self._parse_date(event.person.birth_date),
            birth_place=event.person.birth_place,
            notes=event.person.notes
        )
        result.persons.append(groom)
        
        # Create bride if present
        bride_id = None
        if event.spouse:
            bride_given, bride_surname = self._normalize_name(event.spouse)
            bride_id = self._get_or_create_person_id(bride_given, bride_surname, event.spouse.birth_date)
            
            bride = ParsedPerson(
                person_id=bride_id,
                given_names=bride_given,
                surname=bride_surname,
                gender=event.spouse.gender or "F",
                birth_date=self._parse_date(event.spouse.birth_date),
                birth_place=event.spouse.birth_place,
                notes=event.spouse.notes
            )
            result.persons.append(bride)
        
        # Create family
        family_id = self._create_family_id()
        family = ParsedFamily(
            family_id=family_id,
            husband_id=groom_id,
            wife_id=bride_id,
            marriage_date=self._parse_date(event.event_date),
            marriage_place=event.event_place
        )
        result.families.append(family)
        
        # Update person-to-families mapping
        result.person_to_families.setdefault(groom_id, []).append(family_id)
        if bride_id:
            result.person_to_families.setdefault(bride_id, []).append(family_id)
    
    def _process_death(
        self,
        event: EventRecord,
        result: ParsedGenealogyData,
        source_id: str
    ) -> None:
        """Process a death record."""
        given_names, surname = self._normalize_name(event.person)
        person_id = self._get_or_create_person_id(given_names, surname, event.person.birth_date)
        
        person = ParsedPerson(
            person_id=person_id,
            given_names=given_names,
            surname=surname,
            gender=event.person.gender,
            birth_date=self._parse_date(event.person.birth_date),
            birth_place=event.person.birth_place,
            death_date=self._parse_date(event.event_date),
            death_place=event.event_place,
            notes=event.notes
        )
        result.persons.append(person)
    
    def _normalize_name(self, record: Union[PersonRecord, ParentRecord, WitnessRecord]) -> Tuple[str, str]:
        """
        Normalize person name handling Latin variations.
        
        Args:
            record: PersonRecord, ParentRecord, or WitnessRecord object with name fields
            
        Returns:
            Tuple of (given_names, surname)
        """
        # Use unidecode to convert Latin characters to ASCII equivalents
        given_names = unidecode(record.given_names.strip())
        surname = unidecode(record.surname.strip())
        
        # Capitalize properly
        given_names = self._capitalize_name(given_names)
        surname = self._capitalize_name(surname)
        
        return given_names, surname
    
    def _capitalize_name(self, name: str) -> str:
        """Properly capitalize a name."""
        # Handle hyphenated names
        parts = name.split('-')
        capitalized_parts = [part.capitalize() for part in parts]
        return '-'.join(capitalized_parts)
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[str]:
        """
        Parse and normalize date to GEDCOM-compatible format.
        
        Handles:
        - ISO dates (YYYY-MM-DD, YYYY-MM, YYYY)
        - Latin month names
        - Partial dates
        
        Args:
            date_str: Date string in various formats
            
        Returns:
            Normalized date string or None
        """
        if not date_str:
            return None
        
        date_str = date_str.strip().lower()
        
        # Already in ISO format (YYYY-MM-DD, YYYY-MM, or YYYY)
        if re.match(r'^\d{4}(-\d{2})?(-\d{2})?$', date_str):
            return date_str
        
        # Try to extract date components
        # Pattern: Day Month Year (e.g., "5 Januarius 1820")
        match = re.search(r'(\d{1,2})\s+(\w+)\s+(\d{4})', date_str)
        if match:
            day, month_str, year = match.groups()
            month = self._parse_month(month_str)
            if month:
                return f"{year}-{month}-{int(day):02d}"
        
        # Pattern: Month Year (e.g., "Januarius 1820")
        match = re.search(r'(\w+)\s+(\d{4})', date_str)
        if match:
            month_str, year = match.groups()
            month = self._parse_month(month_str)
            if month:
                return f"{year}-{month}"
        
        # Pattern: Just year (e.g., "1820")
        match = re.search(r'\b(\d{4})\b', date_str)
        if match:
            return match.group(1)
        
        self.logger.warning(f"Could not parse date: {date_str}")
        return None
    
    def _parse_month(self, month_str: str) -> Optional[str]:
        """
        Parse Latin or English month name to number.
        
        Args:
            month_str: Month name in Latin or English
            
        Returns:
            Month number as string (01-12) or None
        """
        month_lower = month_str.lower().strip()
        
        # Check Latin months
        if month_lower in self.LATIN_MONTHS:
            return self.LATIN_MONTHS[month_lower]
        
        # Check English months (first 3 letters)
        english_months = {
            'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
            'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
            'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
        }
        
        if len(month_lower) >= 3:
            prefix = month_lower[:3]
            if prefix in english_months:
                return english_months[prefix]
        
        return None
    
    def _get_or_create_person_id(
        self,
        given_names: str,
        surname: str,
        birth_date: Optional[str] = None
    ) -> str:
        """
        Get existing person ID or create new one.
        
        Uses caching to avoid creating duplicate person records.
        """
        # Create cache key
        cache_key = f"{given_names}|{surname}|{birth_date or ''}"
        
        if cache_key in self._person_cache:
            return self._person_cache[cache_key]
        
        # Create new person ID
        self._person_counter += 1
        person_id = f"I{self._person_counter}"
        self._person_cache[cache_key] = person_id
        
        return person_id
    
    def _create_family_id(self) -> str:
        """Create a new unique family ID."""
        self._family_counter += 1
        return f"F{self._family_counter}"
