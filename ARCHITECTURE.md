# Glacier Architecture

Glacier is a code-centric data pipeline framework with **three layers of explicitness** - use what you need as complexity grows.

## The Three Layers

### Layer 1: Implicit (Simplest)
Everything automatic - perfect for single environment, simple deployments.

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

# Run locally
from glacier_local import LocalExecutor
LocalExecutor().execute(pipeline)
```

No configuration needed. Just define your pipeline and run it.

---

### Layer 2: Environment (Provider-Agnostic!)
When you need multi-account/multi-region or want to organize by environment.

**Key insight:** `Environment` is provider-agnostic. You inject the provider via dependency injection.

```python
from glacier import Pipeline, Dataset, Environment
from glacier_aws import AWSProvider

# Inject AWS provider into generic Environment
env = Environment(
    provider=AWSProvider(account="123456", region="us-east-1"),
    name="prod"
)

# Generic methods that work across any provider
storage = env.object_storage(name="data")     # → S3 on AWS
compute = env.serverless(name="func", ...)    # → Lambda on AWS
db = env.database(name="db", engine="postgres")  # → RDS on AWS

# Use in pipeline
data = Dataset(name="data", storage=storage)
```

**To switch to Azure - just change the provider config:**

```python
from glacier_azure import AzureProvider

env = Environment(
    provider=AzureProvider(subscription="xyz", region="eastus"),
    name="prod"
)

# SAME CODE! Different provider
storage = env.object_storage(name="data")     # → Blob Storage
compute = env.serverless(name="func", ...)    # → Azure Functions
db = env.database(name="db", engine="postgres")  # → Azure SQL
```

**Multi-cloud - different providers per environment:**

```python
from glacier_aws import AWSProvider
from glacier_azure import AzureProvider

dev = Environment(provider=AWSProvider(...), name="dev")
prod = Environment(provider=AzureProvider(...), name="prod")

dev_storage = dev.object_storage(name="data")   # S3
prod_storage = prod.object_storage(name="data") # Blob Storage
```

**What's happening under the hood:**
- `Environment` provides generic methods: `object_storage()`, `serverless()`, `database()`
- These delegate to the provider implementation (`AWSProvider`, `AzureProvider`, etc.)
- Providers call Pulumi with sensible defaults: `pulumi_aws.s3.BucketV2()`, etc.
- Automatic environment tagging and configuration

---

### Layer 3: Raw Pulumi (Escape Hatch)
When you need full control - drop down to Pulumi directly.

```python
from glacier import Pipeline, Dataset
import pulumi_aws as aws

# Use Pulumi directly for advanced features
bucket = aws.s3.BucketV2(
    "my-data",
    bucket="my-data",
    versioning=aws.s3.BucketVersioningArgs(
        enabled=True,
        mfa_delete=True  # Advanced feature!
    ),
    lifecycle_rules=[
        aws.s3.BucketLifecycleRuleArgs(
            enabled=True,
            transitions=[{
                "days": 30,
                "storage_class": "GLACIER"
            }]
        )
    ]
)

# Use in pipeline like any other resource
data = Dataset(name="data", storage=bucket)

# Mix with Layer 2 resources!
compute = env.serverless(name="func", ...)  # Layer 2
```

**No wrappers, no abstractions** - just use Pulumi features directly. Mix freely with Layer 2.

---

## Core Concepts

### Pipeline
Container for tasks with auto-inferred DAG from type annotations.

### Task
Python function decorated with `@pipeline.task()`. Dependencies inferred from parameters/return types.

### Dataset
Data artifact with optional storage. Accepts:
- Nothing (ephemeral)
- Our `ObjectStorage`/`Database` configs (provider-agnostic, Layer 1)
- `Environment.object_storage()` / `Environment.database()` (provider-agnostic, Layer 2)
- Raw Pulumi resources (provider-specific, Layer 3)

### Environment
**Provider-agnostic** wrapper for organizing multi-account/region deployments.

Generic methods:
- `object_storage(name, **kwargs)` → S3, Blob Storage, GCS
- `serverless(name, handler, code, **kwargs)` → Lambda, Functions, Cloud Run
- `database(name, engine, **kwargs)` → RDS, Azure SQL, Cloud SQL

You inject the provider via dependency injection: `Environment(provider=AWSProvider(...))`

### Provider
Provider implementations create Pulumi resources. Examples:
- `AWSProvider` → Uses `pulumi_aws`
- `AzureProvider` → Uses `pulumi_azure`
- `GCPProvider` → Uses `pulumi_gcp`

Providers implement the `Provider` interface with methods like `object_storage()`, `serverless()`, etc.

---

## Design Principles

1. **Progressive disclosure**: Start simple, add complexity as needed
2. **Dependency injection**: Provider config injected into Environment
3. **Provider-agnostic Layer 2**: Switch clouds by changing config, not code
4. **Pulumi, not abstraction**: We wrap Pulumi for convenience, not replace it
5. **Always an escape hatch**: Can drop down to raw Pulumi anytime
6. **Provider-agnostic core**: Base library has zero cloud dependencies
7. **Type-driven**: DAG inferred from function signatures

---

## Package Structure

```
glacier/
├── core/
│   ├── pipeline.py       # Pipeline with auto DAG
│   ├── task.py           # @task decorator
│   ├── dataset.py        # Data artifacts
│   └── environment.py    # Provider-agnostic Environment + Provider interface
├── storage/              # Generic ObjectStorage, Database configs (Layer 1)
└── compute/              # Generic Serverless, Container configs (Layer 1)

providers/
├── glacier-aws/
│   └── provider.py       # AWSProvider (implements Provider interface)
├── glacier-azure/        # (future)
│   └── provider.py       # AzureProvider
├── glacier-gcp/          # (future)
│   └── provider.py       # GCPProvider
└── glacier-local/
    └── executor.py       # LocalExecutor (run locally, no cloud)
```

---

## When to Use Each Layer

**Layer 1 (Implicit):**
- Single account deployment
- Simple use cases
- Prototyping/testing
- Local development

**Layer 2 (Environment):**
- Multi-account (dev/staging/prod)
- Multi-region deployments
- Want organized tagging
- Want less Pulumi boilerplate
- **Need to switch providers** (AWS → Azure → GCP)

**Layer 3 (Raw Pulumi):**
- Need specific Pulumi features
- Complex infrastructure requirements
- Advanced networking/security
- Custom resource configurations

Start with Layer 1. Move to Layer 2 when you need environments or provider flexibility. Use Layer 3 when you need specific Pulumi features.

---

## Key Innovation: Provider-Agnostic Layer 2

Unlike other frameworks, Glacier's Layer 2 is **truly provider-agnostic**:

```python
# Define once
def create_env(provider):
    return Environment(provider=provider, name="prod")

# Deploy to any cloud
aws_env = create_env(AWSProvider(account="123", region="us-east-1"))
azure_env = create_env(AzureProvider(subscription="xyz", region="eastus"))
gcp_env = create_env(GCPProvider(project="my-proj", region="us-central1"))

# Same code works across all providers
for env in [aws_env, azure_env, gcp_env]:
    storage = env.object_storage(name="data")
    compute = env.serverless(name="func", handler="index.handler", code=...)
```

Switch clouds by changing the provider config. No code changes needed.
