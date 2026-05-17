"""
Date parsing utility for GEDCOM date formats.

Handles various GEDCOM date formats including:
- Standard dates (1 JAN 1900)
- Date ranges (BET 1900 AND 1901)
- Approximate dates (ABT 1900, BEF 1900, AFT 1900)
- BC dates (skipped)
- Year ranges (1393/94)
"""
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class DateParser:
    """Parser for GEDCOM date strings."""
    
    # Date prefixes to remove (must check longer prefixes first)
    DATE_PREFIXES = [
        'ABOUT', 'BEFORE', 'AFTER', 'BETWEEN', 'ESTIMATED',
        'ABT', 'BEF', 'AFT', 'BET', 'CAL', 'EST',
        'ORE',  # Italian/Latin for "before"
        'ER',   # Italian/Latin for "after"
        'AND'
    ]
    
    # Date formats to try
    DATE_FORMATS = [
        '%d %b %Y',      # 1 JAN 1900
        '%d %B %Y',      # 1 January 1900
        '%b %Y',         # JAN 1900
        '%B %Y',         # January 1900
        '%Y',            # 1900
    ]
    
    @staticmethod
    def parse(date_str: Optional[str]) -> Optional[datetime]:
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
            
            # Handle year range with slash format: "1393/94"
            date_str = DateParser._handle_year_range(date_str)
            
            # Handle BETWEEN dates - extract first date
            if 'BETWEEN' in date_str.upper() or date_str.upper().startswith('BET '):
                date_str = DateParser._handle_between_dates(date_str)
            
            # Handle WEEN format (shortened BETWEEN)
            elif date_str.upper().startswith('WEEN'):
                date_str = DateParser._handle_ween_dates(date_str)
            
            # Remove date modifiers
            date_str = DateParser._remove_prefixes(date_str)
            
            # Clean up any remaining text
            date_str = date_str.strip()
            
            # Try different date formats
            for fmt in DateParser.DATE_FORMATS:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
            
            # Try parsing just a year number (plain digits)
            if date_str.isdigit():
                year = int(date_str)
                if 1 <= year <= 9999:  # Valid year range
                    return datetime(year, 1, 1)
            
            # Try parsing full date with various separators
            parsed_date = DateParser._parse_complex_date(date_str)
            if parsed_date:
                return parsed_date
                    
            logger.warning(f"Could not parse date: {original_date_str}")
            return None
        except Exception as e:
            logger.error(f"Error parsing date '{date_str}': {e}")
            return None
    
    @staticmethod
    def _handle_year_range(date_str: str) -> str:
        """
        Handle year range with slash format: "1393/94".
        
        Args:
            date_str: Date string that may contain a year range
            
        Returns:
            Date string with year range resolved to first year
        """
        if '/' in date_str and date_str.replace('/', '').isdigit():
            parts = date_str.split('/')
            if len(parts) == 2 and parts[0].isdigit():
                # Use the first year
                return parts[0]
        return date_str
    
    @staticmethod
    def _handle_between_dates(date_str: str) -> str:
        """
        Handle BETWEEN dates - extract first date.
        
        Examples: 
            "BET 07 OCT AND 08 NOV 1260"
            "BET SEP AND NOV 1081"
            "BETWEEN 26 AND 27 NOV 1252"
        
        Args:
            date_str: Date string containing BETWEEN/BET
            
        Returns:
            First date from the range
        """
        # Split by AND to get the two date parts
        and_parts = date_str.upper().split(' AND ')
        if len(and_parts) < 2:
            return date_str
        
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
        
        # Strategy: Try to use first part, but if it lacks a year, extract year from second part
        
        # Check if first part already has a year (last token is 3+ digit number)
        has_year = first_parts and first_parts[-1].isdigit() and len(first_parts[-1]) >= 3
        
        if not has_year:
            # First part lacks a year, find year in second part
            year = None
            for part in reversed(second_parts):
                if part.isdigit() and len(part) >= 3:
                    year = part
                    break
            
            if year:
                # Check if first part is "day month" format (e.g., "25 SEP")
                # and second part is "month year" or "day month year"
                if (len(first_parts) == 2 and
                    first_parts[0].isdigit() and len(first_parts[0]) <= 2):
                    # First part is "day month", append year
                    return first_part + ' ' + year
                else:
                    # Append year to first part
                    return first_part + ' ' + year
            else:
                # No year found anywhere, just use first part
                return first_part
        else:
            # First part already has a year, use it as-is
            return first_part
    
    @staticmethod
    def _handle_ween_dates(date_str: str) -> str:
        """
        Handle WEEN format (shortened BETWEEN).
        
        Args:
            date_str: Date string starting with WEEN
            
        Returns:
            First date from the range
        """
        and_parts = date_str.upper().split(' AND ')
        if len(and_parts) < 2:
            return date_str
        
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
        
        return first_part
    
    @staticmethod
    def _remove_prefixes(date_str: str) -> str:
        """
        Remove date modifier prefixes.
        
        Args:
            date_str: Date string that may contain prefixes
            
        Returns:
            Date string with prefixes removed
        """
        for prefix in DateParser.DATE_PREFIXES:
            if date_str.upper().startswith(prefix + ' ') or date_str.upper() == prefix:
                return date_str[len(prefix):].strip()
        return date_str
    
    @staticmethod
    def _parse_complex_date(date_str: str) -> Optional[datetime]:
        """
        Try parsing dates with various separators (day month year).
        
        Args:
            date_str: Date string to parse
            
        Returns:
            datetime object or None if parsing fails
        """
        parts = date_str.split()
        
        # Try parsing full date: day month year
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
        
        # Try parsing month name + year without day
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
        
        return None
