# GEDCOM Generation Microservice

The GEDCOM Generation Service is the second service in the OCR-to-GEDCOM pipeline. It consumes OCR results from the OCR Image Service, groups them by document, and generates GEDCOM files directly via LLM.

## Architecture Overview

This service is part of a three-service architecture:

1. **OCR Image Service** → Processes images and extracts text
2. **GEDCOM Generation Service** (this service) → Groups OCR results and generates GEDCOM
3. **Upload Service** → Uploads GEDCOM to S3 and hosted application

## Key Features

### Document Grouping
- **Buffers OCR results by document_id**: Groups multiple pages from the same document
- **Completion detection**: Processes when all pages received OR timeout reached
- **Page sorting**: Ensures pages are processed in correct order
- **In-memory state**: Single-instance grouping with no external dependencies

### Direct GEDCOM Generation
- **Single-step generation**: LLM generates GEDCOM directly (no intermediate JSON)
- **Full document context**: Processes entire documents for better relationship detection
- **Metadata enrichment**: Prepends document metadata to improve accuracy
- **Cross-page relationships**: Identifies same individuals across multiple pages

### Context Extraction (Carry-Forward Context)
- **Rolling document-level context**: An LLM carries forward a small, document-level summary between the pages of a single document, so later pages are interpreted with the conventions established by earlier ones
- **Input → output**: Each step takes the *current context* + the *current page* and produces the *updated context* used when generating the next page
- **Deliberately small**: Tracks only document/register-level information (active places, date range, language/terminology/layout conventions, naming conventions, continuation notes). It does **not** accumulate per-person, per-family, or per-relationship data, so the context stays bounded as pages accumulate
- **Non-breaking & fail-soft**: A context-extraction failure never blocks per-page GEDCOM generation — the prior context is simply carried forward unchanged. The feature can be disabled entirely with no effect on existing behavior
- See [`src/services/context_extractor.py`](src/services/context_extractor.py) and the prompts in [`src/prompts/context_extraction.py`](src/prompts/context_extraction.py)

### Validation & Quality
- **GEDCOM validation**: Checks syntax, structure, and references
- **Record counting**: Tracks individuals and families generated
- **Error handling**: Comprehensive logging and retry logic

## Service Flow

```
1. Receive OCR result message from SQS
2. Add to document group (buffer by document_id)
3. Check if document complete:
   - All pages received? → Process
   - Timeout reached? → Process
   - Otherwise → Wait for more pages
4. Format document with metadata header
5. Generate GEDCOM via OpenRouter LLM (per page, prepending the carried-forward context)
   - Update the rolling document-level context from the page (if context extraction is enabled)
6. Validate GEDCOM syntax
7. Upload GEDCOM to S3
8. Publish GEDCOM ready message to SQS
9. Remove document group from buffer
```

## Document Grouping Strategy

### Completion Criteria

**Strategy 1: All Pages Received (Preferred)**
- Wait until `total_pages` messages received for a `document_id`
- Ensures complete document processing
- Requires metadata to include `total_pages`

**Strategy 2: Timeout-Based (Fallback)**
- Wait for timeout (default: 5 minutes) after first page
- Process whatever pages received
- Handles cases where total pages unknown

**Strategy 3: Hybrid (Implemented)**
- Use Strategy 1 if `total_pages` known
- Fall back to Strategy 2 if timeout reached
- Best of both worlds

### State Storage

**In-Memory (Single Instance)**
- Fast, simple, no external dependencies
- Limited to single service instance

## Configuration

### Required Environment Variables

```bash
# AWS Configuration
AWS_ACCESS_KEY_ID=your_aws_access_key_id
AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key
AWS_REGION=us-east-1

# SQS Queues
OCR_RESULTS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/.../ocr-results-queue
GEDCOM_READY_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/.../gedcom-ready-queue

# S3 Storage
S3_OUTPUT_BUCKET=your-output-bucket

# OpenRouter API
OPENROUTER_API_KEY=your_openrouter_api_key
```

### Optional Configuration

```bash
# Document Grouping
GROUPING_TIMEOUT_SECONDS=300        # 5 minutes
GROUPING_CHECK_INTERVAL=30          # Check timeouts every 30s
MAX_PAGES_PER_GROUP=100             # Max pages per document

# GEDCOM Settings
GEDCOM_VERSION=5.5.1
ENABLE_GEDCOM_VALIDATION=true
STRICT_VALIDATION=false

# OpenRouter Settings
OPENROUTER_MODEL=google/gemini-flash-1.5
OPENROUTER_TIMEOUT=300

# Context Extraction (carry-forward document-level context between pages)
# Context extraction is always enabled
CONTEXT_EXTRACTION_MODEL=google/gemini-flash-1.5  # Defaults to OPENROUTER_MODEL when unset
MAX_CONTEXT_CHARS=4000                       # Hard cap on the carried-forward context length

# Logging
LOG_LEVEL=INFO
```

#### Context Extraction Variables

Context extraction is always enabled and cannot be disabled.

| Variable | Default | Description |
|----------|---------|-------------|
| `CONTEXT_EXTRACTION_MODEL` | value of `OPENROUTER_MODEL` (`google/gemini-flash-1.5`) | Intended model for context extraction. **Currently informational / future-proofing**: the extractor shares the single `OpenRouterClient` (and thus `OPENROUTER_MODEL`). To use a dedicated model, construct a second `OpenRouterClient` with `model=CONTEXT_EXTRACTION_MODEL` and pass it to `ContextExtractor` (see [`CONTEXT_EXTRACTOR_DESIGN.md`](CONTEXT_EXTRACTOR_DESIGN.md) §6.2). It is surfaced in `Config.to_dict()` for observability. |
| `MAX_CONTEXT_CHARS` | `4000` | Hard cap on the carried-forward context length. Kept small because the context is document-level only; if the LLM returns more, the most-recent tail is retained. |

## Input Message Format

The service expects OCR result messages from the OCR Image Service:

```json
{
  "message_id": "uuid-v4",
  "timestamp": "2026-05-23T15:30:00Z",
  "source_image": {
    "s3_uri": "s3://bucket/documents/book-123/page-005.jpg",
    "filename": "page-005.jpg"
  },
  "metadata": {
    "document_id": "book-123",
    "page_number": 5,
    "total_pages": 50,
    "document_title": "Bolechowice Parish Baptisms 1820-1850",
    "date_range": "1820-1850",
    "location": "Bolechowice",
    "record_type": "baptism",
    "language": "latin"
  },
  "ocr_result": {
    "markdown_text": "# Page 5\n\nBaptismus...",
    "s3_uri": "s3://bucket/ocr-results/book-123/page-005.md"
  }
}
```

## Output Message Format

The service publishes GEDCOM ready messages:

```json
{
  "message_id": "uuid-v4",
  "timestamp": "2026-05-23T15:35:00Z",
  "document_metadata": {
    "document_id": "book-123",
    "document_title": "Bolechowice Parish Baptisms 1820-1850",
    "total_pages": 50,
    "pages_processed": 50,
    "completion_reason": "all_pages_received"
  },
  "gedcom_data": {
    "content": "0 HEAD\n1 SOUR OCR-to-GEDCOM...",
    "filename": "book-123.ged",
    "s3_uri": "s3://bucket/gedcom-files/book-123.ged",
    "validation_status": "valid",
    "individual_count": 150,
    "family_count": 75
  },
  "source_ocr_uris": [
    "s3://bucket/ocr-results/book-123/page-001.md",
    "s3://bucket/ocr-results/book-123/page-002.md"
  ],
  "metadata": {
    "processing_time_ms": 45000,
    "openrouter_model": "google/gemini-flash-1.5"
  }
}
```

## Running Locally

### Prerequisites
- Python 3.11+
- AWS credentials with SQS and S3 access
- OpenRouter API key
### Setup

1. **Clone and navigate to directory**:
   ```bash
   cd gedcom-generation-microservice
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
   # Edit .env with your credentials
   ```

5. **Run the service**:
   ```bash
   python -m src.main
   ```

## Running with Docker

```bash
# Build image
docker build -t gedcom-generation-service .

# Run container
docker run --env-file .env gedcom-generation-service
```

### Using Docker Compose

```bash
# Start service with docker-compose
docker-compose up -d

# View logs
docker-compose logs -f gedcom-generation

# Stop service
docker-compose down
```

## Deployment

### AWS ECS Deployment

**Task Definition**:
- CPU: 4 vCPU
- Memory: 8 GB
- Reason: Needs to buffer multiple messages and format large documents

**Service Configuration**:
- Desired count: 1-3 tasks
- Auto-scaling: Based on SQS queue depth
- Target: 1 task per 5 active document groups

**Environment**:
- Use AWS Secrets Manager for API keys
- Use Parameter Store for configuration
- Enable CloudWatch logging

### Scaling Considerations

**In-Memory (Single Instance)**:
- Simple, fast, no external dependencies
- Limited to one service instance
- Suitable for low-volume processing

## Monitoring

### Key Metrics

- **Document groups active**: Number of documents being buffered
- **Documents completed**: Rate of document processing
- **Timeout rate**: Percentage of documents timing out
- **GEDCOM validation failures**: Rate of invalid GEDCOM generation
- **Processing time**: Time to generate GEDCOM per document
- **SQS queue depth**: Backlog of OCR results

### Logging

The service logs:
- Document grouping events (new document, page added, completion)
- GEDCOM generation progress
- Validation results
- Upload status
- Errors and warnings

Log level can be configured via `LOG_LEVEL` environment variable.

## Troubleshooting

### Documents Not Processing

**Check**:
1. Are OCR result messages arriving? (Check SQS queue)
2. Is `document_id` present in metadata?
3. Is timeout too short? (Increase `GROUPING_TIMEOUT_SECONDS`)
4. Check logs for errors

### GEDCOM Validation Failures

**Common Issues**:
- Missing header or trailer
- Duplicate IDs
- Undefined ID references
- Invalid line format

**Solutions**:
- Review LLM prompt in [`src/prompts/gedcom_generation.py`](src/prompts/gedcom_generation.py)
- Adjust model parameters
- Enable strict validation for debugging

### High Memory Usage

**Causes**:
- Too many active document groups
- Large documents (many pages)
- Memory leak

**Solutions**:
- Reduce `GROUPING_TIMEOUT_SECONDS`
- Reduce `MAX_PAGES_PER_GROUP`
- Increase container memory

## Development

### Project Structure

```
gedcom-generation-microservice/
├── src/
│   ├── __init__.py
│   ├── main.py                      # Main service entry point
│   ├── config.py                    # Configuration management
│   ├── services/
│   │   ├── sqs_consumer.py          # SQS message consumer
│   │   ├── sqs_publisher.py         # SQS message publisher
│   │   ├── s3_handler.py            # S3 upload handler
│   │   ├── document_grouper.py      # Document grouping logic
│   │   ├── metadata_formatter.py    # Format metadata for LLM
│   │   ├── gedcom_generator.py      # GEDCOM generation orchestration
│   │   ├── gedcom_validator.py      # GEDCOM validation
│   │   ├── context_extractor.py     # Carry-forward document-level context
│   │   └── openrouter_client.py     # OpenRouter API client
│   ├── prompts/
│   │   ├── gedcom_generation.py     # LLM prompts
│   │   └── context_extraction.py    # Context carry-forward prompts
│   └── utils/
│       └── logger.py                # Logging utilities
├── .env.example                     # Example environment variables
├── requirements.txt                 # Python dependencies
├── Dockerfile                       # Docker image definition
├── docker-compose.yml               # Docker Compose configuration
└── README.md                        # This file
```

### Adding New Features

1. **Custom validation rules**: Extend [`GedcomValidator`](src/services/gedcom_validator.py)
2. **Alternative grouping strategies**: Modify [`DocumentGrouper`](src/services/document_grouper.py)
3. **Enhanced prompts**: Update [`gedcom_generation.py`](src/prompts/gedcom_generation.py)
4. **Additional metadata**: Extend [`MetadataFormatter`](src/services/metadata_formatter.py)

## Related Services

- **OCR Image Service**: Upstream service that provides OCR results
- **Upload Service**: Downstream service that uploads GEDCOM files
- **Architecture Documentation**: See [`../ocr-microservice/ARCHITECTURE_SPLIT_REVISED.md`](../ocr-microservice/ARCHITECTURE_SPLIT_REVISED.md)

## License

[Your License Here]

## Support

For issues or questions, please contact [Your Contact Info]
