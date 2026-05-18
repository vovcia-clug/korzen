"""Upload orchestration service.

This module coordinates the complete workflow: detect → upload → notify → post-action.
It handles errors at each stage and implements post-upload actions, duplicate detection,
and metadata enrichment.
"""

import shutil
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, Optional, Set

from .image_detector import ImageDetector
from .s3_uploader import S3Uploader
from .sqs_notifier import SQSNotifier
from .metadata_extractor import MetadataExtractor
from .duplicate_detector import DuplicateDetector
from ..utils.logger import get_logger

logger = get_logger(__name__)


class UploadStatus(Enum):
    """Status of an upload operation."""

    PENDING = "pending"
    VALIDATING = "validating"
    DETECTING_DUPLICATES = "detecting_duplicates"
    UPLOADING = "uploading"
    NOTIFYING = "notifying"
    POST_ACTION = "post_action"
    COMPLETED = "completed"
    FAILED = "failed"
    DUPLICATE_FOUND = "duplicate_found"


class PostUploadAction(Enum):
    """Actions to take after successful upload."""

    KEEP = "keep"  # Keep original file in place
    ARCHIVE = "archive"  # Move file to archive directory
    DELETE = "delete"  # Delete original file


class UploadOrchestrator:
    """Orchestrates the complete image upload workflow."""

    def __init__(
        self,
        image_detector: ImageDetector,
        s3_uploader: S3Uploader,
        sqs_notifier: SQSNotifier,
        post_upload_action: str = "keep",
        archive_directory: Optional[Path] = None,
        enable_metadata_extraction: bool = True,
        enable_duplicate_detection: bool = True,
        enable_metadata_enrichment: bool = True,
        perceptual_hash_size: int = 8,
        similarity_threshold: int = 5,
    ):
        """Initialize the upload orchestrator.
        
        Args:
            image_detector: Image detection service
            s3_uploader: S3 upload service
            sqs_notifier: SQS notification service
            post_upload_action: Action after upload (keep/archive/delete)
            archive_directory: Directory for archived files (required for archive action)
            enable_metadata_extraction: Enable Skanoteka metadata extraction
            enable_duplicate_detection: Enable perceptual hash duplicate detection
            enable_metadata_enrichment: Enable metadata enrichment for duplicates
            perceptual_hash_size: Size of perceptual hash (default: 8)
            similarity_threshold: Maximum Hamming distance for duplicates (default: 5)
        """
        self.image_detector = image_detector
        self.s3_uploader = s3_uploader
        self.sqs_notifier = sqs_notifier
        self.post_upload_action = PostUploadAction(post_upload_action)
        self.archive_directory = archive_directory
        
        # Initialize metadata extractor if enabled
        self.metadata_extractor = MetadataExtractor() if enable_metadata_extraction else None
        self.enable_metadata_extraction = enable_metadata_extraction
        
        # Initialize duplicate detector if enabled
        self.duplicate_detector = DuplicateDetector(
            hash_size=perceptual_hash_size,
            similarity_threshold=similarity_threshold,
        ) if enable_duplicate_detection else None
        self.enable_duplicate_detection = enable_duplicate_detection
        self.enable_metadata_enrichment = enable_metadata_enrichment
        self.similarity_threshold = similarity_threshold

        # Track processed files by hash to avoid duplicates
        self.processed_hashes: Set[str] = set()

        # Statistics
        self.stats = {
            "files_processed": 0,
            "files_uploaded": 0,
            "files_failed": 0,
            "validation_failures": 0,
            "upload_failures": 0,
            "notification_failures": 0,
            "metadata_extracted": 0,
            "duplicates_found": 0,
            "duplicates_enriched": 0,
        }

        logger.info(
            "upload_orchestrator_initialized",
            post_upload_action=post_upload_action,
            archive_directory=str(archive_directory) if archive_directory else None,
            metadata_extraction_enabled=enable_metadata_extraction,
            duplicate_detection_enabled=enable_duplicate_detection,
            metadata_enrichment_enabled=enable_metadata_enrichment,
            perceptual_hash_size=perceptual_hash_size,
            similarity_threshold=similarity_threshold,
        )

    def process_file(self, file_path: Path) -> bool:
        """Process a file through the complete upload workflow.
        
        Args:
            file_path: Path to file to process
            
        Returns:
            True if processing succeeded, False otherwise
        """
        self.stats["files_processed"] += 1

        logger.info(
            "file_processing_started",
            file=str(file_path),
            filename=file_path.name,
        )

        status = UploadStatus.PENDING
        s3_uri = None
        metadata = {}

        try:
            # Stage 1: Validate image
            status = UploadStatus.VALIDATING
            is_valid, reason, metadata = self.image_detector.is_valid_image(file_path)

            if not is_valid:
                self.stats["validation_failures"] += 1
                logger.warning(
                    "file_validation_failed",
                    file=str(file_path),
                    reason=reason,
                )
                self._handle_failed_file(file_path, reason, status)
                return False
            
            # Stage 1.5: Extract Skanoteka metadata if enabled
            if self.enable_metadata_extraction and self.metadata_extractor:
                skanoteka_metadata = self.metadata_extractor.extract_metadata_from_filename(file_path)
                if skanoteka_metadata and "error" not in skanoteka_metadata:
                    # Merge Skanoteka metadata into existing metadata
                    metadata["skanoteka"] = skanoteka_metadata
                    self.stats["metadata_extracted"] += 1
                    logger.info(
                        "skanoteka_metadata_extracted",
                        file=str(file_path),
                        place=skanoteka_metadata.get("place"),
                        unit=skanoteka_metadata.get("unit"),
                        years=skanoteka_metadata.get("years"),
                    )

            # Stage 2: Calculate perceptual hashes if duplicate detection enabled
            if self.enable_duplicate_detection and self.duplicate_detector:
                status = UploadStatus.DETECTING_DUPLICATES
                
                # Calculate all hash types
                hashes = self.duplicate_detector.calculate_all_hashes(file_path)
                metadata.update(hashes)
                
                perceptual_hash = hashes.get("perceptual_hash")
                
                if perceptual_hash:
                    logger.debug(
                        "perceptual_hash_calculated",
                        file=str(file_path),
                        hash=perceptual_hash,
                    )
                    
                    # Check for duplicates in S3 by perceptual hash
                    duplicate_result = self.s3_uploader.find_duplicate_by_perceptual_hash(
                        perceptual_hash,
                        self.similarity_threshold,
                    )
                    
                    if duplicate_result:
                        existing_s3_uri, existing_metadata, distance = duplicate_result
                        self.stats["duplicates_found"] += 1
                        
                        logger.info(
                            "duplicate_found_by_perceptual_hash",
                            file=str(file_path),
                            existing_s3_uri=existing_s3_uri,
                            distance=distance,
                        )
                        
                        # Check if we should enrich the existing duplicate's metadata
                        if self.enable_metadata_enrichment and "skanoteka" in metadata:
                            enriched = self._enrich_duplicate_metadata(
                                existing_s3_uri,
                                existing_metadata,
                                metadata,
                            )
                            if enriched:
                                self.stats["duplicates_enriched"] += 1
                        
                        # Handle post-upload action for the duplicate
                        self._handle_post_upload_action(file_path)
                        
                        status = UploadStatus.DUPLICATE_FOUND
                        return True

            # Check for duplicates by file hash in memory
            file_hash_value = metadata.get("file_hash", {}).get("value", "")
            if file_hash_value and file_hash_value in self.processed_hashes:
                logger.info(
                    "file_duplicate_skipped_memory",
                    file=str(file_path),
                    hash=file_hash_value,
                )
                # Still considered successful, just skip
                self._handle_post_upload_action(file_path)
                return True
            
            # Check if file already exists in S3 by file hash
            if file_hash_value:
                existing_s3_uri = self.s3_uploader.object_exists_by_hash(file_hash_value)
                if existing_s3_uri:
                    logger.info(
                        "file_duplicate_skipped_s3",
                        file=str(file_path),
                        hash=file_hash_value,
                        existing_s3_uri=existing_s3_uri,
                    )
                    # Track hash and handle post-upload action
                    self.processed_hashes.add(file_hash_value)
                    self._handle_post_upload_action(file_path)
                    return True

            # Stage 3: Upload to S3
            status = UploadStatus.UPLOADING
            logger.info(
                "file_upload_starting",
                file=str(file_path),
                size=metadata.get("file_size_bytes", 0),
            )

            s3_uri = self.s3_uploader.upload_file(
                file_path=file_path,
                metadata=metadata,
            )

            logger.info(
                "file_uploaded",
                file=str(file_path),
                s3_uri=s3_uri,
            )

            # Stage 4: Send SQS notification
            status = UploadStatus.NOTIFYING
            message_id = self.sqs_notifier.send_notification(
                s3_uri=s3_uri,
                original_filename=file_path.name,
                metadata=metadata,
            )

            logger.info(
                "notification_sent",
                file=str(file_path),
                message_id=message_id,
                s3_uri=s3_uri,
            )

            # Stage 5: Post-upload action
            status = UploadStatus.POST_ACTION
            self._handle_post_upload_action(file_path)

            # Mark as completed
            status = UploadStatus.COMPLETED
            self.stats["files_uploaded"] += 1

            # Track hash to avoid duplicates
            if file_hash_value:
                self.processed_hashes.add(file_hash_value)

            logger.info(
                "file_processing_completed",
                file=str(file_path),
                s3_uri=s3_uri,
                status=status.value,
                duration_ms=0,  # TODO: Add timing
            )

            return True

        except Exception as e:
            self.stats["files_failed"] += 1

            # Categorize the failure
            if status == UploadStatus.UPLOADING:
                self.stats["upload_failures"] += 1
            elif status == UploadStatus.NOTIFYING:
                self.stats["notification_failures"] += 1

            logger.error(
                "file_processing_failed",
                file=str(file_path),
                status=status.value,
                error=str(e),
                s3_uri=s3_uri,
                exc_info=True,
            )

            self._handle_failed_file(file_path, str(e), status)
            return False

    def _enrich_duplicate_metadata(
        self,
        existing_s3_uri: str,
        existing_metadata: Dict[str, str],
        new_metadata: Dict,
    ) -> bool:
        """Enrich existing duplicate's metadata if it lacks Skanoteka metadata.
        
        Args:
            existing_s3_uri: S3 URI of existing duplicate
            existing_metadata: Existing S3 metadata
            new_metadata: New metadata from current upload
            
        Returns:
            True if metadata was enriched, False otherwise
        """
        # Check if existing duplicate already has Skanoteka metadata
        has_skanoteka = any(
            key.startswith("skanoteka-") for key in existing_metadata.keys()
        )
        
        if has_skanoteka:
            logger.info(
                "duplicate_already_has_metadata",
                s3_uri=existing_s3_uri,
            )
            return False
        
        # Check if new upload has Skanoteka metadata
        if "skanoteka" not in new_metadata or not isinstance(new_metadata["skanoteka"], dict):
            logger.debug(
                "new_upload_lacks_metadata",
                s3_uri=existing_s3_uri,
            )
            return False
        
        # Prepare Skanoteka metadata for enrichment
        skanoteka = new_metadata["skanoteka"]
        enrichment_metadata = {}
        
        if skanoteka.get("place"):
            enrichment_metadata["skanoteka-place"] = str(skanoteka["place"])
        if skanoteka.get("unit"):
            enrichment_metadata["skanoteka-unit"] = str(skanoteka["unit"])
        if skanoteka.get("years"):
            enrichment_metadata["skanoteka-years"] = str(skanoteka["years"])
        if skanoteka.get("page"):
            enrichment_metadata["skanoteka-page"] = str(skanoteka["page"])
        if skanoteka.get("source_url"):
            enrichment_metadata["skanoteka-source-url"] = str(skanoteka["source_url"])
        
        if not enrichment_metadata:
            return False
        
        # Enrich the existing duplicate
        success = self.s3_uploader.enrich_metadata(
            existing_s3_uri,
            enrichment_metadata,
            overwrite=False,
        )
        
        if success:
            logger.info(
                "duplicate_metadata_enriched",
                s3_uri=existing_s3_uri,
                enriched_keys=list(enrichment_metadata.keys()),
            )
        
        return success

    def _handle_post_upload_action(self, file_path: Path) -> None:
        """Handle post-upload action (keep/archive/delete).
        
        Args:
            file_path: Path to original file
        """
        try:
            if self.post_upload_action == PostUploadAction.KEEP:
                logger.debug(
                    "post_upload_keep",
                    file=str(file_path),
                )
                # Do nothing, keep file in place

            elif self.post_upload_action == PostUploadAction.ARCHIVE:
                if not self.archive_directory:
                    logger.error(
                        "archive_directory_not_configured",
                        file=str(file_path),
                    )
                    return

                # Create archive directory structure
                archive_path = self._get_archive_path(file_path)
                archive_path.parent.mkdir(parents=True, exist_ok=True)

                # Move file to archive
                shutil.move(str(file_path), str(archive_path))

                logger.info(
                    "post_upload_archived",
                    file=str(file_path),
                    archive_path=str(archive_path),
                )

            elif self.post_upload_action == PostUploadAction.DELETE:
                file_path.unlink()

                logger.info(
                    "post_upload_deleted",
                    file=str(file_path),
                )

        except Exception as e:
            logger.error(
                "post_upload_action_failed",
                file=str(file_path),
                action=self.post_upload_action.value,
                error=str(e),
                exc_info=True,
            )

    def _get_archive_path(self, file_path: Path) -> Path:
        """Generate archive path for a file.
        
        Args:
            file_path: Original file path
            
        Returns:
            Path in archive directory
        """
        if not self.archive_directory:
            raise ValueError("Archive directory not configured")
            
        # Use date-based structure in archive
        now = datetime.now(timezone.utc)
        date_path = now.strftime("%Y/%m/%d")

        # Preserve original filename
        archive_path = self.archive_directory / date_path / file_path.name

        # Handle duplicates by adding timestamp
        if archive_path.exists():
            timestamp = now.strftime("%H%M%S")
            stem = file_path.stem
            suffix = file_path.suffix
            archive_path = self.archive_directory / date_path / f"{stem}_{timestamp}{suffix}"

        return archive_path

    def _handle_failed_file(
        self,
        file_path: Path,
        reason: str,
        status: UploadStatus,
    ) -> None:
        """Handle a file that failed processing.
        
        Args:
            file_path: Path to failed file
            reason: Reason for failure
            status: Status at time of failure
        """
        # For now, just leave the file in place
        # In production, might move to a failed-uploads directory
        logger.warning(
            "file_failed_left_in_place",
            file=str(file_path),
            reason=reason,
            status=status.value,
        )

    def get_statistics(self) -> Dict:
        """Get processing statistics.
        
        Returns:
            Dictionary of statistics
        """
        stats = self.stats.copy()
        stats["success_rate"] = (
            self.stats["files_uploaded"] / self.stats["files_processed"]
            if self.stats["files_processed"] > 0
            else 0.0
        )
        return stats

    def reset_statistics(self) -> None:
        """Reset statistics counters."""
        for key in self.stats:
            self.stats[key] = 0

        logger.info("statistics_reset")
