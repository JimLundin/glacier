# Glacier 🏔️

A code-centric data pipeline library built on Polars with infrastructure-from-code generation.

## Philosophy

**Infrastructure from Code** - Define your data pipelines in Python, and Glacier automatically generates the required cloud infrastructure (Terraform, IAM policies, etc.) by analyzing your code.

## Key Features

- 🎯 **Code-Centric DX**: Define pipelines using intuitive Python decorators
- ☁️ **Cloud-Agnostic**: Deploy to AWS, Azure, GCP, or local with zero code changes
- 🔗 **Explicit Dependencies**: Type-safe task dependencies (no magic strings!)
- ⚡ **Polars-Native**: Built on Polars LazyFrames for optimal performance
- 🏗️ **Infrastructure Generation**: Auto-generate Terraform from pipeline definitions
- 🔄 **Heterogeneous Execution**: Mix local, Databricks, DBT, Spark in one pipeline
- 📊 **DAG Resolution**: Automatic dependency graph construction and validation

## What's New in V2

✨ **Provider Abstraction**: Write cloud-agnostic pipelines
✨ **Explicit Dependencies**: Pass task objects, not strings
✨ **Executor Specification**: Run tasks on different platforms
✨ **Modern Python**: Uses `|` union syntax and built-in types

See [ARCHITECTURE_V2.md](./ARCHITECTURE_V2.md) for details.

## Quick Start

### Cloud-Agnostic Pipeline

```python
from glacier import pipeline, task
from glacier.providers import AWSProvider, AzureProvider, LocalProvider
import polars as pl

# Choose your cloud provider (or local for testing)
provider = AWSProvider(region="us-east-1")
# provider = AzureProvider(resource_group="my-rg")  # Same code, different cloud!
# provider = LocalProvider(base_path="./data")      # Or local for testing

# Create a cloud-agnostic source
data_source = provider.bucket_source(
    bucket="my-data",
    path="raw/data.parquet"
)

# Define transformation tasks with explicit dependencies
@task
def load_data(source) -> pl.LazyFrame:
    """Load data from source."""
    return source.scan()

@task(depends_on=[load_data])  # Pass the task object, not a string!
def clean_data(df: pl.LazyFrame) -> pl.LazyFrame:
    """Remove null values."""
    return df.filter(pl.col("value").is_not_null())

@task(depends_on=[clean_data])
def aggregate(df: pl.LazyFrame) -> pl.LazyFrame:
    """Aggregate by category."""
    return df.group_by("category").agg(pl.col("value").sum())

# Define the pipeline
@pipeline(name="my_pipeline")
def my_pipeline():
    df = load_data(data_source)
    cleaned = clean_data(df)
    result = aggregate(cleaned)
    return result

# Run locally
if __name__ == "__main__":
    result = my_pipeline.run()
    print(result.collect())
```

### Heterogeneous Execution

Mix different execution backends in one pipeline:

```python
@task
def load_from_s3(source) -> pl.LazyFrame:
    """Runs locally."""
    return source.scan()

@task(depends_on=[load_from_s3], executor="dbt")
def transform_with_dbt() -> pl.LazyFrame:
    """Runs on DBT."""
    # DBT transformation logic
    pass

@task(depends_on=[transform_with_dbt], executor="databricks")
def ml_on_databricks() -> pl.LazyFrame:
    """Runs on Databricks."""
    # ML processing on Databricks
    pass

@task(depends_on=[ml_on_databricks], executor="local")
def save_results(df: pl.LazyFrame):
    """Runs locally."""
    df.collect().write_parquet("output.parquet")
```

## CLI Usage

```bash
# Run pipeline locally
glacier run my_pipeline.py

# Generate infrastructure code
glacier generate my_pipeline.py --output ./infra

# Analyze pipeline structure
glacier analyze my_pipeline.py

# Validate pipeline
glacier validate my_pipeline.py
```

## Multi-Cloud Support

Switch clouds without changing your pipeline code:

```python
# Development: Local
dev_provider = LocalProvider(base_path="./data")

# Staging: AWS
staging_provider = AWSProvider(region="us-west-2")

# Production: Azure
prod_provider = AzureProvider(
    resource_group="prod-rg",
    location="eastus"
)

# GCP option
gcp_provider = GCPProvider(
    project_id="my-project",
    region="us-central1"
)

# Use the same pipeline code with any provider!
data_source = provider.bucket_source(
    bucket="my-data",
    path="data.parquet"
)
```

## Provider Configuration

Load from environment variables (12-factor app):

```python
# Reads AWS_REGION, AWS_PROFILE, etc. from environment
provider = AWSProvider.from_env()

# Reads AZURE_RESOURCE_GROUP, AZURE_LOCATION, etc.
provider = AzureProvider.from_env()

# Reads GCP_PROJECT_ID, GCP_REGION, etc.
provider = GCPProvider.from_env()
```

## Infrastructure Generation

Generate Terraform for your pipeline:

```bash
glacier generate my_pipeline.py --output ./infra
```

Creates:
- `main.tf` - Cloud resources (S3/Azure Blob/GCS buckets, IAM, etc.)
- `variables.tf` - Configurable parameters
- `outputs.tf` - Resource outputs
- `terraform.tfvars.example` - Example configuration
- `README.md` - Documentation

Then deploy:

```bash
cd infra
terraform init
terraform plan
terraform apply
```

## Installation

```bash
# Install from source
pip install -e .

# With cloud provider support
pip install -e ".[aws]"      # AWS (boto3)
pip install -e ".[gcp]"      # GCP (google-cloud-storage)
pip install -e ".[azure]"    # Azure (azure-storage-blob)
pip install -e ".[all]"      # All providers
```

## Explicit Dependencies (No Magic Strings!)

```python
# ❌ OLD WAY - Magic strings, error-prone
@task
def load_data():
    pass

@task(depends_on=["load_data"])  # Typo-prone!
def process_data():
    pass

# ✅ NEW WAY - Type-safe, refactoring-friendly
@task
def load_data():
    pass

@task(depends_on=[load_data])  # Pass the actual task!
def process_data():
    pass
```

Benefits:
- ✅ IDE autocomplete and type checking
- ✅ Refactoring works automatically
- ✅ No typos or missing dependencies
- ✅ Clear errors if task doesn't exist

## Examples

See the [examples](./examples/) directory for:
- `simple_pipeline.py` - Basic local pipeline
- `s3_pipeline.py` - Multi-source AWS pipeline
- `multi_cloud_pipeline.py` - Cloud-agnostic pipeline
- `heterogeneous_pipeline.py` - Mixed execution backends

## Documentation

- [Architecture V2](./ARCHITECTURE_V2.md) - New architecture and improvements
- [Design Document](./DESIGN.md) - Original design philosophy
- [Quick Start Guide](./QUICKSTART.md) - Get started in 5 minutes
- [Contributing](./CONTRIBUTING.md) - How to contribute

## Key Concepts

### Providers

Providers abstract over cloud platforms:

```python
from glacier.providers import AWSProvider, AzureProvider, GCPProvider, LocalProvider

# All providers have the same interface
provider = AWSProvider(region="us-east-1")
source = provider.bucket_source(bucket="data", path="file.parquet")
```

### Sources

Sources represent where data comes from:

```python
# Created via provider (recommended)
source = provider.bucket_source(
    bucket="my-data",
    path="file.parquet"
)

# Or directly (less flexible)
from glacier.sources import S3Source
source = S3Source(bucket="my-data", path="file.parquet")
```

### Tasks

Tasks are decorated functions that form DAG nodes:

```python
@task
def my_task(input: pl.LazyFrame) -> pl.LazyFrame:
    return input.filter(pl.col("value") > 0)

# With explicit dependencies
@task(depends_on=[load_data, clean_data])
def aggregate(df: pl.LazyFrame) -> pl.LazyFrame:
    return df.group_by("category").agg(pl.sum("value"))

# With executor specification
@task(depends_on=[prep_data], executor="databricks")
def train_model():
    # Runs on Databricks
    pass
```

### Pipelines

Pipelines orchestrate tasks:

```python
@pipeline(name="my_pipeline")
def my_pipeline():
    data = load_data(source)
    cleaned = clean_data(data)
    result = aggregate(cleaned)
    return result

# Execute in different modes
result = my_pipeline.run(mode="local")     # Run locally
dag = my_pipeline.run(mode="analyze")      # Analyze structure
infra = my_pipeline.run(mode="generate")   # Generate infrastructure
```

## Why Glacier?

### Before Glacier

```
✏️ Write pipeline code in Python
✏️ Write separate Terraform for infrastructure
✏️ Write separate Airflow/Prefect DAGs
❌ Keep everything in sync manually
❌ Repeat yourself across files
❌ Deploy process is complex
```

### With Glacier

```
✏️ Write pipeline code in Python
✅ Infrastructure generated automatically
✅ DAG built automatically
✅ Everything stays in sync
✅ Single source of truth
✅ Deploy with one command
```

## Design Principles

1. **Code-Centric**: Everything defined in Python
2. **Infrastructure from Code**: Generate infra from code, not vice versa
3. **Explicit over Implicit**: No magic, clear intentions
4. **Cloud-Agnostic**: Deploy anywhere without code changes
5. **Type-Safe**: Leverage Python's type system
6. **Lazy by Default**: Optimize with Polars LazyFrames
7. **Extensible**: Easy to add providers, executors, sources

## Supported Providers

| Provider | Status | Storage | Infrastructure |
|----------|--------|---------|----------------|
| AWS | ✅ Ready | S3 | Terraform |
| Azure | ✅ Ready | Blob Storage | Terraform |
| GCP | ✅ Ready | Cloud Storage | Terraform |
| Local | ✅ Ready | Filesystem | None |

## Supported Executors

| Executor | Status | Description |
|----------|--------|-------------|
| local | ✅ Ready | Local Python process |
| dbt | 🚧 Planned | DBT models |
| databricks | 🚧 Planned | Databricks jobs |
| spark | 🚧 Planned | Spark jobs |
| airflow | 🚧 Planned | Airflow operators |

## Roadmap

### Phase 1: Foundation (✅ Complete)
- ✅ Core abstractions
- ✅ Provider system
- ✅ Local execution
- ✅ Terraform generation
- ✅ CLI

### Phase 2: Multi-Cloud (Current)
- ✅ Azure Blob Storage support
- ✅ Google Cloud Storage support
- ✅ Multi-cloud infrastructure generation
- [ ] Cross-cloud data transfer
- [ ] Provider credential management

### Phase 3: Orchestration
- [ ] DBT executor
- [ ] Databricks executor
- [ ] Airflow DAG generation
- [ ] Prefect flow generation
- [ ] Dagster pipeline generation

### Phase 4: Advanced
- [ ] Streaming pipelines
- [ ] Data quality checks
- [ ] Cost optimization
- [ ] Observability
- [ ] Web UI

## Contributing

We welcome contributions! See [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](./LICENSE) for details.

## Community

- 📚 [Documentation](./docs/)
- 💬 [Discussions](https://github.com/yourusername/glacier/discussions)
- 🐛 [Issues](https://github.com/yourusername/glacier/issues)
- 🎯 [Roadmap](https://github.com/yourusername/glacier/projects)

---

Built with ❤️ by the Glacier team. Deploy data pipelines to any cloud with confidence.
