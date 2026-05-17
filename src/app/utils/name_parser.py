"""
Name parsing utility for GEDCOM name formats.

Handles GEDCOM name format: "FirstName /LastName/"
"""
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class NameParser:
    """Parser for GEDCOM name strings."""
    
    @staticmethod
    def extract_name_parts(name: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
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
        
        # Handle tuple (ged4py returns tuples when GEDCOM has GIVN/SURN sub-records)
        # Tuple format: (given_name, surname, suffix)
        if isinstance(name, tuple):
            if len(name) >= 2:
                given_name = name[0] if name[0] else None
                surname = name[1] if name[1] else None
                # Return both parts from the tuple
                return given_name, surname
            elif len(name) == 1:
                return name[0], None
            else:
                return None, None
        
        # Convert to string if needed
        name = str(name)
        
        # Parse GEDCOM NAME format: "FirstName /LastName/"
        # The surname is enclosed in slashes
        if '/' in name:
            # Extract surname from between slashes
            parts = name.split('/')
            if len(parts) >= 3:
                # Format: "Given /Surname/"
                given_name = parts[0].strip() if parts[0].strip() else None
                surname = parts[1].strip() if parts[1].strip() else None
                return given_name, surname
            elif len(parts) == 2:
                # Format: "Given /Surname" or "/Surname/"
                if parts[0].strip():
                    # "Given /Surname"
                    given_name = parts[0].strip()
                    surname = parts[1].strip() if parts[1].strip() else None
                    return given_name, surname
                else:
                    # "/Surname/"
                    surname = parts[1].strip() if parts[1].strip() else None
                    return None, surname
        
        # No slashes - split on whitespace
        parts = name.strip().split(None, 1)
        
        if len(parts) == 0:
            return None, None
        elif len(parts) == 1:
            return parts[0], None
        else:
            # Check if second part looks like a surname
            if parts[1]:
                return parts[0], parts[1]
            return parts[0], None
