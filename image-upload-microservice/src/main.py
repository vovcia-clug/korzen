"""Main entry point for the image upload microservice.

This module initializes all services, starts the directory watcher,
and handles graceful shutdown.
"""

import signal
import sys
import time
from pathlib import Path

from .config import Config
from .services.directory_watcher import DirectoryWatcher
from .services.image_detector import ImageDetector
from .services.s3_uploader import S3Uploader
from .services.sqs_notifier import SQSNotifier
from .services.upload_orchestrator import UploadOrchestrator
from .utils.logger import configure_aws_logging, get_logger, setup_logging

# Global references for signal handlers
watcher = None
orchestrator = None
logger = None


def signal_handler(signum: int, frame) -> None:
    """Handle shutdown signals gracefully.
    
    Args:
        signum: Signal number
        frame: Current stack frame
    """
    global watcher, orchestrator, logger

    signal_name = signal.Signals(signum).name
    logger.info(
        "shutdown_signal_received",
        signal=signal_name,
    )

    # Stop the directory watcher
    if watcher:
        logger.info("stopping_directory_watcher")
        watcher.stop()

    # Log final statistics
    if orchestrator:
        stats = orchestrator.get_statistics()
        logger.info(
            "shutdown_statistics",
            **stats,
        )

    logger.info("service_stopped")
    sys.exit(0)


def verify_aws_connectivity(config: Config, s3_uploader: S3Uploader, sqs_notifier: SQSNotifier) -> bool:
    """Verify connectivity to AWS services.
    
    Args:
        config: Application configuration
        s3_uploader: S3 uploader instance
        sqs_notifier: SQS notifier instance
        
    Returns:
        True if all services are accessible
    """
    logger.info("verifying_aws_connectivity")

    # Verify S3 bucket access
    if not s3_uploader.verify_bucket_access():
        logger.error(
            "s3_bucket_not_accessible",
            bucket=config.s3_bucket,
        )
        return False

    # Verify SQS queue access
    if not sqs_notifier.verify_queue_access():
        logger.error(
            "sqs_queue_not_accessible",
            queue_url=config.sqs_queue_url,
        )
        return False

    logger.info("aws_connectivity_verified")
    return True


def scan_existing_files(
    directory: Path,
    orchestrator: UploadOrchestrator,
    supported_extensions: set,
    recursive: bool = False
) -> int:
    """Scan directory for existing files and process them.
    
    Args:
        directory: Directory to scan
        orchestrator: Upload orchestrator to process files
        supported_extensions: Set of supported file extensions
        recursive: Whether to scan subdirectories
        
    Returns:
        Number of files found
    """
    scan_logger = get_logger(__name__)
    files_found = 0
    
    try:
        if recursive:
            # Recursively scan all subdirectories
            for file_path in directory.rglob("*"):
                if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
                    # Skip hidden files and system files
                    if not file_path.name.startswith(".") and file_path.name not in {"Thumbs.db", ".DS_Store", "desktop.ini"}:
                        files_found += 1
                        scan_logger.info("initial_scan_file_found", file=str(file_path))
                        # Process file in background (don't block startup)
                        try:
                            orchestrator.process_file(file_path)
                        except Exception as e:
                            scan_logger.error(
                                "initial_scan_file_failed",
                                file=str(file_path),
                                error=str(e),
                                exc_info=True
                            )
        else:
            # Only scan top-level files
            for file_path in directory.iterdir():
                if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
                    # Skip hidden files and system files
                    if not file_path.name.startswith(".") and file_path.name not in {"Thumbs.db", ".DS_Store", "desktop.ini"}:
                        files_found += 1
                        scan_logger.info("initial_scan_file_found", file=str(file_path))
                        # Process file in background (don't block startup)
                        try:
                            orchestrator.process_file(file_path)
                        except Exception as e:
                            scan_logger.error(
                                "initial_scan_file_failed",
                                file=str(file_path),
                                error=str(e),
                                exc_info=True
                            )
    except Exception as e:
        scan_logger.error(
            "initial_scan_error",
            directory=str(directory),
            error=str(e),
            exc_info=True
        )
    
    return files_found


def main() -> None:
    """Main entry point for the service."""
    global watcher, orchestrator, logger

    # Load configuration
    try:
        config = Config.from_env()
    except Exception as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)

    # Setup logging
    setup_logging(config.log_level)
    configure_aws_logging()
    logger = get_logger(__name__)

    logger.info(
        "service_starting",
        version="1.0.0",
        watch_directory=str(config.watch_directory),
        s3_bucket=config.s3_bucket,
        post_upload_action=config.post_upload_action,
    )

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    try:
        # Initialize services
        logger.info("initializing_services")

        # Image detector
        image_detector = ImageDetector(
            supported_extensions=config.supported_extensions,
            min_size_bytes=config.min_image_size_bytes,
            max_size_bytes=config.max_image_size_bytes,
            strict_validation=config.strict_validation,
        )

        # S3 uploader
        s3_uploader = S3Uploader(
            bucket=config.s3_bucket,
            prefix=config.s3_prefix,
            region=config.aws_region,
            server_side_encryption=config.s3_server_side_encryption,
            storage_class=config.s3_storage_class,
            multipart_threshold_mb=config.multipart_threshold_mb,
            max_retries=config.max_retries,
            aws_access_key_id=config.aws_access_key_id,
            aws_secret_access_key=config.aws_secret_access_key,
        )

        # SQS notifier
        sqs_notifier = SQSNotifier(
            queue_url=config.sqs_queue_url,
            region=config.aws_region,
            batch_size=config.sqs_batch_size,
            max_retries=config.max_retries,
            aws_access_key_id=config.aws_access_key_id,
            aws_secret_access_key=config.aws_secret_access_key,
        )

        # Verify AWS connectivity
        if not verify_aws_connectivity(config, s3_uploader, sqs_notifier):
            logger.error("aws_connectivity_check_failed")
            sys.exit(1)

        # Upload orchestrator
        orchestrator = UploadOrchestrator(
            image_detector=image_detector,
            s3_uploader=s3_uploader,
            sqs_notifier=sqs_notifier,
            post_upload_action=config.post_upload_action,
            archive_directory=config.archive_directory,
        )

        # Directory watcher
        watcher = DirectoryWatcher(
            watch_directory=config.watch_directory,
            callback=orchestrator.process_file,
            debounce_seconds=config.debounce_seconds,
            supported_extensions=set(config.supported_extensions),
            recursive=config.watch_recursive,
        )

        logger.info("services_initialized")

        # Initial scan of existing files
        logger.info("starting_initial_directory_scan", directory=str(config.watch_directory))
        initial_files_found = scan_existing_files(
            config.watch_directory,
            orchestrator,
            set(config.supported_extensions),
            config.watch_recursive
        )
        logger.info(
            "initial_scan_completed",
            files_found=initial_files_found,
            directory=str(config.watch_directory)
        )

        # Start watching directory
        watcher.start()

        logger.info(
            "service_started",
            watching=str(config.watch_directory),
            message="Image upload microservice is running",
        )

        # Keep the main thread alive
        try:
            while True:
                time.sleep(1)

                # Periodically log statistics
                if int(time.time()) % 300 == 0:  # Every 5 minutes
                    stats = orchestrator.get_statistics()
                    logger.info(
                        "periodic_statistics",
                        **stats,
                    )

        except KeyboardInterrupt:
            logger.info("keyboard_interrupt_received")

    except Exception as e:
        logger.error(
            "service_error",
            error=str(e),
            exc_info=True,
        )
        sys.exit(1)

    finally:
        # Cleanup
        if watcher:
            watcher.stop()

        if orchestrator:
            stats = orchestrator.get_statistics()
            logger.info(
                "final_statistics",
                **stats,
            )

        logger.info("service_shutdown_complete")


if __name__ == "__main__":
    main()
