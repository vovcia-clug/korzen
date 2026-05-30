# Queue Blocking Fix - Non-Blocking Queue Put with Back-Pressure

## Problem

The GEDCOM generation microservice had a critical issue where `await queue.put(work_item)` at line 278 in `main.py` would block the SQS poller when the per-document queue was full. This caused large documents to completely block processing of other documents, as the poller couldn't receive new messages for ANY document while waiting for queue space.

## Solution

Implemented a non-blocking queue put mechanism with back-pressure to prevent the SQS poller from blocking:

### 1. Configuration Changes (`src/config.py`)

Added two new configuration parameters:

- **`PAGE_QUEUE_MAX_SIZE`**: Changed default from `0` (unlimited) to `100` to prevent memory exhaustion
- **`QUEUE_BACKPRESSURE_VISIBILITY_TIMEOUT`**: New parameter (default: 60 seconds) to control retry delay when queue is full

```python
PAGE_QUEUE_MAX_SIZE: int = int(os.getenv("PAGE_QUEUE_MAX_SIZE", "100"))
QUEUE_BACKPRESSURE_VISIBILITY_TIMEOUT: int = int(
    os.getenv("QUEUE_BACKPRESSURE_VISIBILITY_TIMEOUT", "60")
)
```

### 2. Main Processing Logic Changes (`src/main.py`)

Replaced blocking `await queue.put(work_item)` with non-blocking approach:

**Before:**
```python
await queue.put(work_item)  # BLOCKS if queue is full
```

**After:**
```python
try:
    queue.put_nowait(work_item)
except asyncio.QueueFull:
    logger.warning(
        f"Queue full for document {document_id} "
        f"(size: {queue.qsize()}/{queue.maxsize}), "
        f"applying back-pressure - message will retry in "
        f"{Config.QUEUE_BACKPRESSURE_VISIBILITY_TIMEOUT}s"
    )
    # Change message visibility to delay retry
    await self.sqs_consumer.change_message_visibility(
        receipt_handle=parsed["receipt_handle"],
        visibility_timeout=Config.QUEUE_BACKPRESSURE_VISIBILITY_TIMEOUT
    )
    return  # Don't delete message, let SQS retry
```

### 3. SQS Consumer Support (`src/services/sqs_consumer.py`)

The `change_message_visibility()` method was already implemented in the SQS consumer (lines 193-224), so no changes were needed.

## How It Works

1. **Normal Operation**: When a message arrives, the service attempts to add it to the per-document queue using `queue.put_nowait()`
2. **Queue Full**: If the queue is full (100 pages buffered), an `asyncio.QueueFull` exception is raised
3. **Back-Pressure Applied**:
   - Log a warning with document ID, queue size, and retry delay
   - Change the SQS message visibility timeout to 60 seconds (configurable)
   - Return without deleting the message
4. **Automatic Retry**: SQS will automatically make the message visible again after 60 seconds
5. **Poller Continues**: The SQS poller is NOT blocked and can continue receiving messages for other documents

## Benefits

- **No Blocking**: SQS poller never blocks, ensuring messages for all documents can be received
- **Memory Protection**: Queue size limit (100 pages) prevents memory exhaustion from large documents
- **Graceful Back-Pressure**: Messages are automatically retried when queue has space
- **Observability**: Warning logs track when back-pressure is applied
- **Configurable**: Both queue size and retry delay can be tuned via environment variables

## Configuration

Add to `.env` file to customize:

```bash
# Maximum pages that can be queued per document (default: 100)
PAGE_QUEUE_MAX_SIZE=100

# Retry delay when queue is full in seconds (default: 60)
QUEUE_BACKPRESSURE_VISIBILITY_TIMEOUT=60
```

## Testing Considerations

- **Normal Flow**: Messages are processed normally when queue has space
- **Queue Full**: Messages are properly retried after visibility timeout expires
- **Multi-Document**: SQS poller continues receiving messages for other documents when one document's queue is full
- **Memory**: Queue size limit prevents unbounded memory growth

## Related Files

- [`src/main.py`](src/main.py:278) - Non-blocking queue put implementation
- [`src/config.py`](src/config.py:58) - Back-pressure configuration
- [`src/services/sqs_consumer.py`](src/services/sqs_consumer.py:193) - Message visibility change method
