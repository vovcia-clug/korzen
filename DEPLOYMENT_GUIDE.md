# OCR Pipeline Deployment Guide

Complete step-by-step guide for deploying the three-service OCR-to-GEDCOM pipeline.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [AWS Infrastructure Setup](#aws-infrastructure-setup)
3. [Local Development Setup](#local-development-setup)
4. [Docker Deployment](#docker-deployment)
5. [AWS ECS/Fargate Deployment](#aws-ecsfargate-deployment)
6. [Configuration Management](#configuration-management)
7. [Monitoring Setup](#monitoring-setup)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Accounts & Access

- **AWS Account** with administrative access
- **Datalab API Key** for OCR processing
- **OpenRouter API Key** for GEDCOM generation
- **Hosted Application** URL and API key (optional)

### Required Tools

```bash
# AWS CLI
aws --version  # Should be 2.x or higher

# Docker & Docker Compose
docker --version  # Should be 20.x or higher
docker-compose --version  # Should be 1.29.x or higher

# Python (for local development)
python --version  # Should be 3.11 or higher

# Git
git --version
```

### Install AWS CLI

```bash
# macOS
brew install awscli

# Linux
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Windows
# Download and run: https://awscli.amazonaws.com/AWSCLIV2.msi
```

### Configure AWS CLI

```bash
aws configure
# AWS Access Key ID: YOUR_ACCESS_KEY
# AWS Secret Access Key: YOUR_SECRET_KEY
# Default region name: us-east-1
# Default output format: json
```

---

## AWS Infrastructure Setup

### Step 1: Create S3 Buckets

```bash
# Set your bucket names (must be globally unique)
export INPUT_BUCKET="your-project-images-input"
export OCR_RESULTS_BUCKET="your-project-ocr-results"
export GEDCOM_OUTPUT_BUCKET="your-project-gedcom-output"
export AWS_REGION="us-east-1"

# Create buckets
aws s3 mb s3://${INPUT_BUCKET} --region ${AWS_REGION}
aws s3 mb s3://${OCR_RESULTS_BUCKET} --region ${AWS_REGION}
aws s3 mb s3://${GEDCOM_OUTPUT_BUCKET} --region ${AWS_REGION}

# Enable versioning (recommended)
aws s3api put-bucket-versioning \
  --bucket ${INPUT_BUCKET} \
  --versioning-configuration Status=Enabled

aws s3api put-bucket-versioning \
  --bucket ${OCR_RESULTS_BUCKET} \
  --versioning-configuration Status=Enabled

aws s3api put-bucket-versioning \
  --bucket ${GEDCOM_OUTPUT_BUCKET} \
  --versioning-configuration Status=Enabled

# Enable encryption
aws s3api put-bucket-encryption \
  --bucket ${INPUT_BUCKET} \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }]
  }'

# Repeat for other buckets
aws s3api put-bucket-encryption --bucket ${OCR_RESULTS_BUCKET} \
  --server-side-encryption-configuration '{"Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]}'

aws s3api put-bucket-encryption --bucket ${GEDCOM_OUTPUT_BUCKET} \
  --server-side-encryption-configuration '{"Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]}'
```

### Step 2: Create SQS Queues

```bash
# Create main queues
aws sqs create-queue \
  --queue-name image-upload-queue \
  --attributes VisibilityTimeout=300,MessageRetentionPeriod=1209600

aws sqs create-queue \
  --queue-name ocr-results-queue \
  --attributes VisibilityTimeout=300,MessageRetentionPeriod=1209600

aws sqs create-queue \
  --queue-name gedcom-ready-queue \
  --attributes VisibilityTimeout=300,MessageRetentionPeriod=1209600

# Create dead letter queues
aws sqs create-queue --queue-name image-upload-queue-dlq
aws sqs create-queue --queue-name ocr-results-queue-dlq
aws sqs create-queue --queue-name gedcom-ready-queue-dlq

# Get queue URLs and ARNs
export IMAGE_UPLOAD_QUEUE_URL=$(aws sqs get-queue-url --queue-name image-upload-queue --query 'QueueUrl' --output text)
export OCR_RESULTS_QUEUE_URL=$(aws sqs get-queue-url --queue-name ocr-results-queue --query 'QueueUrl' --output text)
export GEDCOM_READY_QUEUE_URL=$(aws sqs get-queue-url --queue-name gedcom-ready-queue --query 'QueueUrl' --output text)

echo "IMAGE_UPLOAD_QUEUE_URL=${IMAGE_UPLOAD_QUEUE_URL}"
echo "OCR_RESULTS_QUEUE_URL=${OCR_RESULTS_QUEUE_URL}"
echo "GEDCOM_READY_QUEUE_URL=${GEDCOM_READY_QUEUE_URL}"
```

### Step 3: Configure Dead Letter Queues

```bash
# Get DLQ ARNs
export IMAGE_DLQ_ARN=$(aws sqs get-queue-attributes \
  --queue-url $(aws sqs get-queue-url --queue-name image-upload-queue-dlq --query 'QueueUrl' --output text) \
  --attribute-names QueueArn --query 'Attributes.QueueArn' --output text)

export OCR_DLQ_ARN=$(aws sqs get-queue-attributes \
  --queue-url $(aws sqs get-queue-url --queue-name ocr-results-queue-dlq --query 'QueueUrl' --output text) \
  --attribute-names QueueArn --query 'Attributes.QueueArn' --output text)

export GEDCOM_DLQ_ARN=$(aws sqs get-queue-attributes \
  --queue-url $(aws sqs get-queue-url --queue-name gedcom-ready-queue-dlq --query 'QueueUrl' --output text) \
  --attribute-names QueueArn --query 'Attributes.QueueArn' --output text)

# Configure redrive policies
aws sqs set-queue-attributes \
  --queue-url ${IMAGE_UPLOAD_QUEUE_URL} \
  --attributes RedrivePolicy="{\"deadLetterTargetArn\":\"${IMAGE_DLQ_ARN}\",\"maxReceiveCount\":\"3\"}"

aws sqs set-queue-attributes \
  --queue-url ${OCR_RESULTS_QUEUE_URL} \
  --attributes RedrivePolicy="{\"deadLetterTargetArn\":\"${OCR_DLQ_ARN}\",\"maxReceiveCount\":\"3\"}"

aws sqs set-queue-attributes \
  --queue-url ${GEDCOM_READY_QUEUE_URL} \
  --attributes RedrivePolicy="{\"deadLetterTargetArn\":\"${GEDCOM_DLQ_ARN}\",\"maxReceiveCount\":\"3\"}"
```

### Step 4: Configure S3 Event Notifications

```bash
# Create notification configuration
cat > s3-notification.json <<EOF
{
  "QueueConfigurations": [
    {
      "QueueArn": "$(aws sqs get-queue-attributes --queue-url ${IMAGE_UPLOAD_QUEUE_URL} --attribute-names QueueArn --query 'Attributes.QueueArn' --output text)",
      "Events": ["s3:ObjectCreated:*"],
      "Filter": {
        "Key": {
          "FilterRules": [
            {"Name": "prefix", "Value": "documents/"},
            {"Name": "suffix", "Value": ".jpg"}
          ]
        }
      }
    }
  ]
}
EOF

# Allow S3 to send to SQS
export QUEUE_ARN=$(aws sqs get-queue-attributes --queue-url ${IMAGE_UPLOAD_QUEUE_URL} --attribute-names QueueArn --query 'Attributes.QueueArn' --output text)

cat > sqs-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {"Service": "s3.amazonaws.com"},
      "Action": "SQS:SendMessage",
      "Resource": "${QUEUE_ARN}",
      "Condition": {
        "ArnLike": {
          "aws:SourceArn": "arn:aws:s3:::${INPUT_BUCKET}"
        }
      }
    }
  ]
}
EOF

aws sqs set-queue-attributes \
  --queue-url ${IMAGE_UPLOAD_QUEUE_URL} \
  --attributes Policy="$(cat sqs-policy.json | jq -c .)"

# Apply notification configuration
aws s3api put-bucket-notification-configuration \
  --bucket ${INPUT_BUCKET} \
  --notification-configuration file://s3-notification.json
```

### Step 5: Create IAM Roles

#### OCR Image Service Role

```bash
# Create trust policy
cat > ocr-image-trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {"Service": "ecs-tasks.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create role
aws iam create-role \
  --role-name ocr-image-service-role \
  --assume-role-policy-document file://ocr-image-trust-policy.json

# Create policy
cat > ocr-image-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:ChangeMessageVisibility"],
      "Resource": "$(aws sqs get-queue-attributes --queue-url ${IMAGE_UPLOAD_QUEUE_URL} --attribute-names QueueArn --query 'Attributes.QueueArn' --output text)"
    },
    {
      "Effect": "Allow",
      "Action": ["sqs:SendMessage"],
      "Resource": "$(aws sqs get-queue-attributes --queue-url ${OCR_RESULTS_QUEUE_URL} --attribute-names QueueArn --query 'Attributes.QueueArn' --output text)"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:GetObjectTagging"],
      "Resource": "arn:aws:s3:::${INPUT_BUCKET}/*"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject"],
      "Resource": "arn:aws:s3:::${OCR_RESULTS_BUCKET}/*"
    }
  ]
}
EOF

aws iam put-role-policy \
  --role-name ocr-image-service-role \
  --policy-name ocr-image-service-policy \
  --policy-document file://ocr-image-policy.json
```

#### GEDCOM Generation Service Role

```bash
# Create trust policy (same as above)
aws iam create-role \
  --role-name gedcom-generation-service-role \
  --assume-role-policy-document file://ocr-image-trust-policy.json

# Create policy
cat > gedcom-generation-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:ChangeMessageVisibility"],
      "Resource": "$(aws sqs get-queue-attributes --queue-url ${OCR_RESULTS_QUEUE_URL} --attribute-names QueueArn --query 'Attributes.QueueArn' --output text)"
    },
    {
      "Effect": "Allow",
      "Action": ["sqs:SendMessage"],
      "Resource": "$(aws sqs get-queue-attributes --queue-url ${GEDCOM_READY_QUEUE_URL} --attribute-names QueueArn --query 'Attributes.QueueArn' --output text)"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject"],
      "Resource": "arn:aws:s3:::${OCR_RESULTS_BUCKET}/*"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject"],
      "Resource": "arn:aws:s3:::${GEDCOM_OUTPUT_BUCKET}/*"
    }
  ]
}
EOF

aws iam put-role-policy \
  --role-name gedcom-generation-service-role \
  --policy-name gedcom-generation-service-policy \
  --policy-document file://gedcom-generation-policy.json
```

#### Upload Service Role

```bash
aws iam create-role \
  --role-name gedcom-upload-service-role \
  --assume-role-policy-document file://ocr-image-trust-policy.json

cat > gedcom-upload-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:ChangeMessageVisibility"],
      "Resource": "$(aws sqs get-queue-attributes --queue-url ${GEDCOM_READY_QUEUE_URL} --attribute-names QueueArn --query 'Attributes.QueueArn' --output text)"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject"],
      "Resource": "arn:aws:s3:::${GEDCOM_OUTPUT_BUCKET}/*"
    }
  ]
}
EOF

aws iam put-role-policy \
  --role-name gedcom-upload-service-role \
  --policy-name gedcom-upload-service-policy \
  --policy-document file://gedcom-upload-policy.json
```

### Step 6: Store Secrets in AWS Secrets Manager

```bash
# Store Datalab API key
aws secretsmanager create-secret \
  --name ocr-pipeline/datalab-api-key \
  --secret-string "your_datalab_api_key_here"

# Store OpenRouter API key
aws secretsmanager create-secret \
  --name ocr-pipeline/openrouter-api-key \
  --secret-string "your_openrouter_api_key_here"

# Store Application API key (optional)
aws secretsmanager create-secret \
  --name ocr-pipeline/app-api-key \
  --secret-string "your_app_api_key_here"

# Grant services access to secrets
cat > secrets-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["secretsmanager:GetSecretValue"],
      "Resource": [
        "arn:aws:secretsmanager:${AWS_REGION}:*:secret:ocr-pipeline/*"
      ]
    }
  ]
}
EOF

# Attach to each service role
aws iam put-role-policy \
  --role-name ocr-image-service-role \
  --policy-name secrets-access \
  --policy-document file://secrets-policy.json

aws iam put-role-policy \
  --role-name gedcom-generation-service-role \
  --policy-name secrets-access \
  --policy-document file://secrets-policy.json

aws iam put-role-policy \
  --role-name gedcom-upload-service-role \
  --policy-name secrets-access \
  --policy-document file://secrets-policy.json
```

---

## Local Development Setup

### Step 1: Clone Repository

```bash
git clone https://github.com/your-org/korzen.git
cd korzen
```

### Step 2: Create Environment Files

```bash
# Copy template
cp .env.template .env

# Edit with your values
nano .env
```

See [`.env.template`](.env.template) for all required variables.

### Step 3: Install Dependencies (Optional - for local testing)

```bash
# OCR Image Service
cd ocr-image-microservice
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd ..

# GEDCOM Generation Service
cd gedcom-generation-microservice
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd ..

# Upload Service
cd gedcom-upload-microservice
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd ..
```

### Step 4: Test Individual Services

```bash
# Test OCR Image Service
cd ocr-image-microservice
source venv/bin/activate
python -m src.main

# Test GEDCOM Generation Service
cd gedcom-generation-microservice
source venv/bin/activate
python -m src.main

# Test Upload Service
cd gedcom-upload-microservice
source venv/bin/activate
python -m src.main
```

---

## Docker Deployment

### Step 1: Build Docker Images

```bash
# Build OCR Image Service
cd ocr-image-microservice
docker build -t ocr-image-service:latest .
cd ..

# Build GEDCOM Generation Service
cd gedcom-generation-microservice
docker build -t gedcom-generation-service:latest .
cd ..

# Build Upload Service
cd gedcom-upload-microservice
docker build -t gedcom-upload-service:latest .
cd ..
```

### Step 2: Run with Docker Compose (Full Pipeline)

```bash
# Use the full pipeline compose file
docker-compose -f docker-compose.full-pipeline.yml up -d

# View logs
docker-compose -f docker-compose.full-pipeline.yml logs -f

# Stop services
docker-compose -f docker-compose.full-pipeline.yml down
```

### Step 3: Test with LocalStack (Local AWS)

```bash
# Start LocalStack
docker run -d \
  --name localstack \
  -p 4566:4566 \
  -e SERVICES=s3,sqs \
  localstack/localstack

# Configure AWS CLI for LocalStack
export AWS_ENDPOINT_URL=http://localhost:4566
aws --endpoint-url=$AWS_ENDPOINT_URL s3 mb s3://test-bucket

# Run services with LocalStack endpoint
docker-compose -f docker-compose.full-pipeline.yml up -d
```

---

## AWS ECS/Fargate Deployment

### Step 1: Create ECR Repositories

```bash
# Create repositories
aws ecr create-repository --repository-name ocr-image-service
aws ecr create-repository --repository-name gedcom-generation-service
aws ecr create-repository --repository-name gedcom-upload-service

# Get repository URIs
export OCR_IMAGE_REPO=$(aws ecr describe-repositories --repository-names ocr-image-service --query 'repositories[0].repositoryUri' --output text)
export GEDCOM_GEN_REPO=$(aws ecr describe-repositories --repository-names gedcom-generation-service --query 'repositories[0].repositoryUri' --output text)
export UPLOAD_REPO=$(aws ecr describe-repositories --repository-names gedcom-upload-service --query 'repositories[0].repositoryUri' --output text)
```

### Step 2: Push Images to ECR

```bash
# Login to ECR
aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${OCR_IMAGE_REPO}

# Tag and push OCR Image Service
docker tag ocr-image-service:latest ${OCR_IMAGE_REPO}:latest
docker push ${OCR_IMAGE_REPO}:latest

# Tag and push GEDCOM Generation Service
docker tag gedcom-generation-service:latest ${GEDCOM_GEN_REPO}:latest
docker push ${GEDCOM_GEN_REPO}:latest

# Tag and push Upload Service
docker tag gedcom-upload-service:latest ${UPLOAD_REPO}:latest
docker push ${UPLOAD_REPO}:latest
```

### Step 3: Create ECS Cluster

```bash
aws ecs create-cluster --cluster-name ocr-pipeline-cluster
```

### Step 4: Create Task Definitions

#### OCR Image Service Task Definition

```bash
cat > ocr-image-task-def.json <<EOF
{
  "family": "ocr-image-service",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "taskRoleArn": "arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/ocr-image-service-role",
  "executionRoleArn": "arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "ocr-image-service",
      "image": "${OCR_IMAGE_REPO}:latest",
      "essential": true,
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/ocr-image-service",
          "awslogs-region": "${AWS_REGION}",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "environment": [
        {"name": "AWS_REGION", "value": "${AWS_REGION}"},
        {"name": "IMAGE_UPLOAD_QUEUE_URL", "value": "${IMAGE_UPLOAD_QUEUE_URL}"},
        {"name": "OCR_RESULTS_QUEUE_URL", "value": "${OCR_RESULTS_QUEUE_URL}"},
        {"name": "S3_INPUT_BUCKET", "value": "${INPUT_BUCKET}"},
        {"name": "S3_OUTPUT_BUCKET", "value": "${OCR_RESULTS_BUCKET}"}
      ],
      "secrets": [
        {
          "name": "DATALAB_API_KEY",
          "valueFrom": "arn:aws:secretsmanager:${AWS_REGION}:$(aws sts get-caller-identity --query Account --output text):secret:ocr-pipeline/datalab-api-key"
        }
      ]
    }
  ]
}
EOF

# Create CloudWatch log group
aws logs create-log-group --log-group-name /ecs/ocr-image-service

# Register task definition
aws ecs register-task-definition --cli-input-json file://ocr-image-task-def.json
```

#### GEDCOM Generation Service Task Definition

```bash
cat > gedcom-generation-task-def.json <<EOF
{
  "family": "gedcom-generation-service",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "4096",
  "memory": "8192",
  "taskRoleArn": "arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/gedcom-generation-service-role",
  "executionRoleArn": "arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "gedcom-generation-service",
      "image": "${GEDCOM_GEN_REPO}:latest",
      "essential": true,
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/gedcom-generation-service",
          "awslogs-region": "${AWS_REGION}",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "environment": [
        {"name": "AWS_REGION", "value": "${AWS_REGION}"},
        {"name": "OCR_RESULTS_QUEUE_URL", "value": "${OCR_RESULTS_QUEUE_URL}"},
        {"name": "GEDCOM_READY_QUEUE_URL", "value": "${GEDCOM_READY_QUEUE_URL}"},
        {"name": "S3_OUTPUT_BUCKET", "value": "${GEDCOM_OUTPUT_BUCKET}"}
      ],
      "secrets": [
        {
          "name": "OPENROUTER_API_KEY",
          "valueFrom": "arn:aws:secretsmanager:${AWS_REGION}:$(aws sts get-caller-identity --query Account --output text):secret:ocr-pipeline/openrouter-api-key"
        }
      ]
    }
  ]
}
EOF

aws logs create-log-group --log-group-name /ecs/gedcom-generation-service
aws ecs register-task-definition --cli-input-json file://gedcom-generation-task-def.json
```

#### Upload Service Task Definition

```bash
cat > gedcom-upload-task-def.json <<EOF
{
  "family": "gedcom-upload-service",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "taskRoleArn": "arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/gedcom-upload-service-role",
  "executionRoleArn": "arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "gedcom-upload-service",
      "image": "${UPLOAD_REPO}:latest",
      "essential": true,
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/gedcom-upload-service",
          "awslogs-region": "${AWS_REGION}",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "environment": [
        {"name": "AWS_REGION", "value": "${AWS_REGION}"},
        {"name": "GEDCOM_READY_QUEUE_URL", "value": "${GEDCOM_READY_QUEUE_URL}"},
        {"name": "S3_OUTPUT_BUCKET", "value": "${GEDCOM_OUTPUT_BUCKET}"},
        {"name": "APP_URL", "value": "https://korzen.vovcia.net"}
      ],
      "secrets": [
        {
          "name": "APP_API_KEY",
          "valueFrom": "arn:aws:secretsmanager:${AWS_REGION}:$(aws sts get-caller-identity --query Account --output text):secret:ocr-pipeline/app-api-key"
        }
      ]
    }
  ]
}
EOF

aws logs create-log-group --log-group-name /ecs/gedcom-upload-service
aws ecs register-task-definition --cli-input-json file://gedcom-upload-task-def.json
```

### Step 5: Create ECS Services

```bash
# Get VPC and subnet information
export VPC_ID=$(aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" --query 'Vpcs[0].VpcId' --output text)
export SUBNET_IDS=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=${VPC_ID}" --query 'Subnets[*].SubnetId' --output text | tr '\t' ',')

# Create security group
export SG_ID=$(aws ec2 create-security-group \
  --group-name ocr-pipeline-sg \
  --description "Security group for OCR pipeline services" \
  --vpc-id ${VPC_ID} \
  --query 'GroupId' --output text)

# Allow outbound traffic
aws ec2 authorize-security-group-egress \
  --group-id ${SG_ID} \
  --protocol -1 \
  --cidr 0.0.0.0/0

# Create OCR Image Service
aws ecs create-service \
  --cluster ocr-pipeline-cluster \
  --service-name ocr-image-service \
  --task-definition ocr-image-service \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[${SUBNET_IDS}],securityGroups=[${SG_ID}],assignPublicIp=ENABLED}"

# Create GEDCOM Generation Service
aws ecs create-service \
  --cluster ocr-pipeline-cluster \
  --service-name gedcom-generation-service \
  --task-definition gedcom-generation-service \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[${SUBNET_IDS}],securityGroups=[${SG_ID}],assignPublicIp=ENABLED}"

# Create Upload Service
aws ecs create-service \
  --cluster ocr-pipeline-cluster \
  --service-name gedcom-upload-service \
  --task-definition gedcom-upload-service \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[${SUBNET_IDS}],securityGroups=[${SG_ID}],assignPublicIp=ENABLED}"
```

### Step 6: Configure Auto-Scaling

```bash
# Register scalable targets
aws application-autoscaling register-scalable-target \
  --service-namespace ecs \
  --resource-id service/ocr-pipeline-cluster/ocr-image-service \
  --scalable-dimension ecs:service:DesiredCount \
  --min-capacity 1 \
  --max-capacity 5

# Create scaling policy based on SQS queue depth
cat > scaling-policy.json <<EOF
{
  "TargetValue": 10.0,
  "PredefinedMetricSpecification": {
    "PredefinedMetricType": "SQSQueueMessagesVisible"
  },
  "ScaleInCooldown": 300,
  "ScaleOutCooldown": 60
}
EOF

aws application-autoscaling put-scaling-policy \
  --service-namespace ecs \
  --resource-id service/ocr-pipeline-cluster/ocr-image-service \
  --scalable-dimension ecs:service:DesiredCount \
  --policy-name ocr-image-scaling-policy \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration file://scaling-policy.json
```

---

## Kubernetes Deployment

### Step 1: Create Kubernetes Manifests

####