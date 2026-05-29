"""
Document grouper for buffering and grouping OCR results by document_id.

Uses in-memory state storage (single instance).
"""

import time
import threading
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from ..utils.logger import get_logger
from ..utils import langfuse_tracer

logger = get_logger(__name__)


@dataclass
class DocumentGroup:
    """Represents a group of OCR results for a single document."""
    document_id: str
    messages: List[Dict[str, Any]] = field(default_factory=list)
    first_seen: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)
    expected_pages: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    processed_pages: set = field(default_factory=set)
    page_retry_counts: Dict[int, int] = field(default_factory=dict)
    
    def add_message(self, message: Dict[str, Any]) -> None:
        """Add a message to the group and reset the timeout timer."""
        page_number = message.get("metadata", {}).get("page_number")
        
        # Check for duplicate page numbers
        existing_pages = [m.get("metadata", {}).get("page_number") for m in self.messages]
        if page_number in existing_pages and page_number is not None:
            from ..utils.logger import get_logger
            logger = get_logger(__name__)
            logger.warning(
                f"DUPLICATE PAGE DETECTED: Document {self.document_id}, "
                f"page {page_number} already exists in group. "
                f"Current pages: {sorted([p for p in existing_pages if p is not None])}"
            )
        
        self.messages.append(message)
        
        # Reset timeout timer on each new message
        self.last_updated = time.time()
        
        # Update expected pages if provided
        if not self.expected_pages:
            total_pages = message.get("metadata", {}).get("total_pages")
            if total_pages:
                self.expected_pages = total_pages
        
        # Update metadata (use first message's metadata as base)
        if not self.metadata:
            self.metadata = message.get("metadata", {}).copy()
    
    def get_sorted_messages(self) -> List[Dict[str, Any]]:
        """Get messages sorted by page number.
        
        Messages with None page_number are sorted to the end.
        """
        return sorted(
            self.messages,
            key=lambda m: (
                m.get("metadata", {}).get("page_number") is None,
                m.get("metadata", {}).get("page_number") or 0
            )
        )
    
    def get_page_numbers(self) -> List[Optional[int]]:
        """Get list of page numbers received.
        
        Returns list that may contain None for messages without page numbers.
        """
        return [
            m.get("metadata", {}).get("page_number")
            for m in self.messages
        ]
    
    def get_unique_page_count(self) -> int:
        """Get count of unique page numbers received.
        
        Returns count of unique non-None page numbers.
        """
        page_numbers = [
            m.get("metadata", {}).get("page_number")
            for m in self.messages
            if m.get("metadata", {}).get("page_number") is not None
        ]
        return len(set(page_numbers))
    
    def mark_page_processed(self, page_number: int) -> None:
        """Mark a page as successfully processed.
        
        Args:
            page_number: Page number to mark as processed
        """
        self.processed_pages.add(page_number)
        logger.debug(f"Marked page {page_number} as processed for document {self.document_id}")
    
    def get_unprocessed_messages(self) -> List[Dict[str, Any]]:
        """Get only messages for pages that haven't been processed yet.
        
        Returns:
            List of messages for unprocessed pages
        """
        unprocessed = []
        for message in self.messages:
            page_number = message.get("metadata", {}).get("page_number")
            if page_number is None or page_number not in self.processed_pages:
                unprocessed.append(message)
        return unprocessed
    
    def increment_page_retry(self, page_number: int) -> int:
        """Increment and return retry count for a page.
        
        Args:
            page_number: Page number to increment retry count for
            
        Returns:
            New retry count for the page
        """
        current_count = self.page_retry_counts.get(page_number, 0)
        new_count = current_count + 1
        self.page_retry_counts[page_number] = new_count
        logger.debug(
            f"Incremented retry count for page {page_number} "
            f"of document {self.document_id} to {new_count}"
        )
        return new_count
    
    def should_retry_page(self, page_number: int, max_retries: int = 3) -> bool:
        """Check if a page should be retried.
        
        Args:
            page_number: Page number to check
            max_retries: Maximum number of retries allowed
            
        Returns:
            True if page should be retried, False if max retries exceeded
        """
        retry_count = self.page_retry_counts.get(page_number, 0)
        should_retry = retry_count < max_retries
        logger.debug(
            f"Page {page_number} of document {self.document_id}: "
            f"retry_count={retry_count}, max_retries={max_retries}, "
            f"should_retry={should_retry}"
        )
        return should_retry
    
    def is_complete(self, timeout_seconds: int) -> tuple[bool, str]:
        """
        Check if document group is complete.
        
        Args:
            timeout_seconds: Timeout in seconds
        
        Returns:
            Tuple of (is_complete, reason)
        """
        from ..utils.logger import get_logger
        logger = get_logger(__name__)
        
        # Check if all expected pages received (count unique pages, not total messages)
        if self.expected_pages:
            unique_page_count = self.get_unique_page_count()
            page_numbers = sorted([m.get('metadata', {}).get('page_number') for m in self.messages if m.get('metadata', {}).get('page_number') is not None])
            logger.debug(
                f"Document {self.document_id}: {unique_page_count}/{self.expected_pages} unique pages received "
                f"({len(self.messages)} total messages). Pages: {page_numbers}"
            )
            if unique_page_count >= self.expected_pages:
                return True, "all_pages_received"
        else:
            unique_page_count = self.get_unique_page_count()
            logger.debug(
                f"Document {self.document_id}: No expected_pages set, {unique_page_count} unique pages "
                f"({len(self.messages)} total messages) received"
            )
        
        # Check if timeout reached (based on last message received)
        elapsed = time.time() - self.last_updated
        if elapsed >= timeout_seconds:
            return True, "timeout_reached"
        
        return False, "incomplete"


class DocumentGrouper:
    """
    Groups OCR results by document_id using in-memory state storage.
    """
    
    def __init__(
        self,
        timeout_seconds: int = 10
    ):
        """
        Initialize document grouper.
        
        Args:
            timeout_seconds: Timeout for document completion (default: 5 minutes)
        """
        self.timeout_seconds = timeout_seconds
        
        # In-memory storage
        self.groups: Dict[str, DocumentGroup] = {}
        self.lock = threading.Lock()
        
        # Idempotency tracking - stores document IDs that have been successfully processed
        self.processed_documents: set = set()
        
        logger.info("Using in-memory document grouping (single instance only)")
    
    def add_message(self, message: Dict[str, Any]) -> None:
        """
        Add a message to the appropriate document group.
        
        Args:
            message: Parsed SQS message with metadata and ocr_result
        """
        metadata = message.get("metadata", {})
        document_id = metadata.get("document_id")
        page_number = metadata.get("page_number")
        
        if not document_id:
            error = ValueError("Message missing document_id in metadata")
            logger.error(str(error))
            langfuse_tracer.log_error(
                error,
                context={
                    "operation": "add_message_to_group",
                    "error_type": "missing_document_id",
                    "message_metadata": metadata
                }
            )
            raise error
        
        logger.info(f"Adding message to document group: {document_id}, page {page_number}")
        
        try:
            self._add_message_memory(document_id, message)
        except Exception as e:
            logger.error(f"Failed to add message to group {document_id}: {e}")
            langfuse_tracer.log_error(
                e,
                context={
                    "operation": "add_message_to_group",
                    "document_id": document_id,
                    "page_number": page_number
                }
            )
            raise
    
    def _add_message_memory(self, document_id: str, message: Dict[str, Any]) -> None:
        """Add message to in-memory storage."""
        with self.lock:
            if document_id not in self.groups:
                self.groups[document_id] = DocumentGroup(document_id=document_id)
            
            self.groups[document_id].add_message(message)
            
            unique_pages = self.groups[document_id].get_unique_page_count()
            total_messages = len(self.groups[document_id].messages)
            logger.debug(
                f"Document {document_id}: {unique_pages} unique pages ({total_messages} total messages) buffered"
            )
    
    def is_complete(self, document_id: str) -> tuple[bool, str]:
        """
        Check if a document group is complete.
        
        Args:
            document_id: Document identifier
        
        Returns:
            Tuple of (is_complete, reason)
        """
        return self._is_complete_memory(document_id)
    
    def _is_complete_memory(self, document_id: str) -> tuple[bool, str]:
        """Check completion in memory storage."""
        with self.lock:
            if document_id not in self.groups:
                return False, "not_found"
            
            return self.groups[document_id].is_complete(self.timeout_seconds)
    
    def get_group(self, document_id: str) -> Optional[DocumentGroup]:
        """
        Get a document group.
        
        Args:
            document_id: Document identifier
        
        Returns:
            DocumentGroup or None if not found
        """
        return self._get_group_memory(document_id)
    
    def _get_group_memory(self, document_id: str) -> Optional[DocumentGroup]:
        """Get group from memory storage."""
        with self.lock:
            return self.groups.get(document_id)
    
    def remove_group(self, document_id: str) -> None:
        """
        Remove a document group after processing.
        
        Args:
            document_id: Document identifier
        """
        self._remove_group_memory(document_id)
        logger.info(f"Removed document group: {document_id}")
    
    def _remove_group_memory(self, document_id: str) -> None:
        """Remove group from memory storage."""
        with self.lock:
            if document_id in self.groups:
                del self.groups[document_id]
    
    def get_all_document_ids(self) -> List[str]:
        """
        Get all document IDs currently being tracked.
        
        Returns:
            List of document IDs
        """
        return self._get_all_document_ids_memory()
    
    def _get_all_document_ids_memory(self) -> List[str]:
        """Get all document IDs from memory storage."""
        with self.lock:
            return list(self.groups.keys())
    
    def check_timeouts(self) -> List[str]:
        """
        Check for timed-out documents and return their IDs.
        
        Returns:
            List of document IDs that have timed out
        """
        timed_out = []
        
        for document_id in self.get_all_document_ids():
            is_complete, reason = self.is_complete(document_id)
            if is_complete and reason == "timeout_reached":
                timed_out.append(document_id)
                logger.warning(
                    f"Document {document_id} timed out after {self.timeout_seconds}s"
                )
        
        return timed_out
    
    def is_already_processed(self, document_id: str) -> bool:
        """
        Check if a document has already been successfully processed.
        
        This provides idempotency - prevents reprocessing of documents
        that were already completed.
        
        Args:
            document_id: Document identifier
        
        Returns:
            True if document was already processed, False otherwise
        """
        with self.lock:
            return document_id in self.processed_documents
    
    def mark_as_processed(self, document_id: str) -> None:
        """
        Mark a document as successfully processed.
        
        This should be called after successful document processing
        to prevent reprocessing if the same document appears again.
        
        Args:
            document_id: Document identifier
        """
        with self.lock:
            self.processed_documents.add(document_id)
            logger.debug(f"Marked document {document_id} as processed")
