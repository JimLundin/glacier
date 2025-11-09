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

### Layer 2: Explicit Environments
When you need multi-account/multi-region or want to organize by environment.

Our `Environment` wrapper provides **convenience over Pulumi** - sensible defaults, less boilerplate.

```python
from glacier import Pipeline, Dataset
from glacier_aws import Environment

# Define environments (wraps Pulumi with defaults)
aws_prod = Environment(account="123456", region="us-east-1", name="prod")
aws_dev = Environment(account="789012", region="us-west-2", name="dev")

# Resources get environment tags automatically
prod_bucket = aws_prod.s3(bucket="prod-data")  # Creates pulumi_aws.s3.BucketV2
dev_bucket = aws_dev.s3(bucket="dev-data")

# Use in pipeline
prod_data = Dataset(name="data", storage=prod_bucket)

@pipeline.task()
def process() -> prod_data:
    return transform(data)
```

**What's happening:** `aws_prod.s3()` is just calling `pulumi_aws.s3.BucketV2()` with:
- Automatic environment tags
- Sensible defaults
- Less boilerplate

You're still using Pulumi - we're just making it easier.

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
        mfa_delete=True
    ),
    lifecycle_rules=[
        aws.s3.BucketLifecycleRuleArgs(
            enabled=True,
            transitions=[{
                "days": 30,
                "storage_class": "GLACIER"
            }, {
                "days": 90,
                "storage_class": "DEEP_ARCHIVE"
            }]
        )
    ],
    replication_configuration=aws.s3.BucketReplicationConfigurationArgs(
        role=replication_role.arn,
        rules=[...]
    )
)

# Use in pipeline like any other resource
data = Dataset(name="data", storage=bucket)
```

**No wrappers, no abstractions** - just use Pulumi features directly.

---

## Core Concepts

### Pipeline
Container for tasks with auto-inferred DAG from type annotations.

### Task
Python function decorated with `@pipeline.task()`. Dependencies inferred from parameters/return types.

### Dataset
Data artifact with optional storage. Accepts:
- Nothing (ephemeral)
- Our `ObjectStorage`/`Database` configs (provider-agnostic)
- `Environment.s3()` / `Environment.rds()` (Pulumi with defaults)
- Raw Pulumi resources (full control)

### Environment (Optional)
Convenience wrapper for organizing multi-account/region deployments. Creates Pulumi resources with sensible defaults.

---

## Design Principles

1. **Progressive disclosure**: Start simple, add complexity as needed
2. **Pulumi, not abstraction**: We wrap Pulumi for convenience, not replace it
3. **Always an escape hatch**: Can drop down to raw Pulumi anytime
4. **Provider-agnostic core**: Base library has zero cloud dependencies
5. **Type-driven**: DAG inferred from function signatures

---

## Package Structure

```
glacier/
├── core/          # Pipeline, Task, Dataset (no cloud deps)
├── storage/       # Generic ObjectStorage, Database configs
└── compute/       # Generic Serverless, Container configs

providers/
├── glacier-aws/
│   └── Environment    # Convenience wrapper over pulumi_aws
├── glacier-gcp/       # (future)
└── glacier-local/
    └── LocalExecutor  # Run pipelines locally
```

---

## When to Use Each Layer

**Layer 1 (Implicit):**
- Single AWS account
- Simple deployments
- Prototyping/testing
- Local development

**Layer 2 (Environment):**
- Multi-account (dev/staging/prod)
- Multi-region deployments
- Want organized tagging
- Want less Pulumi boilerplate

**Layer 3 (Raw Pulumi):**
- Need specific Pulumi features
- Complex infrastructure requirements
- Advanced networking/security
- Custom resource configurations

Start with Layer 1. Move to Layer 2 when you need environments. Use Layer 3 when you need specific features.
