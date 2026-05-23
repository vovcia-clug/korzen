# Message Recovery Script Documentation

## Overview

The [`recover_lost_messages.py`](recover_lost_messages.py:1) script is a standalone recovery tool designed to scan the S3 bucket and resend SQS messages for images that were uploaded but their messages were lost. This can happen due to:

- SQS queue issues or downtime
- Network failures during message sending
- Service crashes after S3 upload but before SQS notification
- Manual S3 uploads outside the microservice

## Features

✅ **Dry Run Mode**: Preview what would be sent without actually sending messages  
✅ **Date Range Filtering**: Process only images within a specific date range  
✅ **Prefix Filtering**: Target specific S3 prefixes or subdirectories  
✅ **Limit Control**: Process a limited number of images for testing  
✅ **FIFO Queue Support**: Automatically detects and handles FIFO queues  
✅ **Image Dimension Extraction**: Optionally extracts image dimensions using PIL  
✅ **Message Format Matching**: Reconstructs messages in the exact format used by the microservice  
✅ **Progress Tracking**: Shows detailed progress and summary statistics  
✅ **Error Handling**: Continues processing even if individual messages fail  

## Prerequisites

### Required Dependencies

The script requires the same dependencies as the microservice:

```bash
pip install boto3 python-dotenv
```

### Optional Dependencies

For image dimension extraction (recommended):

```bash
pip install Pillow
```

If Pillow is not installed, the script will still work but won't extract image dimensions.

### AWS Permissions

The script requires the following IAM permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "S3ReadPermissions",
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket",
        "s3:GetObject",
        "s3:GetObjectMetadata",
        "s3:HeadObject"
      ],
      "Resource": [
        "arn:aws:s3:::YOUR_BUCKET_NAME",
        "arn:aws:s3:::YOUR_BUCKET_NAME/*"
      ]
    },
    {
      "Sid": "SQSPublishPermissions",
      "Effect": "Allow",
      "Action": [
        "sqs:SendMessage",
        "sqs:GetQueueAttributes"
      ],
      "Resource": "arn:aws:sqs:REGION:ACCOUNT_ID:QUEUE_NAME"
    }
  ]
}
```

## Configuration

The script uses the same environment variables as the microservice. Create a [`.env`](.env.example:1) file or set environment variables:

### Required Variables

```bash
# AWS Configuration
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_access_key_here
AWS_SECRET_ACCESS_KEY=your_secret_key_here

# S3 Configuration
S3_INPUT_BUCKET=my-images-bucket

# SQS Configuration
IMAGE_UPLOAD_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/123456789012/image-upload-queue
```

### Optional Variables

```bash
# S3 prefix (default: "")
S3_INPUT_PREFIX=uploads/

# Supported image extensions (default: jpg,jpeg,png,gif,bmp,tiff,tif,webp)
SUPPORTED_EXTENSIONS=jpg,jpeg,png,gif,bmp,tiff,tif,webp
```

## Usage

### Basic Usage

#### 1. Dry Run (Recommended First Step)

Always start with a dry run to preview what would be sent:

```bash
python recover_lost_messages.py --dry-run
```

This will:
- Scan the S3 bucket
- Show how many images would be processed
- Display what messages would be sent
- **Not actually send any messages**

#### 2. Send Messages

Once you've verified the dry run output, send the messages:

```bash
python recover_lost_messages.py
```

### Advanced Usage

#### Filter by Date Range

Process only images uploaded within a specific date range:

```bash
# Images from May 2026
python recover_lost_messages.py \
  --start-date 2026-05-01 \
  --end-date 2026-05-31

# Images from the last week
python recover_lost_messages.py \
  --start-date 2026-05-16 \
  --end-date 2026-05-23
```

#### Filter by S3 Prefix

Process only images in a specific S3 prefix:

```bash
# Process only images in uploads/2026/05/
python recover_lost_messages.py --prefix uploads/2026/05/

# Process images in a specific subdirectory
python recover_lost_messages.py --prefix uploads/archive/batch-001/
```

#### Limit Number of Messages

Process only a limited number of images (useful for testing):

```bash
# Process only the first 10 images
python recover_lost_messages.py --limit 10

# Dry run with limit
python recover_lost_messages.py --dry-run --limit 5
```

#### Verbose Output

Enable detailed output for debugging:

```bash
python recover_lost_messages.py --verbose

# Verbose dry run
python recover_lost_messages.py --dry-run --verbose
```

#### Skip Image Dimension Extraction

If you don't need image dimensions or don't have Pillow installed:

```bash
python recover_lost_messages.py --no-extract-dimensions
```

### Combined Examples

#### Test with a Small Batch

```bash
# Dry run with first 10 images from May 2026
python recover_lost_messages.py \
  --dry-run \
  --start-date 2026-05-01 \
  --end-date 2026-05-31 \
  --limit 10 \
  --verbose
```

#### Process Specific Subdirectory

```bash
# Process all images in a specific subdirectory
python recover_lost_messages.py \
  --prefix uploads/2026/05/batch-001/ \
  --verbose
```

#### Large-Scale Recovery

```bash
# Process all images from a specific month
python recover_lost_messages.py \
  --start-date 2026-05-01 \
  --end-date 2026-05-31
```

## Output

### Dry Run Output

```
======================================================================
Image Upload Microservice - Message Recovery Script
======================================================================

⚠️  DRY RUN MODE - No messages will be sent

Loading configuration...
  S3 Bucket: my-images-bucket
  S3 Prefix: uploads/
  SQS Queue: https://sqs.us-east-1.amazonaws.com/123456789012/image-upload-queue
  FIFO Queue: False
  Supported Extensions: .jpg, .jpeg, .png, .gif, .bmp, .tiff, .tif, .webp

Scanning S3 bucket for images...
Scanning S3 bucket: s3://my-images-bucket/uploads/
Found 150 image objects

Processing 150 images...

[DRY RUN] Would send message for: s3://my-images-bucket/uploads/image001.jpg
[DRY RUN] Would send message for: s3://my-images-bucket/uploads/image002.jpg
...

======================================================================
Summary
======================================================================
Total images processed: 150
Messages sent successfully: 150
Errors: 0

⚠️  This was a DRY RUN - no messages were actually sent
Run without --dry-run to send messages to the queue
```

### Actual Run Output

```
======================================================================
Image Upload Microservice - Message Recovery Script
======================================================================

Loading configuration...
  S3 Bucket: my-images-bucket
  S3 Prefix: uploads/
  SQS Queue: https://sqs.us-east-1.amazonaws.com/123456789012/image-upload-queue
  FIFO Queue: False
  Supported Extensions: .jpg, .jpeg, .png, .gif, .bmp, .tiff, .tif, .webp

Scanning S3 bucket for images...
Scanning S3 bucket: s3://my-images-bucket/uploads/
Found 150 image objects

Processing 150 images...

✓ Sent message abc123... for: s3://my-images-bucket/uploads/image001.jpg
✓ Sent message def456... for: s3://my-images-bucket/uploads/image002.jpg
✗ Error sending message for s3://my-images-bucket/uploads/image003.jpg: AccessDenied
✓ Sent message ghi789... for: s3://my-images-bucket/uploads/image004.jpg
...

======================================================================
Summary
======================================================================
Total images processed: 150
Messages sent successfully: 149
Errors: 1
```

## Message Format

The script reconstructs messages in the exact format used by the microservice:

```json
{
  "s3_uri": "s3://bucket-name/uploads/image.jpg",
  "metadata": {
    "original_filename": "image.jpg",
    "upload_timestamp": "2026-05-23T21:00:00.000Z",
    "file_size_bytes": 2457600,
    "content_type": "image/jpeg",
    "image_dimensions": {
      "width": 1920,
      "height": 1080
    },
    "file_hash": {
      "value": "abc123...",
      "algorithm": "sha256"
    },
    "image_format": "JPEG"
  },
  "source_service": "image-upload-microservice",
  "message_version": "1.0"
}
```

### Metadata Extraction

The script attempts to extract metadata from multiple sources:

1. **S3 Object Metadata**: Custom metadata attached during upload
2. **S3 Object Properties**: Content-Type, Content-Length, LastModified, ETag
3. **Image Analysis**: Dimensions extracted using PIL (if available)
4. **Inference**: Image format inferred from file extension

### FIFO Queue Handling

For FIFO queues (`.fifo` suffix), the script automatically adds:

- **MessageGroupId**: `image-uploads-recovery`
- **MessageDeduplicationId**: File hash (if available) or SHA-256 of S3 URI

This prevents duplicate processing if the script is run multiple times.

## Troubleshooting

### Common Issues

#### 1. "S3_INPUT_BUCKET environment variable is required"

**Solution**: Set the required environment variables in `.env` file or export them:

```bash
export S3_INPUT_BUCKET=my-images-bucket
export IMAGE_UPLOAD_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/...
```

#### 2. "NoCredentialsError"

**Solution**: Set AWS credentials:

```bash
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
```

Or use IAM roles if running on EC2/ECS.

#### 3. "AccessDenied" errors

**Solution**: Verify IAM permissions for S3 and SQS. See [AWS Permissions](#aws-permissions) section.

#### 4. "No images found matching the criteria"

**Possible causes**:
- Wrong S3 bucket or prefix
- Date range too restrictive
- No images with supported extensions

**Solution**: 
- Verify bucket name and prefix
- Check date range filters
- Use `--verbose` to see detailed scanning output

#### 5. "Warning: PIL/Pillow not available"

**Impact**: Image dimensions won't be extracted (non-critical)

**Solution**: Install Pillow:

```bash
pip install Pillow
```

#### 6. Messages sent but not appearing in queue

**Possible causes**:
- Wrong queue URL
- FIFO queue deduplication (messages already sent)
- Queue visibility timeout

**Solution**:
- Verify queue URL
- Check SQS console for messages
- For FIFO queues, check if messages were already sent (deduplication)

### Debugging

Enable verbose output to see detailed information:

```bash
python recover_lost_messages.py --dry-run --verbose
```

This will show:
- Detailed S3 scanning progress
- Full message bodies
- Error stack traces
- Metadata extraction details

## Safety Features

### 1. Dry Run Mode

Always test with `--dry-run` first to preview what would be sent.

### 2. FIFO Deduplication

For FIFO queues, the script uses message deduplication to prevent duplicate processing if run multiple times.

### 3. Error Handling

The script continues processing even if individual messages fail, ensuring maximum recovery.

### 4. Progress Tracking

Clear progress indicators and summary statistics help monitor the recovery process.

### 5. Limit Control

Use `--limit` to process a small batch first for testing.

## Best Practices

### 1. Start with Dry Run

```bash
# Always start with a dry run
python recover_lost_messages.py --dry-run --limit 10
```

### 2. Test with Small Batch

```bash
# Test with first 10 images
python recover_lost_messages.py --limit 10
```

### 3. Use Date Filters

```bash
# Process specific time period
python recover_lost_messages.py \
  --start-date 2026-05-20 \
  --end-date 2026-05-23
```

### 4. Monitor Progress

```bash
# Use verbose mode for large batches
python recover_lost_messages.py --verbose
```

### 5. Verify Results

After running the script:
- Check SQS queue for messages
- Monitor downstream services (OCR microservice)
- Verify message counts match expectations

## Integration with Microservice

The recovery script is designed to work seamlessly with the image-upload-microservice:

1. **Same Configuration**: Uses the same environment variables
2. **Same Message Format**: Reconstructs messages in the exact format
3. **Same AWS Resources**: Uses the same S3 bucket and SQS queue
4. **Compatible Metadata**: Preserves all metadata from original uploads

## Performance Considerations

### Scanning Speed

- **Small buckets** (<1000 objects): ~1-2 seconds
- **Medium buckets** (1000-10000 objects): ~10-30 seconds
- **Large buckets** (>10000 objects): ~1-5 minutes

### Message Sending Speed

- **Standard queue**: ~100-200 messages/second
- **FIFO queue**: ~10-20 messages/second (due to ordering guarantees)

### Memory Usage

- **Minimal**: Processes objects one at a time
- **Image dimension extraction**: Downloads only first 64KB of each image

### Optimization Tips

1. **Use prefix filtering** to reduce scanning time
2. **Use date filters** to target specific time periods
3. **Use `--no-extract-dimensions`** to skip dimension extraction
4. **Process in batches** using `--limit` for very large buckets

## Examples

### Scenario 1: Complete Queue Failure

All messages lost for a specific day:

```bash
# Dry run first
python recover_lost_messages.py \
  --dry-run \
  --start-date 2026-05-22 \
  --end-date 2026-05-22

# If looks good, send messages
python recover_lost_messages.py \
  --start-date 2026-05-22 \
  --end-date 2026-05-22
```

### Scenario 2: Partial Failure

Some messages lost in a specific subdirectory:

```bash
# Target specific prefix
python recover_lost_messages.py \
  --prefix uploads/2026/05/22/batch-003/
```

### Scenario 3: Manual S3 Uploads

Images uploaded directly to S3 (bypassing microservice):

```bash
# Process all images in manual upload directory
python recover_lost_messages.py \
  --prefix uploads/manual/
```

### Scenario 4: Testing Recovery Process

Test the recovery process before production use:

```bash
# Test with small batch
python recover_lost_messages.py \
  --dry-run \
  --limit 5 \
  --verbose
```

## Monitoring

### Metrics to Track

- **Total images scanned**: Number of images found in S3
- **Messages sent successfully**: Number of messages sent to SQS
- **Errors**: Number of failures
- **Success rate**: (Messages sent / Total images) × 100%

### Logging

The script outputs structured logs that can be parsed for monitoring:

```
✓ Sent message abc123... for: s3://bucket/image.jpg
✗ Error sending message for s3://bucket/image.jpg: AccessDenied
```

### Alerting

Consider setting up alerts for:
- High error rates (>5%)
- Large number of images requiring recovery
- Repeated recovery runs (may indicate ongoing issues)

## Support

For issues or questions:

1. Check this documentation
2. Review the [main README](README.md:1)
3. Check the [microservice architecture](ARCHITECTURE.md:1)
4. Review AWS CloudWatch logs for the microservice

## Changelog

### Version 1.0.0

- ✅ Initial release
- ✅ S3 bucket scanning with pagination
- ✅ Message reconstruction matching microservice format
- ✅ SQS message sending with retry logic
- ✅ Dry run mode
- ✅ Date range filtering
- ✅ Prefix filtering
- ✅ Limit control
- ✅ FIFO queue support
- ✅ Image dimension extraction
- ✅ Verbose output mode
- ✅ Error handling and progress tracking
- ✅ Comprehensive documentation

---

**Made with ❤️ for reliable message recovery**
