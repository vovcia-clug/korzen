"""
GEDCOM file generator service.

This service takes parsed genealogy data and generates valid GEDCOM 5.5.1 format files.
"""

import logging
from datetime import datetime
from typing import Optional, List

from .church_records_parser import ParsedGenealogyData, ParsedPerson, ParsedFamily, ParsedSource


class GedcomGenerator:
    """Generator for GEDCOM 5.5.1 format genealogy files."""
    
    # GEDCOM date format month abbreviations
    GEDCOM_MONTHS = {
        '01': 'JAN', '02': 'FEB', '03': 'MAR', '04': 'APR',
        '05': 'MAY', '06': 'JUN', '07': 'JUL', '08': 'AUG',
        '09': 'SEP', '10': 'OCT', '11': 'NOV', '12': 'DEC'
    }
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize GEDCOM generator.
        
        Args:
            logger: Logger instance for logging operations
        """
        self.logger = logger or logging.getLogger(__name__)
    
    def generate(
        self,
        parsed_data: ParsedGenealogyData,
        source_reference: Optional[str] = None
    ) -> str:
        """
        Generate GEDCOM 5.5.1 format file content.
        
        Args:
            parsed_data: Parsed genealogy data
            source_reference: Reference to source document (e.g., S3 URI)
            
        Returns:
            Complete GEDCOM file content as string
        """
        self.logger.info(
            f"Generating GEDCOM for {len(parsed_data.persons)} persons, "
            f"{len(parsed_data.families)} families"
        )
        
        lines = []
        
        # Header
        lines.extend(self._create_header())
        
        # Sources
        for source in parsed_data.sources:
            lines.extend(self._create_source_record(source, source_reference))
        
        # Individuals
        for person in parsed_data.persons:
            lines.extend(self._create_individual_record(person, parsed_data))
        
        # Families
        for family in parsed_data.families:
            lines.extend(self._create_family_record(family, parsed_data))
        
        # Trailer
        lines.append("0 TRLR")
        
        gedcom_content = "\n".join(lines)
        
        self.logger.info(f"Generated GEDCOM with {len(lines)} lines")
        
        return gedcom_content
    
    def _create_header(self) -> List[str]:
        """
        Generate GEDCOM header.
        
        Returns:
            List of header lines
        """
        now = datetime.utcnow()
        date_str = now.strftime("%d %b %Y").upper()
        time_str = now.strftime("%H:%M:%S")
        
        return [
            "0 HEAD",
            "1 SOUR OCR-to-GEDCOM",
            "2 VERS 1.0",
            "2 NAME OCR to GEDCOM Converter",
            "2 CORP Genealogy OCR Pipeline",
            "1 DEST ANY",
            "1 DATE " + date_str,
            "2 TIME " + time_str,
            "1 SUBM @SUBM1@",
            "1 FILE generated.ged",
            "1 GEDC",
            "2 VERS 5.5.1",
            "2 FORM LINEAGE-LINKED",
            "1 CHAR UTF-8",
            "0 @SUBM1@ SUBM",
            "1 NAME OCR Pipeline",
        ]
    
    def _create_source_record(
        self,
        source: ParsedSource,
        source_reference: Optional[str] = None
    ) -> List[str]:
        """
        Generate source record.
        
        Args:
            source: Source citation data
            source_reference: Additional reference (e.g., S3 URI)
            
        Returns:
            List of source record lines
        """
        lines = [
            f"0 @{source.source_id}@ SOUR",
            f"1 TITL {source.title}",
        ]
        
        if source.text:
            lines.append(f"1 TEXT {source.text}")
        
        if source.date:
            gedcom_date = self._format_date_for_gedcom(source.date)
            if gedcom_date:
                lines.append(f"1 DATE {gedcom_date}")
        
        if source_reference:
            lines.append(f"1 NOTE {source_reference}")
        
        return lines
    
    def _create_individual_record(
        self,
        person: ParsedPerson,
        parsed_data: ParsedGenealogyData
    ) -> List[str]:
        """
        Generate individual (person) record.
        
        Args:
            person: Person data
            parsed_data: Complete parsed data for context
            
        Returns:
            List of individual record lines
        """
        lines = [
            f"0 @{person.person_id}@ INDI",
            f"1 NAME {person.given_names} /{person.surname}/",
        ]
        
        # Given names
        if person.given_names:
            lines.append(f"2 GIVN {person.given_names}")
        
        # Surname
        if person.surname:
            lines.append(f"2 SURN {person.surname}")
        
        # Gender
        if person.gender:
            lines.append(f"1 SEX {person.gender}")
        
        # Birth event
        if person.birth_date or person.birth_place:
            lines.append("1 BIRT")
            if person.birth_date:
                gedcom_date = self._format_date_for_gedcom(person.birth_date)
                if gedcom_date:
                    lines.append(f"2 DATE {gedcom_date}")
            if person.birth_place:
                lines.append(f"2 PLAC {person.birth_place}")
        
        # Baptism event
        if person.baptism_date or person.baptism_place:
            lines.append("1 CHR")  # Christening/Baptism
            if person.baptism_date:
                gedcom_date = self._format_date_for_gedcom(person.baptism_date)
                if gedcom_date:
                    lines.append(f"2 DATE {gedcom_date}")
            if person.baptism_place:
                lines.append(f"2 PLAC {person.baptism_place}")
        
        # Death event
        if person.death_date or person.death_place:
            lines.append("1 DEAT")
            if person.death_date:
                gedcom_date = self._format_date_for_gedcom(person.death_date)
                if gedcom_date:
                    lines.append(f"2 DATE {gedcom_date}")
            if person.death_place:
                lines.append(f"2 PLAC {person.death_place}")
        
        # Notes
        if person.notes:
            # Split long notes across multiple lines if needed
            note_lines = self._wrap_note(person.notes)
            for i, note_line in enumerate(note_lines):
                if i == 0:
                    lines.append(f"1 NOTE {note_line}")
                else:
                    lines.append(f"2 CONT {note_line}")
        
        # Family relationships
        if person.person_id in parsed_data.person_to_families:
            for family_id in parsed_data.person_to_families[person.person_id]:
                family = next(
                    (f for f in parsed_data.families if f.family_id == family_id),
                    None
                )
                if family:
                    # Check if person is spouse or child in this family
                    if person.person_id == family.husband_id or person.person_id == family.wife_id:
                        lines.append(f"1 FAMS @{family_id}@")
                    elif person.person_id in family.children_ids:
                        lines.append(f"1 FAMC @{family_id}@")
        
        return lines
    
    def _create_family_record(
        self,
        family: ParsedFamily,
        parsed_data: ParsedGenealogyData
    ) -> List[str]:
        """
        Generate family record.
        
        Args:
            family: Family data
            parsed_data: Complete parsed data for context
            
        Returns:
            List of family record lines
        """
        lines = [f"0 @{family.family_id}@ FAM"]
        
        # Husband
        if family.husband_id:
            lines.append(f"1 HUSB @{family.husband_id}@")
        
        # Wife
        if family.wife_id:
            lines.append(f"1 WIFE @{family.wife_id}@")
        
        # Children
        for child_id in family.children_ids:
            lines.append(f"1 CHIL @{child_id}@")
        
        # Marriage event
        if family.marriage_date or family.marriage_place:
            lines.append("1 MARR")
            if family.marriage_date:
                gedcom_date = self._format_date_for_gedcom(family.marriage_date)
                if gedcom_date:
                    lines.append(f"2 DATE {gedcom_date}")
            if family.marriage_place:
                lines.append(f"2 PLAC {family.marriage_place}")
        
        return lines
    
    def _format_date_for_gedcom(self, date_str: Optional[str]) -> Optional[str]:
        """
        Format date string to GEDCOM standard format.
        
        GEDCOM format:
        - Full date: DD MMM YYYY (e.g., "15 JAN 1820")
        - Month and year: MMM YYYY (e.g., "JAN 1820")
        - Year only: YYYY (e.g., "1820")
        - Partial dates: "ABT YYYY" for approximate
        
        Args:
            date_str: Date in ISO format (YYYY-MM-DD, YYYY-MM, or YYYY)
            
        Returns:
            GEDCOM-formatted date string or None
        """
        if not date_str:
            return None
        
        date_str = date_str.strip()
        
        # Check format: YYYY-MM-DD
        if len(date_str) == 10 and date_str.count('-') == 2:
            year, month, day = date_str.split('-')
            month_abbr = self.GEDCOM_MONTHS.get(month, month)
            return f"{int(day)} {month_abbr} {year}"
        
        # Check format: YYYY-MM
        elif len(date_str) == 7 and date_str.count('-') == 1:
            year, month = date_str.split('-')
            month_abbr = self.GEDCOM_MONTHS.get(month, month)
            return f"{month_abbr} {year}"
        
        # Check format: YYYY
        elif len(date_str) == 4 and date_str.isdigit():
            return date_str
        
        # Fallback: try to extract year
        import re
        year_match = re.search(r'\b(\d{4})\b', date_str)
        if year_match:
            return f"ABT {year_match.group(1)}"
        
        self.logger.warning(f"Could not format date for GEDCOM: {date_str}")
        return None
    
    def _wrap_note(self, note: str, max_length: int = 248) -> List[str]:
        """
        Wrap long note text into multiple lines.
        
        GEDCOM recommends maximum line length of 248 characters.
        
        Args:
            note: Note text
            max_length: Maximum length per line
            
        Returns:
            List of note lines
        """
        if len(note) <= max_length:
            return [note]
        
        lines = []
        words = note.split()
        current_line = []
        current_length = 0
        
        for word in words:
            word_length = len(word) + 1  # +1 for space
            if current_length + word_length > max_length:
                if current_line:
                    lines.append(' '.join(current_line))
                    current_line = [word]
                    current_length = len(word)
                else:
                    # Single word too long, split it
                    lines.append(word[:max_length])
                    current_line = []
                    current_length = 0
            else:
                current_line.append(word)
                current_length += word_length
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines
