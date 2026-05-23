# OCR Microservice

A production-ready Python microservice for processing images through an OCR pipeline using AWS services (SQS, S3) and Datalab SDK.

## Architecture Overview

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│   AWS SQS   │─────▶│ OCR Service  │─────▶│   AWS S3    │
│   Queue     │      │              │      │  (Results)  │
└─────────────┘      └──────────────┘      └─────────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │   AWS S3     │
                     │  (Images)    │
                     └──────────────┘
```

### Workflow

1. **Message Reception**: Poll SQS queue for messages containing S3 image URIs
2. **Image Download**: Download image from S3 to local temporary storage
3. **OCR Processing**: Process image using Datalab SDK to extract text
4. **Result Upload**: Upload markdown results back to S3
5. **Message Deletion**: Delete SQS message after successful processing
6. **Cleanup**: Remove temporary local files

## Project Structure

```
ocr-microservice/
├── src/
│   ├── __init__.py
│   ├── main.py                    # Entry point
│   ├── config.py                  # Configuration management
│   ├── services/
│   │   ├── __init__.py
│   │   ├── sqs_consumer.py        # AWS SQS message consumer
│   │   ├── s3_handler.py          # S3 download/upload operations
│   │   ├── ocr_processor.py       # Datalab SDK integration
│   │   └── message_processor.py   # Workflow orchestration
│   └── utils/
│       ├── __init__.py
│       └── logger.py              # Logging configuration
├── requirements.txt               # Python dependencies
├── Dockerfile                     # Docker image definition
├── docker-compose.yml             # Docker Compose configuration
├── .env.example                   # Environment variables template
└── README.md                      # This file
```

## Setup Instructions

### Prerequisites

- Python 3.11+
- AWS account with SQS and S3 access
- Datalab SDK credentials (if required)
- Docker and Docker Compose (for containerized deployment)

### Local Development Setup

1. **Clone the repository**
   ```bash
   cd ocr-microservice
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

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your actual credentials and configuration
   ```

5. **Run the service**
   ```bash
   python -m src.main
   ```

### Docker Deployment

1. **Build the Docker image**
   ```bash
   docker build -t ocr-microservice:latest .
   ```

2. **Run with Docker Compose**
   ```bash
   # Edit docker-compose.yml or create .env file with your configuration
   docker-compose up -d
   ```

3. **View logs**
   ```bash
   docker-compose logs -f ocr-microservice
   ```

4. **Stop the service**
   ```bash
   docker-compose down
   ```

## Environment Variables

### Required Configuration

| Variable | Description | Example |
|----------|-------------|---------|
| `AWS_REGION` | AWS region for services | `us-east-1` |
| `AWS_ACCESS_KEY_ID` | AWS access key | `AKIAIOSFODNN7EXAMPLE` |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key | `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` |
| `SQS_QUEUE_URL` | Full SQS queue URL | `https://sqs.us-east-1.amazonaws.com/123456789012/ocr-queue` |
| `S3_INPUT_BUCKET` | S3 bucket for input images | `my-images-bucket` |
| `S3_OUTPUT_BUCKET` | S3 bucket for OCR results | `my-results-bucket` |

### Optional Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `S3_OUTPUT_PREFIX` | Prefix for output files in S3 | `ocr-results/` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `TEMP_DIR` | Local temporary directory | `/tmp/ocr-processing` |
| `MAX_RETRIES` | Maximum retry attempts | `3` |
| `RETRY_BACKOFF_BASE` | Exponential backoff base | `2.0` |
| `RETRY_BACKOFF_MAX` | Maximum backoff time (seconds) | `60.0` |
| `SQS_MAX_MESSAGES` | Messages per poll (1-10) | `1` |
| `SQS_WAIT_TIME_SECONDS` | Long polling wait time | `20` |
| `SQS_VISIBILITY_TIMEOUT` | Message visibility timeout | `300` |
| `OCR_OUTPUT_FORMAT` | OCR output format | `markdown` |
| `OCR_MODE` | OCR processing mode | `balanced` |
| `OCR_PAGINATE` | Enable pagination | `true` |

## Message Format

The microservice expects SQS messages with the following JSON format:

```json
{
  "s3_uri": "s3://my-images-bucket/path/to/image.png",
  "metadata": {
    "document_id": "12345",
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

**Supported field names for S3 URI:**
- `s3_uri`
- `s3Uri`
- `imageUri`
- `image_uri`

## Features

### Error Handling

- **Retry Logic**: Automatic retry with exponential backoff for transient failures
- **Dead Letter Queue**: Failed messages (after max retries) return to queue or move to DLQ
- **Comprehensive Logging**: All operations logged with timestamps and context
- **Exception Tracking**: Full stack traces for debugging

### Graceful Shutdown

The service handles `SIGTERM` and `SIGINT` signals for graceful shutdown:
- Completes current message processing
- Logs statistics (total polls, messages processed)
- Cleans up resources

### Resource Management

- **Temporary File Cleanup**: Automatic cleanup of downloaded images and results
- **Memory Efficient**: Processes one message at a time by default
- **Configurable Resources**: Docker resource limits can be adjusted

## Monitoring and Logging

### Log Levels

- `DEBUG`: Detailed diagnostic information
- `INFO`: General informational messages (default)
- `WARNING`: Warning messages for potential issues
- `ERROR`: Error messages with stack traces
- `CRITICAL`: Critical errors requiring immediate attention

### Key Log Messages

- `Message received from SQS`: New message detected
- `Downloading s3://...`: Image download started
- `Starting OCR processing`: OCR processing initiated
- `Successfully uploaded result`: Result uploaded to S3
- `Message deleted successfully`: SQS message removed
- `Processing failed, retrying`: Retry attempt with backoff time

### Metrics to Monitor

- Messages processed per minute
- Average processing time per message
- Retry rate
- Error rate
- S3 upload/download latency

## Deployment Considerations

### AWS IAM Permissions

The service requires the following IAM permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:ChangeMessageVisibility"
      ],
      "Resource": "arn:aws:sqs:REGION:ACCOUNT:QUEUE_NAME"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject"
      ],
      "Resource": "arn:aws:s3:::INPUT_BUCKET/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject"
      ],
      "Resource": "arn:aws:s3:::OUTPUT_BUCKET/*"
    }
  ]
}
```

### Scaling Considerations

- **Horizontal Scaling**: Deploy multiple instances to process messages in parallel
- **SQS Configuration**: Adjust visibility timeout based on average processing time
- **Resource Allocation**: Allocate sufficient CPU/memory for OCR processing
- **Network Bandwidth**: Ensure adequate bandwidth for S3 transfers

### Production Best Practices

1. **Use AWS Secrets Manager** for credentials instead of environment variables
2. **Enable CloudWatch Logs** for centralized logging
3. **Set up CloudWatch Alarms** for error rates and processing delays
4. **Configure Dead Letter Queue** for failed messages
5. **Use VPC Endpoints** for S3 and SQS to reduce costs and improve security
6. **Implement health checks** for container orchestration
7. **Enable X-Ray tracing** for distributed tracing

### High Availability

- Deploy across multiple availability zones
- Use Auto Scaling Groups for automatic scaling
- Configure SQS queue with appropriate retention period
- Implement circuit breakers for external dependencies

## Troubleshooting

### Common Issues

**Issue**: Messages not being received
- Check SQS queue URL is correct
- Verify IAM permissions
- Check network connectivity to AWS

**Issue**: S3 download failures
- Verify S3 bucket exists and is accessible
- Check IAM permissions for S3 GetObject
- Ensure S3 URI format is correct

**Issue**: OCR processing failures
- Check Datalab SDK installation
- Verify image format is supported
- Check available disk space in temp directory

**Issue**: High memory usage
- Reduce `SQS_MAX_MESSAGES` to process fewer messages concurrently
- Increase Docker memory limits
- Check for memory leaks in OCR processing

### Debug Mode

Enable debug logging for detailed diagnostics:

```bash
export LOG_LEVEL=DEBUG
python -m src.main
```

## Testing

### Manual Testing

1. **Upload test image to S3**
   ```bash
   aws s3 cp test-image.png s3://my-images-bucket/test/
   ```

2. **Send test message to SQS**
   ```bash
   aws sqs send-message \
     --queue-url https://sqs.us-east-1.amazonaws.com/123456789012/ocr-queue \
     --message-body '{"s3_uri": "s3://my-images-bucket/test/test-image.png"}'
   ```

3. **Monitor logs**
   ```bash
   docker-compose logs -f ocr-microservice
   ```

4. **Verify result in S3**
   ```bash
   aws s3 ls s3://my-results-bucket/ocr-results/
   ```

## License

[Your License Here]

## Support

For issues and questions:
- Create an issue in the repository
- Contact: [Your Contact Information]

## Contributing

Contributions are welcome! Please follow these guidelines:
1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Submit a pull request

## Changelog

### Version 1.0.0
- Initial release
- SQS message consumption
- S3 download/upload
- Datalab SDK OCR integration
- Retry logic with exponential backoff
- Graceful shutdown
- Docker support
