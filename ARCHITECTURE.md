# Glacier Architecture

Glacier is a code-centric data pipeline framework that lets you define pipelines in Python and optionally generate infrastructure.

## Core Concepts

### 1. Pipeline
A pipeline is a collection of tasks with automatically inferred dependencies.

```python
from glacier import Pipeline

pipeline = Pipeline(name="etl")
```

### 2. Tasks
Tasks are Python functions that process data. Dependencies are inferred from type annotations.

```python
@pipeline.task()
def extract() -> raw_data:
    return fetch_data()

@pipeline.task()
def transform(data: raw_data) -> clean_data:
    return process(data)
```

The DAG is built automatically: `extract → transform` because `transform` consumes what `extract` produces.

### 3. Datasets
Datasets represent data with optional storage configuration.

```python
from glacier import Dataset

raw_data = Dataset(name="raw", storage=some_storage)
```

### 4. Resources (Storage & Compute)

Resources can be specified in two ways:

**Option 1: Use our simple abstractions**
```python
from glacier.storage import ObjectStorage
from glacier.compute import Serverless

storage = ObjectStorage(bucket="my-data", provider="aws")
compute = Serverless(memory=512, timeout=300, provider="aws")
```

**Option 2: Use Pulumi resources directly**
```python
import pulumi_aws as aws

storage = aws.s3.Bucket("my-data",
    versioning=aws.s3.BucketVersioningArgs(enabled=True),
    lifecycle_rules=[...])

compute = aws.lambda_.Function("my-function",
    memory_size=512,
    timeout=300)
```

Both work the same way - Glacier accepts either.

## Provider Agnosticism

The core library has zero cloud dependencies:
- No imports of `boto3`, `google-cloud-storage`, `pulumi`, etc.
- Provider-specific code lives in separate packages: `glacier-aws`, `glacier-gcp`, `glacier-local`

When you need provider-specific features, install the provider package:
```bash
pip install glacier-pipeline[aws]  # Adds pulumi-aws, boto3
```

## Execution

**Local (for testing):**
```python
from glacier_local import LocalExecutor

results = LocalExecutor().execute(pipeline)
```

**Cloud (generates infrastructure):**
```python
from glacier_aws import AWSExecutor

executor = AWSExecutor(region="us-east-1")
executor.deploy(pipeline)  # Generates and deploys Pulumi code
```

## Key Design Principles

1. **Simple by default**: Use our abstractions for common cases
2. **Powerful when needed**: Drop down to Pulumi for advanced features
3. **Provider-agnostic core**: No cloud SDKs in the base library
4. **Type-driven**: DAG inferred from function signatures
5. **Optional infrastructure**: Can run locally without generating any cloud resources

## Package Structure

```
glacier/
├── core/           # Pipeline, Task, Dataset (no cloud deps)
├── storage/        # Generic storage abstractions
├── compute/        # Generic compute abstractions
└── execution/      # Execution interfaces

providers/
├── glacier-aws/    # AWS-specific (optional)
├── glacier-gcp/    # GCP-specific (optional)
└── glacier-local/  # Local execution (optional)
```

That's it. Keep it simple.
