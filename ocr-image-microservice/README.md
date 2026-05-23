# OCR Image Microservice

The OCR Image Service is the first component in the three-service OCR pipeline. It handles image processing and OCR text extraction from historical church records.

## Overview

This microservice:
- Consumes image upload notifications from SQS
- Downloads images from S3
- Extracts metadata from S3 paths and object tags
- Performs OCR using Datalab SDK
- Uploads OCR results (markdown) to S3
- Publishes OCR results with metadata to the next service

## Architecture

This service is part of a three-service architecture:

```
┌─────────────────────────┐
│  OCR Image Service      │  ← This Service
│  - Download image       │
│  - Perform OCR          │
│  - Upload markdown      │
│  - Publish with metadata│
└─────────────────────────┘
           │
           ▼
   SQS: ocr-results-queue
           │
           ▼
┌─────────────────────────────────────┐
│  GEDCOM Generation Service          │
│  - Group by metadata (document ID)  │
│  - Sort pages                       │
│  - Prepend metadata                 │
│  - LLM → Direct GEDCOM generation   │
└─────────────────────────────────────┘
           │
           ▼
   SQS: gedcom-ready-queue
           │
           ▼
┌─────────────────────┐
│   Upload Service    │
│  - Upload to S3     │
│  - Upload to app    │
└─────────────────────┘
```

## Features

### Image Processing
- Automatic image resizing for Datalab SDK constraints (max 4800x4800)
- High-quality resampling with aspect ratio preservation
- Support for multiple image formats (JPEG, PNG, etc.)

### Metadata Extraction
- Extracts `document_id` and `page_number` from S3 path patterns
- Reads S3 object tags for additional metadata
- Supports multiple path patterns:
  - `s3://bucket/documents/{document_id}/page-{page_number}.jpg`
  - `s3://bucket/{document_id}/page-{page_number}.jpg`
  - Custom patterns with numeric page identifiers

### OCR Processing
- Uses Datalab SDK for accurate OCR
- Configurable OCR modes: `accurate`, `balanced`, `fast`
- Markdown output format
- Automatic pagination

### Message Publishing
- Publishes structured OCR results to output queue
- Includes complete metadata for document grouping
- Follows OCR Results Message format (see Architecture document)

## Environment Variables

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `AWS_ACCESS_KEY_ID` | AWS access key | `AKIAIOSFODNN7EXAMPLE` |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key | `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` |
| `AWS_REGION` | AWS region | `us-east-1` |
| `IMAGE_UPLOAD_QUEUE_URL` | Input SQS queue URL | `https://sqs.us-east-1.amazonaws.com/123456789012/image-upload-queue` |
| `OCR_RESULTS_QUEUE_URL` | Output SQS queue URL | `https://sqs.us-east-1.amazonaws.com/123456789012/ocr-results-queue` |
| `S3_INPUT_BUCKET` | S3 bucket for input images | `my-images-bucket` |
| `S3_OUTPUT_BUCKET` | S3 bucket for OCR results | `my-ocr-results-bucket` |
| `DATALAB_API_KEY` | Datalab SDK API key | `your_api_key_here` |

### Optional

| Variable | Description | Default |
|----------|-------------|---------|
| `S3_OUTPUT_PREFIX` | Prefix for OCR results in S3 | `ocr-results/` |
| `OCR_OUTPUT_FORMAT` | OCR output format | `markdown` |
| `OCR_MODE` | OCR processing mode | `accurate` |
| `OCR_PAGINATE` | Enable pagination | `true` |
| `SQS_MAX_MESSAGES` | Max messages per poll | `1` |
| `SQS_WAIT_TIME_SECONDS` | Long polling wait time | `20` |
| `SQS_VISIBILITY_TIMEOUT` | Message visibility timeout | `300` |
| `TEMP_DIR` | Temporary directory for processing | `/tmp/ocr-processing` |
| `POLL_INTERVAL_SECONDS` | Polling interval when no messages | `5` |
| `MAX_RETRIES` | Max retry attempts | `3` |
| `LOG_LEVEL` | Logging level | `INFO` |

## Installation

### Prerequisites

- Python 3.11+
- Docker (optional, for containerized deployment)
- AWS account with SQS and S3 access
- Datalab API key

### Local Development

1. **Clone the repository**
   ```bash
   cd ocr-image-microservice
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Run the service**
   ```bash
   python -m src.main
   ```

### Docker Deployment

1. **Build the image**
   ```bash
   docker build -t ocr-image-service .
   ```

2. **Run with Docker Compose**
   ```bash
   docker-compose up -d
   ```

3. **View logs**
   ```bash
   docker-compose logs -f ocr-image-service
   ```

4. **Stop the service**
   ```bash
   docker-compose down
   ```

## Message Formats

### Input Message (from Image Upload Queue)

Standard S3 Event Notification format:
```json
{
  "Records": [
    {
      "s3": {
        "bucket": {
          "name": "my-images-bucket"
        },
        "object": {
          "key": "documents/book-123/page-005.jpg"
        }
      }
    }
  ]
}
```

Or custom format:
```json
{
  "s3_uri": "s3://my-images-bucket/documents/book-123/page-005.jpg"
}
```

### Output Message (to OCR Results Queue)

```json
{
  "message_id": "uuid-v4",
  "timestamp": "2026-05-23T15:00:00Z",
  "metadata": {
    "document_id": "book-123",
    "page_number": 5,
    "total_pages": 50,
    "document_title": "Bolechowice Parish Baptisms 1820-1850",
    "date_range": "1820-1850",
    "location": "Bolechowice",
    "record_type": "baptism",
    "language": "latin",
    "source": "parish_register"
  },
  "ocr_result": {
    "markdown_text": "# Page 5\n\nBaptismus...",
    "s3_uri": "s3://my-ocr-results-bucket/ocr-results/page-005.md",
    "character_count": 1234
  },
  "source_image": {
    "s3_uri": "s3://my-images-bucket/documents/book-123/page-005.jpg",
    "filename": "page-005.jpg",
    "width": 2000,
    "height": 3000
  }
}
```

## S3 Object Tags

To provide metadata, tag S3 objects with:

| Tag Key | Description | Example |
|---------|-------------|---------|
| `document_id` | Unique document identifier | `book-123` |
| `page_number` | Page number | `5` |
| `total_pages` | Total pages in document | `50` |
| `document_title` | Document title | `Bolechowice Parish Baptisms 1820-1850` |
| `date_range` | Date range | `1820-1850` |
| `location` | Location/parish | `Bolechowice` |
| `record_type` | Record type | `baptism` |
| `language` | Document language | `latin` |
| `source` | Source type | `parish_register` |

## Error Handling

- **Image Download Failures**: Logged and message remains in queue for retry
- **OCR Processing Failures**: Logged and message remains in queue for retry
- **Upload Failures**: Logged and message remains in queue for retry
- **Visibility Timeout**: Messages become visible again after 300 seconds (configurable)
- **Dead Letter Queue**: Configure DLQ on input queue for permanent failures

## Monitoring

### Logs

The service logs to stdout with structured formatting:
```
2026-05-23 15:00:00 - src.main - INFO - [main.py:123] - Processing image: s3://bucket/image.jpg
```

### Metrics to Monitor

- Messages processed per minute
- OCR processing time
- S3 upload success rate
- Queue depth (input and output)
- Error rate

### CloudWatch Integration

Configure CloudWatch Logs for container logs:
```bash
docker-compose logs -f | aws logs put-log-events ...
```

## Scaling

### Horizontal Scaling

Run multiple instances of the service:
```bash
docker-compose up --scale ocr-image-service=3
```

Each instance will independently poll the SQS queue.

### Resource Requirements

- **CPU**: 1 vCPU per instance
- **Memory**: 2 GB RAM per instance
- **Storage**: Minimal (temporary files only)

### Performance Tuning

- Increase `SQS_MAX_MESSAGES` to process multiple images per poll
- Adjust `SQS_VISIBILITY_TIMEOUT` based on average processing time
- Use faster OCR mode (`balanced` or `fast`) for lower accuracy requirements

## Troubleshooting

### No messages being processed

1. Check SQS queue URL is correct
2. Verify AWS credentials have SQS permissions
3. Check AWS region matches queue region
4. Verify queue has messages: `aws sqs get-queue-attributes --queue-url <url> --attribute-names ApproximateNumberOfMessages`

### OCR failures

1. Verify Datalab API key is valid
2. Check image dimensions (will auto-resize if needed)
3. Verify image format is supported
4. Check Datalab SDK logs for errors

### S3 upload failures

1. Verify S3 bucket exists
2. Check AWS credentials have S3 write permissions
3. Verify bucket region matches AWS_REGION
4. Check S3 bucket policies

### High memory usage

1. Reduce `SQS_MAX_MESSAGES` to process fewer images concurrently
2. Ensure temporary files are being cleaned up
3. Check for memory leaks in image processing

## Development

### Project Structure

```
ocr-image-microservice/
├── src/
│   ├── __init__.py
│   ├── main.py                    # Main entry point
│   ├── config.py                  # Configuration management
│   ├── services/
│   │   ├── __init__.py
│   │   ├── sqs_consumer.py        # SQS message consumption
│   │   ├── s3_handler.py          # S3 download/upload
│   │   ├── ocr_processor.py       # OCR processing
│   │   ├── metadata_extractor.py  # Metadata extraction
│   │   └── sqs_publisher.py       # SQS message publishing
│   └── utils/
│       ├── __init__.py
│       └── logger.py              # Logging utilities
├── .env.example                   # Environment template
├── requirements.txt               # Python dependencies
├── Dockerfile                     # Container definition
├── docker-compose.yml             # Docker Compose config
└── README.md                      # This file
```

### Running Tests

```bash
# Unit tests
pytest tests/unit/

# Integration tests (requires AWS credentials)
pytest tests/integration/

# End-to-end tests
pytest tests/e2e/
```

### Code Style

```bash
# Format code
black src/

# Lint code
pylint src/

# Type checking
mypy src/
```

## Related Services

- **Image Upload Microservice**: Uploads images to S3 and triggers this service
- **GEDCOM Generation Service**: Consumes OCR results and generates GEDCOM files
- **Upload Service**: Uploads final GEDCOM files to hosted application

## License

[Your License Here]

## Support

For issues and questions:
- GitHub Issues: [Your Repo URL]
- Email: [Your Email]
- Documentation: See `ARCHITECTURE_SPLIT_REVISED.md` in parent directory
