#!/usr/bin/env python3
"""Test script for date parsing improvements."""

from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


def parse_date(date_str):
    """
    Parse GEDCOM date string to datetime object.
    This is a standalone version for testing.
    """
    if not date_str:
        return None
        
    try:
        # Convert to string if needed
        date_str = str(date_str) if not isinstance(date_str, str) else date_str
        original_date_str = date_str
        
        # Remove parentheses
        date_str = date_str.strip().strip('()')
        
        # Handle BC dates and UNKNOWN - skip them
        if 'BC' in date_str.upper():
            logger.debug(f"Skipping BC date: {original_date_str}")
            return None
        
        if date_str.upper() in ('UNKNOWN', 'UNK', ''):
            logger.debug(f"Skipping unknown date: {original_date_str}")
            return None
        
        # Handle year range with slash format: "1393/94"
        if '/' in date_str and date_str.replace('/', '').isdigit():
            parts = date_str.split('/')
            if len(parts) == 2 and parts[0].isdigit():
                # Use the first year
                date_str = parts[0]
        
        # Handle BETWEEN dates - extract first date
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
                            date_str = first_part + ' ' + year
                        else:
                            # Append year to first part
                            date_str = first_part + ' ' + year
                    else:
                        # No year found anywhere, just use first part
                        date_str = first_part
                else:
                    # First part already has a year, use it as-is
                    date_str = first_part
        
        # Remove date modifiers
        prefixes_to_remove = [
            'ABOUT', 'BEFORE', 'AFTER', 'BETWEEN', 'ESTIMATED',
            'ABT', 'BEF', 'AFT', 'BET', 'CAL', 'EST',
            'ORE', 'ER', 'AND'
        ]
        
        for prefix in prefixes_to_remove:
            if date_str.upper().startswith(prefix + ' ') or date_str.upper() == prefix:
                date_str = date_str[len(prefix):].strip()
                break
        
        # Clean up
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
        
        # Try parsing just a year number
        if date_str.isdigit():
            year = int(date_str)
            if 1 <= year <= 9999:
                return datetime(year, 1, 1)
        
        # Try parsing full date with various separators
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
        
        # Try parsing month name + year
        if len(parts) == 2:
            month_str, year_str = parts
            if year_str.isdigit():
                year = int(year_str)
                if 1 <= year <= 9999:
                    for month_fmt in ['%b', '%B']:
                        try:
                            month_obj = datetime.strptime(month_str.upper(), month_fmt.upper())
                            return datetime(year, month_obj.month, 1)
                        except ValueError:
                            try:
                                month_obj = datetime.strptime(month_str, month_fmt)
                                return datetime(year, month_obj.month, 1)
                            except ValueError:
                                continue
        
        logger.warning(f"Could not parse date: {original_date_str}")
        return None
    except Exception as e:
        logger.error(f"Error parsing date '{date_str}': {e}")
        return None


# Test problematic dates
test_dates = [
    'BETWEEN 1399 AND 26 JUN 1404',
    '(BET 25 SEP AND NOV 915)',
    'BETWEEN 1282 AND DEC 1313',
    'BETWEEN 1756 AND 9 OCT 1759',
    'BETWEEN 975 AND 1001',
    'BETWEEN 1588 AND 20 AUG 1593',
    'BETWEEN 1312 AND 29 SEP 1319',
    'BETWEEN OCT 1581 AND 10 MAY 1582',
    'BETWEEN 1179 AND 10 APR 1183',
    'BETWEEN JAN 1124 AND JAN 1126',
    'BETWEEN OCT 1602 AND JUL 1603',
    'BETWEEN 1576 AND 1 AUG 1582',
    'BETWEEN JUN 1328 AND 21 MAY 1329',
    'BETWEEN 1263 AND 25 MAY 1265',
    'BETWEEN 1289 AND 20 DEC 1290',
    'BETWEEN 1298 AND 17 MAR 1303',
    'BETWEEN 1298 AND 11 AUG 1308',
    'BETWEEN 1242 AND 8 MAY 1253',
    'BETWEEN APR 1346 AND JAN 1347',
    'BETWEEN 1497 AND 4 FEB 1500',
    '(BET JUN AND AUG 968)',
    'BETWEEN 1290 AND 27 DEC 1302',
    'BETWEEN 1666 AND 8 JAN 1668',
    '(BET 27 MAR AND 13 JUN 897)',
    'BETWEEN 997 AND 1000',
    '1393/94'
]

print('Testing date parsing improvements:')
print('=' * 80)
success_count = 0
for date_str in test_dates:
    result = parse_date(date_str)
    if result:
        print(f'✓ {date_str:50} → {result.strftime("%Y-%m-%d")}')
        success_count += 1
    else:
        print(f'✗ {date_str:50} → None')

print('=' * 80)
print(f'Successfully parsed: {success_count}/{len(test_dates)} dates ({100*success_count//len(test_dates)}%)')
