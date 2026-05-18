# Image Upload Microservice

🚀 A production-ready Python microservice that automatically monitors directories for new image files, validates and uploads them to AWS S3, and triggers downstream OCR processing via AWS SQS notifications.

## 📋 Overview

The Image Upload Microservice serves as the entry point for an automated image processing pipeline. It continuously watches a specified directory for new image files, validates them, uploads to S3, and notifies downstream services (like the OCR microservice) through SQS messages.

### Architecture

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
│                        │  (Downstream)    │                              │
│                        └──────────────────┘                              │
└──────────────────────────────────────────────────────────────────────────┘
```

## ✨ Features

- **🔍 Automatic File Detection**: Real-time monitoring using the `watchdog` library
- **📂 Recursive Directory Scanning**: Automatically descends into subdirectories to find all images
- **🚀 Initial Startup Scan**: Processes all existing files on startup, not just new ones
- **#️⃣ File Hashing**: SHA-256 hash calculation for every file
- **🔁 Duplicate Detection**: Checks S3 before upload to avoid re-uploading existing files
- **✅ Multi-Format Support**: JPEG, PNG, GIF, BMP, TIFF, WebP, and more
- **🛡️ Robust Validation**: Multi-layer validation (extension, MIME type, image headers)
- **☁️ AWS S3 Integration**: Efficient uploads with multipart support for large files
- **📬 SQS Notifications**: Automatic message publishing to trigger downstream processing
- **🔄 Smart Retry Logic**: Exponential backoff for transient failures
- **🗂️ Flexible Post-Processing**: Keep, archive, or delete files after upload
- **📊 Structured Logging**: JSON logging for easy monitoring and debugging
- **🐳 Docker Ready**: Full containerization with Docker and Docker Compose
- **⚙️ Highly Configurable**: Comprehensive environment-based configuration
- **🏛️ Skanoteka Metadata Extraction**: Automatic extraction of genealogical archive metadata from Skanoteka URLs

> **🆕 New in Latest Version**:
> - Recursive scanning, initial directory scan on startup, file hashing, and S3 duplicate detection. See [RECURSIVE_SCAN_FEATURE.md](RECURSIVE_SCAN_FEATURE.md) for details.
> - **Skanoteka metadata integration**: Automatically extracts and attaches metadata (place, unit, years, page) from Skanoteka genealogical archives. See [METADATA_INTEGRATION.md](METADATA_INTEGRATION.md) for details.

## 📦 Prerequisites

- **Python 3.11+** (for local development)
- **Docker and Docker Compose** (for containerized deployment)
- **AWS Account** with:
  - S3 bucket for image storage
  - SQS queue for notifications
  - IAM credentials with appropriate permissions
- **Sufficient disk space** for temporary file storage

## 🚀 Quick Start

### Option 1: Docker Compose (Recommended)

1. **Clone and navigate to the microservice directory**
   ```bash
   cd image-upload-microservice
   ```

2. **Create environment configuration**
   ```bash
   cp .env.example .env
   # Edit .env with your AWS credentials and configuration
   ```

3. **Create watched directory**
   ```bash
   mkdir -p watched-images processed-images
   ```

4. **Start the service**
   ```bash
   docker-compose up -d
   ```

5. **View logs**
   ```bash
   docker-compose logs -f image-upload-microservice
   ```

6. **Test by adding an image**
   ```bash
   cp /path/to/your/image.jpg watched-images/
   # Check logs to see the upload process
   ```

### Option 2: Local Development

1. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Create watched directory**
   ```bash
   mkdir -p watched-images processed-images
   ```

5. **Run the service**
   ```bash
   python -m src.main
   ```

## ⚙️ Configuration

### Required Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `AWS_REGION` | AWS region for S3/SQS | `us-east-1` |
| `AWS_ACCESS_KEY_ID` | AWS access key† | `AKIAIOSFODNN7EXAMPLE` |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key† | `wJalrXUtnFEMI/K7MDENG/...` |
| `AWS_S3_BUCKET` | Target S3 bucket | `my-images-bucket` |
| `AWS_SQS_QUEUE_URL` | SQS queue URL | `https://sqs.us-east-1.amazonaws.com/...` |
| `WATCH_DIRECTORY` | Directory to monitor | `/app/watched-images` |

**†** Optional when using IAM roles (recommended for ECS/EC2)

### Optional Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `S3_PREFIX` | S3 object key prefix | `uploads/` |
| `S3_SERVER_SIDE_ENCRYPTION` | Encryption algorithm | `AES256` |
| `S3_STORAGE_CLASS` | S3 storage class | `STANDARD` |
| `MULTIPART_THRESHOLD_MB` | Multipart upload threshold | `5` |
| `WATCH_RECURSIVE` | Monitor subdirectories | `false` |
| `DEBOUNCE_SECONDS` | Wait time before processing | `2.0` |
| `POST_UPLOAD_ACTION` | Action after upload | `keep` |
| `ARCHIVE_DIRECTORY` | Archive location (if archive) | `/app/processed-images` |
| `SUPPORTED_EXTENSIONS` | Allowed file extensions | `jpg,jpeg,png,gif,...` |
| `MIN_IMAGE_SIZE_BYTES` | Minimum file size | `1024` |
| `MAX_IMAGE_SIZE_BYTES` | Maximum file size | `104857600` (100MB) |
| `LOG_LEVEL` | Logging level | `INFO` |
| `MAX_CONCURRENT_UPLOADS` | Parallel uploads | `3` |
| `MAX_RETRIES` | Retry attempts | `3` |

See [`.env.example`](.env.example:1) for complete configuration options.

## 🔧 Deployment Options

### Local Development

Perfect for testing and development:

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env

# Run
python -m src.main
```

### Docker

Build and run as a Docker container:

```bash
# Build image
docker build -t image-upload-microservice:latest .

# Run container
docker run -d \
  --name image-upload-service \
  --env-file .env \
  -v $(pwd)/watched-images:/app/watched-images \
  -v $(pwd)/processed-images:/app/processed-images \
  image-upload-microservice:latest
```

### Docker Compose

Simplest deployment with volume management:

```bash
docker-compose up -d
```

Customize [`docker-compose.yml`](docker-compose.yml:1) for your environment.

### AWS ECS/Fargate

For production deployment on AWS:

1. **Create ECR repository**
   ```bash
   aws ecr create-repository --repository-name image-upload-microservice
   ```

2. **Build and push image**
   ```bash
   docker build -t image-upload-microservice:latest .
   docker tag image-upload-microservice:latest <ecr-uri>:latest
   docker push <ecr-uri>:latest
   ```

3. **Create ECS task definition** with:
   - IAM role with S3/SQS permissions
   - Environment variables from AWS Secrets Manager
   - EFS volume mount for watched directory (if needed)
   - CloudWatch Logs configuration

4. **Create ECS service** with:
   - Desired count: 1 (or more for scaling)
   - Auto-scaling based on queue depth
   - Health checks enabled

See [`USAGE.md`](USAGE.md:1) for detailed deployment instructions.

## 📤 Usage Examples

### Basic Upload

1. Copy an image to the watched directory:
   ```bash
   cp photo.jpg watched-images/
   ```

2. The service automatically:
   - Detects the new file
   - Validates it's a valid image
   - Uploads to S3 with metadata
   - Sends SQS notification
   - Archives/deletes based on configuration

### Batch Upload

```bash
# Copy multiple files
cp /path/to/scans/*.jpg watched-images/

# Or use rsync for large batches
rsync -av --progress /source/images/ watched-images/
```

### Monitor Processing

```bash
# View logs in real-time
docker-compose logs -f image-upload-microservice

# Check for specific events
docker-compose logs image-upload-microservice | grep "upload_completed"
```

## 🔗 Integration with OCR Microservice

This service sends SQS messages in the format expected by the [OCR microservice](../ocr-microservice/README.md:1):

```json
{
  "s3_uri": "s3://bucket-name/uploads/2026/05/17/uuid_image.jpg",
  "metadata": {
    "original_filename": "image.jpg",
    "upload_timestamp": "2026-05-17T23:01:00.123Z",
    "source_directory": "/watched-images",
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

The OCR microservice polls this queue and processes each uploaded image automatically.

## 📊 Monitoring and Logging

### Log Events

Key events to monitor:

- `service_started`: Service initialization
- `file_detected`: New file found
- `image_validated`: Image passed validation
- `upload_completed`: S3 upload successful
- `notification_sent`: SQS message sent
- `upload_failed`: Upload or validation failed
- `retry_attempted`: Retrying after failure

### Log Format

Structured JSON logging for easy parsing:

```json
{
  "timestamp": "2026-05-17T23:01:00.123Z",
  "level": "INFO",
  "event": "upload_completed",
  "file_path": "/watched-images/scan_001.jpg",
  "s3_key": "uploads/2026/05/17/uuid_scan_001.jpg",
  "file_size": 2457600,
  "upload_duration_ms": 1234
}
```

### Health Monitoring

Monitor these metrics:

- **Files processed/minute**: Upload throughput
- **Success rate**: Uploads / attempts
- **Error rate**: Failed uploads
- **Average upload duration**: Performance indicator
- **Queue depth**: Pending uploads

## 🔒 AWS IAM Permissions

### Required IAM Policy

Attach this policy to your IAM user or role:

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
    }
  ]
}
```

### Best Practices

- Use **IAM roles** instead of access keys when running on AWS (EC2/ECS)
- Apply **least privilege** principle
- Use **AWS Secrets Manager** for credential management in production
- Enable **CloudTrail** for audit logging
- Rotate credentials regularly

## 🐛 Troubleshooting

### Service Not Starting

**Problem**: Service fails to start or exits immediately

**Solutions**:
- Check environment variables are set correctly
- Verify AWS credentials are valid
- Ensure watched directory exists and is accessible
- Check Docker logs: `docker-compose logs image-upload-microservice`
- Enable debug logging: `LOG_LEVEL=DEBUG`

### Files Not Being Detected

**Problem**: Files added to directory are not processed

**Solutions**:
- Verify `WATCH_DIRECTORY` path is correct
- Check file extensions are in `SUPPORTED_EXTENSIONS`
- Ensure file meets minimum/maximum size requirements
- Check file permissions (readable by service)
- Look for validation errors in logs
- Try with `WATCH_RECURSIVE=true` if files are in subdirectories

### Upload Failures

**Problem**: Images detected but uploads fail

**Solutions**:
- Verify S3 bucket exists and is accessible
- Check IAM permissions for S3 PutObject
- Verify network connectivity to AWS
- Check `AWS_REGION` matches bucket region
- Review error messages in logs
- Ensure file size is within limits

### SQS Messages Not Appearing

**Problem**: Files upload successfully but no SQS messages

**Solutions**:
- Verify `AWS_SQS_QUEUE_URL` is correct
- Check IAM permissions for SQS SendMessage
- Verify queue exists and is accessible
- Check for errors in logs around `notification_sent`
- Try sending a test message manually

### High Memory Usage

**Problem**: Service consuming too much memory

**Solutions**:
- Reduce `MAX_CONCURRENT_UPLOADS` (default: 3)
- Decrease `MAX_IMAGE_SIZE_BYTES` limit
- Check for memory leaks (restart periodically in production)
- Increase Docker memory limits if needed

### Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| `Watch directory does not exist` | Invalid path | Create directory or fix path |
| `NoCredentialsError` | Missing AWS credentials | Set credentials or use IAM roles |
| `AccessDenied` | Insufficient permissions | Update IAM policy |
| `NoSuchBucket` | Bucket doesn't exist | Create bucket or fix name |
| `QueueDoesNotExist` | Invalid queue URL | Fix SQS queue URL |
| `File too large` | Exceeds max size | Reduce file size or increase limit |

## 📚 Additional Documentation

- **[`ARCHITECTURE.md`](ARCHITECTURE.md:1)** - Detailed technical architecture and design
- **[`USAGE.md`](USAGE.md:1)** - Step-by-step usage guide and examples
- **[`METADATA_INTEGRATION.md`](METADATA_INTEGRATION.md:1)** - Skanoteka metadata extraction integration
- **[`RECURSIVE_SCAN_FEATURE.md`](RECURSIVE_SCAN_FEATURE.md:1)** - Recursive scanning and duplicate detection
- **[`../ocr-microservice/README.md`](../ocr-microservice/README.md:1)** - Downstream OCR service documentation

## 🧪 Testing

### Manual Testing

1. **Test single file upload**
   ```bash
   cp test-image.jpg watched-images/
   # Check logs and verify S3 upload
   aws s3 ls s3://your-bucket/uploads/ --recursive
   ```

2. **Verify SQS message**
   ```bash
   aws sqs receive-message --queue-url <your-queue-url>
   ```

3. **Test different formats**
   ```bash
   cp test.jpg test.png test.gif watched-images/
   ```

4. **Test invalid files**
   ```bash
   cp document.pdf watched-images/  # Should be rejected
   ```

### Integration Testing

Test the full pipeline with downstream services:

1. Start both services:
   ```bash
   docker-compose up -d
   ```

2. Add test image:
   ```bash
   cp test-scan.jpg watched-images/
   ```

3. Monitor both services:
   ```bash
   docker-compose logs -f
   ```

4. Verify end-to-end processing through OCR service

## 🔄 Post-Upload Actions

Configure what happens to files after successful upload:

### Keep (Default)
```bash
POST_UPLOAD_ACTION=keep
```
Files remain in the watched directory after upload.

### Archive
```bash
POST_UPLOAD_ACTION=archive
ARCHIVE_DIRECTORY=/app/processed-images
```
Files are moved to the archive directory, preserving directory structure.

### Delete
```bash
POST_UPLOAD_ACTION=delete
```
Files are deleted after successful upload. **Use with caution!**

## 🚦 Graceful Shutdown

The service handles shutdown signals properly:

```bash
# Send SIGTERM
docker-compose stop

# Or SIGINT (Ctrl+C) if running in foreground
```

On shutdown, the service:
1. Stops watching for new files
2. Completes in-progress uploads
3. Logs statistics and summary
4. Cleans up resources

## 🔐 Security Considerations

- **Run as non-root user** in Docker (implemented)
- **Use IAM roles** instead of hardcoded credentials
- **Enable encryption** at rest (S3) and in transit (TLS)
- **Restrict network access** with security groups
- **Validate all inputs** (file paths, sizes, formats)
- **Use VPC endpoints** for S3/SQS to avoid internet gateway
- **Enable CloudTrail** for audit logging
- **Rotate credentials** regularly

## 📈 Scaling Considerations

### Horizontal Scaling

Deploy multiple instances for higher throughput:

- Use **separate subdirectories** per instance
- Use **file locking** or coordination (Redis/DynamoDB) for shared directory
- Enable **SQS FIFO with deduplication** to prevent duplicate processing

### Vertical Scaling

Increase resources for larger files:

- Increase `MAX_CONCURRENT_UPLOADS` for more parallelism
- Allocate more memory for processing large images
- Use faster storage (SSD/EBS) for watched directory

## 📄 Project Structure

```
image-upload-microservice/
├── src/
│   ├── main.py                      # Entry point
│   ├── config.py                    # Configuration management
│   ├── services/
│   │   ├── directory_watcher.py     # File system monitoring
│   │   ├── image_detector.py        # Image validation
│   │   ├── s3_uploader.py           # S3 uploads
│   │   ├── sqs_notifier.py          # SQS notifications
│   │   └── upload_orchestrator.py   # Workflow coordination
│   └── utils/
│       └── logger.py                # Logging configuration
├── requirements.txt                 # Python dependencies
├── Dockerfile                       # Docker image
├── docker-compose.yml               # Docker Compose config
├── .env.example                     # Environment template
├── .gitignore                       # Git ignore rules
├── README.md                        # This file
├── ARCHITECTURE.md                  # Technical architecture
└── USAGE.md                         # Usage guide
```

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Update documentation as needed
5. Submit a pull request

## 📝 License

[Your License Here]

## 💬 Support

For issues, questions, or feature requests:

- **Documentation**: Check [`USAGE.md`](USAGE.md:1) and [`ARCHITECTURE.md`](ARCHITECTURE.md:1)
- **Issues**: Create an issue in the repository
- **Integration**: See [OCR microservice docs](../ocr-microservice/README.md:1) for pipeline setup

## 📋 Changelog

### Version 1.0.0

- ✅ Initial release
- ✅ Directory monitoring with watchdog
- ✅ Multi-format image validation
- ✅ S3 uploads with multipart support
- ✅ SQS notification publishing
- ✅ Retry logic with exponential backoff
- ✅ Docker containerization
- ✅ Structured logging
- ✅ Comprehensive configuration
- ✅ Health checks
- ✅ Post-upload actions (keep/archive/delete)

---

**Made with ❤️ for automated image processing pipelines**
