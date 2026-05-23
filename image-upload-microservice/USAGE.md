# Image Upload Microservice - Usage Guide

This guide provides detailed, step-by-step instructions for setting up, configuring, and using the Image Upload Microservice.

## 📑 Table of Contents

- [Initial Setup](#initial-setup)
- [AWS Resources Configuration](#aws-resources-configuration)
- [Service Configuration](#service-configuration)
- [Running the Service](#running-the-service)
- [Example Workflows](#example-workflows)
- [Post-Upload Actions](#post-upload-actions)
- [Testing the Service](#testing-the-service)
- [Integration Testing](#integration-testing)
- [Common Use Cases](#common-use-cases)
- [Advanced Configuration](#advanced-configuration)
- [Production Deployment](#production-deployment)
- [Monitoring and Maintenance](#monitoring-and-maintenance)

## Initial Setup

### 1. Clone the Repository

```bash
cd /home/user/korzen/image-upload-microservice
```

### 2. Prepare Your Environment

Choose one of the following setups:

#### Option A: Docker Setup (Recommended)

**Prerequisites:**
- Docker 20.10+
- Docker Compose 2.0+

**Verify installation:**
```bash
docker --version
docker-compose --version
```

#### Option B: Local Python Setup

**Prerequisites:**
- Python 3.11+
- pip package manager

**Verify installation:**
```bash
python --version
pip --version
```

### 3. Create Directory Structure

```bash
# Create watched and archive directories
mkdir -p watched-images
mkdir -p processed-images
mkdir -p logs

# Verify structure
ls -la
```

## AWS Resources Configuration

### Step 1: Create S3 Bucket

Create an S3 bucket to store uploaded images:

```bash
# Set your desired bucket name
BUCKET_NAME="my-church-records-images"
AWS_REGION="us-east-1"

# Create bucket
aws s3 mb s3://${BUCKET_NAME} --region ${AWS_REGION}

# Enable versioning (optional but recommended)
aws s3api put-bucket-versioning \
  --bucket ${BUCKET_NAME} \
  --versioning-configuration Status=Enabled

# Enable server-side encryption
aws s3api put-bucket-encryption \
  --bucket ${BUCKET_NAME} \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }]
  }'
```

**Verify bucket creation:**
```bash
aws s3 ls s3://${BUCKET_NAME}
```

### Step 2: Create SQS Queue

Create an SQS queue for notifications:

```bash
# Standard queue (recommended for most use cases)
QUEUE_NAME="ocr-processing-queue"

# Create queue
aws sqs create-queue \
  --queue-name ${QUEUE_NAME} \
  --attributes '{
    "VisibilityTimeout": "300",
    "MessageRetentionPeriod": "1209600",
    "ReceiveMessageWaitTimeSeconds": "20"
  }' \
  --region ${AWS_REGION}

# Get queue URL (save this for configuration)
QUEUE_URL=$(aws sqs get-queue-url --queue-name ${QUEUE_NAME} --region ${AWS_REGION} --query 'QueueUrl' --output text)
echo "Queue URL: ${QUEUE_URL}"
```

**For FIFO queue (ordered processing):**
```bash
QUEUE_NAME="ocr-processing-queue.fifo"

aws sqs create-queue \
  --queue-name ${QUEUE_NAME} \
  --attributes '{
    "FifoQueue": "true",
    "ContentBasedDeduplication": "true",
    "VisibilityTimeout": "300",
    "MessageRetentionPeriod": "1209600"
  }' \
  --region ${AWS_REGION}
```

### Step 3: Configure IAM Permissions

Create an IAM user or role with appropriate permissions:

#### Create IAM Policy

Save this as `image-upload-policy.json`:

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

**Create and attach the policy:**

```bash
# Replace placeholders in the policy file
sed -i "s/YOUR_BUCKET_NAME/${BUCKET_NAME}/g" image-upload-policy.json
sed -i "s/QUEUE_NAME/${QUEUE_NAME}/g" image-upload-policy.json
sed -i "s/REGION/${AWS_REGION}/g" image-upload-policy.json
sed -i "s/ACCOUNT_ID/$(aws sts get-caller-identity --query Account --output text)/g" image-upload-policy.json

# Create policy
aws iam create-policy \
  --policy-name ImageUploadMicroservicePolicy \
  --policy-document file://image-upload-policy.json

# Create IAM user
aws iam create-user --user-name image-upload-service

# Attach policy to user
POLICY_ARN=$(aws iam list-policies --query 'Policies[?PolicyName==`ImageUploadMicroservicePolicy`].Arn' --output text)
aws iam attach-user-policy \
  --user-name image-upload-service \
  --policy-arn ${POLICY_ARN}

# Create access keys
aws iam create-access-key --user-name image-upload-service
# SAVE THE ACCESS KEY AND SECRET KEY!
```

## Service Configuration

### Step 1: Create Environment File

```bash
# Copy example configuration
cp .env.example .env
```

### Step 2: Edit Configuration

Edit the `.env` file with your actual values:

```bash
# Using your preferred editor
nano .env
# or
vim .env
# or
code .env
```

**Minimum required configuration:**

```bash
# AWS Configuration
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY

# S3 Configuration
S3_INPUT_BUCKET=my-church-records-images
S3_INPUT_PREFIX=uploads/

# SQS Configuration
IMAGE_UPLOAD_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/123456789012/image-upload-queue

# Directory Configuration
WATCH_DIRECTORY=/app/watched-images
ARCHIVE_DIRECTORY=/app/processed-images

# Basic Settings
LOG_LEVEL=INFO
POST_UPLOAD_ACTION=archive
```

### Step 3: Verify Configuration

Test your AWS credentials and connectivity:

```bash
# Test S3 access
aws s3 ls s3://${BUCKET_NAME} \
  --region ${AWS_REGION}

# Test SQS access
aws sqs get-queue-attributes \
  --queue-url ${QUEUE_URL} \
  --attribute-names All \
  --region ${AWS_REGION}
```

## Running the Service

### Method 1: Docker Compose (Recommended)

**Start the service:**
```bash
docker-compose up -d
```

**View logs:**
```bash
# Follow logs in real-time
docker-compose logs -f image-upload-microservice

# View last 100 lines
docker-compose logs --tail=100 image-upload-microservice

# Search for specific events
docker-compose logs image-upload-microservice | grep "upload_completed"
```

**Stop the service:**
```bash
docker-compose down
```

**Restart after configuration changes:**
```bash
docker-compose down
docker-compose up -d
```

### Method 2: Docker CLI

**Build image:**
```bash
docker build -t image-upload-microservice:latest .
```

**Run container:**
```bash
docker run -d \
  --name image-upload-service \
  --env-file .env \
  -v $(pwd)/watched-images:/app/watched-images \
  -v $(pwd)/processed-images:/app/processed-images \
  -v $(pwd)/logs:/app/logs \
  --restart unless-stopped \
  image-upload-microservice:latest
```

**View logs:**
```bash
docker logs -f image-upload-service
```

**Stop container:**
```bash
docker stop image-upload-service
docker rm image-upload-service
```

### Method 3: Local Python

**Activate virtual environment:**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

**Install dependencies:**
```bash
pip install -r requirements.txt
```

**Run service:**
```bash
python -m src.main
```

**Stop service:**
```bash
# Press Ctrl+C for graceful shutdown
```

## Example Workflows

### Workflow 1: Single Image Upload

**Scenario:** Upload a single scanned document

```bash
# 1. Start the service
docker-compose up -d

# 2. Check service is running
docker-compose logs --tail=20 image-upload-microservice

# 3. Copy image to watched directory
cp ~/Documents/scan_001.jpg watched-images/

# 4. Monitor the upload process
docker-compose logs -f image-upload-microservice

# Expected log output:
# INFO: file_detected - /app/watched-images/scan_001.jpg
# INFO: image_validated - File size: 2457600 bytes
# INFO: upload_started - Uploading to S3
# INFO: upload_completed - s3://bucket/uploads/2026/05/17/uuid_scan_001.jpg
# INFO: notification_sent - SQS message published
```

### Workflow 2: Batch Upload

**Scenario:** Upload multiple historical church records

```bash
# 1. Prepare batch of images
ls ~/church-records/1850-baptisms/
# page_001.jpg, page_002.jpg, page_003.jpg, ...

# 2. Copy entire directory
cp ~/church-records/1850-baptisms/*.jpg watched-images/

# 3. Monitor batch processing
docker-compose logs -f image-upload-microservice | grep -E "(file_detected|upload_completed)"

# 4. Verify uploads in S3
aws s3 ls s3://${BUCKET_NAME}/uploads/ --recursive --human-readable

# 5. Check SQS queue depth
aws sqs get-queue-attributes \
  --queue-url ${QUEUE_URL} \
  --attribute-names ApproximateNumberOfMessages \
  --query 'Attributes.ApproximateNumberOfMessages'
```

### Workflow 3: Continuous Monitoring

**Scenario:** Service runs continuously, processing files as they arrive

```bash
# 1. Start service in detached mode
docker-compose up -d

# 2. Set up file sync (e.g., from scanner to watched directory)
# Using inotify-tools or similar

# 3. Monitor service health
watch -n 10 'docker-compose ps && docker stats --no-stream image-upload-microservice'

# 4. Check processing statistics
docker-compose logs image-upload-microservice | grep -c "upload_completed"
```

### Workflow 4: Large File Upload

**Scenario:** Upload high-resolution scans (>50MB)

```bash
# 1. Configure for large files
# Edit .env:
MAX_IMAGE_SIZE_BYTES=524288000  # 500MB
MULTIPART_THRESHOLD_MB=10
UPLOAD_TIMEOUT_SECONDS=600

# 2. Restart service
docker-compose restart

# 3. Upload large file
cp ~/high-res-scan.tiff watched-images/

# 4. Monitor multipart upload progress
docker-compose logs -f image-upload-microservice | grep -E "(upload_started|upload_progress|upload_completed)"
```

## Post-Upload Actions

Configure what happens to files after successful upload:

### Option 1: Keep Files (Default)

Files remain in the watched directory:

```bash
# .env configuration
POST_UPLOAD_ACTION=keep
```

**Use case:** When you want to maintain originals or process multiple times

**Directory after upload:**
```
watched-images/
├── scan_001.jpg  (remains here)
├── scan_002.jpg  (remains here)
└── scan_003.jpg  (remains here)
```

### Option 2: Archive Files

Files are moved to archive directory:

```bash
# .env configuration
POST_UPLOAD_ACTION=archive
ARCHIVE_DIRECTORY=/app/processed-images
```

**Use case:** Organize processed files while keeping originals

**Directory after upload:**
```
watched-images/
(empty - files moved)

processed-images/
├── scan_001.jpg  (moved here)
├── scan_002.jpg  (moved here)
└── scan_003.jpg  (moved here)
```

**With subdirectory structure:**
```bash
# If WATCH_RECURSIVE=true and files in subdirectories
WATCH_RECURSIVE=true

watched-images/
└── batch-2026-05/
    └── page_001.jpg

# After processing, preserves structure:
processed-images/
└── batch-2026-05/
    └── page_001.jpg
```

### Option 3: Delete Files

Files are deleted after successful upload:

```bash
# .env configuration
POST_UPLOAD_ACTION=delete
```

**⚠️ Warning:** Use with caution! Files are permanently deleted.

**Use case:** When S3 is the primary storage and local space is limited

**Recommendation:** Test with `keep` or `archive` first, then switch to `delete` when confident.

## Testing the Service

### Test 1: Basic Functionality

```bash
# 1. Create a test image
convert -size 800x600 xc:white -pointsize 72 -draw "text 250,300 'TEST IMAGE'" test-image.jpg
# Or use any existing image

# 2. Start service with debug logging
docker-compose down
# Edit .env: LOG_LEVEL=DEBUG
docker-compose up

# 3. Copy test image
cp test-image.jpg watched-images/

# 4. Verify in logs:
# - File detected
# - Image validated
# - Upload started
# - Upload completed
# - Notification sent

# 5. Verify in S3
aws s3 ls s3://${BUCKET_NAME}/uploads/ --recursive | grep test-image

# 6. Verify SQS message
aws sqs receive-message --queue-url ${QUEUE_URL} --max-number-of-messages 1
```

### Test 2: Format Support

Test various image formats:

```bash
# Create test images in different formats
convert -size 400x300 xc:blue test.jpg
convert -size 400x300 xc:green test.png
convert -size 400x300 xc:red test.gif
convert -size 400x300 xc:yellow test.bmp

# Copy all to watched directory
cp test.{jpg,png,gif,bmp} watched-images/

# Monitor logs to verify all are processed
docker-compose logs -f image-upload-microservice | grep "upload_completed"

# Verify count
aws s3 ls s3://${BUCKET_NAME}/uploads/ --recursive | wc -l
```

### Test 3: Validation

Test that invalid files are rejected:

```bash
# Test 1: Non-image file
echo "This is not an image" > watched-images/test.txt
# Expected: File ignored or validation failed

# Test 2: Corrupt image
dd if=/dev/urandom of=watched-images/corrupt.jpg bs=1024 count=10
# Expected: Image validation failed

# Test 3: File too small
dd if=/dev/zero of=watched-images/tiny.jpg bs=1 count=100
# Expected: File size validation failed (if MIN_IMAGE_SIZE_BYTES=1024)

# Test 4: File too large (if limits configured)
# Create large dummy file
dd if=/dev/zero of=watched-images/huge.jpg bs=1M count=200
# Expected: File size exceeds maximum (if MAX_IMAGE_SIZE_BYTES is lower)

# Check logs for validation messages
docker-compose logs image-upload-microservice | grep -E "(validation_failed|file_ignored)"
```

### Test 4: Retry Logic

Test retry mechanism by temporarily breaking connectivity:

```bash
# 1. Start service normally
docker-compose up -d

# 2. Add image
cp test.jpg watched-images/

# 3. While processing, pause container (simulates network issue)
docker-compose pause image-upload-microservice

# Wait 10 seconds

# 4. Resume container
docker-compose unpause image-upload-microservice

# 5. Check logs for retry attempts
docker-compose logs image-upload-microservice | grep -E "(retry_attempted|upload_failed)"
```

### Test 5: Graceful Shutdown

Test that service shuts down cleanly:

```bash
# 1. Start service
docker-compose up -d

# 2. Start uploading a large file
cp large-scan.tiff watched-images/

# 3. Immediately send stop signal
docker-compose stop

# 4. Check logs for graceful shutdown
docker-compose logs --tail=50 image-upload-microservice

# Expected:
# - "Shutdown signal received"
# - "Completing in-progress uploads"
# - "Service stopped gracefully"
```

## Integration Testing

### End-to-End Pipeline Test

Test the complete pipeline with the OCR microservice:

#### Step 1: Start Both Services

```bash
# From the korzen directory
cd /home/user/korzen

# Start image upload service
cd image-upload-microservice
docker-compose up -d
cd ..

# Start OCR service
cd ocr-microservice
docker-compose up -d
cd ..
```

#### Step 2: Monitor Both Services

```bash
# Terminal 1: Image upload service
docker-compose -f image-upload-microservice/docker-compose.yml logs -f

# Terminal 2: OCR service
docker-compose -f ocr-microservice/docker-compose.yml logs -f
```

#### Step 3: Upload Test Image

```bash
# Copy a church record scan
cp ~/test-records/baptism-1850.jpg image-upload-microservice/watched-images/
```

#### Step 4: Verify Complete Flow

**Expected sequence:**

1. **Image Upload Service:**
   - Detects file
   - Validates image
   - Uploads to S3
   - Sends SQS message

2. **SQS Queue:**
   - Message available for consumption

3. **OCR Service:**
   - Receives SQS message
   - Downloads image from S3
   - Processes with OCR
   - Uploads result to S3
   - Deletes SQS message

**Verify results:**

```bash
# Check S3 for input image
aws s3 ls s3://${INPUT_BUCKET}/uploads/ --recursive

# Check S3 for OCR result
aws s3 ls s3://${OUTPUT_BUCKET}/ocr-results/ --recursive

# Download OCR result
aws s3 cp s3://${OUTPUT_BUCKET}/ocr-results/baptism-1850.md ./result.md
cat result.md
```

### Load Testing

Test performance under load:

```bash
# Create test dataset
mkdir -p test-images
for i in {1..100}; do
  convert -size 1920x1080 xc:white -pointsize 48 \
    -draw "text 500,500 'Test Image $i'" \
    test-images/image_$(printf "%03d" $i).jpg
done

# Start service
docker-compose up -d

# Start monitoring
docker stats image-upload-microservice &

# Copy all files at once
cp test-images/*.jpg watched-images/

# Monitor processing rate
watch -n 5 'docker-compose logs image-upload-microservice | grep -c "upload_completed"'

# Calculate throughput
START_TIME=$(date +%s)
# Wait for all files to process
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
RATE=$((100 / DURATION))
echo "Processing rate: ${RATE} files/second"
```

## Common Use Cases

### Use Case 1: Historical Document Digitization

**Scenario:** Digitizing centuries-old church records

**Setup:**
```bash
# .env configuration
S3_INPUT_BUCKET=church-records-archive
S3_INPUT_PREFIX=historical-documents/
WATCH_DIRECTORY=/app/watched-images
WATCH_RECURSIVE=true
POST_UPLOAD_ACTION=archive
ARCHIVE_DIRECTORY=/app/processed-images
SUPPORTED_EXTENSIONS=jpg,jpeg,tiff,tif,png
MAX_IMAGE_SIZE_BYTES=524288000  # 500MB for high-res scans
STRICT_VALIDATION=true
```

**Workflow:**
1. Organize source documents by year/type
2. Scan documents into watched subdirectories
3. Service automatically processes and uploads
4. Originals moved to archive
5. OCR service extracts text for database import

### Use Case 2: Automated Scanner Integration

**Scenario:** Network scanner automatically saves to watched directory

**Setup:**
```bash
# Configure scanner to save to network share
# Mount network share as watched directory

# .env configuration
WATCH_DIRECTORY=/mnt/scanner-output
WATCH_RECURSIVE=false
DEBOUNCE_SECONDS=5  # Allow time for large files to complete
POST_UPLOAD_ACTION=delete  # Scanner output is temporary
MIN_IMAGE_SIZE_BYTES=102400  # 100KB minimum (avoid incomplete scans)
```

**Workflow:**
1. User scans document on network scanner
2. Scanner saves to network location
3. Service detects new file after debounce period
4. Uploads to S3 and sends for OCR
5. Deletes local copy after successful upload

### Use Case 3: Batch Processing Existing Archives

**Scenario:** Migrate existing digitized records to cloud

**Setup:**
```bash
# .env configuration
S3_INPUT_BUCKET=migration-bucket
S3_INPUT_PREFIX=legacy-records/
POST_UPLOAD_ACTION=archive
MAX_CONCURRENT_UPLOADS=10  # Higher parallelism for batch
LOG_LEVEL=INFO
```

**Workflow:**
```bash
# 1. Start service
docker-compose up -d

# 2. Use rsync for controlled transfer
rsync -av --progress --bwlimit=10000 \
  /archive/legacy-records/ \
  watched-images/ \
  --log-file=migration.log

# 3. Monitor progress
watch 'echo "Uploaded: $(docker-compose logs image-upload-microservice | grep -c upload_completed)"; \
       echo "Pending: $(ls watched-images | wc -l)"'

# 4. Verify completion
echo "Total files: $(find processed-images -type f | wc -l)"
echo "Failed files: $(docker-compose logs image-upload-microservice | grep -c upload_failed)"
```

### Use Case 4: Multi-Location Collection

**Scenario:** Multiple locations uploading to centralized system

**Setup:** Deploy separate instances per location with different prefixes

**Location 1 (.env):**
```bash
S3_PREFIX=location-warsaw/
WATCH_DIRECTORY=/app/watched-images-warsaw
```

**Location 2 (.env):**
```bash
S3_PREFIX=location-krakow/
WATCH_DIRECTORY=/app/watched-images-krakow
```

**Central monitoring:**
```bash
# View uploads by location
aws s3 ls s3://${BUCKET_NAME}/location-warsaw/ --recursive --human-readable
aws s3 ls s3://${BUCKET_NAME}/location-krakow/ --recursive --human-readable
```

## Advanced Configuration

### Recursive Directory Watching

Monitor subdirectories for organized collections:

```bash
# .env
WATCH_RECURSIVE=true

# Directory structure
watched-images/
├── 1850/
│   ├── baptisms/
│   └── marriages/
├── 1851/
│   ├── baptisms/
│   └── marriages/
└── 1852/
    └── baptisms/

# All subdirectories are monitored
# S3 structure preserves hierarchy:
# s3://bucket/uploads/1850/baptisms/image.jpg
```

### Custom Metadata

Modify [`src/services/s3_uploader.py`](src/services/s3_uploader.py:1) to add custom metadata:

```python
# Add custom metadata based on file path
metadata = {
    'original-filename': file.name,
    'upload-timestamp': datetime.utcnow().isoformat(),
    'custom-project': 'church-records-2026',
    'custom-location': extract_location_from_path(file_path),
}
```

### Filtering by Subdirectory

Modify [`src/services/directory_watcher.py`](src/services/directory_watcher.py:1) to filter by pattern:

```python
# Only process files in specific subdirectories
if 'pending/' in str(event.src_path):
    # Process file
elif 'completed/' in str(event.src_path):
    # Skip file
```

### S3 Storage Tiers

Optimize costs with intelligent tiering:

```bash
# .env
S3_STORAGE_CLASS=INTELLIGENT_TIERING  # Auto-optimize

# Or specific tiers
S3_STORAGE_CLASS=STANDARD_IA  # Infrequent access (cheaper)
S3_STORAGE_CLASS=GLACIER       # Archive (cheapest, slower retrieval)
```

### KMS Encryption

Use AWS KMS for encryption:

```bash
# .env
S3_SERVER_SIDE_ENCRYPTION=aws:kms
# Note: Requires additional IAM permissions for KMS key
```

## Production Deployment

### AWS ECS/Fargate Deployment

#### Step 1: Create ECS Cluster

```bash
# Create cluster
aws ecs create-cluster --cluster-name image-upload-cluster

# Create ECS task execution role
aws iam create-role \
  --role-name ecsTaskExecutionRole \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "ecs-tasks.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'

aws iam attach-role-policy \
  --role-name ecsTaskExecutionRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
```

#### Step 2: Create ECR Repository

```bash
# Create repository
aws ecr create-repository --repository-name image-upload-microservice

# Get repository URI
REPO_URI=$(aws ecr describe-repositories --repository-names image-upload-microservice --query 'repositories[0].repositoryUri' --output text)

# Login to ECR
aws ecr get-login-password | docker login --username AWS --password-stdin ${REPO_URI}

# Build and push
docker build -t image-upload-microservice:latest .
docker tag image-upload-microservice:latest ${REPO_URI}:latest
docker push ${REPO_URI}:latest
```

#### Step 3: Create Task Definition

Save as `ecs-task-definition.json`:

```json
{
  "family": "image-upload-microservice",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::ACCOUNT_ID:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::ACCOUNT_ID:role/ImageUploadServiceRole",
  "containerDefinitions": [{
    "name": "image-upload-microservice",
    "image": "REPO_URI:latest",
    "essential": true,
    "logConfiguration": {
      "logDriver": "awslogs",
      "options": {
        "awslogs-group": "/ecs/image-upload-microservice",
        "awslogs-region": "us-east-1",
        "awslogs-stream-prefix": "ecs"
      }
    },
    "environment": [
      {"name": "AWS_REGION", "value": "us-east-1"},
      {"name": "LOG_LEVEL", "value": "INFO"}
    ],
    "secrets": [
      {
        "name": "S3_INPUT_BUCKET",
        "valueFrom": "arn:aws:secretsmanager:REGION:ACCOUNT:secret:image-upload/s3-bucket"
      },
      {
        "name": "IMAGE_UPLOAD_QUEUE_URL",
        "valueFrom": "arn:aws:secretsmanager:REGION:ACCOUNT:secret:image-upload/sqs-queue-url"
      }
    ],
    "mountPoints": [{
      "sourceVolume": "efs-watched-images",
      "containerPath": "/app/watched-images"
    }]
  }],
  "volumes": [{
    "name": "efs-watched-images",
    "efsVolumeConfiguration": {
      "fileSystemId": "fs-12345678",
      "transitEncryption": "ENABLED"
    }
  }]
}
```

#### Step 4: Create EFS for Watched Directory

```bash
# Create EFS
aws efs create-file-system --tags Key=Name,Value=image-upload-efs

# Create mount targets in each subnet
aws efs create-mount-target \
  --file-system-id fs-12345678 \
  --subnet-id subnet-12345678 \
  --security-groups sg-12345678
```

#### Step 5: Deploy Service

```bash
# Register task definition
aws ecs register-task-definition --cli-input-json file://ecs-task-definition.json

# Create service
aws ecs create-service \
  --cluster image-upload-cluster \
  --service-name image-upload-service \
  --task-definition image-upload-microservice:1 \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration '{
    "awsvpcConfiguration": {
      "subnets": ["subnet-12345678"],
      "securityGroups": ["sg-12345678"],
      "assignPublicIp": "DISABLED"
    }
  }'
```

### Kubernetes Deployment

See [`ARCHITECTURE.md`](ARCHITECTURE.md:1) for Kubernetes deployment manifests.

## Monitoring and Maintenance

### CloudWatch Monitoring

**Create CloudWatch Alarms:**

```bash
# High error rate alarm
aws cloudwatch put-metric-alarm \
  --alarm-name image-upload-high-error-rate \
  --alarm-description "Alert when error rate exceeds 10%" \
  --metric-name UploadFailures \
  --namespace ImageUpload \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold

# Disk usage alarm
aws cloudwatch put-metric-alarm \
  --alarm-name image-upload-disk-full \
  --alarm-description "Alert when disk usage exceeds 90%" \
  --metric-name DiskUsage \
  --namespace ImageUpload \
  --statistic Average \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 90 \
  --comparison-operator GreaterThanThreshold
```

### Regular Maintenance Tasks

**Daily:**
```bash
# Check service health
docker-compose ps

# Check disk usage
df -h /path/to/watched-images

# Review error logs
docker-compose logs --since 24h image-upload-microservice | grep ERROR
```

**Weekly:**
```bash
# Check upload statistics
docker-compose logs image-upload-microservice | grep upload_completed | wc -l

# Review retry rates
docker-compose logs image-upload-microservice | grep retry_attempted | wc -l

# Verify Archive/Processed directory size
du -sh processed-images/
```

**Monthly:**
```bash
# Update Docker images
docker-compose pull
docker-compose up -d

# Review AWS costs
aws ce get-cost-and-usage --time-period Start=2026-04-01,End=2026-05-01 \
  --granularity MONTHLY --metrics BlendedCost \
  --group-by Type=SERVICE

# Backup configuration
tar -czf config-backup-$(date +%Y%m%d).tar.gz .env docker-compose.yml
```

### Performance Optimization

**Increase throughput:**
```bash
# Increase concurrent uploads
MAX_CONCURRENT_UPLOADS=10

# Reduce debounce for faster processing
DEBOUNCE_SECONDS=1

# Use larger multipart threshold
MULTIPART_THRESHOLD_MB=20
```

**Reduce memory usage:**
```bash
# Reduce concurrent uploads
MAX_CONCURRENT_UPLOADS=1

# Limit image size
MAX_IMAGE_SIZE_BYTES=52428800  # 50MB
```

---

## 📚 Additional Resources

- **[`README.md`](README.md:1)** - Main documentation and overview
- **[`ARCHITECTURE.md`](ARCHITECTURE.md:1)** - Technical architecture details
- **[OCR Microservice](../ocr-microservice/README.md:1)** - Downstream service integration

## 💡 Tips and Best Practices

1. **Always test with `POST_UPLOAD_ACTION=keep` first** before using `archive` or `delete`
2. **Use appropriate debounce times** - longer for network filesystems or large files
3. **Monitor S3 costs** - enable S3 Intelligent-Tiering for automatic cost optimization
4. **Set up CloudWatch alarms** for production deployments
5. **Use IAM roles** instead of access keys when running on AWS infrastructure
6. **Enable S3 versioning** to protect against accidental overwrites
7. **Configure SQS Dead Letter Queue** for failed messages
8. **Regular backups** of configuration and archive directories
9. **Test disaster recovery** procedures periodically
10. **Document custom configurations** for your specific use case

---

**For technical questions or issues, refer to the [Troubleshooting section in README.md](README.md:1) or create an issue in the repository.**
