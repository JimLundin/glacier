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
- 🔄 **Heterogeneous Execution**: Mix local, Databricks, DBT, Spark in one pipeline
- 📊 **DAG Resolution**: Automatic dependency graph construction and validation

## What's New

✨ **Environment-First Design**: Dependency injection with `GlacierEnv` for better testability and multi-environment support
✨ **Provider Configuration Classes**: Type-safe configs (`AwsConfig`, `GcpConfig`, `AzureConfig`, `LocalConfig`)
✨ **Environment Registry**: Centralized resource management (`env.register()`, `env.get()`)
✨ **Provider Abstraction**: Write cloud-agnostic pipelines
✨ **Explicit Dependencies**: Pass task objects, not strings
✨ **Executor Specification**: Run tasks on different platforms
✨ **Modern Python**: Uses `|` union syntax and built-in types

See [DESIGN_UX.md](./DESIGN_UX.md) for the full design and [ARCHITECTURE_V2.md](./ARCHITECTURE_V2.md) for architecture details.

## Quick Start

### Environment-First Pattern

Glacier uses dependency injection with `GlacierEnv` for better testability, type safety, and multi-environment support:

```python
from glacier import GlacierEnv
from glacier.providers import AWSProvider
from glacier.config import AwsConfig
import polars as pl

# 1. Create provider with config
aws_config = AwsConfig(
    region="us-east-1",
    profile="production",
    tags={"environment": "prod", "team": "data-eng"}
)
provider = AWSProvider(config=aws_config)

# 2. Create environment
env = GlacierEnv(provider=provider, name="production")

# 3. Define tasks bound to environment
@env.task()
def load_data(source) -> pl.LazyFrame:
    """Load data from source."""
    return source.scan()

@env.task()
def clean_data(df: pl.LazyFrame) -> pl.LazyFrame:
    """Remove null values."""
    return df.filter(pl.col("value").is_not_null())

@env.task()
def aggregate(df: pl.LazyFrame) -> pl.LazyFrame:
    """Aggregate by category."""
    return df.group_by("category").agg(pl.col("value").sum())

# 4. Define pipeline
@env.pipeline(name="my_pipeline")
def my_pipeline():
    # Access provider via env.provider
    data_source = env.provider.bucket("my-data", path="raw/data.parquet")

    df = load_data(data_source)
    cleaned = clean_data(df)
    result = aggregate(cleaned)
    return result

# 5. Run locally
if __name__ == "__main__":
    result = my_pipeline.run(mode="local")
    print(result.collect())
```

**Benefits of Environment-First:**
- ✅ **Explicit dependencies** - Configuration flows clearly through the system
- ✅ **Environment isolation** - Dev, staging, and prod environments coexist
- ✅ **Type safety** - Full IDE autocomplete and type checking
- ✅ **Testability** - Easy to inject mock providers for testing
- ✅ **Multi-cloud** - Switch providers without code changes

### Cloud-Agnostic Pipeline

Switch clouds by changing the provider config:

```python
from glacier import GlacierEnv
from glacier.providers import AWSProvider, AzureProvider, LocalProvider
from glacier.config import AwsConfig, AzureConfig, LocalConfig

# Development: Local
dev_provider = LocalProvider(config=LocalConfig(base_path="./data"))
dev_env = GlacierEnv(provider=dev_provider, name="development")

# Staging: AWS
staging_provider = AWSProvider(config=AwsConfig(region="us-west-2"))
staging_env = GlacierEnv(provider=staging_provider, name="staging")

# Production: Azure
prod_provider = AzureProvider(config=AzureConfig(
    resource_group="prod-rg",
    location="eastus",
    subscription_id="..."
))
prod_env = GlacierEnv(provider=prod_provider, name="production")

# Same task logic, different environments!
@dev_env.task()
def process_data(source) -> pl.LazyFrame:
    return source.scan()
```

### Heterogeneous Execution

Mix different execution backends in one pipeline:

```python
env = GlacierEnv(provider=AWSProvider(config=AwsConfig(region="us-east-1")))

@env.task()
def load_from_s3(source) -> pl.LazyFrame:
    """Runs locally."""
    return source.scan()

@env.task(executor="dbt")
def transform_with_dbt(df: pl.LazyFrame) -> pl.LazyFrame:
    """Runs on DBT."""
    # DBT transformation logic
    pass

@env.task(executor="databricks")
def ml_on_databricks(df: pl.LazyFrame) -> pl.LazyFrame:
    """Runs on Databricks."""
    # ML processing on Databricks
    pass

@env.task()
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

## Environment Registry Pattern

Register commonly used resources in the environment for easy access:

```python
from glacier import GlacierEnv
from glacier.providers import AWSProvider
from glacier.config import AwsConfig, S3Config

# Create environment
provider = AWSProvider(config=AwsConfig(region="us-east-1"))
env = GlacierEnv(provider=provider, name="production")

# Register shared resources
env.register("sales_raw", provider.bucket(
    "sales",
    path="raw/transactions.parquet",
    config=S3Config(versioning=True, encryption="AES256")
))

env.register("sales_processed", provider.bucket(
    "sales",
    path="processed/transactions.parquet",
    config=S3Config(versioning=True, encryption="AES256")
))

env.register("customers", provider.bucket(
    "customers",
    path="customers.parquet"
))

# Tasks can retrieve resources from registry
@env.task()
def extract_sales() -> pl.LazyFrame:
    source = env.get("sales_raw")
    return source.scan()

@env.task()
def save_results(df: pl.LazyFrame) -> None:
    target = env.get("sales_processed")
    df.collect().write_parquet(target.get_uri())

# List registered resources
print(env.list_resources())  # ['sales_raw', 'sales_processed', 'customers']
```

## Multi-Cloud Support

The environment-first pattern makes multi-cloud deployment simple:

```python
from glacier import GlacierEnv
from glacier.providers import AWSProvider, AzureProvider, LocalProvider, GCPProvider
from glacier.config import AwsConfig, AzureConfig, LocalConfig, GcpConfig

# Development: Local
dev_env = GlacierEnv(
    provider=LocalProvider(config=LocalConfig(base_path="./data")),
    name="development"
)

# Staging: AWS
staging_env = GlacierEnv(
    provider=AWSProvider(config=AwsConfig(region="us-west-2", profile="staging")),
    name="staging"
)

# Production: Azure
prod_env = GlacierEnv(
    provider=AzureProvider(config=AzureConfig(
        resource_group="prod-rg",
        location="eastus",
        subscription_id="..."
    )),
    name="production"
)

# GCP option
gcp_env = GlacierEnv(
    provider=GCPProvider(config=GcpConfig(
        project_id="my-project",
        region="us-central1"
    )),
    name="gcp-prod"
)

# Define tasks once, bind to multiple environments
def create_tasks(env: GlacierEnv):
    @env.task()
    def process_data(source) -> pl.LazyFrame:
        return source.scan()

    return process_data

# Bind to each environment
dev_task = create_tasks(dev_env)
staging_task = create_tasks(staging_env)
prod_task = create_tasks(prod_env)
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

### GlacierEnv (Environment)

The central orchestrator using dependency injection:

```python
from glacier import GlacierEnv
from glacier.providers import AWSProvider
from glacier.config import AwsConfig

# Create environment with provider
provider = AWSProvider(config=AwsConfig(region="us-east-1"))
env = GlacierEnv(provider=provider, name="production")

# Environment manages:
# - Provider configuration
# - Resource registry (env.register(), env.get())
# - Task binding (@env.task())
# - Pipeline binding (@env.pipeline())
```

### Providers

Providers abstract over cloud platforms and require configuration classes:

```python
from glacier.providers import AWSProvider, AzureProvider, GCPProvider, LocalProvider
from glacier.config import AwsConfig

# With config (required)
provider = AWSProvider(config=AwsConfig(region="us-east-1", profile="prod"))

# From environment variables
provider = AWSProvider.from_env()

# Create environment from provider
env = provider.env(name="production")
```

### Resources

Resources are cloud-agnostic abstractions (Bucket, Serverless):

```python
# Created via provider (recommended)
bucket = provider.bucket(
    "my-data",
    path="file.parquet",
    config=S3Config(versioning=True)
)

# Register in environment for shared access
env.register("data", bucket)

# Retrieve from environment
data = env.get("data")
```

### Tasks

Tasks are environment-bound functions:

```python
# Basic task
@env.task()
def my_task(input: pl.LazyFrame) -> pl.LazyFrame:
    return input.filter(pl.col("value") > 0)

# Task with configuration
@env.task(timeout=600, retries=3, executor="databricks")
def heavy_task(df: pl.LazyFrame) -> pl.LazyFrame:
    return df.filter(pl.col("value") > 100)
```

### Pipelines

Pipelines orchestrate tasks:

```python
# Define pipeline
@env.pipeline(name="my_pipeline")
def my_pipeline():
    source = env.provider.bucket("data", path="input.parquet")
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
