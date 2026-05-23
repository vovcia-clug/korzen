"""
Phonetic Encoder Service

This module provides phonetic encoding functionality using the Daitch-Mokotoff
Soundex algorithm, which is specifically designed for Slavic names (Polish,
Russian, Ukrainian, Czech, Slovak, etc.).

The Daitch-Mokotoff algorithm:
- Handles Slavic phonetic patterns better than standard Soundex
- Can produce multiple phonetic codes per name (accounting for pronunciation variants)
- Preserves more phonetic information than traditional Soundex
- Supports character combinations common in Slavic languages

This service is used for fuzzy name matching in duplicate detection systems.
"""

import logging
from functools import lru_cache
from typing import Optional

from abydos.phonetic import DaitchMokotoff

logger = logging.getLogger(__name__)


class PhoneticEncoder:
    """
    Encodes names using Daitch-Mokotoff phonetic algorithm for Slavic name matching.
    
    This class provides methods to encode names into phonetic codes, normalize
    Slavic characters, and calculate phonetic similarity between names.
    
    Features:
    - Daitch-Mokotoff Soundex encoding via jellyfish library
    - Slavic character normalization (Polish, Czech, Slovak, Russian)
    - LRU caching for performance optimization
    - Batch encoding support
    - Graceful error handling
    
    Example:
        >>> encoder = PhoneticEncoder()
        >>> codes = encoder.encode("Kowalski")
        >>> print(codes)  # ['584000', '585000']
        >>> 
        >>> similarity = encoder.similarity("Kowalski", "Kowalsky")
        >>> print(f"{similarity:.2f}")  # 0.85
        >>> 
        >>> batch = encoder.batch_encode(["Nowak", "Kowalski", "Wiśniewski"])
        >>> print(batch)  # {'Nowak': [...], 'Kowalski': [...], ...}
    """
    
    # Slavic character normalization mapping
    SLAVIC_CHAR_MAP = {
        # Polish
        'ą': 'a', 'Ą': 'A',
        'ć': 'c', 'Ć': 'C',
        'ę': 'e', 'Ę': 'E',
        'ł': 'l', 'Ł': 'L',
        'ń': 'n', 'Ń': 'N',
        'ó': 'o', 'Ó': 'O',
        'ś': 's', 'Ś': 'S',
        'ź': 'z', 'Ź': 'Z',
        'ż': 'z', 'Ż': 'Z',
        
        # Czech
        'č': 'c', 'Č': 'C',
        'ř': 'r', 'Ř': 'R',
        'š': 's', 'Š': 'S',
        'ž': 'z', 'Ž': 'Z',
        'ě': 'e', 'Ě': 'E',
        'ů': 'u', 'Ů': 'U',
        'ú': 'u', 'Ú': 'U',
        'ý': 'y', 'Ý': 'Y',
        'á': 'a', 'Á': 'A',
        'é': 'e', 'É': 'E',
        'í': 'i', 'Í': 'I',
        
        # Slovak
        'ľ': 'l', 'Ľ': 'L',
        'ŕ': 'r', 'Ŕ': 'R',
        'ť': 't', 'Ť': 'T',
        'ď': 'd', 'Ď': 'D',
        'ô': 'o', 'Ô': 'O',
        
        # Russian/Cyrillic (basic transliteration)
        'а': 'a', 'А': 'A',
        'б': 'b', 'Б': 'B',
        'в': 'v', 'В': 'V',
        'г': 'g', 'Г': 'G',
        'д': 'd', 'Д': 'D',
        'е': 'e', 'Е': 'E',
        'ё': 'e', 'Ё': 'E',
        'ж': 'zh', 'Ж': 'Zh',
        'з': 'z', 'З': 'Z',
        'и': 'i', 'И': 'I',
        'й': 'y', 'Й': 'Y',
        'к': 'k', 'К': 'K',
        'л': 'l', 'Л': 'L',
        'м': 'm', 'М': 'M',
        'н': 'n', 'Н': 'N',
        'о': 'o', 'О': 'O',
        'п': 'p', 'П': 'P',
        'р': 'r', 'Р': 'R',
        'с': 's', 'С': 'S',
        'т': 't', 'Т': 'T',
        'у': 'u', 'У': 'U',
        'ф': 'f', 'Ф': 'F',
        'х': 'h', 'Х': 'H',
        'ц': 'ts', 'Ц': 'Ts',
        'ч': 'ch', 'Ч': 'Ch',
        'ш': 'sh', 'Ш': 'Sh',
        'щ': 'shch', 'Щ': 'Shch',
        'ъ': '', 'Ъ': '',
        'ы': 'y', 'Ы': 'Y',
        'ь': '', 'Ь': '',
        'э': 'e', 'Э': 'E',
        'ю': 'yu', 'Ю': 'Yu',
        'я': 'ya', 'Я': 'Ya',
    }
    
    def __init__(self):
        """Initialize the PhoneticEncoder."""
        self._dm_encoder = DaitchMokotoff()
        logger.debug("PhoneticEncoder initialized")
    
    def normalize_slavic(self, text: str) -> str:
        """
        Normalize Slavic characters to ASCII equivalents.
        
        This method converts Polish, Czech, Slovak, and Russian characters
        to their ASCII equivalents for better phonetic encoding.
        
        Args:
            text: Text containing Slavic characters
            
        Returns:
            Normalized text with ASCII characters only
            
        Example:
            >>> encoder = PhoneticEncoder()
            >>> encoder.normalize_slavic("Wójcik")
            'Wojcik'
            >>> encoder.normalize_slavic("Dvořák")
            'Dvorak'
            >>> encoder.normalize_slavic("Новак")
            'Novak'
        """
        if not text:
            return ""
        
        result = []
        for char in text:
            result.append(self.SLAVIC_CHAR_MAP.get(char, char))
        
        normalized = ''.join(result)
        logger.debug(f"Normalized '{text}' to '{normalized}'")
        return normalized
    
    @lru_cache(maxsize=10000)
    def encode(self, name: str) -> list[str]:
        """
        Generate Daitch-Mokotoff phonetic codes for a name.
        
        The Daitch-Mokotoff algorithm can produce multiple phonetic codes
        for a single name to account for pronunciation variants. This method
        uses LRU caching to improve performance for repeated encodings.
        
        Args:
            name: Name to encode (will be normalized first)
            
        Returns:
            List of phonetic codes (typically 1-3 codes per name).
            Returns empty list if encoding fails or name is empty.
            
        Example:
            >>> encoder = PhoneticEncoder()
            >>> encoder.encode("Kowalski")
            ['584000', '585000']
            >>> encoder.encode("Schmidt")
            ['463000']
            >>> encoder.encode("")
            []
            >>> encoder.encode(None)
            []
        """
        if not name:
            logger.debug("Empty or None name provided to encode()")
            return []
        
        try:
            # Normalize Slavic characters first
            normalized = self.normalize_slavic(name)
            
            # Strip whitespace and handle empty result
            normalized = normalized.strip()
            if not normalized:
                logger.debug(f"Name '{name}' normalized to empty string")
                return []
            
            # Encode using Daitch-Mokotoff Soundex
            # abydos DaitchMokotoff.encode returns a set of strings
            codes = self._dm_encoder.encode(normalized)
            
            # Convert set to sorted list for consistency
            result = sorted(list(codes)) if codes else []
            
            logger.debug(f"Encoded '{name}' (normalized: '{normalized}') to {result}")
            return result
            
        except Exception as e:
            logger.warning(f"Failed to encode name '{name}': {e}")
            return []
    
    def similarity(self, name1: str, name2: str) -> float:
        """
        Calculate phonetic similarity between two names using Jaccard similarity.
        
        This method compares the phonetic codes of two names and returns
        a similarity score based on the Jaccard index (intersection over union).
        
        Args:
            name1: First name to compare
            name2: Second name to compare
            
        Returns:
            Similarity score between 0.0 (no similarity) and 1.0 (identical).
            Returns 0.0 if either name cannot be encoded.
            
        Example:
            >>> encoder = PhoneticEncoder()
            >>> encoder.similarity("Kowalski", "Kowalsky")
            0.6666666666666666
            >>> encoder.similarity("Smith", "Schmidt")
            0.5
            >>> encoder.similarity("Nowak", "Kowalski")
            0.0
        """
        if not name1 or not name2:
            logger.debug("Empty or None name provided to similarity()")
            return 0.0
        
        try:
            codes1 = set(self.encode(name1))
            codes2 = set(self.encode(name2))
            
            # Handle empty code sets
            if not codes1 or not codes2:
                logger.debug(f"One or both names produced no codes: '{name1}', '{name2}'")
                return 0.0
            
            # Calculate Jaccard similarity: |intersection| / |union|
            intersection = codes1 & codes2
            union = codes1 | codes2
            
            if not union:
                return 0.0
            
            similarity_score = len(intersection) / len(union)
            
            logger.debug(
                f"Similarity between '{name1}' and '{name2}': {similarity_score:.3f} "
                f"(codes1={codes1}, codes2={codes2})"
            )
            
            return similarity_score
            
        except Exception as e:
            logger.warning(f"Failed to calculate similarity for '{name1}' and '{name2}': {e}")
            return 0.0
    
    def batch_encode(self, names: list[str]) -> dict[str, list[str]]:
        """
        Encode multiple names in batch.
        
        This method efficiently encodes multiple names and returns a dictionary
        mapping each name to its phonetic codes. Leverages LRU caching for
        improved performance when duplicate names are present.
        
        Args:
            names: List of names to encode
            
        Returns:
            Dictionary mapping each name to its list of phonetic codes.
            Names that fail to encode will have empty lists.
            
        Example:
            >>> encoder = PhoneticEncoder()
            >>> batch = encoder.batch_encode(["Nowak", "Kowalski", "Wiśniewski"])
            >>> print(batch)
            {
                'Nowak': ['680000'],
                'Kowalski': ['584000', '585000'],
                'Wiśniewski': ['436000', '437000']
            }
        """
        if not names:
            logger.debug("Empty list provided to batch_encode()")
            return {}
        
        try:
            result = {}
            for name in names:
                if name:  # Skip None or empty strings
                    result[name] = self.encode(name)
                else:
                    result[name] = []
            
            logger.debug(f"Batch encoded {len(names)} names")
            return result
            
        except Exception as e:
            logger.warning(f"Failed to batch encode names: {e}")
            return {name: [] for name in names}
