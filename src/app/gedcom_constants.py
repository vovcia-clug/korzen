"""
Constants for GEDCOM parsing.

Contains magic strings, configuration values, and character mappings
used throughout the GEDCOM parsing process.
"""

# Unicode character replacement mappings for GEDCOM normalization
# Handles OCR artifacts like smart quotes and other Unicode characters
UNICODE_REPLACEMENTS = {
    '\u201c': '"',  # Left double quotation mark
    '\u201d': '"',  # Right double quotation mark
    '\u2018': "'",  # Left single quotation mark
    '\u2019': "'",  # Right single quotation mark
    '\u2013': '-',  # En dash
    '\u2014': '-',  # Em dash
}

# Default encoding for GEDCOM files
DEFAULT_ENCODING = 'utf-8'

# Supported encodings to try during detection
SUPPORTED_ENCODINGS = ['utf-8', 'latin-1', 'cp1252', 'ansel', 'ascii']

# GEDCOM character set declarations
CHAR_DECLARATIONS = {
    'UTF-8': 'utf-8',
    'UTF8': 'utf-8',
    'ANSEL': 'ansel',
    'ASCII': 'ascii',
    'LATIN-1': 'latin-1',
    'ISO-8859-1': 'latin-1',
}

# Known date value patterns to skip
SKIP_DATE_VALUES = ['UNKNOWN', 'UNK', '']

# Valid year range for date parsing
MIN_YEAR = 1
MAX_YEAR = 9999

# Valid day range
MIN_DAY = 1
MAX_DAY = 31

# Duplicate detection threshold
DUPLICATE_THRESHOLD = 0.85

# Auto-merge configuration
AUTO_MERGE_THRESHOLD = 0.95  # Only auto-merge at 100% similarity
ENABLE_AUTO_MERGE = True    # Feature flag to enable/disable auto-merge
