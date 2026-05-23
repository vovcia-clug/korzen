# OCR Pipeline Architecture Overview

## Executive Summary

The OCR-to-GEDCOM pipeline is a distributed microservices architecture that processes historical church record images and converts them into standardized GEDCOM genealogy files. The system is split into three specialized services that communicate via AWS SQS queues.

**Key Features:**
- **Document-level processing** - Groups multiple pages for complete context
- **Direct GEDCOM generation** - LLM generates GEDCOM in a single step
- **Scalable architecture** - Each service scales independently
- **Fault-tolerant** - Retry logic and dead letter queues
- **Cost-optimized** - Processes entire documents in single API calls

---

## Table of Contents

1. [High-Level Architecture](#high-level-architecture)
2. [Service Responsibilities](#service-responsibilities)
3. [Data Flow](#data-flow)
4. [Message Formats](#message-formats)
5. [Infrastructure Components](#infrastructure-components)
6. [Scaling Considerations](#scaling-considerations)
7. [Cost Analysis](#cost-analysis)
8. [Related Documentation](#related-documentation)

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    OCR-to-GEDCOM Pipeline                            │
└─────────────────────────────────────────────────────────────────────┘

    ┌──────────────┐
    │  S3 Bucket   │
    │   (Images)   │
    └──────┬───────┘
           │ S3 Event Notification
           ▼
    ┌──────────────────────────────────────────┐
    │  SQS: image-upload-queue                 │
    └──────┬───────────────────────────────────┘
           │
           ▼
    ┌─────────────────────────────────────────────────────┐
    │  Service 1: OCR Image Service                       │
    │  ┌──────────────────────────────────────────────┐   │
    │  │ • Download image from S3                     │   │
    │  │ • Extract metadata (document_id, page_num)   │   │
    │  │ • Perform OCR (Datalab SDK)                  │   │
    │  │ • Upload markdown to S3                      │   │
    │  │ • Publish OCR result with metadata           │   │
    │  └──────────────────────────────────────────────┘   │
    └─────────────────────┬───────────────────────────────┘
                          │
                          ▼
    ┌──────────────────────────────────────────┐
    │  SQS: ocr-results-queue                  │
    └──────┬───────────────────────────────────┘
           │
           ▼
    ┌─────────────────────────────────────────────────────┐
    │  Service 2: GEDCOM Generation Service               │
    │  ┌──────────────────────────────────────────────┐   │
    │  │ • Group OCR results by document_id           │   │
    │  │ • Wait for complete document (or timeout)    │   │
    │  │ • Sort pages in order                        │   │
    │  │ • Prepend document metadata                  │   │
    │  │ • Generate GEDCOM via LLM (OpenRouter)       │   │
    │  │ • Validate GEDCOM syntax                     │   │
    │  │ • Upload GEDCOM to S3                        │   │
    │  │ • Publish GEDCOM ready message               │   │
    │  └──────────────────────────────────────────────┘   │
    │  ┌──────────────────────────────────────────────┐   │
    │  │ Optional: Redis for distributed grouping     │   │
    │  └──────────────────────────────────────────────┘   │
    └─────────────────────┬───────────────────────────────┘
                          │
                          ▼
    ┌──────────────────────────────────────────┐
    │  SQS: gedcom-ready-queue                 │
    └──────┬───────────────────────────────────┘
           │
           ▼
    ┌─────────────────────────────────────────────────────┐
    │  Service 3: GEDCOM Upload Service                   │
    │  ┌──────────────────────────────────────────────┐   │
    │  │ • Download GEDCOM from message               │   │
    │  │ • Upload to S3 final location                │   │
    │  │ • Upload to hosted application API           │   │
    │  │ • Trigger parsing (optional)                 │   │
    │  └──────────────────────────────────────────────┘   │
    └─────────────────────┬───────────────────────────────┘
                          │
                          ▼
                   ┌──────────────┐
                   │  S3 Bucket   │
                   │  (GEDCOM)    │
                   └──────────────┘
                          │
                          ▼
                   ┌──────────────┐
                   │   Hosted     │
                   │ Application  │
                   └──────────────┘
```

---

## Service Responsibilities

### Service 1: OCR Image Service

**Purpose:** Extract text from images using OCR

**Responsibilities:**
- Consume image upload notifications from SQS
- Download images from S3 input bucket
- Extract metadata from S3 paths and object tags
- Perform OCR using Datalab SDK
- Handle image resizing for API constraints
- Upload OCR results (markdown) to S3
- Publish OCR results with metadata to next queue

**Technology Stack:**
- Python 3.11+
- Datalab SDK (OCR)
- boto3 (AWS SDK)
- Pillow (image processing)

**Resource Requirements:**
- CPU: 1 vCPU
- Memory: 2 GB RAM
- Storage: Minimal (temporary files)

**Scaling Strategy:**
- Horizontal scaling based on queue depth
- Target: < 10 messages in queue
- Min: 1 instance, Max: 5 instances

**Documentation:** [`ocr-image-microservice/README.md`](ocr-image-microservice/README.md)

---

### Service 2: GEDCOM Generation Service

**Purpose:** Group OCR results and generate GEDCOM files

**Responsibilities:**
- Consume OCR results from queue
- Group messages by `document_id`
- Wait for complete document (all pages or timeout)
- Sort pages in correct order
- Format document with metadata header
- Generate GEDCOM directly via OpenRouter LLM
- Validate GEDCOM syntax and structure
- Upload GEDCOM to S3
- Publish GEDCOM ready message

**Technology Stack:**
- Python 3.11+
- OpenRouter API (LLM)
- boto3 (AWS SDK)
- Redis (optional, for distributed grouping)

**Resource Requirements:**
- CPU: 4 vCPU
- Memory: 8 GB RAM
- Storage: Minimal
- Redis: Optional for multi-instance deployment

**Scaling Strategy:**
- Horizontal scaling with Redis coordination
- Target: 1 instance per 5 active document groups
- Min: 1 instance, Max: 3 instances

**Key Innovation:**
- **Document-level processing** - Groups multiple pages for complete context
- **Direct GEDCOM generation** - Single LLM call generates complete GEDCOM
- **Metadata enrichment** - Prepends document metadata for better accuracy

**Documentation:** [`gedcom-generation-microservice/README.md`](gedcom-generation-microservice/README.md)

---

### Service 3: GEDCOM Upload Service

**Purpose:** Upload GEDCOM files to storage and application

**Responsibilities:**
- Consume GEDCOM ready messages from queue
- Upload GEDCOM to S3 final location
- Upload GEDCOM to hosted application API
- Trigger parsing in application (optional)
- Handle upload retries and errors

**Technology Stack:**
- Python 3.11+
- boto3 (AWS SDK)
- requests (HTTP client)

**Resource Requirements:**
- CPU: 0.5 vCPU
- Memory: 1 GB RAM
- Storage: Minimal

**Scaling Strategy:**
- Horizontal scaling based on queue depth
- Target: < 10 messages in queue
- Min: 1 instance, Max: 3 instances

**Documentation:** [`gedcom-upload-microservice/README.md`](gedcom-upload-microservice/README.md)

---

## Data Flow

### Stage 1: Image Upload → OCR Processing

**Input:** S3 image file with metadata
```
s3://bucket/documents/book-123/page-005.jpg
Tags: document_id=book-123, page_number=5, total_pages=50
```

**Process:**
1. S3 event notification → `image-upload-queue`
2. OCR Image Service downloads image
3. Extracts metadata from path/tags
4. Performs OCR → markdown text
5. Uploads markdown to S3
6. Publishes to `ocr-results-queue`

**Output:** OCR result message with metadata
```json
{
  "metadata": {
    "document_id": "book-123",
    "page_number": 5,
    "total_pages": 50
  },
  "ocr_result": {
    "markdown_text": "...",
    "s3_uri": "s3://bucket/ocr-results/book-123/page-005.md"
  }
}
```

---

### Stage 2: OCR Results → GEDCOM Generation

**Input:** Multiple OCR result messages (grouped by document_id)

**Process:**
1. GEDCOM Generation Service receives messages
2. Groups by `document_id` in memory or Redis
3. Waits for completion:
   - All pages received (if `total_pages` known), OR
   - Timeout reached (default: 5 minutes)
4. Sorts pages by `page_number`
5. Formats document with metadata header
6. Sends to OpenRouter LLM for direct GEDCOM generation
7. Validates GEDCOM syntax
8. Uploads GEDCOM to S3
9. Publishes to `gedcom-ready-queue`

**Output:** GEDCOM ready message
```json
{
  "document_metadata": {
    "document_id": "book-123",
    "total_pages": 50,
    "pages_processed": 50
  },
  "gedcom_data": {
    "content": "0 HEAD\n1 SOUR OCR-to-GEDCOM...",
    "filename": "book-123.ged",
    "validation_status": "valid"
  }
}
```

**Key Innovation:** Document-level processing allows LLM to:
- Identify same individuals across multiple pages
- Build complete family structures
- Understand document context and structure
- Generate higher-quality GEDCOM with proper relationships

---

### Stage 3: GEDCOM Upload → Storage & Application

**Input:** GEDCOM ready message

**Process:**
1. Upload Service receives message
2. Uploads GEDCOM to S3 final location
3. Uploads GEDCOM to hosted application API
4. Optionally triggers parsing in application
5. Deletes message from queue

**Output:**
- GEDCOM file in S3: `s3://bucket/gedcom-files/book-123/book-123.ged`
- GEDCOM imported into hosted application

---

## Message Formats

### Queue 1: image-upload-queue

**Format:** S3 Event Notification (standard)
```json
{
  "Records": [
    {
      "s3": {
        "bucket": {"name": "my-images-bucket"},
        "object": {"key": "documents/book-123/page-005.jpg"}
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

---

### Queue 2: ocr-results-queue

**Format:** OCR Result with Metadata
```json
{
  "message_id": "uuid-v4",
  "timestamp": "2026-05-23T15:30:00Z",
  "source_image": {
    "s3_uri": "s3://bucket/documents/book-123/page-005.jpg",
    "filename": "page-005.jpg",
    "width": 2000,
    "height": 3000
  },
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
    "s3_uri": "s3://bucket/ocr-results/book-123/page-005.md",
    "character_count": 1234
  }
}
```

**Key Fields:**
- `metadata.document_id` - Grouping key for document assembly
- `metadata.page_number` - Sorting key for page order
- `metadata.total_pages` - Completion detection (optional)

---

### Queue 3: gedcom-ready-queue

**Format:** GEDCOM Ready Message
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

---

## Infrastructure Components

### AWS SQS Queues

**Required Queues:**
1. `image-upload-queue` - Image upload notifications
2. `ocr-results-queue` - OCR processing results
3. `gedcom-ready-queue` - GEDCOM files ready for upload

**Recommended Configuration:**
- **Visibility Timeout:** 300 seconds (5 minutes)
- **Message Retention:** 14 days
- **Dead Letter Queue:** Configure for each queue
- **Max Receives:** 3 attempts before DLQ

**Queue Policies:**
- Allow S3 to send to `image-upload-queue`
- Allow services to read/delete from their input queues
- Allow services to write to their output queues

---

### AWS S3 Buckets

**Required Buckets:**
1. **Input Images Bucket** - Original images
   - Path pattern: `documents/{document_id}/page-{page_number}.jpg`
   - Object tags: `document_id`, `page_number`, `total_pages`, etc.

2. **OCR Results Bucket** - Markdown OCR output
   - Path pattern: `ocr-results/{document_id}/page-{page_number}.md`

3. **GEDCOM Output Bucket** - Final GEDCOM files
   - Path pattern: `gedcom-files/{document_id}/{filename}.ged`

**Bucket Policies:**
- OCR Image Service: Read from input, write to OCR results
- GEDCOM Generation Service: Read from OCR results, write to GEDCOM output
- Upload Service: Read from GEDCOM output

---

### Optional: Redis (for distributed grouping)

**Purpose:** Coordinate document grouping across multiple GEDCOM Generation Service instances

**Configuration:**
- **Host:** Redis cluster or ElastiCache
- **Port:** 6379
- **Database:** 0
- **Key Pattern:** `gedcom:docgroup:{document_id}`

**When to Use:**
- Running multiple GEDCOM Generation Service instances
- High-volume processing (> 100 documents/hour)
- Need for persistent grouping state

**When NOT to Use:**
- Single instance deployment
- Low-volume processing
- Prefer simplicity over scalability

---

## Scaling Considerations

### Horizontal Scaling

**OCR Image Service:**
- ✅ **Stateless** - Easy to scale horizontally
- Scale based on `image-upload-queue` depth
- Each instance processes messages independently
- No coordination needed

**GEDCOM Generation Service:**
- ⚠️ **Stateful** - Requires coordination for grouping
- **Single Instance:** Use in-memory grouping (simple, fast)
- **Multiple Instances:** Use Redis for shared state
- Scale based on number of active document groups
- Distributed locking prevents duplicate processing

**Upload Service:**
- ✅ **Stateless** - Easy to scale horizontally
- Scale based on `gedcom-ready-queue` depth
- Each instance processes messages independently

---

### Vertical Scaling

**When to Scale Up:**
- OCR Image Service: Large images (> 4800x4800)
- GEDCOM Generation Service: Large documents (> 50 pages)
- Upload Service: Large GEDCOM files (> 10 MB)

**Resource Limits:**
- Set appropriate CPU/memory limits in ECS/Kubernetes
- Monitor resource utilization via CloudWatch
- Adjust based on actual usage patterns

---

### Auto-Scaling Policies

**Recommended Metrics:**
- **SQS Queue Depth** - Primary scaling metric
- **CPU Utilization** - Secondary metric
- **Memory Utilization** - Secondary metric

**Example Policy (OCR Image Service):**
```yaml
ScaleUp:
  Metric: ApproximateNumberOfMessages (image-upload-queue)
  Threshold: > 20 messages
  Action: Add 1 instance
  Cooldown: 60 seconds

ScaleDown:
  Metric: ApproximateNumberOfMessages (image-upload-queue)
  Threshold: < 5 messages
  Action: Remove 1 instance
  Cooldown: 300 seconds
```

---

## Cost Analysis

### Per-Document Cost Breakdown

**Assumptions:**
- Document: 50 pages
- Image size: 2 MB per page
- OCR: $0.001 per page (Datalab SDK)
- LLM: $0.10 per 1M tokens (OpenRouter)
- Storage: $0.023 per GB-month (S3)

**Old Architecture (Per-Page Processing):**
```
OCR:        50 pages × $0.001 = $0.05
LLM:        50 calls × 5K tokens × $0.10/1M = $0.025
Storage:    100 MB × $0.023/GB = $0.0023
Total:      $0.0773 per document
```

**New Architecture (Document-Level Processing):**
```
OCR:        50 pages × $0.001 = $0.05
LLM:        1 call × 50K tokens × $0.10/1M = $0.005
Storage:    100 MB × $0.023/GB = $0.0023
Total:      $0.0573 per document
Savings:    26% cost reduction
```

**Annual Cost Projection (1000 documents/month):**
```
Old: $0.0773 × 1000 × 12 = $927.60/year
New: $0.0573 × 1000 × 12 = $687.60/year
Savings: $240/year (26%)
```

---

### Cost Optimization Tips

1. **Use Spot Instances** - Save up to 70% on compute costs
2. **Optimize Image Sizes** - Resize images before upload
3. **Batch Processing** - Process multiple documents together
4. **S3 Lifecycle Policies** - Move old files to Glacier
5. **Reserved Capacity** - For predictable workloads
6. **Monitor Token Usage** - Optimize LLM prompts
7. **Use S3 Intelligent-Tiering** - Automatic cost optimization

---

## Related Documentation

### Service Documentation
- [OCR Image Service README](ocr-image-microservice/README.md)
- [GEDCOM Generation Service README](gedcom-generation-microservice/README.md)
- [GEDCOM Upload Service README](gedcom-upload-microservice/README.md)

### Deployment & Migration
- [Deployment Guide](DEPLOYMENT_GUIDE.md) - Step-by-step deployment instructions
- [Migration Guide](MIGRATION_GUIDE.md) - Migrate from monolithic service
- [Docker Compose Setup](docker-compose.full-pipeline.yml) - Local testing

### Architecture Details
- [Architecture Split Document](ocr-microservice/ARCHITECTURE_SPLIT_REVISED.md) - Detailed design decisions

---

## Monitoring & Observability

### Key Metrics to Monitor

**Service Health:**
- Service uptime and availability
- Error rates per service
- Request latency (p50, p95, p99)

**Queue Metrics:**
- Queue depth (messages waiting)
- Message age (oldest message)
- Messages in flight
- Dead letter queue depth

**Processing Metrics:**
- Documents processed per hour
- Average processing time per document
- OCR success rate
- GEDCOM validation success rate
- Upload success rate

**Cost Metrics:**
- API calls per day (Datalab, OpenRouter)
- Token usage per document
- S3 storage costs
- Data transfer costs

### Recommended Dashboards

**CloudWatch Dashboard:**
```
┌─────────────────────────────────────────────────────┐
│ OCR Pipeline Overview                                │
├─────────────────────────────────────────────────────┤
│ Queue Depths:                                        │
│   image-upload-queue:    [Graph]                    │
│   ocr-results-queue:     [Graph]                    │
│   gedcom-ready-queue:    [Graph]                    │
├─────────────────────────────────────────────────────┤
│ Service Health:                                      │
│   OCR Image Service:     [Status] [Error Rate]      │
│   GEDCOM Generation:     [Status] [Error Rate]      │
│   Upload Service:        [Status] [Error Rate]      │
├─────────────────────────────────────────────────────┤
│ Processing Stats:                                    │
│   Documents/Hour:        [Graph]                    │
│   Avg Processing Time:   [Graph]                    │
│   Success Rate:          [Graph]                    │
└─────────────────────────────────────────────────────┘
```

### Alerting

**Critical Alerts:**
- Service down for > 5 minutes
- Queue depth > 100 messages for > 10 minutes
- Error rate > 10% for > 5 minutes
- Dead letter queue has messages

**Warning Alerts:**
- Queue depth > 50 messages
- Error rate > 5%
- Processing time > 2x average
- Disk space > 80%

---

## Security Considerations

### IAM Roles & Permissions

**Principle of Least Privilege:**
- Each service has its own IAM role
- Only grant necessary permissions
- Use resource-level permissions where possible

**OCR Image Service IAM Policy:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["sqs:ReceiveMessage", "sqs:DeleteMessage"],
      "Resource": "arn:aws:sqs:*:*:image-upload-queue"
    },
    {
      "Effect": "Allow",
      "Action": ["sqs:SendMessage"],
      "Resource": "arn:aws:sqs:*:*:ocr-results-queue"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject"],
      "Resource": "arn:aws:s3:::input-bucket/*"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject"],
      "Resource": "arn:aws:s3:::ocr-results-bucket/*"
    }
  ]
}
```

### API Keys & Secrets

**Use AWS Secrets Manager:**
- Store Datalab API key
- Store OpenRouter API key
- Store application API key
- Rotate keys regularly

**Environment Variables:**
- Never commit API keys to git
- Use `.env` files for local development
- Use Secrets Manager for production

### Network Security

**VPC Configuration:**
- Deploy services in private subnets
- Use VPC endpoints for AWS services (S3, SQS)
- Restrict outbound internet access
- Use security groups for service isolation

**Encryption:**
- Enable encryption at rest for S3 buckets
- Enable encryption in transit (HTTPS/TLS)
- Use encrypted SQS queues

---

## Troubleshooting

### Common Issues

**Issue: Messages stuck in queue**
- Check service is running and healthy
- Verify IAM permissions
- Check visibility timeout settings
- Review service logs for errors

**Issue: GEDCOM validation failures**
- Review LLM prompt in [`gedcom_generation.py`](gedcom-generation-microservice/src/prompts/gedcom_generation.py)
- Check input OCR quality
- Verify metadata completeness
- Try different LLM model

**Issue: High costs**
- Review token usage per document
- Optimize LLM prompts
- Consider cheaper LLM models
- Batch process documents

**Issue: Slow processing**
- Check queue depths
- Scale up services
- Optimize OCR settings
- Review network latency

---

## Future Enhancements

### Potential Improvements

1. **Parallel Page Processing** - Process multiple pages simultaneously
2. **Smart Grouping** - ML-based document boundary detection
3. **Quality Scoring** - Automatic quality assessment of GEDCOM
4. **Incremental Processing** - Process new pages as they arrive
5. **Multi-Language Support** - Better handling of non-Latin scripts
6. **Relationship Validation** - Verify family relationships make sense
7. **Duplicate Detection** - Identify duplicate individuals across documents
8. **Web UI** - Dashboard for monitoring and management

### Roadmap

**Q2 2026:**
- ✅ Three-service architecture deployed
- ✅ Document-level processing
- ✅ Direct GEDCOM generation

**Q3 2026:**
- 🔄 Redis-based distributed grouping
- 🔄 Enhanced monitoring dashboards
- 🔄 Cost optimization improvements

**Q4 2026:**
- 📋 Parallel page processing
- 📋 Quality scoring system
- 📋 Web UI for management

---

## Support & Contributing

### Getting Help

- **Documentation:** Start with service-specific READMEs
- **Issues:** Check existing GitHub issues
- **Deployment:** See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
- **Migration:** See [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)

### Contributing

Contributions are welcome! Areas for contribution:
- Bug fixes and improvements
- Documentation enhancements
- New features and optimizations
- Testing and quality assurance

---

## License

This project is part of the Korzen genealogy platform.

---

## Conclusion

The three-service OCR pipeline provides a scalable, cost-effective solution for converting historical church records into GEDCOM files. The document-level processing approach with direct GEDCOM generation significantly improves quality while reducing costs.

**Key Benefits:**
- ✅ 26% cost reduction vs. per-page processing
- ✅ Higher quality GEDCOM with complete document context
- ✅ Scalable architecture with independent service scaling
- ✅ Fault-tolerant with retry logic and DLQs
- ✅ Easy to deploy and maintain

For deployment instructions, see [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md).
