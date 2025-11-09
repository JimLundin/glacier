# Glacier 🏔️

**Code-centric data pipeline framework with progressive disclosure**

Build data pipelines in Python with three layers of explicitness - start simple, add complexity only when needed.

**⚠️ ALPHA SOFTWARE** - API may change. No backwards compatibility guarantees until v1.0.

---

## Quick Example

```python
from glacier import Pipeline, Dataset

pipeline = Pipeline(name="etl")

raw = Dataset(name="raw")
clean = Dataset(name="clean")

@pipeline.task()
def extract() -> raw:
    return fetch_data()

@pipeline.task()
def transform(data: raw) -> clean:
    return process(data)

# Run locally (no cloud needed)
from glacier_local import LocalExecutor
LocalExecutor().execute(pipeline)
```

That's it. **No configuration, no cloud dependencies, just Python.**

---

## The Three Layers

Glacier has **three layers of explicitness** - use what you need as complexity grows:

### Layer 1: Implicit (Simplest)
Start here. No cloud configuration needed.

```python
from glacier import Pipeline, Dataset

pipeline = Pipeline(name="etl")
raw = Dataset(name="raw")
clean = Dataset(name="clean")

@pipeline.task()
def extract() -> raw:
    return fetch_data()

@pipeline.task()
def transform(data: raw) -> clean:
    return process(data)

# Run locally for development/testing
from glacier_local import LocalExecutor
LocalExecutor().execute(pipeline)
```

**Perfect for:** Single environment, prototyping, local development

---

### Layer 2: Environment (Provider-Agnostic)
When you need multi-account/multi-region or want to organize by environment.

```python
from glacier import Pipeline, Dataset, Environment
from glacier_aws import AWSProvider

# Inject provider config
env = Environment(
    provider=AWSProvider(account="123456", region="us-east-1"),
    name="prod"
)

# Generic methods work across any provider
storage = env.object_storage(name="data")  # → S3 on AWS
compute = env.serverless(name="func", handler="index.handler", code=...)

data = Dataset(name="data", storage=storage)
```

**Switch to Azure? Just change the provider:**

```python
from glacier_azure import AzureProvider

env = Environment(
    provider=AzureProvider(subscription="xyz", region="eastus"),
    name="prod"
)

# SAME CODE! Different cloud
storage = env.object_storage(name="data")  # → Blob Storage on Azure
```

**Perfect for:** Multi-account, multi-region, switching clouds, organized tagging

---

### Layer 3: Raw Pulumi (Escape Hatch)
When you need full control, use Pulumi directly.

```python
import pulumi_aws as aws

# Use Pulumi features directly - no wrappers!
bucket = aws.s3.BucketV2(
    "my-data",
    versioning=aws.s3.BucketVersioningArgs(enabled=True, mfa_delete=True),
    lifecycle_rules=[...],
    replication_configuration=[...]
)

# Use in pipeline like any other resource
data = Dataset(name="data", storage=bucket)
```

**Perfect for:** Advanced Pulumi features, complex requirements, custom configurations

---

## Core Concepts

### Pipeline
Container for tasks with auto-inferred DAG from type annotations.

### Task
Python function with `@pipeline.task()`. Dependencies inferred from type hints.

```python
@pipeline.task()
def extract() -> raw_data:  # Produces raw_data
    return fetch()

@pipeline.task()
def transform(data: raw_data) -> clean_data:  # Consumes raw_data, produces clean_data
    return process(data)

# DAG automatically inferred: extract → transform
```

### Dataset
Data artifact that flows through the pipeline. Accepts:
- Nothing (ephemeral)
- Our generic configs: `ObjectStorage`, `Database`
- Environment resources: `env.object_storage()`
- Raw Pulumi resources: `aws.s3.BucketV2()`

### Environment
**Provider-agnostic** wrapper for multi-account/region deployments.

Generic methods:
- `object_storage(name)` → S3, Blob Storage, GCS
- `serverless(name, handler, code)` → Lambda, Azure Functions, Cloud Run
- `database(name, engine)` → RDS, Azure SQL, Cloud SQL

You inject the provider: `Environment(provider=AWSProvider(...))`

**Key insight:** Switch clouds by changing provider config, not code.

---

## Key Features

**Type-Driven DAG** - Dependencies inferred from function signatures. No manual wiring.

**Progressive Disclosure** - Start simple (Layer 1), add complexity as needed (Layer 2, 3).

**Provider-Agnostic Layer 2** - Generic methods work across AWS, Azure, GCP. Switch by changing config.

**Pulumi Escape Hatch** - Drop down to raw Pulumi anytime for full control.

**Zero Cloud Dependencies** - Core library has no cloud SDKs. Provider packages are optional.

**Local Execution** - Test pipelines locally before deploying to cloud.

---

## Installation

```bash
# Core library (no cloud dependencies)
pip install glacier-pipeline

# Add AWS provider
pip install glacier-pipeline[aws]

# Add local executor
pip install glacier-pipeline[local]

# Add all providers
pip install glacier-pipeline[all]
```

---

## Examples

See [examples/](./examples/) for complete working examples:

- **three_layers.py** - Demonstrates all three layers of explicitness
- **provider_switching.py** - Shows switching between AWS/Azure/GCP

Run them:

```bash
python examples/three_layers.py
python examples/provider_switching.py
```

---

## Architecture

For detailed design documentation, see [ARCHITECTURE.md](./ARCHITECTURE.md)

Key components:

```
glacier/
├── core/
│   ├── pipeline.py      # Pipeline with auto DAG inference
│   ├── task.py          # @task decorator
│   ├── dataset.py       # Data artifacts
│   └── environment.py   # Provider-agnostic Environment + Provider interface
├── storage/             # Generic storage configs (Layer 1)
└── compute/             # Generic compute configs (Layer 1)

providers/
├── glacier-aws/         # AWS provider implementation
├── glacier-local/       # Local execution
└── glacier-azure/       # (future) Azure provider
```

---

## Design Principles

1. **Progressive disclosure** - Start simple, add complexity as needed
2. **Dependency injection** - Provider config injected into Environment
3. **Provider-agnostic Layer 2** - Switch clouds by changing config, not code
4. **Pulumi, not abstraction** - We wrap Pulumi for convenience, not replace it
5. **Always an escape hatch** - Can drop down to raw Pulumi anytime
6. **Type-driven** - DAG inferred from function signatures

---

## Current Status

**Implemented:**
- ✅ Three-layer architecture (Implicit, Environment, Raw Pulumi)
- ✅ Provider-agnostic Environment with dependency injection
- ✅ Auto DAG inference from type hints
- ✅ Local execution
- ✅ AWS provider implementation
- ✅ Generic storage/compute abstractions

**Coming Soon:**
- 🚧 Azure provider
- 🚧 GCP provider
- 🚧 Schema validation
- 🚧 Data lineage tracking
- 🚧 Execution on deployed infrastructure

---

## License

MIT License - see [LICENSE](./LICENSE) for details.
