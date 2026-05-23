"""
Document grouper for buffering and grouping OCR results by document_id.

Supports both in-memory (single instance) and Redis (distributed) state storage.
"""

import json
import time
import threading
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone

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
    
    def add_message(self, message: Dict[str, Any]) -> None:
        """Add a message to the group and reset the timeout timer."""
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
    
    def is_complete(self, timeout_seconds: int) -> tuple[bool, str]:
        """
        Check if document group is complete.
        
        Args:
            timeout_seconds: Timeout in seconds
        
        Returns:
            Tuple of (is_complete, reason)
        """
        # Check if all expected pages received
        if self.expected_pages:
            if len(self.messages) >= self.expected_pages:
                return True, "all_pages_received"
        
        # Check if timeout reached (based on last message received)
        elapsed = time.time() - self.last_updated
        if elapsed >= timeout_seconds:
            return True, "timeout_reached"
        
        return False, "incomplete"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "document_id": self.document_id,
            "messages": self.messages,
            "first_seen": self.first_seen,
            "last_updated": self.last_updated,
            "expected_pages": self.expected_pages,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocumentGroup":
        """Create from dictionary."""
        return cls(
            document_id=data["document_id"],
            messages=data.get("messages", []),
            first_seen=data.get("first_seen", time.time()),
            last_updated=data.get("last_updated", time.time()),
            expected_pages=data.get("expected_pages"),
            metadata=data.get("metadata", {})
        )


class DocumentGrouper:
    """
    Groups OCR results by document_id with support for in-memory or Redis storage.
    """
    
    def __init__(
        self,
        timeout_seconds: int = 10,
        use_redis: bool = False,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_db: int = 0,
        redis_key_prefix: str = "gedcom:docgroup:"
    ):
        """
        Initialize document grouper.
        
        Args:
            timeout_seconds: Timeout for document completion (default: 5 minutes)
            use_redis: Whether to use Redis for distributed state
            redis_host: Redis host
            redis_port: Redis port
            redis_db: Redis database number
            redis_key_prefix: Prefix for Redis keys
        """
        self.timeout_seconds = timeout_seconds
        self.use_redis = use_redis
        self.redis_key_prefix = redis_key_prefix
        
        # In-memory storage
        self.groups: Dict[str, DocumentGroup] = {}
        self.lock = threading.Lock()
        
        # Idempotency tracking - stores document IDs that have been successfully processed
        self.processed_documents: set = set()
        
        # Redis storage (optional)
        self.redis_client = None
        if use_redis:
            try:
                import redis
                self.redis_client = redis.Redis(
                    host=redis_host,
                    port=redis_port,
                    db=redis_db,
                    decode_responses=True
                )
                # Test connection
                self.redis_client.ping()
                logger.info(f"Connected to Redis at {redis_host}:{redis_port}")
            except ImportError:
                logger.error("Redis library not installed. Install with: pip install redis")
                raise
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                raise
        else:
            logger.info("Using in-memory document grouping (single instance only)")
    
    @langfuse_tracer.observe(name="group-document")
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
            raise ValueError("Message missing document_id in metadata")
        
        logger.info(f"Adding message to document group: {document_id}, page {page_number}")
        
        if self.use_redis:
            self._add_message_redis(document_id, message)
        else:
            self._add_message_memory(document_id, message)
    
    def _add_message_memory(self, document_id: str, message: Dict[str, Any]) -> None:
        """Add message to in-memory storage."""
        with self.lock:
            if document_id not in self.groups:
                self.groups[document_id] = DocumentGroup(document_id=document_id)
            
            self.groups[document_id].add_message(message)
            
            logger.debug(
                f"Document {document_id}: {len(self.groups[document_id].messages)} messages buffered"
            )
    
    def _add_message_redis(self, document_id: str, message: Dict[str, Any]) -> None:
        """Add message to Redis storage with distributed locking."""
        redis_key = f"{self.redis_key_prefix}{document_id}"
        lock_key = f"{redis_key}:lock"
        
        # Acquire distributed lock
        lock_acquired = self.redis_client.set(lock_key, "1", nx=True, ex=10)
        
        try:
            if not lock_acquired:
                # Wait briefly and retry
                time.sleep(0.1)
                lock_acquired = self.redis_client.set(lock_key, "1", nx=True, ex=10)
            
            if not lock_acquired:
                logger.warning(f"Could not acquire lock for document {document_id}")
                # Fall back to adding without lock (may cause race conditions)
            
            # Get existing group or create new
            group_data = self.redis_client.get(redis_key)
            if group_data:
                group = DocumentGroup.from_dict(json.loads(group_data))
            else:
                group = DocumentGroup(document_id=document_id)
            
            # Add message
            group.add_message(message)
            
            # Save back to Redis with TTL (2x timeout to allow for processing)
            self.redis_client.setex(
                redis_key,
                self.timeout_seconds * 2,
                json.dumps(group.to_dict())
            )
            
            logger.debug(
                f"Document {document_id}: {len(group.messages)} messages buffered (Redis)"
            )
            
        finally:
            # Release lock
            if lock_acquired:
                self.redis_client.delete(lock_key)
    
    def is_complete(self, document_id: str) -> tuple[bool, str]:
        """
        Check if a document group is complete.
        
        Args:
            document_id: Document identifier
        
        Returns:
            Tuple of (is_complete, reason)
        """
        if self.use_redis:
            return self._is_complete_redis(document_id)
        else:
            return self._is_complete_memory(document_id)
    
    def _is_complete_memory(self, document_id: str) -> tuple[bool, str]:
        """Check completion in memory storage."""
        with self.lock:
            if document_id not in self.groups:
                return False, "not_found"
            
            return self.groups[document_id].is_complete(self.timeout_seconds)
    
    def _is_complete_redis(self, document_id: str) -> tuple[bool, str]:
        """Check completion in Redis storage."""
        redis_key = f"{self.redis_key_prefix}{document_id}"
        group_data = self.redis_client.get(redis_key)
        
        if not group_data:
            return False, "not_found"
        
        group = DocumentGroup.from_dict(json.loads(group_data))
        return group.is_complete(self.timeout_seconds)
    
    def get_group(self, document_id: str) -> Optional[DocumentGroup]:
        """
        Get a document group.
        
        Args:
            document_id: Document identifier
        
        Returns:
            DocumentGroup or None if not found
        """
        if self.use_redis:
            return self._get_group_redis(document_id)
        else:
            return self._get_group_memory(document_id)
    
    def _get_group_memory(self, document_id: str) -> Optional[DocumentGroup]:
        """Get group from memory storage."""
        with self.lock:
            return self.groups.get(document_id)
    
    def _get_group_redis(self, document_id: str) -> Optional[DocumentGroup]:
        """Get group from Redis storage."""
        redis_key = f"{self.redis_key_prefix}{document_id}"
        group_data = self.redis_client.get(redis_key)
        
        if not group_data:
            return None
        
        return DocumentGroup.from_dict(json.loads(group_data))
    
    def remove_group(self, document_id: str) -> None:
        """
        Remove a document group after processing.
        
        Args:
            document_id: Document identifier
        """
        if self.use_redis:
            self._remove_group_redis(document_id)
        else:
            self._remove_group_memory(document_id)
        
        logger.info(f"Removed document group: {document_id}")
    
    def _remove_group_memory(self, document_id: str) -> None:
        """Remove group from memory storage."""
        with self.lock:
            if document_id in self.groups:
                del self.groups[document_id]
    
    def _remove_group_redis(self, document_id: str) -> None:
        """Remove group from Redis storage."""
        redis_key = f"{self.redis_key_prefix}{document_id}"
        self.redis_client.delete(redis_key)
    
    def get_all_document_ids(self) -> List[str]:
        """
        Get all document IDs currently being tracked.
        
        Returns:
            List of document IDs
        """
        if self.use_redis:
            return self._get_all_document_ids_redis()
        else:
            return self._get_all_document_ids_memory()
    
    def _get_all_document_ids_memory(self) -> List[str]:
        """Get all document IDs from memory storage."""
        with self.lock:
            return list(self.groups.keys())
    
    def _get_all_document_ids_redis(self) -> List[str]:
        """Get all document IDs from Redis storage."""
        pattern = f"{self.redis_key_prefix}*"
        keys = self.redis_client.keys(pattern)
        
        # Extract document IDs from keys
        prefix_len = len(self.redis_key_prefix)
        document_ids = []
        
        for key in keys:
            if not key.endswith(":lock"):
                document_ids.append(key[prefix_len:])
        
        return document_ids
    
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
