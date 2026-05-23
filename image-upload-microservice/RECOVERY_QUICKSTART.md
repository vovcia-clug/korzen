# Recovery Script Quick Start Guide

## TL;DR

```bash
# 1. Install dependencies (if not already installed)
pip install boto3 python-dotenv Pillow

# 2. Configure environment (use existing .env from microservice)
cd image-upload-microservice

# 3. Test with dry run
python recover_lost_messages.py --dry-run --limit 10

# 4. If looks good, send messages
python recover_lost_messages.py
```

## Common Use Cases

### Recover All Lost Messages

```bash
python recover_lost_messages.py
```

### Recover Messages from Specific Date

```bash
python recover_lost_messages.py \
  --start-date 2026-05-22 \
  --end-date 2026-05-22
```

### Recover Messages from Specific Directory

```bash
python recover_lost_messages.py --prefix uploads/2026/05/22/
```

### Test Before Running

```bash
# Always test first!
python recover_lost_messages.py --dry-run --verbose
```

## What It Does

1. **Scans S3 bucket** for all image files
2. **Extracts metadata** from S3 object properties
3. **Reconstructs SQS messages** in the exact format used by the microservice
4. **Sends messages** to the SQS queue

## Safety Features

- ✅ **Dry run mode** - Preview before sending
- ✅ **FIFO deduplication** - Prevents duplicate processing
- ✅ **Error handling** - Continues even if some messages fail
- ✅ **Progress tracking** - Shows what's happening

## Requirements

- Same environment variables as the microservice (`.env` file)
- AWS credentials with S3 read and SQS write permissions
- Python 3.11+ with boto3, python-dotenv, and optionally Pillow

## Full Documentation

See [`RECOVERY_SCRIPT.md`](RECOVERY_SCRIPT.md:1) for complete documentation including:
- Detailed usage examples
- Troubleshooting guide
- Performance considerations
- AWS permissions requirements

## Help

```bash
python recover_lost_messages.py --help
```
