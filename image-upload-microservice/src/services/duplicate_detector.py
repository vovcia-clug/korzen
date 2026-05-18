"""Duplicate detection service using perceptual image hashing.

This module provides duplicate detection functionality using perceptual hashing
(pHash) to identify visually similar images, even if they have been resized,
compressed, or slightly modified.
"""

from pathlib import Path
from typing import Dict, Optional, Tuple

import imagehash
from PIL import Image

try:
    from utils.logger import get_logger
    logger = get_logger(__name__)
except ImportError:
    # Fallback for testing
    import logging
    logger = logging.getLogger(__name__)


class DuplicateDetector:
    """Detects duplicate images using perceptual hashing."""

    def __init__(
        self,
        hash_size: int = 8,
        similarity_threshold: int = 5,
    ):
        """Initialize the duplicate detector.
        
        Args:
            hash_size: Size of the perceptual hash (default: 8, produces 64-bit hash)
            similarity_threshold: Maximum Hamming distance for duplicates (0-64)
                                 Lower = more strict, Higher = more lenient
                                 Recommended: 0-5 for exact/near-exact duplicates
        """
        self.hash_size = hash_size
        self.similarity_threshold = similarity_threshold
        
        logger.info(
            "duplicate_detector_initialized",
            hash_size=hash_size,
            similarity_threshold=similarity_threshold,
        )

    def calculate_perceptual_hash(self, file_path: Path) -> Optional[str]:
        """Calculate perceptual hash (pHash) for an image.
        
        Args:
            file_path: Path to the image file
            
        Returns:
            Hexadecimal string representation of the perceptual hash,
            or None if calculation fails
        """
        try:
            with Image.open(file_path) as img:
                # Convert to RGB if necessary (handles RGBA, grayscale, etc.)
                if img.mode not in ('RGB', 'L'):
                    img = img.convert('RGB')
                
                # Calculate perceptual hash
                phash = imagehash.phash(img, hash_size=self.hash_size)
                hash_str = str(phash)
                
                logger.debug(
                    "perceptual_hash_calculated",
                    file=str(file_path),
                    hash=hash_str,
                )
                
                return hash_str
                
        except Exception as e:
            logger.error(
                "perceptual_hash_calculation_failed",
                file=str(file_path),
                error=str(e),
                exc_info=True,
            )
            return None

    def calculate_average_hash(self, file_path: Path) -> Optional[str]:
        """Calculate average hash (aHash) for an image.
        
        Average hash is faster but less robust than perceptual hash.
        
        Args:
            file_path: Path to the image file
            
        Returns:
            Hexadecimal string representation of the average hash,
            or None if calculation fails
        """
        try:
            with Image.open(file_path) as img:
                if img.mode not in ('RGB', 'L'):
                    img = img.convert('RGB')
                
                ahash = imagehash.average_hash(img, hash_size=self.hash_size)
                hash_str = str(ahash)
                
                logger.debug(
                    "average_hash_calculated",
                    file=str(file_path),
                    hash=hash_str,
                )
                
                return hash_str
                
        except Exception as e:
            logger.error(
                "average_hash_calculation_failed",
                file=str(file_path),
                error=str(e),
                exc_info=True,
            )
            return None

    def calculate_difference_hash(self, file_path: Path) -> Optional[str]:
        """Calculate difference hash (dHash) for an image.
        
        Difference hash tracks gradients and is good for detecting crops/edits.
        
        Args:
            file_path: Path to the image file
            
        Returns:
            Hexadecimal string representation of the difference hash,
            or None if calculation fails
        """
        try:
            with Image.open(file_path) as img:
                if img.mode not in ('RGB', 'L'):
                    img = img.convert('RGB')
                
                dhash = imagehash.dhash(img, hash_size=self.hash_size)
                hash_str = str(dhash)
                
                logger.debug(
                    "difference_hash_calculated",
                    file=str(file_path),
                    hash=hash_str,
                )
                
                return hash_str
                
        except Exception as e:
            logger.error(
                "difference_hash_calculation_failed",
                file=str(file_path),
                error=str(e),
                exc_info=True,
            )
            return None

    def calculate_all_hashes(self, file_path: Path) -> Dict[str, Optional[str]]:
        """Calculate all hash types for an image.
        
        Args:
            file_path: Path to the image file
            
        Returns:
            Dictionary with hash types as keys and hash strings as values
        """
        return {
            "perceptual_hash": self.calculate_perceptual_hash(file_path),
            "average_hash": self.calculate_average_hash(file_path),
            "difference_hash": self.calculate_difference_hash(file_path),
        }

    def are_duplicates(self, hash1: str, hash2: str) -> Tuple[bool, int]:
        """Check if two hashes represent duplicate images.
        
        Args:
            hash1: First image hash (hexadecimal string)
            hash2: Second image hash (hexadecimal string)
            
        Returns:
            Tuple of (is_duplicate, hamming_distance)
        """
        try:
            # Convert hex strings back to imagehash objects
            h1 = imagehash.hex_to_hash(hash1)
            h2 = imagehash.hex_to_hash(hash2)
            
            # Calculate Hamming distance
            distance = h1 - h2
            
            is_duplicate = distance <= self.similarity_threshold
            
            logger.debug(
                "duplicate_check",
                hash1=hash1,
                hash2=hash2,
                distance=distance,
                is_duplicate=is_duplicate,
                threshold=self.similarity_threshold,
            )
            
            return is_duplicate, distance
            
        except Exception as e:
            logger.error(
                "duplicate_check_failed",
                hash1=hash1,
                hash2=hash2,
                error=str(e),
                exc_info=True,
            )
            return False, -1

    def find_similar_hash(
        self,
        target_hash: str,
        hash_list: list[str],
    ) -> Optional[Tuple[str, int]]:
        """Find the most similar hash from a list.
        
        Args:
            target_hash: Hash to compare against
            hash_list: List of hashes to search
            
        Returns:
            Tuple of (matching_hash, distance) if found within threshold,
            None otherwise
        """
        best_match = None
        best_distance = float('inf')
        
        for candidate_hash in hash_list:
            is_dup, distance = self.are_duplicates(target_hash, candidate_hash)
            if is_dup and distance < best_distance:
                best_match = candidate_hash
                best_distance = distance
        
        if best_match is not None:
            logger.info(
                "similar_hash_found",
                target_hash=target_hash,
                match_hash=best_match,
                distance=best_distance,
            )
            return best_match, best_distance
        
        return None
