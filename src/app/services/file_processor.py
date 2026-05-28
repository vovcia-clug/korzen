"""
Background file processing service using a queue-based approach.

This module provides a queue-based file processing system that allows
file uploads to return immediately while processing happens asynchronously
in the background.
"""

import logging
import queue
import threading
from datetime import datetime
from typing import Optional

from ..extensions import db
from ..gedcom_parser import GedcomParser
from ..models import UploadedFile

logger = logging.getLogger(__name__)


class FileProcessorQueue:
    """
    Queue-based file processor that handles GEDCOM file parsing asynchronously.
    
    This class implements a producer-consumer pattern where:
    - Producers (upload endpoints) add files to the queue
    - A background worker thread processes files sequentially from the queue
    """
    
    def __init__(self):
        """Initialize the file processor queue."""
        self._queue = queue.Queue()
        self._worker_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()
        self._is_running = False
        logger.info("FileProcessorQueue initialized")
    
    def start(self):
        """Start the background worker thread."""
        if self._is_running:
            logger.warning("FileProcessorQueue is already running")
            return
        
        self._shutdown_event.clear()
        self._worker_thread = threading.Thread(
            target=self._process_queue,
            name="FileProcessorWorker",
            daemon=True
        )
        self._worker_thread.start()
        self._is_running = True
        logger.info("FileProcessorQueue worker thread started")
    
    def stop(self, timeout: float = 30.0):
        """
        Stop the background worker thread gracefully.
        
        Args:
            timeout: Maximum time to wait for the worker to finish (seconds)
        """
        if not self._is_running:
            logger.warning("FileProcessorQueue is not running")
            return
        
        logger.info("Stopping FileProcessorQueue worker thread...")
        self._shutdown_event.set()
        
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=timeout)
            
            if self._worker_thread.is_alive():
                logger.warning("Worker thread did not stop within timeout")
            else:
                logger.info("Worker thread stopped successfully")
        
        self._is_running = False
    
    def enqueue_file(self, file_id: str, filepath: str) -> bool:
        """
        Add a file to the processing queue.
        
        Args:
            file_id: The UUID of the uploaded file record
            filepath: Path to the file on disk
            
        Returns:
            True if file was successfully queued, False otherwise
        """
        try:
            self._queue.put({
                'file_id': file_id,
                'filepath': filepath,
                'queued_at': datetime.utcnow()
            }, block=False)
            
            logger.info(f"File {file_id} queued for processing (queue size: {self._queue.qsize()})")
            return True
            
        except queue.Full:
            logger.error(f"Queue is full, cannot enqueue file {file_id}")
            return False
        except Exception as e:
            logger.error(f"Error enqueueing file {file_id}: {e}", exc_info=True)
            return False
    
    def get_queue_size(self) -> int:
        """Get the current number of files waiting in the queue."""
        return self._queue.qsize()
    
    def is_running(self) -> bool:
        """Check if the worker thread is running."""
        return self._is_running
    
    def _process_queue(self):
        """
        Background worker that processes files from the queue.
        
        This method runs in a separate thread and continuously processes
        files from the queue until shutdown is requested.
        """
        logger.info("File processor worker started")
        
        while not self._shutdown_event.is_set():
            try:
                # Wait for a file with a timeout to allow checking shutdown event
                try:
                    file_data = self._queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                
                file_id = file_data['file_id']
                filepath = file_data['filepath']
                queued_at = file_data['queued_at']
                
                # Calculate queue wait time
                wait_time = (datetime.utcnow() - queued_at).total_seconds()
                logger.info(f"Processing file {file_id} (waited {wait_time:.2f}s in queue)")
                
                # Process the file
                self._process_file(file_id, filepath)
                
                # Mark task as done
                self._queue.task_done()
                
            except Exception as e:
                logger.error(f"Error in file processor worker: {e}", exc_info=True)
                # Continue processing other files even if one fails
        
        logger.info("File processor worker stopped")
    
    def _process_file(self, file_id: str, filepath: str):
        """
        Process a single GEDCOM file.
        
        Args:
            file_id: The UUID of the uploaded file record
            filepath: Path to the file on disk
        """
        # Create a new application context for this thread
        from flask import current_app
        
        with current_app.app_context():
            try:
                # Get the uploaded file record
                uploaded_file = db.session.get(UploadedFile, file_id)
                
                if not uploaded_file:
                    logger.error(f"File record not found: {file_id}")
                    return
                
                # Update status to processing
                uploaded_file.processing_status = 'processing'
                db.session.commit()
                
                logger.info(f"Starting to parse file {file_id}: {uploaded_file.filename}")
                
                # Create parser and import data
                parser = GedcomParser(filepath, file_id)
                stats = parser.parse_and_import()
                
                # Update status to completed
                uploaded_file.processing_status = 'completed'
                db.session.commit()
                
                logger.info(f"File {file_id} parsed successfully. Statistics: {stats}")
                
            except Exception as e:
                logger.error(f"Failed to parse file {file_id}: {e}", exc_info=True)
                
                # Update status to failed
                try:
                    uploaded_file = db.session.get(UploadedFile, file_id)
                    if uploaded_file:
                        uploaded_file.processing_status = 'failed'
                        db.session.commit()
                except Exception as update_error:
                    logger.error(f"Failed to update file status: {update_error}", exc_info=True)
                    db.session.rollback()


# Global instance of the file processor queue
_file_processor_queue: Optional[FileProcessorQueue] = None


def get_file_processor_queue() -> FileProcessorQueue:
    """
    Get the global file processor queue instance.
    
    Returns:
        The global FileProcessorQueue instance
    """
    global _file_processor_queue
    
    if _file_processor_queue is None:
        _file_processor_queue = FileProcessorQueue()
        _file_processor_queue.start()
    
    return _file_processor_queue


def initialize_file_processor():
    """Initialize and start the file processor queue."""
    queue_instance = get_file_processor_queue()
    logger.info(f"File processor initialized (running: {queue_instance.is_running()})")
    return queue_instance


def shutdown_file_processor():
    """Shutdown the file processor queue gracefully."""
    global _file_processor_queue
    
    if _file_processor_queue is not None:
        _file_processor_queue.stop()
        _file_processor_queue = None
        logger.info("File processor shutdown complete")
