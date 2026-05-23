"""Upload orchestration service.

This module coordinates the complete workflow: detect → upload → notify → post-action.
It handles errors at each stage and implements post-upload actions.
"""

import shutil
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, Optional

from .image_detector import ImageDetector
from .s3_uploader import S3Uploader
from .sqs_notifier import SQSNotifier
from .metadata_extractor import MetadataHandler
from ..utils.logger import get_logger

logger = get_logger(__name__)


class UploadStatus(Enum):
    """Status of an upload operation."""

    PENDING = "pending"
    VALIDATING = "validating"
    UPLOADING = "uploading"
    NOTIFYING = "notifying"
    POST_ACTION = "post_action"
    COMPLETED = "completed"
    FAILED = "failed"


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
        base_directory: Optional[Path] = None,
    ):
        """Initialize the upload orchestrator.
        
        Args:
            image_detector: Image detection service
            s3_uploader: S3 upload service
            sqs_notifier: SQS notification service
            post_upload_action: Action after upload (keep/archive/delete)
            archive_directory: Directory for archived files (required for archive action)
            base_directory: Base directory for preserving directory structure in S3
        """
        self.image_detector = image_detector
        self.s3_uploader = s3_uploader
        self.sqs_notifier = sqs_notifier
        self.post_upload_action = PostUploadAction(post_upload_action)
        self.archive_directory = archive_directory
        self.base_directory = base_directory
        
        # Initialize metadata handler
        self.metadata_handler = MetadataHandler()

        # Statistics
        self.stats = {
            "files_processed": 0,
            "files_uploaded": 0,
            "files_failed": 0,
            "validation_failures": 0,
            "upload_failures": 0,
            "notification_failures": 0,
            "json_files_uploaded": 0,
        }

        logger.info(
            "upload_orchestrator_initialized",
            post_upload_action=post_upload_action,
            archive_directory=str(archive_directory) if archive_directory else None,
            base_directory=str(base_directory) if base_directory else None,
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
            
            # Stage 2: Upload image to S3
            status = UploadStatus.UPLOADING
            logger.info(
                "file_upload_starting",
                file=str(file_path),
                size=metadata.get("file_size_bytes", 0),
            )

            s3_uri = self.s3_uploader.upload_file(
                file_path=file_path,
                metadata=metadata,
                base_directory=self.base_directory,
            )

            logger.info(
                "image_uploaded",
                file=str(file_path),
                s3_uri=s3_uri,
            )
            
            # Stage 3: Upload companion JSON file if it exists
            json_file = self.metadata_handler.find_companion_json(file_path)
            json_s3_uri = None
            if json_file:
                try:
                    json_s3_uri = self.s3_uploader.upload_json_file(
                        json_file_path=json_file,
                        image_s3_key=s3_uri.replace(f"s3://{self.s3_uploader.bucket}/", ""),
                    )
                    self.stats["json_files_uploaded"] += 1
                    logger.info(
                        "json_metadata_uploaded",
                        json_file=str(json_file),
                        json_s3_uri=json_s3_uri,
                        image_s3_uri=s3_uri,
                    )
                except Exception as e:
                    logger.warning(
                        "json_upload_failed",
                        json_file=str(json_file),
                        error=str(e),
                        exc_info=True,
                    )
                    # Continue even if JSON upload fails

            # Stage 4: Send SQS notification
            status = UploadStatus.NOTIFYING
            
            # Add JSON S3 URI to metadata if available
            if json_s3_uri:
                metadata["json_metadata_s3_uri"] = json_s3_uri
            
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

    def _handle_post_upload_action(self, file_path: Path) -> None:
        """Handle post-upload action (keep/archive/delete).
        
        Also handles companion JSON metadata files if they exist.
        
        Args:
            file_path: Path to original file
        """
        try:
            # Check for companion JSON file
            json_file = file_path.with_suffix(".json")
            has_json_companion = json_file.exists()
            
            if self.post_upload_action == PostUploadAction.KEEP:
                logger.debug(
                    "post_upload_keep",
                    file=str(file_path),
                    has_json_companion=has_json_companion,
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

                # Move image file to archive
                shutil.move(str(file_path), str(archive_path))

                # Move companion JSON file if it exists
                if has_json_companion:
                    json_archive_path = archive_path.with_suffix(".json")
                    shutil.move(str(json_file), str(json_archive_path))
                    logger.info(
                        "post_upload_archived_with_json",
                        file=str(file_path),
                        archive_path=str(archive_path),
                        json_archive_path=str(json_archive_path),
                    )
                else:
                    logger.info(
                        "post_upload_archived",
                        file=str(file_path),
                        archive_path=str(archive_path),
                    )

            elif self.post_upload_action == PostUploadAction.DELETE:
                file_path.unlink()
                
                # Delete companion JSON file if it exists
                if has_json_companion:
                    json_file.unlink()
                    logger.info(
                        "post_upload_deleted_with_json",
                        file=str(file_path),
                        json_file=str(json_file),
                    )
                else:
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
