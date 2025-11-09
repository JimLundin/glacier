# Glacier Architecture

## Design Philosophy

Glacier is built on three core principles:

1. **Zero Provider Coupling**: The core library has no cloud dependencies
2. **Dependency Injection**: Providers are injected at compile/execution time
3. **Late Binding**: Provider selection happens when you compile or run, not when you define

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  User Code (Provider-Agnostic)                                  │
│  ├── Pipeline                                                    │
│  ├── Datasets (with generic storage)                            │
│  └── Tasks (with generic compute)                               │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
         ┌───────────────────────┐
         │   Core Library        │
         │   (glacier)           │
         │                       │
         │   - Pipeline          │
         │   - Dataset           │
         │   - Task              │
         │   - StorageResource   │
         │   - ComputeResource   │
         │   - Compiler ABC      │
         │   - Executor ABC      │
         └───────────┬───────────┘
                     │
                     │ Dependency Injection
                     │
         ┌───────────┴────────────────────┐
         │                                │
         ▼                                ▼
┌────────────────┐              ┌────────────────┐
│  Providers     │              │  Providers     │
│  (glacier-aws) │              │  (glacier-gcp) │
│                │              │                │
│  - AWSCompiler │              │  - GCPCompiler │
│  - AWSExecutor │              │  - GCPExecutor │
└────────────────┘              └────────────────┘
         │                                │
         ▼                                ▼
┌────────────────┐              ┌────────────────┐
│   Pulumi       │              │   Pulumi       │
│   (AWS)        │              │   (GCP)        │
└────────────────┘              └────────────────┘
```

## Package Structure

```
glacier/                          # Core library (zero cloud dependencies)
  ├── core/
  │   ├── pipeline.py            # Pipeline with @pipeline.task()
  │   ├── dataset.py             # Dataset abstraction
  │   └── task.py                # Task decorator
  ├── storage/
  │   └── resources.py           # Generic storage (ObjectStorage, Database, Cache, Queue)
  ├── compute/
  │   └── resources.py           # Generic compute (Local, Container, Serverless)
  ├── compilation/
  │   └── compiler.py            # Abstract Compiler interface
  └── execution/
      └── executor.py            # Abstract Executor interface

providers/                        # Provider packages (workspace members)
  ├── glacier-aws/               # pip install glacier-pipeline[aws]
  │   └── glacier_aws/
  │       ├── compiler.py        # AWSCompiler (Pulumi-based)
  │       └── executor.py        # AWSExecutor
  ├── glacier-gcp/               # pip install glacier-pipeline[gcp]
  │   └── glacier_gcp/
  │       ├── compiler.py        # GCPCompiler (Pulumi-based)
  │       └── executor.py        # GCPExecutor
  └── glacier-local/             # pip install glacier-pipeline[local]
      └── glacier_local/
          └── executor.py        # LocalExecutor (in-memory)
```

## Core Abstractions

### 1. Storage Resources (Generic)

```python
from glacier.storage import ObjectStorage, Database, Cache, Queue

# All provider-agnostic!
storage = ObjectStorage(
    access_pattern="frequent",  # Generic configuration
    versioning=True,
    encryption=True,

    # Optional provider hints (passed through opaquely)
    aws_storage_class="INTELLIGENT_TIERING",
    gcp_storage_class="STANDARD",
)
```

**Key points:**
- Core library defines abstract types only
- No cloud SDK imports
- Provider hints are opaque key-value pairs
- Compiler interprets hints for target provider

### 2. Compute Resources (Generic)

```python
from glacier import compute

# Local process (development)
compute.local(workers=4)

# Container (maps to Docker, K8s, ECS, Cloud Run, etc.)
compute.container(
    image="python:3.11",
    cpu=2.0,
    memory=4096,
)

# Serverless (maps to Lambda, Cloud Functions, Azure Functions)
compute.serverless(
    memory=1024,
    timeout=300,
)
```

**Key points:**
- Capability-based, not service-specific
- Describe **what** you need, not **how** to implement
- Same definitions work across all providers

### 3. Pipeline Registration Pattern

**New Pattern (Recommended):**

```python
# Create pipeline first
pipeline = Pipeline(name="etl")

# Tasks auto-register via decorator
@pipeline.task(compute=compute.serverless(memory=512))
def extract() -> raw_data:
    return fetch_data()

@pipeline.task(compute=compute.local())
def transform(data: raw_data) -> clean_data:
    return process(data)
```

**Old Pattern (Still Supported):**

```python
@task(compute=compute.serverless())
def extract() -> raw_data:
    return fetch_data()

@task(compute=compute.local())
def transform(data: raw_data) -> clean_data:
    return process(data)

# Manual registration
pipeline = Pipeline([extract, transform], name="etl")
```

## Dependency Injection

### Compilation (IaC Generation)

```python
# Import provider only when needed
from glacier_aws import AWSCompiler

compiler = AWSCompiler(
    region="us-east-1",
    naming_prefix="prod",
    tags={"Environment": "production"},
    defaults={
        "serverless": {"runtime": "python3.11"},
    },
)

# Inject compiler to generate infrastructure
infra = pipeline.compile(compiler)
infra.export_pulumi("./infra")
```

**What happens:**
1. Compiler validates resources against provider capabilities
2. Maps generic resources to provider-specific services
   - `ObjectStorage` → S3 buckets
   - `Serverless` → Lambda functions
3. Generates IAM policies from task→dataset relationships
4. Produces Pulumi Python code

### Execution

```python
# Import executor only when needed
from glacier_local import LocalExecutor

executor = LocalExecutor()

# Inject executor to run pipeline
results = pipeline.run(executor)
```

**What happens:**
1. Executor validates pipeline structure
2. Executes tasks in topological order
3. Passes data between tasks
4. Returns results

## Provider Hints

Provider hints allow passing provider-specific configuration without coupling to the provider:

```python
from glacier.storage import ObjectStorage

storage = ObjectStorage(
    # Generic config
    access_pattern="frequent",
    versioning=True,

    # Provider hints (opaque to core library)
    aws_storage_class="INTELLIGENT_TIERING",
    aws_kms_key="arn:aws:kms:...",
    gcp_storage_class="STANDARD",
    gcp_location="us-central1",
)
```

**How it works:**
1. Core library accepts `**provider_hints` as kwargs
2. Stored opaquely in `provider_hints` dict
3. Compiler extracts relevant hints for target provider
4. Invalid hints are ignored or warned about

## Compilation Flow

```
User Pipeline
    ↓
Pipeline.compile(compiler)  # Dependency injection
    ↓
Compiler.compile(pipeline)
    ↓
┌──────────────────────────────────────────┐
│ For each task:                           │
│  1. Validate compute resource            │
│  2. Map to provider service              │
│                                          │
│ For each dataset:                        │
│  1. Validate storage resource            │
│  2. Map to provider service              │
│  3. Generate resource name               │
│                                          │
│ For task→dataset relationships:          │
│  1. Generate IAM read/write policies     │
│  2. Create execution roles               │
└──────────────────────────────────────────┘
    ↓
CompiledPipeline
    ↓
export_pulumi(output_dir)
    ↓
┌──────────────────────────────────────────┐
│ Pulumi Project:                          │
│  - __main__.py (Pulumi resources)        │
│  - Pulumi.yaml (project config)          │
│  - requirements.txt (dependencies)       │
│  - README.md (deployment instructions)   │
└──────────────────────────────────────────┘
```

## Example: AWS Compilation

**Input:**

```python
raw_data = Dataset("raw_data", storage=ObjectStorage())
clean_data = Dataset("clean_data", storage=ObjectStorage())

@pipeline.task(compute=compute.serverless(memory=1024))
def process(data: raw_data) -> clean_data:
    return transform(data)

compiler = AWSCompiler(region="us-east-1", naming_prefix="prod")
infra = pipeline.compile(compiler)
```

**Generated Pulumi code:**

```python
import pulumi
import pulumi_aws as aws

# S3 buckets
raw_data = aws.s3.BucketV2(
    'raw_data',
    bucket='prod-raw-data-bucket',
    tags={'Dataset': 'raw_data'}
)

clean_data = aws.s3.BucketV2(
    'clean_data',
    bucket='prod-clean-data-bucket',
    tags={'Dataset': 'clean_data'}
)

# IAM role
process_role = aws.iam.Role(
    'process_role',
    assume_role_policy={...},
)

# IAM policy (auto-generated from data flow)
process_policy = aws.iam.RolePolicy(
    'process_policy',
    role=process_role.id,
    policy={
        'Statement': [
            # Read from raw_data
            {'Effect': 'Allow', 'Action': ['s3:GetObject'], ...},
            # Write to clean_data
            {'Effect': 'Allow', 'Action': ['s3:PutObject'], ...},
        ]
    }
)

# Lambda function
process_func = aws.lambda_.Function(
    'process',
    function_name='prod-process',
    runtime='python3.11',
    memory_size=1024,
    role=process_role.arn,
    # ... code packaging
)
```

## Validation

### Compile-Time Validation

```python
# AWSCompiler validates:
# - Lambda timeout ≤ 900s
# - Lambda memory: 128-10240 MB
# - Storage class is valid for AWS
# - No cycles in DAG
# - All datasets have producers

try:
    infra = pipeline.compile(compiler)
except ValueError as e:
    print(f"Compilation failed: {e}")
    # ValueError: AWS Lambda max timeout is 900s, got 1200
```

### Runtime Validation

```python
# LocalExecutor validates:
# - All input datasets are available
# - Task outputs match declared datasets
# - No cycles in execution

try:
    results = pipeline.run(executor)
except RuntimeError as e:
    print(f"Execution failed: {e}")
    # RuntimeError: Dataset 'raw_data' has not been materialized
```

## Benefits of This Architecture

### 1. True Provider Agnosticism

```python
# Same pipeline code
pipeline = Pipeline(name="etl")

@pipeline.task(compute=compute.serverless())
def process(data: raw_data) -> clean_data:
    return transform(data)

# Different targets
aws_infra = pipeline.compile(AWSCompiler())    # → Lambda
gcp_infra = pipeline.compile(GCPCompiler())    # → Cloud Functions
local_result = pipeline.run(LocalExecutor())   # → Local process
```

### 2. No Cloud SDK Pollution

```python
# Core library imports - zero cloud dependencies!
from glacier import Pipeline, Dataset, compute
from glacier.storage import ObjectStorage

# Cloud SDKs imported ONLY in provider packages
# providers/glacier-aws/glacier_aws/compiler.py:
#   import pulumi_aws as aws  ✓
#
# glacier/core/pipeline.py:
#   import pulumi_aws  ✗ NEVER
```

### 3. Testability

```python
# Test without cloud dependencies
def test_pipeline_structure():
    pipeline = Pipeline(name="test")

    @pipeline.task(compute=compute.local())
    def task1() -> data:
        return [1, 2, 3]

    assert len(pipeline.tasks) == 1
    pipeline.validate()  # No cloud SDK needed!
```

### 4. Pay Only for What You Use

```bash
# Minimal install (no providers)
pip install glacier-pipeline

# With AWS support
pip install glacier-pipeline[aws]

# With all providers
pip install glacier-pipeline[all]
```

### 5. Extensibility

Adding a new provider:

```python
# providers/glacier-azure/glacier_azure/compiler.py
from glacier.compilation import Compiler

class AzureCompiler(Compiler):
    def compile(self, pipeline):
        # Map to Azure services
        # - ObjectStorage → Blob Storage
        # - Serverless → Functions
        # - Database → SQL Database
        pass
```

## Current Status

### ✅ Implemented

- Core pipeline with @pipeline.task() pattern
- Generic storage resources (ObjectStorage, Database, Cache, Queue)
- Generic compute resources (Local, Container, Serverless)
- Compiler/Executor abstractions
- AWS provider with Pulumi compiler
- Local executor
- uv workspace structure

### 🚧 In Progress

- GCP provider
- Azure provider
- Kubernetes compiler

### 📋 Roadmap

- Schema validation
- Data lineage tracking
- Cost estimation
- Multi-region deployment
- Provider capability discovery
- Auto-scaling configuration

## Next Steps

1. **Implement additional providers** (GCP, Azure)
2. **Add runtime execution** for AWS/GCP (currently compile-only)
3. **Schema validation** using Pydantic or Pandera
4. **Data lineage** tracking through pipeline
5. **Cost estimation** based on resource configuration

---

For implementation details, see:
- [PROVIDER_ABSTRACTION_ANALYSIS.md](./PROVIDER_ABSTRACTION_ANALYSIS.md)
- [NEW_DESIGN.md](./NEW_DESIGN.md)
- [Examples](./examples/)
