# GEDCOM Upload Microservice

The **GEDCOM Upload Microservice** is the third and final service in the OCR-to-GEDCOM pipeline. It handles uploading generated GEDCOM files to both S3 storage and the hosted genealogy application.

## Overview

This microservice is part of a three-service architecture that processes genealogical records:

1. **OCR Image Service** - Extracts text from images
2. **GEDCOM Generation Service** - Generates GEDCOM files from OCR results
3. **GEDCOM Upload Service** (this service) - Uploads GEDCOM files to storage and application

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    GEDCOM Upload Service                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  SQS: gedcom-ready-queue                                    │
│         │                                                    │
│         ▼                                                    │
│  ┌──────────────────┐                                       │
│  │  SQS Consumer    │  Receive GEDCOM ready messages        │
│  └──────────────────┘                                       │
│         │                                                    │
│         ▼                                                    │
│  ┌──────────────────┐                                       │
│  │  S3 Handler      │  Upload to S3 final location          │
│  └──────────────────┘                                       │
│         │                                                    │
│         ▼                                                    │
│  ┌──────────────────┐                                       │
│  │ App Uploader     │  Upload to hosted application         │
│  └──────────────────┘                                       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Features

- **Dual Upload Destinations**: Uploads GEDCOM files to both S3 and hosted application
- **Reliable Processing**: Retry logic with configurable attempts and delays
- **Graceful Shutdown**: Handles termination signals cleanly
- **Optional Application Upload**: Can disable application upload via configuration
- **Auto-Parse**: Optionally triggers parsing after upload to application
- **Comprehensive Logging**: Detailed logging for monitoring and debugging
- **Error Handling**: Robust error handling with detailed error messages

## Message Processing Flow

1. **Receive Message**: Poll SQS queue for GEDCOM ready messages
2. **Parse Message**: Extract GEDCOM content and metadata
3. **Upload to S3**: Store GEDCOM in final S3 location (organized by document_id)
4. **Upload to Application**: POST GEDCOM to hosted application API
5. **Trigger Parse**: Optionally trigger parsing in the application
6. **Delete Message**: Remove message from queue after successful processing

## Directory Structure

```
gedcom-upload-microservice/
├── src/
│   ├── __init__.py
│   ├── main.py                      # Main entry point and processing loop
│   ├── config.py                    # Configuration management
│   ├── services/
│   │   ├── __init__.py
│   │   ├── sqs_consumer.py          # SQS message consumption
│   │   ├── s3_handler.py            # S3 upload operations
│   │   └── application_uploader.py  # Application API integration
│   └── utils/
│       ├── __init__.py
│       └── logger.py                # Logging utilities
├── .env.example                     # Example environment variables
├── .gitignore                       # Git ignore rules
├── .dockerignore                    # Docker ignore rules
├── requirements.txt                 # Python dependencies
├── Dockerfile                       # Docker image definition
├── docker-compose.yml               # Docker Compose configuration
└── README.md                        # This file
```

## Environment Variables

### AWS Configuration

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `AWS_REGION` | AWS region | Yes | `us-east-1` |
| `AWS_ACCESS_KEY_ID` | AWS access key | Yes* | - |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key | Yes* | - |

*Not required if using IAM roles (e.g., in ECS)

### SQS Configuration

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `GEDCOM_READY_QUEUE_URL` | SQS queue URL for GEDCOM ready messages | Yes | - |
| `SQS_MAX_MESSAGES` | Max messages per poll | No | `1` |
| `SQS_WAIT_TIME_SECONDS` | Long polling wait time | No | `20` |
| `SQS_VISIBILITY_TIMEOUT` | Message visibility timeout | No | `300` |

### S3 Configuration

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `S3_OUTPUT_BUCKET` | S3 bucket for GEDCOM files | Yes | - |
| `S3_OUTPUT_PREFIX` | S3 prefix for GEDCOM files | No | `gedcom-files/` |

### Application Upload Configuration

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `APP_UPLOAD_ENABLED` | Enable application upload | No | `true` |
| `APP_URL` | Hosted application base URL | Yes* | - |
| `APP_API_KEY` | API key for authentication | No | - |
| `APP_UPLOAD_TIMEOUT` | Upload request timeout (seconds) | No | `30` |
| `APP_PARSE_TIMEOUT` | Parse request timeout (seconds) | No | `300` |
| `APP_AUTO_PARSE` | Auto-trigger parsing after upload | No | `true` |

*Required if `APP_UPLOAD_ENABLED=true`

### Retry Configuration

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `MAX_RETRIES` | Maximum retry attempts | No | `3` |
| `RETRY_DELAY_SECONDS` | Delay between retries | No | `5` |

### Other Configuration

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `TEMP_DIR` | Temporary directory for file processing | No | `/tmp/gedcom-upload` |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | No | `INFO` |
| `SHUTDOWN_GRACE_PERIOD` | Graceful shutdown wait time (seconds) | No | `30` |

## Input Message Format

The service expects messages in the following format from the GEDCOM Generation Service:

```json
{
  "message_id": "uuid-v4",
  "timestamp": "2026-05-23T15:35:00Z",
  "document_metadata": {
    "document_id": "book-123",
    "document_title": "Bolechowice Parish Baptisms 1820-1850",
    "date_range": "1820-1850",
    "location": "Bolechowice",
    "total_pages": 50,
    "pages_processed": 50
  },
  "gedcom_data": {
    "content": "0 HEAD\n1 SOUR OCR-to-GEDCOM...",
    "filename": "book-123.ged",
    "record_counts": {
      "individuals": 150,
      "families": 45,
      "sources": 1
    },
    "validation_status": "valid"
  },
  "source_ocr_uris": [
    "s3://bucket/ocr-results/book-123/page-001.md",
    "s3://bucket/ocr-results/book-123/page-002.md"
  ],
  "metadata": {
    "processing_time_ms": 45000,
    "openrouter_model": "google/gemini-3-flash-preview",
    "total_tokens": 25000
  }
}
```

## Upload Destinations

### 1. S3 Storage

GEDCOM files are uploaded to S3 with the following structure:

```
s3://{S3_OUTPUT_BUCKET}/{S3_OUTPUT_PREFIX}{document_id}/{filename}
```

Example:
```
s3://my-gedcom-bucket/gedcom-files/book-123/book-123.ged
```

### 2. Hosted Application

GEDCOM files are uploaded to the hosted application via HTTP API:

**Upload Endpoint**: `POST {APP_URL}/upload`
- Multipart form data with GEDCOM file
- Returns `file_id` for tracking

**Parse Endpoint**: `POST {APP_URL}/parse/{file_id}` (optional)
- Triggers parsing of uploaded GEDCOM
- Returns parsing statistics

## Running Locally

### Prerequisites

- Python 3.11+
- AWS credentials configured
- Access to SQS queue and S3 bucket

### Setup

1. **Clone the repository**:
   ```bash
   cd gedcom-upload-microservice
   ```

2. **Create virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Run the service**:
   ```bash
   python -m src.main
   ```

## Running with Docker

### Build and Run

```bash
# Build the image
docker build -t gedcom-upload-microservice .

# Run with environment file
docker run --env-file .env gedcom-upload-microservice
```

### Using Docker Compose

```bash
# Start the service
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the service
docker-compose down
```

## Deployment

### AWS ECS Deployment

1. **Build and push Docker image**:
   ```bash
   docker build -t gedcom-upload-microservice .
   docker tag gedcom-upload-microservice:latest {ECR_REPO}:latest
   docker push {ECR_REPO}:latest
   ```

2. **Create ECS Task Definition**:
   - Use the Docker image from ECR
   - Configure environment variables
   - Set resource limits (0.5 vCPU, 1 GB RAM recommended)
   - Use IAM role for AWS credentials

3. **Create ECS Service**:
   - Use Fargate or EC2 launch type
   - Configure auto-scaling (min: 1, max: 3)
   - Set up CloudWatch logging

### Resource Requirements

- **CPU**: 0.5 vCPU (minimum)
- **Memory**: 1 GB RAM (minimum)
- **Storage**: Minimal (temporary files only)

### Scaling Strategy

- **Metric**: SQS queue depth
- **Target**: < 10 messages in queue
- **Scale up**: When queue depth > 20
- **Scale down**: When queue depth < 5
- **Min tasks**: 1
- **Max tasks**: 3

## Monitoring

### Key Metrics

- **Messages Processed**: Count of successfully processed messages
- **Upload Success Rate**: Percentage of successful uploads
- **Processing Time**: Time to process each message
- **Error Rate**: Percentage of failed messages
- **Queue Depth**: Number of messages in SQS queue

### CloudWatch Logs

The service logs to stdout/stderr, which can be captured by CloudWatch:

- **Log Group**: `/ecs/gedcom-upload-microservice`
- **Log Level**: Configurable via `LOG_LEVEL` environment variable

### Health Checks

Docker health check runs every 30 seconds:
```bash
python -c "import sys; sys.exit(0)"
```

## Error Handling

### Retry Logic

- Failed messages are retried up to `MAX_RETRIES` times
- Delay between retries: `RETRY_DELAY_SECONDS`
- Messages remain in SQS queue until successfully processed or max retries exceeded

### Error Scenarios

1. **S3 Upload Failure**: Message is retried, logged as error
2. **Application Upload Failure**: Logged as warning, does not fail entire process
3. **Invalid Message Format**: Logged as error, message is not deleted
4. **Network Errors**: Retried with exponential backoff

## Graceful Shutdown

The service handles `SIGINT` and `SIGTERM` signals:

1. Stop polling for new messages
2. Complete processing of current message
3. Wait for `SHUTDOWN_GRACE_PERIOD` seconds
4. Exit cleanly

## Development

### Code Structure

- **[`main.py`](src/main.py)**: Main entry point and processing loop
- **[`config.py`](src/config.py)**: Configuration management
- **[`sqs_consumer.py`](src/services/sqs_consumer.py)**: SQS message consumption
- **[`s3_handler.py`](src/services/s3_handler.py)**: S3 upload operations
- **[`application_uploader.py`](src/services/application_uploader.py)**: Application API integration
- **[`logger.py`](src/utils/logger.py)**: Logging utilities

### Adding Features

1. **New Upload Destination**: Add new uploader class in `services/`
2. **Custom Validation**: Add validation logic in message processing
3. **Metrics Collection**: Add metrics collection in processing loop

## Troubleshooting

### Common Issues

**Issue**: Messages not being received
- Check SQS queue URL is correct
- Verify AWS credentials have SQS permissions
- Check queue has messages

**Issue**: S3 upload fails
- Verify S3 bucket exists and is accessible
- Check AWS credentials have S3 write permissions
- Verify bucket region matches AWS_REGION

**Issue**: Application upload fails
- Check APP_URL is correct and accessible
- Verify API key if authentication is required
- Check application is running and healthy

### Debug Mode

Enable debug logging:
```bash
export LOG_LEVEL=DEBUG
python -m src.main
```

## Related Services

- **[OCR Image Microservice](../ocr-image-microservice/)**: Extracts text from images
- **[GEDCOM Generation Microservice](../gedcom-generation-microservice/)**: Generates GEDCOM files
- **[Architecture Documentation](../ocr-microservice/ARCHITECTURE_SPLIT_REVISED.md)**: Complete system architecture

## License

This microservice is part of the Korzen genealogy project.

## Support

For issues or questions, please refer to the main project documentation or create an issue in the repository.
