# Migration Guide: Monolithic to Three-Service Architecture

Guide for migrating from the monolithic [`ocr-microservice/`](ocr-microservice/) to the new three-service OCR pipeline.

---

## Table of Contents

1. [Overview](#overview)
2. [Why Migrate?](#why-migrate)
3. [Migration Strategy](#migration-strategy)
4. [Pre-Migration Checklist](#pre-migration-checklist)
5. [Step-by-Step Migration](#step-by-step-migration)
6. [Data Migration](#data-migration)
7. [Testing Strategy](#testing-strategy)
8. [Rollback Procedures](#rollback-procedures)
9. [Post-Migration Validation](#post-migration-validation)
10. [Troubleshooting](#troubleshooting)

---

## Overview

### What's Changing?

**Old Architecture (Monolithic):**
```
Image → OCR → LLM (JSON) → Parser → GEDCOM Generator → Upload
```
- Single service handles entire pipeline
- Per-page processing
- Two-step GEDCOM generation (JSON → GEDCOM)

**New Architecture (Three Services):**
```
Service 1: Image → OCR → Publish
Service 2: Group Pages → LLM (Direct GEDCOM) → Publish
Service 3: Upload to S3 & Application
```
- Three specialized services
- Document-level processing
- Direct GEDCOM generation

### Key Differences

| Aspect | Old (Monolithic) | New (Three Services) |
|--------|------------------|----------------------|
| **Services** | 1 service | 3 services |
| **Processing** | Per-page | Per-document |
| **GEDCOM Generation** | JSON → Parser → GEDCOM | Direct GEDCOM from LLM |
| **Queues** | 1 queue | 3 queues |
| **Scaling** | Vertical only | Horizontal per service |
| **Context** | Single page | Full document |
| **Cost** | Higher (50 API calls/doc) | Lower (1 API call/doc) |

---

## Why Migrate?

### Benefits of New Architecture

1. **Better Quality** - Full document context improves GEDCOM accuracy
2. **Lower Costs** - 26% cost reduction through document-level processing
3. **Simplified Pipeline** - Removes intermediate parsing steps
4. **Better Scaling** - Each service scales independently
5. **Improved Relationships** - Can identify individuals across pages
6. **Faster Processing** - Single LLM call per document vs. per page

### When to Migrate

✅ **Migrate if:**
- Processing multi-page documents
- Need better relationship detection
- Want to reduce API costs
- Need independent service scaling
- Have development resources for migration

⚠️ **Consider waiting if:**
- Only processing single-page documents
- Current system meets all needs
- Limited development resources
- Need to maintain exact current behavior

---

## Migration Strategy

### Recommended Approach: Gradual Rollout

**Phase 1: Parallel Deployment (Week 1-2)**
- Deploy new services alongside old service
- Route small percentage of traffic to new pipeline
- Compare outputs and quality

**Phase 2: Gradual Increase (Week 3-4)**
- Increase traffic to new pipeline incrementally
- Monitor quality metrics and costs
- Adjust configuration as needed

**Phase 3: Full Cutover (Week 5)**
- Route all traffic to new pipeline
- Keep old service running for 1 week as backup
- Monitor for issues

**Phase 4: Decommission (Week 6)**
- Stop old service
- Archive old code
- Update documentation

### Alternative: Big Bang Migration

**Only recommended if:**
- Low traffic volume
- Can afford downtime
- Have comprehensive test coverage
- Can quickly rollback if needed

---

## Pre-Migration Checklist

### Infrastructure Preparation

- [ ] AWS account with sufficient permissions
- [ ] Three SQS queues created (image-upload, ocr-results, gedcom-ready)
- [ ] Three S3 buckets configured (input, ocr-results, gedcom-output)
- [ ] IAM roles created for each service
- [ ] Secrets stored in AWS Secrets Manager
- [ ] CloudWatch logging configured
- [ ] Monitoring dashboards created

### API Keys & Credentials

- [ ] Datalab API key obtained and tested
- [ ] OpenRouter API key obtained and tested
- [ ] Application API key obtained (if using upload service)
- [ ] All keys stored in Secrets Manager
- [ ] IAM roles have access to secrets

### Code Preparation

- [ ] New services cloned from repository
- [ ] Docker images built successfully
- [ ] Environment variables configured
- [ ] Local testing completed
- [ ] Integration tests passing

### Team Preparation

- [ ] Team trained on new architecture
- [ ] Runbooks updated
- [ ] On-call procedures updated
- [ ] Rollback plan documented
- [ ] Communication plan ready

---

## Step-by-Step Migration

### Step 1: Deploy Infrastructure (Day 1)

```bash
# Follow DEPLOYMENT_GUIDE.md sections:
# 1. Create S3 buckets
# 2. Create SQS queues
# 3. Configure IAM roles
# 4. Store secrets

# Verify infrastructure
aws s3 ls
aws sqs list-queues
aws iam list-roles | grep ocr-pipeline
```

### Step 2: Deploy New Services (Day 2-3)

```bash
# Build and push Docker images
cd ocr-image-microservice
docker build -t ocr-image-service:v1 .
# Push to ECR (see DEPLOYMENT_GUIDE.md)

cd ../gedcom-generation-microservice
docker build -t gedcom-generation-service:v1 .
# Push to ECR

cd ../gedcom-upload-microservice
docker build -t gedcom-upload-service:v1 .
# Push to ECR

# Deploy to ECS
# Follow DEPLOYMENT_GUIDE.md ECS deployment section
```

### Step 3: Configure Traffic Routing (Day 4)

**Option A: Separate Input Bucket**
```bash
# Create new input bucket for new pipeline
aws s3 mb s3://new-pipeline-images

# Configure S3 event notification to new queue
# Upload test images to new bucket
```

**Option B: Prefix-Based Routing**
```bash
# Configure S3 event notification with prefix filter
# Old: prefix="legacy/"
# New: prefix="new/"

# Upload to different prefixes based on routing
```

**Option C: Dual Processing (Recommended for testing)**
```bash
# Configure S3 to send events to BOTH queues
# Process same images through both pipelines
# Compare outputs
```

### Step 4: Test with Sample Data (Day 5-7)

```bash
# Upload test document (10 pages)
for i in {1..10}; do
  aws s3 cp test-page-$i.jpg \
    s3://new-pipeline-images/test-doc/page-$(printf "%03d" $i).jpg \
    --tagging "document_id=test-doc&page_number=$i&total_pages=10"
done

# Monitor processing
watch -n 5 'aws sqs get-queue-attributes \
  --queue-url $IMAGE_UPLOAD_QUEUE_URL \
  --attribute-names ApproximateNumberOfMessages'

# Verify output
aws s3 ls s3://gedcom-output-bucket/gedcom-files/test-doc/
aws s3 cp s3://gedcom-output-bucket/gedcom-files/test-doc/test-doc.ged ./
```

### Step 5: Gradual Traffic Increase (Week 2-4)

**Week 2: 10% Traffic**
```bash
# Route 10% of new uploads to new pipeline
# Monitor metrics:
# - Processing time
# - Error rate
# - GEDCOM quality
# - Cost per document
```

**Week 3: 50% Traffic**
```bash
# Increase to 50% if Week 2 successful
# Continue monitoring
# Compare quality metrics with old pipeline
```

**Week 4: 100% Traffic**
```bash
# Route all traffic to new pipeline
# Keep old pipeline running as backup
# Monitor closely for issues
```

### Step 6: Decommission Old Service (Week 5-6)

```bash
# Week 5: Stop accepting new requests to old service
# Let old service finish processing existing queue

# Week 6: Stop old service
aws ecs update-service \
  --cluster old-cluster \
  --service ocr-microservice \
  --desired-count 0

# Archive old service code
git tag v1-monolithic-final
git push --tags

# Update documentation
# Remove old service from monitoring
```

---

## Data Migration

### Existing Data Considerations

**Scenario 1: No Existing Data**
- Fresh start with new pipeline
- No migration needed

**Scenario 2: Reprocess Existing Images**
```bash
# List all existing images
aws s3 ls s3://old-input-bucket/ --recursive > existing-images.txt

# Add metadata tags to existing images
while read image; do
  # Extract document_id and page_number from path
  # Add tags
  aws s3api put-object-tagging \
    --bucket old-input-bucket \
    --key "$image" \
    --tagging "TagSet=[{Key=document_id,Value=...},{Key=page_number,Value=...}]"
done < existing-images.txt

# Trigger reprocessing by copying to new bucket
aws s3 sync s3://old-input-bucket/ s3://new-input-bucket/
```

**Scenario 3: Keep Existing GEDCOM Files**
```bash
# Copy existing GEDCOM files to new bucket
aws s3 sync \
  s3://old-output-bucket/ \
  s3://new-output-bucket/legacy/ \
  --exclude "*" --include "*.ged"

# No reprocessing needed
```

### Metadata Migration

**Add Required Metadata to Images:**
```python
import boto3
import re

s3 = boto3.client('s3')

def add_metadata_tags(bucket, key):
    # Extract from path: documents/{doc_id}/page-{num}.jpg
    match = re.match(r'documents/([^/]+)/page-(\d+)\.jpg', key)
    if match:
        doc_id = match.group(1)
        page_num = match.group(2)
        
        # Add tags
        s3.put_object_tagging(
            Bucket=bucket,
            Key=key,
            Tagging={
                'TagSet': [
                    {'Key': 'document_id', 'Value': doc_id},
                    {'Key': 'page_number', 'Value': page_num},
                    # Add more metadata as needed
                ]
            }
        )

# Process all images
paginator = s3.get_paginator('list_objects_v2')
for page in paginator.paginate(Bucket='old-input-bucket'):
    for obj in page.get('Contents', []):
        add_metadata_tags('old-input-bucket', obj['Key'])
```

---

## Testing Strategy

### Unit Testing

```bash
# Test each service independently
cd ocr-image-microservice
python -m pytest tests/unit/

cd ../gedcom-generation-microservice
python -m pytest tests/unit/

cd ../gedcom-upload-microservice
python -m pytest tests/unit/
```

### Integration Testing

```bash
# Test service-to-service communication
# Use LocalStack for local AWS services
docker-compose -f docker-compose.full-pipeline.yml up -d

# Upload test image
aws --endpoint-url=http://localhost:4566 s3 cp test.jpg s3://test-bucket/test-doc/page-001.jpg

# Monitor logs
docker-compose -f docker-compose.full-pipeline.yml logs -f
```

### End-to-End Testing

```bash
# Test complete pipeline with real AWS services
# Upload multi-page document
for i in {1..5}; do
  aws s3 cp test-page-$i.jpg \
    s3://${INPUT_BUCKET}/e2e-test/page-$(printf "%03d" $i).jpg \
    --tagging "document_id=e2e-test&page_number=$i&total_pages=5"
done

# Wait for processing (5-10 minutes)
sleep 600

# Verify GEDCOM output
aws s3 cp s3://${GEDCOM_OUTPUT_BUCKET}/gedcom-files/e2e-test/e2e-test.ged ./
cat e2e-test.ged

# Validate GEDCOM
python -c "
import re
content = open('e2e-test.ged').read()
assert content.startswith('0 HEAD'), 'Missing GEDCOM header'
assert '0 TRLR' in content, 'Missing GEDCOM trailer'
print('✓ GEDCOM validation passed')
"
```

### Quality Comparison Testing

```bash
# Process same document through both pipelines
# Compare outputs

# Old pipeline output
OLD_GEDCOM="old-output.ged"

# New pipeline output
NEW_GEDCOM="new-output.ged"

# Compare metrics
python compare_gedcom.py $OLD_GEDCOM $NEW_GEDCOM
```

**compare_gedcom.py:**
```python
import sys
import re

def count_records(gedcom_file):
    content = open(gedcom_file).read()
    individuals = len(re.findall(r'^0 @I\d+@ INDI', content, re.MULTILINE))
    families = len(re.findall(r'^0 @F\d+@ FAM', content, re.MULTILINE))
    return individuals, families

old_ind, old_fam = count_records(sys.argv[1])
new_ind, new_fam = count_records(sys.argv[2])

print(f"Old: {old_ind} individuals, {old_fam} families")
print(f"New: {new_ind} individuals, {new_fam} families")
print(f"Difference: {new_ind - old_ind} individuals, {new_fam - old_fam} families")
```

### Load Testing

```bash
# Upload 100 documents (10 pages each)
for doc in {1..100}; do
  for page in {1..10}; do
    aws s3 cp test-page.jpg \
      s3://${INPUT_BUCKET}/load-test-$doc/page-$(printf "%03d" $page).jpg \
      --tagging "document_id=load-test-$doc&page_number=$page&total_pages=10" &
  done
done
wait

# Monitor processing
watch -n 10 'echo "Queue Depths:" && \
  aws sqs get-queue-attributes --queue-url $IMAGE_UPLOAD_QUEUE_URL --attribute-names ApproximateNumberOfMessages && \
  aws sqs get-queue-attributes --queue-url $OCR_RESULTS_QUEUE_URL --attribute-names ApproximateNumberOfMessages && \
  aws sqs get-queue-attributes --queue-url $GEDCOM_READY_QUEUE_URL --attribute-names ApproximateNumberOfMessages'
```

---

## Rollback Procedures

### When to Rollback

Rollback if:
- Error rate > 10% for > 15 minutes
- Data loss detected
- Critical bug discovered
- Performance degradation > 50%
- Cost increase > 50% unexpectedly

### Rollback Steps

**Step 1: Stop New Services**
```bash
# Stop accepting new requests
aws ecs update-service \
  --cluster ocr-pipeline-cluster \
  --service ocr-image-service \
  --desired-count 0

aws ecs update-service \
  --cluster ocr-pipeline-cluster \
  --service gedcom-generation-service \
  --desired-count 0

aws ecs update-service \
  --cluster ocr-pipeline-cluster \
  --service gedcom-upload-service \
  --desired-count 0
```

**Step 2: Restart Old Service**
```bash
# Scale up old service
aws ecs update-service \
  --cluster old-cluster \
  --service ocr-microservice \
  --desired-count 3
```

**Step 3: Redirect Traffic**
```bash
# Update S3 event notification to old queue
aws s3api put-bucket-notification-configuration \
  --bucket ${INPUT_BUCKET} \
  --notification-configuration file://old-notification-config.json
```

**Step 4: Process Stuck Messages**
```bash
# Move messages from new queues to old queue
# Or let them expire and reprocess images
```

**Step 5: Communicate**
```bash
# Notify team of rollback
# Update status page
# Document rollback reason
```

### Post-Rollback Analysis

1. **Identify root cause** - Review logs and metrics
2. **Document issues** - Create detailed incident report
3. **Fix problems** - Address issues in new services
4. **Test fixes** - Comprehensive testing before retry
5. **Plan retry** - Schedule new migration attempt

---

## Post-Migration Validation

### Validation Checklist

- [ ] All services running and healthy
- [ ] Queue depths stable (< 10 messages)
- [ ] Error rate < 1%
- [ ] Processing time within expected range
- [ ] GEDCOM quality meets standards
- [ ] Cost per document as expected
- [ ] No data loss
- [ ] Monitoring and alerts working
- [ ] Documentation updated
- [ ] Team trained on new system

### Metrics to Monitor (First 2 Weeks)

**Service Health:**
- Uptime: Target 99.9%
- Error rate: Target < 1%
- Response time: Target < 5 min per document

**Queue Metrics:**
- Queue depth: Target < 10 messages
- Message age: Target < 5 minutes
- DLQ messages: Target 0

**Quality Metrics:**
- GEDCOM validation rate: Target 100%
- Individual count per document: Compare with baseline
- Family count per document: Compare with baseline

**Cost Metrics:**
- Cost per document: Target 26% reduction
- API calls per document: Target 1 (vs 50)
- S3 storage costs: Monitor growth

### Success Criteria

Migration is successful if:
- ✅ All services stable for 2 weeks
- ✅ Error rate < 1%
- ✅ Quality metrics match or exceed old pipeline
- ✅ Cost reduction achieved (target 26%)
- ✅ No critical bugs
- ✅ Team comfortable with new system

---

## Troubleshooting

### Common Migration Issues

#### Issue: Messages stuck in queue

**Symptoms:**
- Queue depth increasing
- No processing activity

**Solutions:**
1. Check service is running
2. Verify IAM permissions
3. Check queue URLs in configuration
4. Review service logs for errors

```bash
# Check service status
aws ecs describe-services --cluster ocr-pipeline-cluster --services ocr-image-service

# Check logs
aws logs tail /ecs/ocr-image-service --follow
```

#### Issue: GEDCOM quality lower than expected

**Symptoms:**
- Fewer individuals/families than old pipeline
- Missing relationships
- Validation errors

**Solutions:**
1. Review LLM prompts
2. Check document grouping logic
3. Verify metadata completeness
4. Try different LLM model

```bash
# Compare outputs
python compare_gedcom.py old-output.ged new-output.ged

# Review grouping logs
aws logs filter-pattern "document_id" /ecs/gedcom-generation-service
```

#### Issue: Higher costs than expected

**Symptoms:**
- AWS bill higher than projected
- More API calls than expected

**Solutions:**
1. Check for retry loops
2. Verify document grouping working
3. Review token usage per document
4. Check for duplicate processing

```bash
# Check API call counts
aws cloudwatch get-metric-statistics \
  --namespace AWS/SQS \
  --metric-name NumberOfMessagesSent \
  --start-time $(date -u -d '1 day ago' +%s) \
  --end-time $(date -u +%s) \
  --period 3600 \
  --statistics Sum
```

#### Issue: Data loss

**Symptoms:**
- Images processed but no GEDCOM output
- Messages disappearing from queues

**Solutions:**
1. Check dead letter queues
2. Review service logs for errors
3. Verify S3 bucket permissions
4. Check visibility timeout settings

```bash
# Check DLQ
aws sqs get-queue-attributes \
  --queue-url $IMAGE_UPLOAD_DLQ_URL \
  --attribute-names ApproximateNumberOfMessages

# Recover messages from DLQ
aws sqs receive-message --queue-url $IMAGE_UPLOAD_DLQ_URL --max-number-of-messages 10
```

---

## Support During Migration

### Getting Help

- **Documentation:** Review service READMEs and architecture docs
- **Logs:** Check CloudWatch logs for detailed error messages
- **Metrics:** Review CloudWatch dashboards
- **Team:** Escalate to senior engineers if needed

### Migration Support Checklist

- [ ] Dedicated migration team assigned
- [ ] Daily standup during migration period
- [ ] 24/7 on-call coverage
- [ ] Rollback plan tested and ready
- [ ] Communication channels established
- [ ] Stakeholders informed of timeline

---

## Conclusion

Migrating to the three-service architecture provides significant benefits in quality, cost, and scalability. Follow this guide carefully, test thoroughly, and don't hesitate to rollback if issues arise.

**Key Success Factors:**
- ✅ Thorough testing before migration
- ✅ Gradual rollout with monitoring
- ✅ Clear rollback procedures
- ✅ Team training and preparation
- ✅ Continuous monitoring and validation

For deployment details, see [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md).

For architecture details, see [ARCHITECTURE_OVERVIEW.md](ARCHITECTURE_OVERVIEW.md).

**Good luck with your migration!** 🚀
