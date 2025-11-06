# Glacier 🏔️

A code-centric data pipeline library built on Polars with infrastructure-from-code generation.

**⚠️ ALPHA SOFTWARE** - API may change. No backwards compatibility guarantees until v1.0.

## Philosophy

**Infrastructure from Code** - Define your data pipelines in Python, and Glacier automatically generates the required cloud infrastructure (Terraform, IAM policies, etc.) by analyzing your code.

## Key Features

- 🎯 **Code-Centric DX**: Define pipelines using intuitive Python decorators
- ☁️ **Cloud-Agnostic**: Deploy to AWS, Azure, GCP, or local with zero code changes
- 🔗 **Explicit Dependencies**: Type-safe task dependencies (no magic strings!)
- ⚡ **Polars-Native**: Built on Polars LazyFrames for optimal performance
- 🏗️ **Infrastructure Generation**: Auto-generate Terraform from pipeline definitions
- 🔄 **Heterogeneous Execution**: Mix local, Lambda, Databricks, Spark in one pipeline
- 📊 **DAG Resolution**: Automatic dependency graph construction and validation
- 🧩 **Execution Resources**: First-class execution resources (local, serverless, VM, cluster)

## What's New

✨ **Execution Resources as First-Class Objects**: Create execution environments from provider
✨ **Provider Configuration Classes**: Type-safe configs (`AwsConfig`, `GcpConfig`, `AzureConfig`, `LocalConfig`)
✨ **Single Provider Class**: Behavior determined by config injection, not subclasses
✨ **Task Binding to Executors**: `@executor.task()` pattern - bind tasks to execution resources
✨ **Provider Abstraction**: Same code works with AWS, Azure, GCP, or local
✨ **No Deployment Environment**: Glacier handles execution environment only (dev/staging/prod is infrastructure concern)

See [DESIGN_UX.md](./DESIGN_UX.md) for complete architecture details and [examples/](./examples/) for usage examples.

## Quick Start

### Simple Local Pipeline

```python
from glacier import Provider, pipeline
from glacier.config import LocalConfig
import polars as pl

# 1. Create provider with config injection
# Config determines WHERE DATA LIVES (local filesystem)
provider = Provider(config=LocalConfig(base_path="./data"))

# 2. Create EXECUTION resource (where code runs)
local_exec = provider.local()

# 3. Create STORAGE resource (where data lives)
data_source = provider.bucket(bucket="data", path="input.parquet")

# 4. Define tasks bound to execution resource
@local_exec.task()
def load_data(source) -> pl.LazyFrame:
    """Load data from source."""
    return source.scan()

@local_exec.task()
def clean_data(df: pl.LazyFrame) -> pl.LazyFrame:
    """Remove null values."""
    return df.filter(pl.col("value").is_not_null())

@local_exec.task()
def aggregate(df: pl.LazyFrame) -> pl.LazyFrame:
    """Aggregate by category."""
    return df.group_by("category").agg(pl.col("value").sum())

# 5. Define pipeline
@pipeline(name="simple_etl")
def simple_pipeline():
    df = load_data(data_source)
    cleaned = clean_data(df)
    result = aggregate(cleaned)
    return result

# 6. Run locally
if __name__ == "__main__":
    result = simple_pipeline.run(mode="local")
    print(result.collect())
```

### Cloud-Agnostic Pipeline

Switch clouds by changing ONLY the provider config - same code works everywhere!

```python
from glacier import Provider, pipeline
from glacier.config import AwsConfig, AzureConfig, GcpConfig, LocalConfig
import polars as pl
import os

# Dynamic provider selection based on environment
def create_provider():
    cloud = os.getenv("GLACIER_CLOUD", "local")

    if cloud == "aws":
        return Provider(config=AwsConfig(region="us-east-1"))
    elif cloud == "azure":
        return Provider(config=AzureConfig(
            subscription_id="...",
            resource_group="glacier-rg",
            location="eastus"
        ))
    elif cloud == "gcp":
        return Provider(config=GcpConfig(
            project_id="my-project",
            region="us-central1"
        ))
    else:
        return Provider(config=LocalConfig(base_path="./data"))

provider = create_provider()

# Rest of code is IDENTICAL regardless of cloud!
local_exec = provider.local()
bucket = provider.bucket(bucket="company-data", path="sales.parquet")

@local_exec.task()
def process(source):
    return source.scan().filter(pl.col("amount") > 0)

@pipeline(name="cloud_agnostic")
def my_pipeline():
    return process(bucket)

# Works on AWS S3, Azure Blob, GCS, or local filesystem!
```

### Heterogeneous Execution

Run different tasks on different execution platforms in the same pipeline:

```python
from glacier import Provider, pipeline
from glacier.config import AwsConfig, LambdaConfig, DatabricksConfig
import polars as pl

# Provider determines WHERE DATA LIVES (AWS S3)
provider = Provider(config=AwsConfig(region="us-east-1"))

# Create different EXECUTION resources (where code runs)
local_exec = provider.local()
lambda_exec = provider.serverless(config=LambdaConfig(memory=1024))
databricks_exec = provider.cluster(config=DatabricksConfig(
    cluster_id="cluster-123",
    instance_type="i3.xlarge"
))

# Storage resources
raw_data = provider.bucket(bucket="data-lake", path="raw/data.parquet")

# Tasks on different executors
@local_exec.task()
def extract(source) -> pl.LazyFrame:
    """Runs on local Python process."""
    return source.scan()

@lambda_exec.task()
def transform(df: pl.LazyFrame) -> pl.LazyFrame:
    """Runs on AWS Lambda."""
    return df.filter(pl.col("value") > 0)

@databricks_exec.task()
def ml_predict(df: pl.LazyFrame) -> pl.LazyFrame:
    """Runs on Databricks cluster with GPUs."""
    return df.with_columns(pl.lit(0.9).alias("prediction"))

@pipeline(name="ml_pipeline")
def ml_pipeline():
    data = extract(raw_data)        # Local
    cleaned = transform(data)       # Lambda
    predictions = ml_predict(cleaned)  # Databricks
    return predictions

result = ml_pipeline.run(mode="local")
```

## Key Concepts

### Provider Creates Resources

The `Provider` is the single entry point for creating resources:

**Storage Resources (where data lives):**
```python
bucket = provider.bucket(
    bucket="my-bucket",
    path="file.parquet",
    config=S3Config(versioning=True, encryption="AES256")
)
```

**Execution Resources (where code runs):**
```python
local_exec = provider.local()
lambda_exec = provider.serverless(config=LambdaConfig(...))
vm_exec = provider.vm(config=EC2Config(...))
databricks_exec = provider.cluster(config=DatabricksConfig(...))
spark_exec = provider.cluster(config=SparkConfig(...))
```

### Tasks Bound to Execution Resources

```python
# Tasks bound to specific execution resources
@local_exec.task()
def runs_locally():
    pass

@databricks_exec.task()
def runs_on_databricks():
    pass
```

### Config Determines Behavior

- **Provider config** determines WHERE DATA LIVES (AWS S3, Azure Blob, GCS, local)
- **Resource config** determines specific backend (LambdaConfig → Lambda, DatabricksConfig → Databricks)
- **Same code**, different configs = different clouds!

### No Deployment Environment

Glacier handles **execution environment** (where code runs, where data lives), NOT deployment environment (dev/staging/prod).

Deployment environments should be handled via:
- Separate Terraform workspaces
- Different AWS accounts/GCP projects/Azure subscriptions
- CI/CD pipeline configuration

## Examples

See [examples/](./examples/) for complete working examples:

- **simple_pipeline.py** - Basic local pipeline with `@local_exec.task()`
- **cloud_agnostic_pipeline.py** - Same code works with AWS, Azure, GCP, or local
- **heterogeneous_pipeline.py** - Mix local, Lambda, Spark, Databricks execution

## Documentation

- [DESIGN_UX.md](./DESIGN_UX.md) - Complete architecture and design patterns
- [QUICKSTART.md](./QUICKSTART.md) - Step-by-step tutorial
- [CONTRIBUTING.md](./CONTRIBUTING.md) - How to contribute

## Installation

```bash
# Clone the repository
git clone https://github.com/JimLundin/glacier.git
cd glacier

# Install in development mode
pip install -e .
```

## License

MIT License - see [LICENSE](./LICENSE) for details.
