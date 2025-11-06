# Glacier Quick Start Guide

Get started with Glacier in 5 minutes!

## Installation

```bash
# Clone the repository
git clone https://github.com/JimLundin/glacier.git
cd glacier

# Install in development mode
pip install -e .

# Or install from PyPI (when published)
pip install glacier-pipeline
```

## Your First Pipeline

### 1. Create Sample Data

Create `./data/input.parquet`:

```python
import polars as pl

# Create sample data
df = pl.DataFrame({
    "id": [1, 2, 3, 4, 5],
    "category": ["A", "B", "A", "C", "B"],
    "value": [100, 200, 150, 300, 250]
})

# Save as parquet
df.write_parquet("./data/input.parquet")
```

### 2. Create Your First Pipeline

Create `my_first_pipeline.py`:

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
    print("Loading data...")
    return source.scan()

@local_exec.task()
def clean_data(df: pl.LazyFrame) -> pl.LazyFrame:
    """Remove rows with null values."""
    print("Cleaning data...")
    return df.filter(pl.col("value").is_not_null())

@local_exec.task()
def transform(df: pl.LazyFrame) -> pl.LazyFrame:
    """Calculate derived columns."""
    print("Transforming data...")
    return df.with_columns([
        (pl.col("value") * 1.1).alias("value_with_markup")
    ])

@local_exec.task()
def aggregate(df: pl.LazyFrame) -> pl.LazyFrame:
    """Aggregate by category."""
    print("Aggregating data...")
    return df.group_by("category").agg([
        pl.col("value").sum().alias("total_value"),
        pl.col("value").mean().alias("avg_value"),
        pl.count().alias("count")
    ])

# 5. Define pipeline
@pipeline(name="my_first_pipeline")
def my_pipeline():
    """My first Glacier pipeline."""
    data = load_data(data_source)
    cleaned = clean_data(data)
    transformed = transform(cleaned)
    result = aggregate(transformed)
    return result

# 6. Run locally
if __name__ == "__main__":
    print("=" * 60)
    print("Running My First Glacier Pipeline")
    print("=" * 60)

    result = my_pipeline.run(mode="local")

    print("\nPipeline Result:")
    print(result.collect())

    print("\n✓ Pipeline completed successfully!")
```

### 3. Run Your Pipeline

```bash
python my_first_pipeline.py
```

You should see:

```
============================================================
Running My First Glacier Pipeline
============================================================
Loading data...
Cleaning data...
Transforming data...
Aggregating data...

Pipeline Result:
shape: (3, 3)
┌──────────┬─────────────┬───────────┐
│ category ┆ total_value ┆ avg_value │
│ ---      ┆ ---         ┆ ---       │
│ str      ┆ i64         ┆ f64       │
╞══════════╪═════════════╪═══════════╡
│ A        ┆ 250         ┆ 125.0     │
│ B        ┆ 450         ┆ 225.0     │
│ C        ┆ 300         ┆ 300.0     │
└──────────┴─────────────┴───────────┘

✓ Pipeline completed successfully!
```

## Understanding the Pattern

### Provider Creates Resources

Glacier has TWO types of resources:

**1. Storage Resources (where data lives):**
```python
bucket = provider.bucket(
    bucket="my-bucket",
    path="file.parquet"
)
```

**2. Execution Resources (where code runs):**
```python
local_exec = provider.local()
```

### Tasks Bound to Execution Resources

```python
@local_exec.task()
def my_task(source) -> pl.LazyFrame:
    return source.scan()
```

Tasks are bound to execution resources using `@executor.task()`, NOT `@task(executor="...")`.

### Pipelines Orchestrate Tasks

```python
@pipeline(name="my_pipeline")
def my_pipeline():
    data = load_data(data_source)
    result = process(data)
    return result
```

## Going Cloud

### Switch to AWS S3

Update your pipeline to use AWS:

```python
from glacier import Provider, pipeline
from glacier.config import AwsConfig, S3Config
import polars as pl

# Provider config determines WHERE DATA LIVES (AWS S3)
provider = Provider(config=AwsConfig(
    region="us-east-1",
    profile="default"  # or use AWS_PROFILE environment variable
))

# Create execution resource (still runs locally!)
local_exec = provider.local()

# Create storage resource (now in S3!)
data_source = provider.bucket(
    bucket="my-s3-bucket",
    path="input.parquet",
    config=S3Config(
        storage_class="STANDARD",
        encryption="AES256"
    )
)

# Tasks are IDENTICAL - no code changes!
@local_exec.task()
def load_data(source) -> pl.LazyFrame:
    return source.scan()

@local_exec.task()
def process(df: pl.LazyFrame) -> pl.LazyFrame:
    return df.filter(pl.col("value") > 0)

@pipeline(name="s3_pipeline")
def s3_pipeline():
    data = load_data(data_source)
    result = process(data)
    return result

# Run locally, but data comes from S3!
result = s3_pipeline.run(mode="local")
```

**Key insight**: Only the provider config changed! Task code is identical.

### Cloud-Agnostic Pipeline

Make your pipeline work with ANY cloud:

```python
import os
from glacier import Provider, pipeline
from glacier.config import AwsConfig, AzureConfig, GcpConfig, LocalConfig

def create_provider():
    """Create provider based on environment variable."""
    cloud = os.getenv("GLACIER_CLOUD", "local")

    if cloud == "aws":
        return Provider(config=AwsConfig(region="us-east-1"))
    elif cloud == "azure":
        return Provider(config=AzureConfig(
            subscription_id=os.getenv("AZURE_SUBSCRIPTION_ID"),
            resource_group="glacier-rg",
            location="eastus"
        ))
    elif cloud == "gcp":
        return Provider(config=GcpConfig(
            project_id=os.getenv("GCP_PROJECT_ID"),
            region="us-central1"
        ))
    else:
        return Provider(config=LocalConfig(base_path="./data"))

provider = create_provider()

# Rest of code is IDENTICAL!
local_exec = provider.local()
bucket = provider.bucket(bucket="data", path="input.parquet")

@local_exec.task()
def process(source):
    return source.scan().filter(pl.col("value") > 0)

@pipeline(name="cloud_agnostic")
def my_pipeline():
    return process(bucket)
```

Run on different clouds:

```bash
# Local
GLACIER_CLOUD=local python my_pipeline.py

# AWS S3
GLACIER_CLOUD=aws AWS_PROFILE=default python my_pipeline.py

# Azure Blob
GLACIER_CLOUD=azure python my_pipeline.py

# Google Cloud Storage
GLACIER_CLOUD=gcp python my_pipeline.py
```

## Heterogeneous Execution

Run different tasks on different platforms:

```python
from glacier import Provider, pipeline
from glacier.config import AwsConfig, LambdaConfig, DatabricksConfig
import polars as pl

# Provider determines where data lives (AWS S3)
provider = Provider(config=AwsConfig(region="us-east-1"))

# Create DIFFERENT execution resources
local_exec = provider.local()  # Runs locally
lambda_exec = provider.serverless(config=LambdaConfig(memory=1024))  # Runs on Lambda
databricks_exec = provider.cluster(config=DatabricksConfig(
    cluster_id="cluster-123",
    instance_type="i3.xlarge"
))  # Runs on Databricks

# Storage
data_source = provider.bucket(bucket="data-lake", path="raw.parquet")

# Tasks on DIFFERENT executors
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

@pipeline(name="heterogeneous")
def heterogeneous_pipeline():
    data = extract(data_source)        # Local
    cleaned = transform(data)          # Lambda
    predictions = ml_predict(cleaned)  # Databricks
    return predictions

result = heterogeneous_pipeline.run(mode="local")
```

## Next Steps

1. **Explore Examples**: Check out [examples/](./examples/) for complete working examples
2. **Read Design Doc**: See [DESIGN_UX.md](./DESIGN_UX.md) for complete architecture details
3. **Generate Infrastructure**: Learn how to generate Terraform from your pipelines
4. **Contribute**: See [CONTRIBUTING.md](./CONTRIBUTING.md) to contribute

## Key Takeaways

✓ **Provider creates resources** - Both storage (bucket) and execution (local, serverless, VM, cluster)
✓ **Tasks bound to executors** - `@executor.task()` pattern, not string-based
✓ **Config determines behavior** - Single Provider class, config injection determines AWS/Azure/GCP/Local
✓ **Cloud portability** - Same code, different configs = different clouds
✓ **No deployment environment** - Glacier handles execution environment only

Happy pipelining! 🏔️
