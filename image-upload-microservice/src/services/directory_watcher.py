"""Directory watching service using watchdog.

This module monitors a directory for new image files and triggers
callbacks when files are created or modified with debouncing logic.
"""

import time
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Callable, Dict, Set

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from ..utils.logger import get_logger

logger = get_logger(__name__)


class DebouncedFileHandler(FileSystemEventHandler):
    """File system event handler with debouncing logic.
    
    Debouncing ensures we don't process a file while it's still being written.
    Files are only processed after they haven't been modified for the specified
    debounce period.
    """

    def __init__(
        self,
        callback: Callable[[Path], None],
        debounce_seconds: float = 2.0,
        supported_extensions: Set[str] = None,
    ):
        """Initialize the debounced file handler.
        
        Args:
            callback: Function to call when a file is ready to process
            debounce_seconds: Seconds to wait after last modification
            supported_extensions: Set of supported file extensions (with dots)
        """
        super().__init__()
        self.callback = callback
        self.debounce_seconds = debounce_seconds
        self.supported_extensions = supported_extensions or set()

        # Track pending files with their last modification time
        self.pending_files: Dict[Path, float] = {}
        self.pending_lock = Lock()

        # Track already processed files to avoid duplicates
        self.processed_files: Set[Path] = set()
        self.processed_lock = Lock()

        # Debounce check thread
        self.stop_event = Event()
        self.debounce_thread = Thread(target=self._debounce_loop, daemon=True)
        self.debounce_thread.start()

        logger.info(
            "file_handler_initialized",
            debounce_seconds=debounce_seconds,
            supported_extensions=list(self.supported_extensions),
        )

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation events.
        
        Args:
            event: File system event
        """
        if event.is_directory:
            return

        file_path = Path(event.src_path)
        self._handle_file_event(file_path, "created")

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification events.
        
        Args:
            event: File system event
        """
        if event.is_directory:
            return

        file_path = Path(event.src_path)
        self._handle_file_event(file_path, "modified")

    def _handle_file_event(self, file_path: Path, event_type: str) -> None:
        """Handle a file event with filtering and debouncing.
        
        Args:
            file_path: Path to the file
            event_type: Type of event (created/modified)
        """
        # Filter system files
        if self._is_system_file(file_path):
            logger.debug(
                "file_ignored_system",
                file=str(file_path),
                event_type=event_type,
            )
            return

        # Filter by extension
        if self.supported_extensions:
            if file_path.suffix.lower() not in self.supported_extensions:
                logger.debug(
                    "file_ignored_extension",
                    file=str(file_path),
                    extension=file_path.suffix,
                    event_type=event_type,
                )
                return

        # Check if already processed
        with self.processed_lock:
            if file_path in self.processed_files:
                logger.debug(
                    "file_already_processed",
                    file=str(file_path),
                )
                return

        # Add to pending files with current timestamp
        with self.pending_lock:
            self.pending_files[file_path] = time.time()

        logger.debug(
            "file_detected",
            file=str(file_path),
            event_type=event_type,
        )

    def _is_system_file(self, file_path: Path) -> bool:
        """Check if file is a system/temporary file to ignore.
        
        Args:
            file_path: Path to check
            
        Returns:
            True if file should be ignored
        """
        filename = file_path.name

        # Ignore hidden files
        if filename.startswith("."):
            return True

        # Ignore temporary files
        temp_extensions = {".tmp", ".temp", ".part", ".crdownload"}
        if file_path.suffix.lower() in temp_extensions:
            return True

        # Ignore system files
        system_files = {"Thumbs.db", ".DS_Store", "desktop.ini"}
        if filename in system_files:
            return True

        return False

    def _debounce_loop(self) -> None:
        """Background thread that processes debounced files.
        
        Continuously checks pending files and processes those that haven't
        been modified for the debounce period.
        """
        while not self.stop_event.is_set():
            try:
                current_time = time.time()
                files_to_process = []

                # Check which files are ready to process
                with self.pending_lock:
                    for file_path, last_modified in list(self.pending_files.items()):
                        if current_time - last_modified >= self.debounce_seconds:
                            files_to_process.append(file_path)
                            del self.pending_files[file_path]

                # Process ready files
                for file_path in files_to_process:
                    self._process_file(file_path)

                # Sleep briefly before next check
                time.sleep(0.5)

            except Exception as e:
                logger.error(
                    "debounce_loop_error",
                    error=str(e),
                    exc_info=True,
                )
                time.sleep(1)  # Back off on error

    def _process_file(self, file_path: Path) -> None:
        """Process a debounced file.
        
        Args:
            file_path: Path to file to process
        """
        try:
            # Verify file still exists
            if not file_path.exists():
                logger.debug(
                    "file_disappeared",
                    file=str(file_path),
                )
                return

            # Mark as processed to avoid duplicates
            with self.processed_lock:
                self.processed_files.add(file_path)

            logger.info(
                "file_ready_for_processing",
                file=str(file_path),
            )

            # Call the callback
            self.callback(file_path)

        except Exception as e:
            logger.error(
                "file_processing_error",
                file=str(file_path),
                error=str(e),
                exc_info=True,
            )

            # Remove from processed on error so it can retry
            with self.processed_lock:
                self.processed_files.discard(file_path)

    def stop(self) -> None:
        """Stop the debounce thread."""
        self.stop_event.set()
        if self.debounce_thread.is_alive():
            self.debounce_thread.join(timeout=5)


class DirectoryWatcher:
    """Watches a directory for new image files."""

    def __init__(
        self,
        watch_directory: Path,
        callback: Callable[[Path], None],
        debounce_seconds: float = 2.0,
        supported_extensions: Set[str] = None,
        recursive: bool = False,
    ):
        """Initialize the directory watcher.
        
        Args:
            watch_directory: Directory to monitor
            callback: Function to call when a file is ready
            debounce_seconds: Seconds to wait after last modification
            supported_extensions: Set of supported file extensions
            recursive: Enable recursive subdirectory monitoring
        """
        self.watch_directory = watch_directory
        self.recursive = recursive

        # Create event handler
        self.event_handler = DebouncedFileHandler(
            callback=callback,
            debounce_seconds=debounce_seconds,
            supported_extensions=supported_extensions,
        )

        # Create observer
        self.observer = Observer()
        self.observer.schedule(
            self.event_handler,
            str(watch_directory),
            recursive=recursive,
        )

        logger.info(
            "directory_watcher_initialized",
            directory=str(watch_directory),
            recursive=recursive,
            debounce_seconds=debounce_seconds,
        )

    def start(self) -> None:
        """Start watching the directory."""
        logger.info(
            "directory_watcher_starting",
            directory=str(self.watch_directory),
        )
        self.observer.start()
        logger.info("directory_watcher_started")

    def stop(self, timeout: float = 30.0) -> None:
        """Stop watching the directory.
        
        Args:
            timeout: Maximum seconds to wait for graceful shutdown
        """
        logger.info("directory_watcher_stopping")

        # Stop the event handler's debounce thread
        self.event_handler.stop()

        # Stop the observer
        self.observer.stop()
        self.observer.join(timeout=timeout)

        logger.info("directory_watcher_stopped")

    def is_alive(self) -> bool:
        """Check if the watcher is running.
        
        Returns:
            True if watcher is running
        """
        return self.observer.is_alive()
