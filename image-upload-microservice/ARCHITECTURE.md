# Image Upload Microservice - Architecture & Technical Specification

## Executive Summary

The Image Upload Microservice is a Python-based service designed to automatically monitor a directory for new image files, upload them to AWS S3, and trigger downstream processing by sending notification messages to AWS SQS. This service acts as the entry point in an automated OCR pipeline, feeding images to the existing OCR microservice.

## Architecture Overview

### System Context

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         Image Upload Pipeline                             │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ┌───────────────┐     ┌──────────────────┐     ┌──────────────────┐   │
│  │  Monitored    │────▶│  Image Upload    │────▶│    AWS S3        │   │
│  │  Directory    │     │  Microservice    │     │  (Input Bucket)  │   │
│  └───────────────┘     └──────────────────┘     └──────────────────┘   │
│                                 │                                         │
│                                 ▼                                         │
│                        ┌──────────────────┐                              │
│                        │    AWS SQS       │                              │
│                        │  (OCR Queue)     │                              │
│                        └──────────────────┘                              │
│                                 │                                         │
│                                 ▼                                         │
│                        ┌──────────────────┐                              │
│                        │ OCR Microservice │                              │
│                        │  (Existing)      │                              │
│                        └──────────────────┘                              │
└──────────────────────────────────────────────────────────────────────────┘
```

### Component Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│              Image Upload Microservice - Internal Components            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌─────────────────────┐                                                │
│  │  Directory Watcher  │ (watchdog library)                             │
│  │  - File Events      │                                                │
│  │  - Event Filter     │                                                │
│  └──────────┬──────────┘                                                │
│             │                                                             │
│             ▼                                                             │
│  ┌─────────────────────┐                                                │
│  │  Image Detector     │ (image file validation)                        │
│  │  - Format Check     │                                                │
│  │  - MIME Detection   │                                                │
│  └──────────┬──────────┘                                                │
│             │                                                             │
│             ▼                                                             │
│  ┌─────────────────────┐                                                │
│  │  Upload Orchestrator│                                                │
│  │  - Workflow Control │                                                │
│  │  - Error Handling   │                                                │
│  └──────────┬──────────┘                                                │
│             │                                                             │
│    ┌────────┴────────┐                                                  │
│    │                 │                                                   │
│    ▼                 ▼                                                   │
│  ┌──────────┐   ┌──────────┐                                           │
│  │ S3       │   │ SQS      │                                            │
│  │ Uploader │   │ Notifier │                                            │
│  └──────────┘   └──────────┘                                            │
│                                                                           │
│  ┌─────────────────────────────────────────┐                           │
│  │  Supporting Components                  │                            │
│  │  - Config Manager                       │                            │
│  │  - Logger (structured logging)          │                            │
│  │  - Metrics Collector (optional)         │                            │
│  └─────────────────────────────────────────┘                           │
└─────────────────────────────────────────────────────────────────────────┘
```

## Technology Stack

### Core Technologies

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|----------|
| Runtime | Python | 3.11+ | Application runtime |
| Containerization | Docker | 20.10+ | Container runtime |
| Container Orchestration | Docker Compose | 2.0+ | Multi-container apps |
| Package Manager | pip | Latest | Dependency management |

### Python Libraries

| Library | Version | Purpose |
|---------|---------|---------|
| `watchdog` | 3.0+ | File system event monitoring |
| `boto3` | 1.28+ | AWS SDK for S3 and SQS |
| `Pillow` | 10.0+ | Image validation and format detection |
| `python-magic` | 0.4+ | MIME type detection |
| `python-dotenv` | 1.0+ | Environment variable management |
| `tenacity` | 8.2+ | Retry logic with exponential backoff |
| `structlog` | 23.0+ | Structured logging |
| `pydantic` | 2.0+ | Configuration validation |
| `pytest` | 7.4+ | Testing framework (dev) |

### AWS Services

- **AWS S3**: Object storage for uploaded images
- **AWS SQS**: Message queue for triggering OCR processing
- **AWS IAM**: Identity and access management

## Directory Structure

```
image-upload-microservice/
├── src/
│   ├── __init__.py
│   ├── main.py                          # Entry point and main loop
│   ├── config.py                        # Configuration management
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── directory_watcher.py         # Watchdog-based file monitoring
│   │   ├── image_detector.py            # Image validation and detection
│   │   ├── s3_uploader.py               # S3 upload operations
│   │   ├── sqs_notifier.py              # SQS message publishing
│   │   └── upload_orchestrator.py       # Workflow coordination
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── upload_event.py              # Upload event data models
│   │   └── notification_message.py      # SQS message models
│   │
│   └── utils/
│       ├── __init__.py
│       ├── logger.py                     # Logging configuration
│       ├── validators.py                 # File validation utilities
│       └── retry_handler.py              # Retry logic utilities
│
├── tests/
│   ├── __init__.py
│   ├── test_directory_watcher.py
│   ├── test_image_detector.py
│   ├── test_s3_uploader.py
│   ├── test_sqs_notifier.py
│   └── fixtures/
│       └── sample_images/
│
├── .env.example                          # Environment variables template
├── .gitignore                            # Git ignore rules
├── docker-compose.yml                    # Docker Compose configuration
├── Dockerfile                            # Docker image definition
├── requirements.txt                      # Python dependencies
├── requirements-dev.txt                  # Development dependencies
├── README.md                             # User documentation
├── ARCHITECTURE.md                       # This file
└── CHANGELOG.md                          # Version history

```

## Core Components

### 1. Directory Watcher

**Responsibility**: Monitor specified directory for file system events

**Technology**: `watchdog` library with `Observer` pattern

**Key Features**:
- Real-time file system event monitoring
- Configurable polling interval (for network filesystems)
- Event filtering (create, modify events)
- Debouncing to avoid duplicate processing
- Recursive directory watching (optional)

**Implementation Details**:
```python
# Monitors for:
# - FileCreatedEvent: New file added
# - FileModifiedEvent: Existing file completed writing

# Filters out:
# - Directory events
# - Temporary files (.tmp, .temp)
# - Hidden files (starting with .)
# - System files (.DS_Store, Thumbs.db)
```

**Configuration**:
- `WATCH_DIRECTORY`: Directory path to monitor
- `WATCH_RECURSIVE`: Enable recursive subdirectory monitoring
- `DEBOUNCE_SECONDS`: Time to wait before processing (avoid partial writes)
- `POLLING_INTERVAL`: Fallback polling for network filesystems

### 2. Image Detector

**Responsibility**: Validate and detect image files

**Technology**: `Pillow` + `python-magic`

**Key Features**:
- Multi-layer validation
- MIME type detection
- File extension validation
- Image header verification
- Corrupt file detection

**Supported Formats**:
- JPEG/JPG (image/jpeg)
- PNG (image/png)
- GIF (image/gif)
- BMP (image/bmp)
- TIFF/TIF (image/tiff)
- WEBP (image/webp)
- HEIC/HEIF (image/heic, image/heif)
- SVG (image/svg+xml) - optional, configurable

**Validation Layers**:

1. **Extension Check**: Quick pre-filter based on file extension
2. **MIME Type Detection**: Use python-magic to detect actual file type
3. **Image Header Validation**: Use Pillow to verify image can be opened
4. **Minimum Size Check**: Configurable minimum file size (avoid empty files)
5. **Maximum Size Check**: Configurable maximum file size (resource protection)

**Configuration**:
- `ALLOWED_IMAGE_EXTENSIONS`: Comma-separated list of extensions
- `MIN_IMAGE_SIZE_BYTES`: Minimum file size (default: 1024 bytes)
- `MAX_IMAGE_SIZE_BYTES`: Maximum file size (default: 100MB)
- `STRICT_VALIDATION`: Enable header validation (default: true)

### 3. S3 Uploader

**Responsibility**: Upload validated images to AWS S3

**Technology**: `boto3` S3 client

**Key Features**:
- Multipart upload for large files
- Progress tracking
- Automatic content-type detection
- Metadata attachment
- Server-side encryption support
- Object tagging

**Upload Strategy**:
- Files < 5MB: Standard `put_object`
- Files ≥ 5MB: Multipart upload with 5MB chunks
- Automatic retry with exponential backoff
- Upload progress logging

**Object Naming Strategy**:
```
s3://{bucket}/{prefix}/{timestamp}/{uuid}_{original_filename}

Example:
s3://my-images-bucket/uploads/2026/05/17/a7f3c4e1-2b45-4f89-b123-9d8e7f6a5b4c_scan_001.jpg
```

**Metadata Attached**:
- `original-filename`: Original file name
- `upload-timestamp`: ISO 8601 timestamp
- `source-path`: Original directory path (relative)
- `content-type`: MIME type
- `file-size`: File size in bytes
- `upload-service`: "image-upload-microservice"
- `upload-version`: Service version

**Configuration**:
- `S3_BUCKET`: Target S3 bucket name
- `S3_PREFIX`: Object key prefix (default: "uploads/")
- `S3_REGION`: AWS region
- `S3_SERVER_SIDE_ENCRYPTION`: Encryption algorithm (AES256, aws:kms)
- `S3_STORAGE_CLASS`: Storage class (STANDARD, INTELLIGENT_TIERING)
- `MULTIPART_THRESHOLD_MB`: Size threshold for multipart uploads

### 4. SQS Notifier

**Responsibility**: Send notification messages to SQS queue

**Technology**: `boto3` SQS client

**Key Features**:
- Message batching (up to 10 messages)
- Message deduplication
- Delivery confirmation
- Message attributes support
- FIFO queue support (optional)

**Message Format**:
```json
{
  "s3_uri": "s3://bucket-name/path/to/image.jpg",
  "metadata": {
    "original_filename": "scan_001.jpg",
    "upload_timestamp": "2026-05-17T23:01:00Z",
    "source_directory": "/watched-images/batch-01",
    "file_size_bytes": 2457600,
    "content_type": "image/jpeg",
    "image_dimensions": {
      "width": 1920,
      "height": 1080
    }
  },
  "source_service": "image-upload-microservice",
  "message_version": "1.0"
}
```

**Message Attributes**:
- `ContentType`: "application/json"
- `SourceService`: "image-upload-microservice"
- `EventType`: "image.uploaded"
- `ImageFormat`: File format (e.g., "jpeg", "png")

**Configuration**:
- `SQS_QUEUE_URL`: Target SQS queue URL
- `SQS_MESSAGE_GROUP_ID`: Message group ID (for FIFO queues)
- `SQS_BATCH_SIZE`: Messages per batch (default: 10)
- `SQS_MESSAGE_RETENTION`: Expected message retention (for validation)

### 5. Upload Orchestrator

**Responsibility**: Coordinate the upload workflow

**Key Features**:
- Centralized workflow management
- Transaction-like processing (all or nothing)
- State tracking
- Error recovery
- Upload history tracking (optional)

**Workflow Steps**:

1. **Receive Upload Event**: From directory watcher
2. **Validate Image**: Call image detector
3. **Upload to S3**: Call S3 uploader
4. **Send SQS Notification**: Call SQS notifier
5. **Handle Post-Upload**: Move/archive/delete original file
6. **Log Completion**: Record successful upload

**State Management**:
- Track upload state (PENDING, UPLOADING, NOTIFYING, COMPLETED, FAILED)
- Maintain in-memory queue of pending uploads
- Prevent duplicate processing with file hash tracking

**Configuration**:
- `POST_UPLOAD_ACTION`: Action after successful upload (keep, archive, delete)
- `ARCHIVE_DIRECTORY`: Directory for archived files (if action=archive)
- `MAX_CONCURRENT_UPLOADS`: Maximum parallel uploads
- `UPLOAD_TIMEOUT_SECONDS`: Maximum time for complete workflow

## Configuration Requirements

### Environment Variables

```bash
# === AWS Configuration ===
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_access_key_here
AWS_SECRET_ACCESS_KEY=your_secret_key_here

# === Directory Watching ===
WATCH_DIRECTORY=/app/watched-images
WATCH_RECURSIVE=false
DEBOUNCE_SECONDS=2
POLLING_INTERVAL=1

# === Image Detection ===
ALLOWED_IMAGE_EXTENSIONS=jpg,jpeg,png,gif,bmp,tiff,tif,webp
MIN_IMAGE_SIZE_BYTES=1024
MAX_IMAGE_SIZE_BYTES=104857600
STRICT_VALIDATION=true

# === S3 Configuration ===
S3_BUCKET=my-images-bucket
S3_PREFIX=uploads/
S3_SERVER_SIDE_ENCRYPTION=AES256
S3_STORAGE_CLASS=STANDARD
MULTIPART_THRESHOLD_MB=5

# === SQS Configuration ===
SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/123456789012/ocr-queue
SQS_MESSAGE_GROUP_ID=
SQS_BATCH_SIZE=10

# === Post-Upload Actions ===
POST_UPLOAD_ACTION=archive
ARCHIVE_DIRECTORY=/app/processed-images

# === Application Configuration ===
LOG_LEVEL=INFO
MAX_CONCURRENT_UPLOADS=3
UPLOAD_TIMEOUT_SECONDS=300

# === Retry Configuration ===
MAX_RETRIES=3
RETRY_BACKOFF_BASE=2.0
RETRY_BACKOFF_MAX=60.0
RETRY_ON_EXCEPTIONS=ConnectionError,TimeoutError,ClientError

# === Health Check & Monitoring ===
ENABLE_HEALTH_ENDPOINT=true
HEALTH_CHECK_PORT=8080
METRICS_ENABLED=false
```

### Configuration Validation

Configuration is validated on startup using Pydantic models:

```python
class Config(BaseModel):
    # Required fields
    aws_region: str
    aws_access_key_id: str
    aws_secret_access_key: str
    watch_directory: Path
    s3_bucket: str
    sqs_queue_url: HttpUrl
    
    # Optional with defaults
    log_level: str = "INFO"
    max_retries: conint(ge=0, le=10) = 3
    
    # Validation
    @validator('watch_directory')
    def directory_must_exist(cls, v):
        if not v.exists():
            raise ValueError(f"Directory does not exist: {v}")
        return v
```

## Error Handling & Retry Strategies

### Error Categories

#### 1. Transient Errors (Retry)
- **Network Errors**: Connection timeouts, DNS failures
- **AWS Service Throttling**: Rate limit exceeded
- **Temporary S3 Issues**: 503 Service Unavailable
- **Temporary SQS Issues**: Queue temporarily unavailable

**Retry Strategy**: Exponential backoff
- Base delay: 2 seconds
- Max delay: 60 seconds
- Max retries: 3
- Jitter: ±20% randomization

#### 2. Permanent Errors (No Retry)
- **Invalid Credentials**: 403 Forbidden
- **Resource Not Found**: 404 bucket/queue not found
- **Invalid File Format**: Corrupt or unsupported image
- **Oversized Files**: Exceeds maximum size limit
- **Access Denied**: Insufficient IAM permissions

**Handling**: Log error, move to failed directory, alert

#### 3. Critical Errors (Shutdown)
- **Configuration Errors**: Missing required configuration
- **Disk Full**: No space for temporary files
- **Fatal AWS Errors**: Region mismatch, invalid configuration

**Handling**: Log critical error, graceful shutdown

### Retry Implementation

```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential_jitter,
    retry_if_exception_type
)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=2, max=60),
    retry=retry_if_exception_type((ConnectionError, Throttling)),
    reraise=True
)
def upload_to_s3(file_path: Path, bucket: str, key: str):
    # Upload logic
    pass
```

### Circuit Breaker Pattern

For AWS service failures, implement circuit breaker:
- **Closed**: Normal operation
- **Open**: After 5 consecutive failures, stop attempts for 60 seconds
- **Half-Open**: After cooldown, try one request to test recovery

### Dead Letter Queue (DLQ)

Files that fail after all retries:
- Move to `failed-uploads/` directory
- Log detailed error information
- Optionally send to separate SQS DLQ
- Alert monitoring system

### Graceful Shutdown

Handle SIGTERM and SIGINT:
1. Stop accepting new file events
2. Complete in-progress uploads
3. Flush pending SQS messages
4. Close file handles and connections
5. Log shutdown statistics

## Logging Strategy

### Structured Logging

Use `structlog` for structured JSON logging:

```json
{
  "timestamp": "2026-05-17T23:01:00.123Z",
  "level": "INFO",
  "event": "image_uploaded",
  "service": "image-upload-microservice",
  "version": "1.0.0",
  "file_path": "/watched-images/scan_001.jpg",
  "file_size": 2457600,
  "s3_key": "uploads/2026/05/17/a7f3c4e1_scan_001.jpg",
  "upload_duration_ms": 1234,
  "request_id": "abc123"
}
```

### Log Levels

| Level | Use Case |
|-------|----------|
| DEBUG | Detailed diagnostic info, file events, validation steps |
| INFO | Normal operations, successful uploads, processing metrics |
| WARNING | Retry attempts, validation failures, slow operations |
| ERROR | Failed uploads, AWS errors, exceptions |
| CRITICAL | Service failures, configuration errors, shutdown triggers |

### Key Log Events

1. **Service Lifecycle**
   - `service_started`: Service initialization complete
   - `service_stopped`: Graceful shutdown complete
   - `configuration_loaded`: Configuration validated

2. **File Processing**
   - `file_detected`: New file detected in watched directory
   - `image_validated`: Image passed validation
   - `image_validation_failed`: Image failed validation
   - `file_ignored`: File ignored (wrong type, system file)

3. **Upload Operations**
   - `upload_started`: S3 upload initiated
   - `upload_progress`: Progress update (for large files)
   - `upload_completed`: S3 upload successful
   - `upload_failed`: S3 upload failed

4. **Notifications**
   - `notification_sent`: SQS message sent successfully
   - `notification_failed`: SQS message send failed

5. **Error Events**
   - `retry_attempted`: Retry initiated after failure
   - `max_retries_exceeded`: All retries exhausted
   - `circuit_breaker_opened`: Circuit breaker triggered

### Log Destinations

- **Console/STDOUT**: Primary output for Docker logs
- **File**: Optional local file logging (for debugging)
- **CloudWatch Logs**: AWS native log aggregation (production)
- **ELK Stack**: Optional centralized logging
- **Datadog/New Relic**: Optional APM integration

### Performance Logging

Track key metrics:
- Upload duration (by file size buckets)
- Queue depth (pending uploads)
- Success/failure rates
- Retry rates
- File processing throughput (files/minute)

## SQS Message Format Specification

### Standard Message Format

```json
{
  "s3_uri": "s3://my-images-bucket/uploads/2026/05/17/a7f3c4e1-2b45-4f89-b123-9d8e7f6a5b4c_scan_001.jpg",
  "metadata": {
    "original_filename": "scan_001.jpg",
    "upload_timestamp": "2026-05-17T23:01:00.123Z",
    "source_directory": "/watched-images/batch-01",
    "file_size_bytes": 2457600,
    "content_type": "image/jpeg",
    "image_dimensions": {
      "width": 1920,
      "height": 1080
    },
    "file_hash": {
      "algorithm": "sha256",
      "value": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    }
  },
  "source_service": "image-upload-microservice",
  "message_version": "1.0",
  "processing_hints": {
    "priority": "normal",
    "language": "pl"
  }
}
```

### Field Definitions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `s3_uri` | string | Yes | Full S3 URI to uploaded image |
| `metadata` | object | Yes | Image metadata object |
| `metadata.original_filename` | string | Yes | Original filename before upload |
| `metadata.upload_timestamp` | string | Yes | ISO 8601 timestamp of upload |
| `metadata.source_directory` | string | No | Original directory path |
| `metadata.file_size_bytes` | integer | Yes | File size in bytes |
| `metadata.content_type` | string | Yes | MIME type |
| `metadata.image_dimensions` | object | No | Image width and height |
| `metadata.file_hash` | object | No | File hash for deduplication |
| `source_service` | string | Yes | Service identifier |
| `message_version` | string | Yes | Message schema version |
| `processing_hints` | object | No | Optional processing hints |

### Alternative Field Names (for compatibility)

The OCR microservice accepts multiple field name variants:
- `s3_uri`, `s3Uri`, `imageUri`, `image_uri`

This service will use `s3_uri` as the standard field name.

### Message Attributes

SQS message attributes (metadata separate from body):

```python
MessageAttributes={
    'ContentType': {'StringValue': 'application/json', 'DataType': 'String'},
    'SourceService': {'StringValue': 'image-upload-microservice', 'DataType': 'String'},
    'EventType': {'StringValue': 'image.uploaded', 'DataType': 'String'},
    'ImageFormat': {'StringValue': 'jpeg', 'DataType': 'String'},
    'FileSize': {'StringValue': '2457600', 'DataType': 'Number'},
    'Timestamp': {'StringValue': '2026-05-17T23:01:00Z', 'DataType': 'String'}
}
```

## Docker Containerization

### Dockerfile

```dockerfile
# Multi-stage build for smaller image size
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Create virtualenv
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Final stage
FROM python:3.11-slim

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Copy virtualenv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create app user (security best practice)
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/watched-images /app/processed-images && \
    chown -R appuser:appuser /app

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=appuser:appuser src/ ./src/

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Run the application
CMD ["python", "-m", "src.main"]
```

### Docker Compose Configuration

```yaml
version: '3.8'

services:
  image-upload-microservice:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: image-upload-microservice
    restart: unless-stopped
    
    environment:
      # AWS Configuration
      - AWS_REGION=${AWS_REGION}
      - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
      - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
      
      # Directory Watching
      - WATCH_DIRECTORY=/app/watched-images
      - WATCH_RECURSIVE=${WATCH_RECURSIVE:-false}
      - DEBOUNCE_SECONDS=${DEBOUNCE_SECONDS:-2}
      
      # Image Detection
      - ALLOWED_IMAGE_EXTENSIONS=${ALLOWED_IMAGE_EXTENSIONS:-jpg,jpeg,png,gif,bmp,tiff}
      - MIN_IMAGE_SIZE_BYTES=${MIN_IMAGE_SIZE_BYTES:-1024}
      - MAX_IMAGE_SIZE_BYTES=${MAX_IMAGE_SIZE_BYTES:-104857600}
      
      # S3 Configuration
      - S3_BUCKET=${S3_BUCKET}
      - S3_PREFIX=${S3_PREFIX:-uploads/}
      - S3_SERVER_SIDE_ENCRYPTION=${S3_SERVER_SIDE_ENCRYPTION:-AES256}
      
      # SQS Configuration
      - SQS_QUEUE_URL=${SQS_QUEUE_URL}
      - SQS_BATCH_SIZE=${SQS_BATCH_SIZE:-10}
      
      # Application Configuration
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
      - POST_UPLOAD_ACTION=${POST_UPLOAD_ACTION:-archive}
      - ARCHIVE_DIRECTORY=/app/processed-images
      - MAX_CONCURRENT_UPLOADS=${MAX_CONCURRENT_UPLOADS:-3}
      
      # Retry Configuration
      - MAX_RETRIES=${MAX_RETRIES:-3}
      - RETRY_BACKOFF_BASE=${RETRY_BACKOFF_BASE:-2.0}
      - RETRY_BACKOFF_MAX=${RETRY_BACKOFF_MAX:-60.0}
    
    volumes:
      # Mount watched directory from host
      - ${HOST_WATCH_DIRECTORY:-./watched-images}:/app/watched-images
      # Mount archive directory
      - ${HOST_ARCHIVE_DIRECTORY:-./processed-images}:/app/processed-images
      # Optional: mount logs directory
      - ./logs:/app/logs
    
    # Resource limits
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M
    
    # Logging configuration
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
    
    # Health check
    healthcheck:
      test: ["CMD", "python", "-c", "import sys; sys.exit(0)"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s

volumes:
  watched-images:
    driver: local
  processed-images:
    driver: local
```

### Container Optimization

1. **Multi-stage builds**: Smaller final image (remove build tools)
2. **Non-root user**: Security best practice
3. **Layer caching**: Dependencies before application code
4. **Minimal base image**: `python:3.11-slim` instead of full image
5. **Health checks**: Container orchestration compatibility
6. **Resource limits**: Prevent resource exhaustion

### Volume Management

- **Watched Images**: Host directory mounted as read-only (optional)
- **Processed Images**: Persistent volume for archived files
- **Logs**: Optional external log storage

## AWS IAM Permissions

### Required IAM Policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "S3UploadPermissions",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:PutObjectAcl",
        "s3:PutObjectTagging"
      ],
      "Resource": "arn:aws:s3:::YOUR_BUCKET_NAME/uploads/*"
    },
    {
      "Sid": "S3BucketAccess",
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket",
        "s3:GetBucketLocation"
      ],
      "Resource": "arn:aws:s3:::YOUR_BUCKET_NAME"
    },
    {
      "Sid": "SQSPublishPermissions",
      "Effect": "Allow",
      "Action": [
        "sqs:SendMessage",
        "sqs:GetQueueAttributes",
        "sqs:GetQueueUrl"
      ],
      "Resource": "arn:aws:sqs:REGION:ACCOUNT_ID:QUEUE_NAME"
    },
    {
      "Sid": "KMSEncryptionPermissions",
      "Effect": "Allow",
      "Action": [
        "kms:Decrypt",
        "kms:GenerateDataKey"
      ],
      "Resource": "arn:aws:kms:REGION:ACCOUNT_ID:key/KEY_ID",
      "Condition": {
        "StringEquals": {
          "kms:ViaService": [
            "s3.REGION.amazonaws.com",
            "sqs.REGION.amazonaws.com"
          ]
        }
      }
    }
  ]
}
```

## Deployment Considerations

### Local Development

```bash
# 1. Clone repository
cd /home/user/korzen/image-upload-microservice

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your credentials

# 5. Create watch directory
mkdir -p watched-images processed-images

# 6. Run service
python -m src.main
```

### Docker Deployment

```bash
# 1. Build image
docker build -t image-upload-microservice:latest .

# 2. Run with Docker Compose
docker-compose up -d

# 3. View logs
docker-compose logs -f image-upload-microservice

# 4. Stop service
docker-compose down
```

### Production Deployment

**AWS ECS (Elastic Container Service)**:
- Task definition with environment variables from Secrets Manager
- Auto-scaling based on queue depth
- EFS mount for shared file system (if needed)
- CloudWatch Logs integration

**Kubernetes**:
- Deployment with ConfigMaps and Secrets
- Persistent Volume Claims for watched directory
- Horizontal Pod Autoscaling
- Prometheus metrics export

**AWS Lambda (Alternative)**:
- Event-driven with S3 event notifications
- Lambda function triggered on S3 PUT
- SNS/SQS fan-out pattern
- Lower operational overhead

### Scaling Considerations

1. **Horizontal Scaling**: Multiple instances watching same directory
   - Use file locking or distributed coordination (Redis/DynamoDB)
   - Assign different subdirectories to different instances
   - Use SQS FIFO with deduplication

2. **Vertical Scaling**: Increase container resources
   - More memory for larger images
   - More CPU for parallel uploads

3. **Batch Processing**: Process multiple files concurrently
   - Thread pool for parallel uploads
   - Async I/O for better throughput

## Monitoring & Observability

### Health Checks

**Liveness Probe**: Is the service running?
- Check main process is alive
- Endpoint: `http://localhost:8080/health/live`

**Readiness Probe**: Can the service handle requests?
- Check AWS connectivity (S3, SQS)
- Check watched directory is accessible
- Endpoint: `http://localhost:8080/health/ready`

### Metrics

**Key Performance Indicators (KPIs)**:
- Files processed per minute
- Average upload duration
- Success rate (uploads / attempts)
- Error rate by type
- Queue depth (pending uploads)
- Disk usage (watched directory)

**Custom Metrics** (CloudWatch/Prometheus):
```
image_upload_files_detected_total
image_upload_files_validated_total
image_upload_files_uploaded_total
image_upload_files_failed_total
image_upload_duration_seconds
image_upload_file_size_bytes
image_upload_queue_depth
```

### Alerting

**Critical Alerts**:
- Service down for > 5 minutes
- Error rate > 10% for > 10 minutes
- Disk usage > 90%
- AWS credentials expired
- SQS queue unavailable

**Warning Alerts**:
- Upload duration > 60 seconds
- Retry rate > 5%
- Queue depth > 100 files

### Tracing

Optional AWS X-Ray integration for distributed tracing:
- Trace file from detection → upload → notification
- Visualize latency breakdown
- Identify bottlenecks

## Security Considerations

### Data Security

1. **Encryption in Transit**:
   - TLS/SSL for all AWS communication
   - HTTPS for S3 uploads

2. **Encryption at Rest**:
   - S3 server-side encryption (AES256 or KMS)
   - Encrypted EBS volumes for temporary storage

3. **Access Control**:
   - Least privilege IAM policies
   - No inline credentials in code
   - Environment variables or AWS Secrets Manager

### Network Security

1. **VPC Endpoints**: S3 and SQS access without internet gateway
2. **Security Groups**: Restrict inbound/outbound traffic
3. **Private Subnets**: Deploy in private subnets (no public IP)

### Application Security

1. **Input Validation**: Strict image file validation
2. **Path Traversal Prevention**: Sanitize file paths
3. **Resource Limits**: Prevent DoS (max file size, rate limiting)
4. **Non-root Container**: Run as unprivileged user

### Secrets Management

**Best Practices**:
- AWS Secrets Manager for credentials
- IAM roles for EC2/ECS (no static keys)
- Environment variable injection at runtime
- Rotate credentials regularly

## Testing Strategy

### Unit Tests

- Image detector validation logic
- S3 upload path generation
- SQS message formatting
- Configuration validation
- Retry logic

### Integration Tests

- S3 upload with test bucket
- SQS message publishing with test queue
- Watchdog event handling
- End-to-end workflow

### Test Fixtures

```
tests/fixtures/
├── sample_images/
│   ├── valid_image.jpg
│   ├── valid_image.png
│   ├── corrupt_image.jpg
│   ├── large_image.tiff
│   └── not_an_image.txt
└── mock_responses/
    ├── s3_upload_success.json
    └── sqs_send_success.json
```

### Performance Tests

- Upload 1000 files concurrently
- Large file handling (>50MB)
- Memory usage under load
- Throughput benchmarks

## Migration from Manual Process

### Migration Plan

If migrating from manual upload process:

1. **Phase 1: Parallel Run**
   - Run new service alongside existing process
   - Compare outputs for consistency
   - Monitor for issues

2. **Phase 2: Gradual Cutover**
   - Route subset of files to new service
   - Gradually increase percentage
   - Keep manual process as fallback

3. **Phase 3: Full Cutover**
   - 100% traffic to new service
   - Decommission manual process
   - Document new workflow

### Rollback Plan

If issues arise:
1. Stop new service
2. Resume manual process
3. Investigate failures
4. Fix and redeploy

## Future Enhancements

### Potential Features

1. **Duplicate Detection**:
   - Calculate file hashes
   - Check for existing S3 objects
   - Skip or deduplicate uploads

2. **Image Preprocessing**:
   - Auto-rotation based on EXIF
   - Resolution normalization
   - Format conversion (e.g., HEIC → JPEG)
   - Quality optimization

3. **Batch Uploads**:
   - Combine multiple small files
   - Create ZIP archives
   - Reduce S3 API calls

4. **Priority Queue**:
   - Prioritize certain directories
   - VIP file processing
   - Configurable priority rules

5. **Web Dashboard**:
   - Real-time upload status
   - Historical statistics
   - Manual file reprocessing
   - Configuration management

6. **Event Webhooks**:
   - HTTP callbacks on upload completion
   - Slack/Teams notifications
   - Custom integrations

7. **AI-Powered Validation**:
   - Content-based filtering
   - Automatic categorization
   - Document type detection

## Changelog

### Version 1.0.0 (Initial Release)
- Directory monitoring with watchdog
- Multi-format image detection
- S3 upload with multipart support
- SQS notification publishing
- Comprehensive error handling and retry logic
- Docker containerization
- Structured logging
- Configuration validation
- Health checks

## Support & Maintenance

### Troubleshooting

**Service not starting**:
- Check environment variables
- Verify AWS credentials
- Ensure watched directory exists
- Check Docker logs

**Files not being detected**:
- Verify directory path is correct
- Check file permissions
- Ensure format is in allowed list
- Review DEBUG logs

**Uploads failing**:
- Verify S3 bucket exists and is accessible
- Check IAM permissions
- Review network connectivity
- Check file size limits

**SQS messages not appearing**:
- Verify queue URL is correct
- Check SQS permissions
- Review message format
- Check queue configuration

### Maintenance Tasks

**Regular**:
- Monitor disk usage in watched directory
- Review error logs for patterns
- Check AWS service quotas
- Rotate logs

**Periodic**:
- Update Python dependencies
- Review and update IAM policies
- Test disaster recovery procedures
- Performance benchmarking

**As Needed**:
- Scale resources based on load
- Adjust retry parameters
- Update image format support
- Implement new features

## Appendix

### Related Documentation

- OCR Microservice README: [`../ocr-microservice/README.md`](../ocr-microservice/README.md)
- AWS S3 Documentation: https://docs.aws.amazon.com/s3/
- AWS SQS Documentation: https://docs.aws.amazon.com/sqs/
- Watchdog Library: https://python-watchdog.readthedocs.io/

### Glossary

- **Watchdog**: Python library for file system event monitoring
- **Debounce**: Delay processing to ensure file write completion
- **Circuit Breaker**: Pattern to prevent cascading failures
- **Multipart Upload**: S3 upload method for large files in chunks
- **FIFO Queue**: First-In-First-Out SQS queue with ordering guarantees
- **DLQ**: Dead Letter Queue for failed messages

### Contact

For questions, issues, or contributions:
- Repository: [Project Repository URL]
- Issue Tracker: [Issue Tracker URL]
- Maintainer: [Maintainer Contact]

---

**Document Version**: 1.0  
**Last Updated**: 2026-05-17  
**Authors**: Technical Architecture Team  
**Status**: Final for Review
