# Multi-Cloud Pipelines

Glacier supports building data pipelines that span multiple cloud providers **without coupling your code to any specific provider**.

## The Multi-Cloud Problem

Traditional approaches force you to choose ONE provider:

```python
# ❌ Locked to AWS
pipeline.deploy_to_aws()

# ❌ Can't mix providers
```

**Glacier's Solution:** Provider selection happens at compile time, not in your pipeline code.

## Three Levels of Provider Control

### Level 1: Fully Generic (Provider-Agnostic)

```python
from glacier import Pipeline, Dataset, compute
from glacier.storage import ObjectStorage

pipeline = Pipeline(name="analytics")

raw_data = Dataset("raw", storage=ObjectStorage())
clean_data = Dataset("clean", storage=ObjectStorage())

@pipeline.task(compute=compute.serverless(memory=1024))
def process(data: raw_data) -> clean_data:
    return transform(data)

# Choose provider at compile time
aws_infra = pipeline.compile(AWSCompiler())    # → All AWS
gcp_infra = pipeline.compile(GCPCompiler())    # → All GCP
```

**Benefits:**
- ✅ Maximum portability
- ✅ Easy cloud migration
- ✅ No provider lock-in

### Level 2: Provider Hints (Portable with Preferences)

```python
from glacier.storage import ObjectStorage

storage = ObjectStorage(
    access_pattern="frequent",  # Generic

    # Provider hints - optional customization
    aws_storage_class="INTELLIGENT_TIERING",
    gcp_storage_class="NEARLINE",
    azure_tier="Cool",
)
```

**Benefits:**
- ✅ Still portable (hints are ignored if not applicable)
- ✅ Optimize for specific providers when deployed there
- ✅ No hard coupling

### Level 3: Provider-Specific Resources (Explicit Control)

```python
# Import provider-specific resources when you need them
from glacier_aws.storage import S3
from glacier_aws.compute import Lambda

raw_data = Dataset(
    "raw",
    storage=S3(
        bucket="existing-bucket",
        storage_class="GLACIER",
        object_lock_enabled=True,  # AWS-specific feature
    )
)

@pipeline.task(compute=Lambda(
    memory=1024,
    layers=["arn:aws:lambda:..."],  # AWS-specific
    reserved_concurrency=10,
))
def process(data: raw_data) -> clean_data:
    return transform(data)
```

**Benefits:**
- ✅ Access to provider-specific features
- ✅ Explicit about provider requirements
- ✅ Validates at compile time

**Trade-off:**
- ❌ This pipeline now requires AWS

## Multi-Cloud Compilation

Mix generic and provider-specific resources in one pipeline:

```python
from glacier import Pipeline, Dataset, compute
from glacier.storage import ObjectStorage
from glacier.compilation import MultiCloudCompiler

# Import provider-specific resources
from glacier_aws.storage import S3
from glacier_gcp.compute import CloudFunction

pipeline = Pipeline(name="hybrid")

# Explicit: AWS S3 (existing bucket)
legacy_data = Dataset(
    "legacy_data",
    storage=S3(bucket="legacy-bucket", region="us-east-1")
)

# Generic: Will use default provider
processed_data = Dataset(
    "processed",
    storage=ObjectStorage()
)

# Explicit: GCP Cloud Function
@pipeline.task(compute=CloudFunction(memory=2048))
def process(data: legacy_data) -> processed_data:
    return transform(data)

# Compile with multiple providers
from glacier_aws import AWSCompiler
from glacier_gcp import GCPCompiler

compiler = MultiCloudCompiler(
    providers={
        "aws": AWSCompiler(region="us-east-1"),
        "gcp": GCPCompiler(project="my-project", region="us-central1"),
    },
    default_provider="gcp",  # Generic resources → GCP
)

infra = pipeline.compile(compiler)
```

### What Happens

1. **Provider Detection**: Compiler detects S3 (AWS) and CloudFunction (GCP)
2. **Resource Mapping**: Generic resources go to default provider (GCP)
3. **Cross-Cloud Warning**: Alerts about AWS → GCP data transfer
4. **Infrastructure Generation**: Creates Pulumi code for both providers

```
Output:
  infra/
    aws/
      __main__.py   # S3 bucket
      Pulumi.yaml
    gcp/
      __main__.py   # Cloud Function + Storage
      Pulumi.yaml
    README.md       # Deployment guide
```

## Cross-Provider Data Transfer Detection

Glacier automatically detects when data crosses cloud boundaries:

```python
# AWS storage
raw = Dataset("raw", storage=S3(bucket="data"))

# GCP compute
@pipeline.task(compute=CloudFunction())
def process(data: raw) -> clean:  # Reads from AWS!
    return transform(data)
```

**Warning Output:**

```
⚠️  CROSS-PROVIDER DATA TRANSFERS DETECTED

The following data transfers cross cloud provider boundaries:

  • raw
    extract (aws) → process (gcp)
    Estimated cost: ~5x normal transfer

Recommendations:
  1. Consider co-locating compute and storage
  2. Use intermediate storage to batch transfers
  3. Compress data before transfer
  4. Monitor egress costs carefully
```

## Use Cases

### 1. Cloud Migration (AWS → GCP)

```python
# Phase 1: Fully on AWS
pipeline.compile(AWSCompiler())

# Phase 2: Hybrid (gradual migration)
pipeline.compile(MultiCloudCompiler({
    "aws": AWSCompiler(),  # Legacy resources
    "gcp": GCPCompiler(),  # New resources
}))

# Phase 3: Fully on GCP
pipeline.compile(GCPCompiler())

# Same pipeline code throughout!
```

### 2. Cost Optimization

```python
# Use cheapest storage
from glacier_gcp.storage import GCS  # Cheaper for archival

archive = Dataset("archive", storage=GCS(
    bucket="cold-storage",
    storage_class="ARCHIVE",
))

# Use best compute
from glacier_aws.compute import Lambda  # Better cold start

@pipeline.task(compute=Lambda(memory=512))
def quick_task() -> archive:
    return process()
```

### 3. Compliance & Data Residency

```python
# EU data must stay in EU
eu_data = Dataset(
    "eu_data",
    storage=S3(bucket="eu-bucket", region="eu-west-1")
)

# US data in US
us_data = Dataset(
    "us_data",
    storage=GCS(bucket="us-bucket", location="us-central1")
)
```

### 4. Best-of-Breed Services

```python
# Use AWS for data lake (S3)
from glacier_aws.storage import S3

# Use GCP for ML (Vertex AI, BigQuery)
from glacier_gcp.compute import CloudFunction

# Use Azure for specific enterprise features
from glacier_azure.storage import BlobStorage
```

## How It Works Internally

### 1. Resource Analysis

```python
# Compiler analyzes pipeline
for task in pipeline.tasks:
    # Check compute resource
    provider = task.compute.get_provider()
    # None → generic, use default
    # "aws" → requires AWS
    # "gcp" → requires GCP

    # Check storage resources
    for dataset in task.datasets:
        provider = dataset.storage.get_provider()
```

### 2. Provider Grouping

```
Resources by Provider:
  AWS:
    - S3 bucket: legacy-data
    - Lambda: extract_task
  GCP:
    - Cloud Storage: processed-data
    - Cloud Function: process_task
    - Cloud Function: analyze_task
```

### 3. Cross-Provider Detection

```python
# Task reads from different provider
task_provider = "gcp"
input_dataset_provider = "aws"

if task_provider != input_dataset_provider:
    warn_cross_provider_transfer()
```

### 4. Delegation to Provider Compilers

```python
# For each provider in use
for provider in ["aws", "gcp"]:
    compiler = providers[provider]
    infra = compiler.compile(pipeline)
    # Generate infrastructure for this provider only
```

## API Reference

### MultiCloudCompiler

```python
from glacier.compilation import MultiCloudCompiler

compiler = MultiCloudCompiler(
    providers={
        "aws": AWSCompiler(...),
        "gcp": GCPCompiler(...),
        "azure": AzureCompiler(...),
    },
    default_provider="aws",  # For generic resources
    enable_cross_cloud_warnings=True,  # Warn about transfers
)

infra = pipeline.compile(compiler)
```

### Provider-Specific Resources

Import from provider packages:

```python
# AWS
from glacier_aws.storage import S3, RDS
from glacier_aws.compute import Lambda

# GCP (when implemented)
from glacier_gcp.storage import GCS, CloudSQL
from glacier_gcp.compute import CloudFunction

# Azure (when implemented)
from glacier_azure.storage import BlobStorage, CosmosDB
from glacier_azure.compute import AzureFunction
```

### Resource Methods

All resources implement:

```python
class StorageResource:
    def get_type(self) -> str:
        # "object_storage", "database", "cache", etc.

    def get_provider(self) -> Optional[str]:
        # None = generic
        # "aws", "gcp", "azure" = provider-specific

    def supports_provider(self, provider: str) -> bool:
        # Can this resource compile to given provider?
```

## Best Practices

### 1. Start Generic, Specialize When Needed

```python
# Good: Start generic
storage = ObjectStorage()

# Only specialize if you need provider-specific features
storage = S3(bucket="...", object_lock_enabled=True)
```

### 2. Group Resources by Provider

```python
# Good: Related resources on same provider
input_data = Dataset("input", storage=S3(bucket="data"))

@pipeline.task(compute=Lambda())  # Same provider (AWS)
def process(data: input_data) -> output:
    return transform(data)
```

### 3. Batch Cross-Provider Transfers

```python
# Bad: Many small transfers
@pipeline.task(compute=gcp_compute)
def process_each_record(record: aws_storage) -> result:
    # Called 1000 times = 1000 cross-cloud transfers!
    pass

# Good: One large transfer
@pipeline.task(compute=gcp_compute)
def process_batch(records: aws_storage) -> results:
    # Called once, processes all records
    pass
```

### 4. Use Provider Hints for Portability

```python
# Good: Portable with optimization hints
storage = ObjectStorage(
    aws_storage_class="INTELLIGENT_TIERING",
    gcp_storage_class="STANDARD",
)

# Less portable: Locked to AWS
storage = S3(bucket="...")  # Requires AWS
```

## Limitations

### Current Limitations

1. **Cross-provider execution orchestration**: You need to manually orchestrate cross-cloud execution (or use a workflow engine)
2. **Provider implementations**: Only AWS fully implemented (GCP, Azure coming)
3. **Runtime data transfer**: Compile-time warnings only, no automatic transfer optimization

### Future Enhancements

- [ ] Automatic data transfer optimization (compression, batching)
- [ ] Cost estimation for cross-provider transfers
- [ ] Multi-cloud execution orchestration
- [ ] Data locality optimization suggestions
- [ ] Provider-agnostic secrets management
- [ ] Cross-cloud networking configuration

## Summary

Glacier's multi-cloud support gives you three levels of control:

1. **Generic Resources**: Maximum portability, provider chosen at compile time
2. **Provider Hints**: Portable with optional provider-specific optimization
3. **Provider-Specific**: Explicit provider requirements, access to all features

The `MultiCloudCompiler` enables mixing providers in one pipeline while detecting cross-cloud transfers and generating appropriate infrastructure.

**No provider lock-in. Maximum flexibility. Same pipeline code everywhere.**

---

For implementation details, see:
- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [examples/multicloud_example.py](./examples/multicloud_example.py)
