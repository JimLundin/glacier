# Deploying Glacier Pipelines with Pulumi

Glacier compiles pipelines to actual Pulumi resource objects that can be deployed using the Pulumi CLI.

## Quick Start

### 1. Create a Pulumi Program

Create a file `__main__.py`:

```python
from glacier import Pipeline, Dataset
from glacier_aws import AWSCompiler

# Define pipeline
pipeline = Pipeline(name="my-pipeline")

raw = Dataset(name="raw")
processed = Dataset(name="processed")

@pipeline.task()
def extract() -> raw:
    return {"data": [1, 2, 3]}

@pipeline.task()
def transform(data: raw) -> processed:
    return {"processed": data}

# Compile to Pulumi resources
compiler = AWSCompiler(
    account="123456789012",  # Your AWS account ID
    region="us-east-1"
)

compiled = pipeline.compile(compiler)
compiled.export_outputs()
```

### 2. Create Pulumi.yaml

```yaml
name: my-pipeline
runtime: python
description: Glacier data pipeline
```

### 3. Deploy

```bash
# Install dependencies
pip install glacier-pipeline[aws]

# Configure Pulumi backend
pulumi login  # or: pulumi login file://~/.pulumi

# Create stack
pulumi stack init dev

# Preview changes
pulumi preview

# Deploy
pulumi up

# View outputs
pulumi stack output

# Destroy (when done)
pulumi destroy
```

## How It Works

The `AWSCompiler` creates actual Pulumi resource objects:

- `aws.lambda_.Function` for each task
- `aws.s3.BucketV2` for datasets with storage
- `aws.cloudwatch.EventRule` for scheduling
- `aws.cloudwatch.LogGroup` for monitoring
- `aws.iam.Role` and `aws.iam.RolePolicy` for permissions

These resources are automatically registered with Pulumi's runtime when instantiated, so there's no code generation needed.

## What Gets Created

For each pipeline, the compiler creates:

### Compute
- **Lambda function** for each task
- **IAM role** for each Lambda function
- **IAM policy** with S3 and CloudWatch permissions

### Storage
- **S3 bucket** for each dataset with storage configuration

### Scheduling
- **EventBridge rule** for tasks with cron schedules
- **EventBridge target** to invoke Lambda on schedule
- **Lambda permission** for EventBridge to invoke function

### Monitoring
- **CloudWatch log group** for each Lambda function
- **CloudWatch alarm** for Lambda errors (if monitoring configured)
- **SNS topic** for alerts (if notifications configured)

## Multi-Cloud Support

Switch providers by changing the compiler:

```python
# AWS
from glacier_aws import AWSCompiler
compiler = AWSCompiler(account="...", region="us-east-1")

# GCP (when implemented)
from glacier_gcp import GCPCompiler
compiler = GCPCompiler(project="...", region="us-central1")

# Azure (when implemented)
from glacier_azure import AzureCompiler
compiler = AzureCompiler(subscription="...", region="eastus")
```

The same pipeline definition works with any provider!

## Advanced Configuration

### Custom Lambda Settings

```python
compiler = AWSCompiler(
    account="123456789012",
    region="us-east-1",
    lambda_runtime="python3.11",
    lambda_memory=1024,      # MB
    lambda_timeout=600       # seconds
)
```

### Task-Level Compute Config

```python
from glacier.compute import Serverless

@pipeline.task(compute=Serverless(memory=2048, timeout=900))
def heavy_task() -> output:
    # This task gets custom memory and timeout
    return process_large_dataset()
```

### Scheduling

```python
from glacier.scheduling import cron, on_update

@pipeline.task(schedule=cron("0 2 * * *"))  # Daily at 2 AM
def daily_extract() -> raw:
    return fetch_daily_data()

@pipeline.task(schedule=on_update(raw))  # On data upload
def process_new_data(data: raw) -> processed:
    return transform(data)
```

### Monitoring

```python
from glacier.monitoring import monitoring, notify_email

pipeline_monitoring = monitoring(
    log_level="INFO",
    log_retention_days=90,
    enable_metrics=True,
    alert_on_failure=True,
    notifications=[
        notify_email("team@example.com")
    ]
)

@pipeline.task(monitoring=pipeline_monitoring)
def critical_task() -> output:
    return important_work()
```

## Accessing Resources

Get references to created resources:

```python
compiled = pipeline.compile(compiler)

# Get specific resource
extract_function = compiled.get_resource("my-pipeline-extract")

# List all resources
for name in compiled.list_resources():
    print(f"Created: {name}")

# Export outputs
outputs = compiled.export_outputs()
```

## Example: Production Pipeline

See `examples/deploy_with_pulumi.py` for a complete example with:
- Multiple tasks and datasets
- Environment configuration
- Storage and compute resources
- Scheduling and monitoring
- Stack outputs
