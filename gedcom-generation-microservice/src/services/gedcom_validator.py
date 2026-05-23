"""
GEDCOM validator for checking syntax and structure of generated GEDCOM files.
"""

import re
from typing import List, Tuple
from ..utils.logger import get_logger

logger = get_logger(__name__)


class GedcomValidator:
    """Validates GEDCOM file syntax and structure."""
    
    def __init__(self, strict: bool = False):
        """
        Initialize GEDCOM validator.
        
        Args:
            strict: Whether to use strict validation (default: False)
        """
        self.strict = strict
        logger.info(f"Initialized GEDCOM validator (strict={strict})")
    
    def validate(self, gedcom_content: str) -> Tuple[bool, List[str]]:
        """
        Validate GEDCOM content.
        
        Args:
            gedcom_content: GEDCOM file content as string
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        logger.debug(f"Validating GEDCOM content ({len(gedcom_content)} bytes)")
        
        # Check basic structure
        errors.extend(self._check_structure(gedcom_content))
        
        # Check IDs and references
        errors.extend(self._check_ids_and_references(gedcom_content))
        
        # Check line format
        if self.strict:
            errors.extend(self._check_line_format(gedcom_content))
        
        is_valid = len(errors) == 0
        
        if is_valid:
            logger.info("GEDCOM validation passed")
        else:
            logger.warning(f"GEDCOM validation failed with {len(errors)} error(s)")
            for error in errors[:5]:  # Log first 5 errors
                logger.warning(f"  - {error}")
        
        return is_valid, errors
    
    def _check_structure(self, content: str) -> List[str]:
        """Check basic GEDCOM structure."""
        errors = []
        
        # Check for header
        if not content.strip().startswith("0 HEAD"):
            errors.append("Missing GEDCOM header (0 HEAD)")
        
        # Check for trailer
        if "0 TRLR" not in content:
            errors.append("Missing GEDCOM trailer (0 TRLR)")
        
        # Check that trailer is at the end
        lines = content.strip().split('\n')
        if lines and not lines[-1].strip().startswith("0 TRLR"):
            errors.append("GEDCOM trailer (0 TRLR) must be the last line")
        
        return errors
    
    def _check_ids_and_references(self, content: str) -> List[str]:
        """Check ID definitions and references."""
        errors = []
        
        # Find all ID definitions (0 @ID@ TYPE)
        defined_ids = set()
        id_definition_pattern = r'^0 @([^@]+)@ \w+'
        
        for line in content.split('\n'):
            match = re.match(id_definition_pattern, line)
            if match:
                id_value = match.group(1)
                if id_value in defined_ids:
                    errors.append(f"Duplicate ID definition: @{id_value}@")
                defined_ids.add(id_value)
        
        # Find all ID references (not at level 0)
        referenced_ids = set()
        id_reference_pattern = r'^[^0].*@([^@]+)@'
        
        for line in content.split('\n'):
            matches = re.finditer(r'@([^@]+)@', line)
            # Skip level 0 lines (definitions)
            if not line.startswith('0 @'):
                for match in matches:
                    referenced_ids.add(match.group(1))
        
        # Check for undefined references
        undefined = referenced_ids - defined_ids
        if undefined:
            for id_value in list(undefined)[:10]:  # Limit to first 10
                errors.append(f"Undefined ID reference: @{id_value}@")
            if len(undefined) > 10:
                errors.append(f"... and {len(undefined) - 10} more undefined references")
        
        return errors
    
    def _check_line_format(self, content: str) -> List[str]:
        """Check line format (strict mode)."""
        errors = []
        
        # GEDCOM line format: LEVEL [XREF] TAG [VALUE]
        # Level: 0-99
        # XREF: @ID@ (optional)
        # TAG: alphanumeric, underscore
        # VALUE: any text
        
        line_pattern = r'^\d+ (@[^@]+@ )?\w+( .*)?$'
        
        for line_num, line in enumerate(content.split('\n'), 1):
            line = line.rstrip()
            if not line:
                continue
            
            if not re.match(line_pattern, line):
                errors.append(f"Line {line_num}: Invalid format: {line[:50]}")
                if len(errors) >= 20:  # Limit errors
                    errors.append("... too many format errors, stopping validation")
                    break
        
        return errors
    
    def get_validation_summary(self, gedcom_content: str) -> dict:
        """
        Get a summary of GEDCOM content for validation.
        
        Args:
            gedcom_content: GEDCOM file content
        
        Returns:
            Dictionary with summary information
        """
        lines = gedcom_content.split('\n')
        
        summary = {
            "total_lines": len(lines),
            "has_header": gedcom_content.strip().startswith("0 HEAD"),
            "has_trailer": "0 TRLR" in gedcom_content,
            "individual_count": 0,
            "family_count": 0,
            "source_count": 0
        }
        
        for line in lines:
            if line.startswith('0 @I') and '@ INDI' in line:
                summary["individual_count"] += 1
            elif line.startswith('0 @F') and '@ FAM' in line:
                summary["family_count"] += 1
            elif line.startswith('0 @S') and '@ SOUR' in line:
                summary["source_count"] += 1
        
        return summary
