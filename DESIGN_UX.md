# Glacier Library - UX Design Document (CORRECT ARCHITECTURE)

**Version:** 3.0
**Date:** 2025-11-06
**Status:** Living Document | Alpha Software | **BREAKING REDESIGN**

---

## ⚠️ Alpha Status Notice

**Glacier is currently in ALPHA**. This means:

- **No Backwards Compatibility Guarantees**: The API may change significantly between releases
- **Breaking Changes Expected**: We prioritize getting the design right over maintaining compatibility
- **Clean Slate Approach**: Old patterns are removed in favor of better designs
- **Production Use**: Not recommended until we reach v1.0

This document describes the **CORRECT architecture** that Glacier should implement.

---

## 🚨 CRITICAL DESIGN PRINCIPLES

### 1. NO PROVIDER-SPECIFIC CLASSES

**THE ENTIRE POINT OF THIS DESIGN IS DEPENDENCY INJECTION THROUGH CONFIGURATION, NOT SUBCLASSES.**

❌ **WRONG:**
```python
from glacier.providers import AWSProvider, GCPProvider, AzureProvider

provider = AWSProvider(config=AwsConfig(...))      # BAD
provider = GCPProvider(config=GcpConfig(...))      # BAD
provider = AzureProvider(config=AzureConfig(...))  # BAD
```

✅ **CORRECT:**
```python
from glacier import Provider
from glacier.config import AwsConfig, GcpConfig, AzureConfig

provider = Provider(config=AwsConfig(region="us-east-1"))        # AWS behavior
provider = Provider(config=GcpConfig(project_id="my-project"))   # GCP behavior
provider = Provider(config=AzureConfig(subscription_id="..."))   # Azure behavior
```

### 2. EXECUTION RESOURCES ARE FIRST-CLASS OBJECTS

**Execution resources (where code runs) are created from the provider, just like storage resources (where data lives).**

❌ **WRONG:**
```python
@env.task(executor="databricks")  # String - not a resource!
def my_task():
    pass
```

✅ **CORRECT:**
```python
# Execution resource is a first-class object
databricks_exec = provider.cluster(
    config=DatabricksConfig(
        cluster_id="cluster-123",
        instance_type="i3.xlarge"
    )
)

# Tasks bound to execution resources
@databricks_exec.task()
def my_task():
    pass
```

### 3. NO DEPLOYMENT ENVIRONMENT IN GLACIER

**Glacier handles EXECUTION environments (where code runs, where data lives), NOT deployment environments (dev/staging/prod).**

Deployment environments are INFRASTRUCTURE concerns handled via:
- Separate Terraform workspaces
- Different AWS accounts/GCP projects/Azure subscriptions
- CI/CD pipeline configuration

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Core Architecture](#core-architecture)
3. [Resource Types](#resource-types)
4. [Task Binding Pattern](#task-binding-pattern)
5. [Pipeline Pattern](#pipeline-pattern)
6. [Cloud Portability](#cloud-portability)
7. [Complete Examples](#complete-examples)

---

## Executive Summary

Glacier is a **cloud-agnostic data pipeline library** built on **dependency injection** and **resource-centric design**. The library prioritizes:

- **Provider creates resources** - Both storage AND execution are first-class resources
- **Config determines behavior** - No provider-specific classes, only config classes
- **Tasks bound to execution resources** - @executor.task(), not string-based executor
- **Cloud portability** - Switch providers via configuration injection only
- **Infrastructure from code** - Auto-generate Terraform from pipeline definitions
- **NO deployment environment** - Glacier does not handle dev/staging/prod concerns

---

## Core Architecture

### The Provider Pattern

The `Provider` is the single entry point for creating resources. Its behavior is determined by the injected configuration.

```python
from glacier import Provider, pipeline
from glacier.config import AwsConfig, LocalConfig
import polars as pl

# Provider configuration determines WHERE DATA LIVES
provider = Provider(config=AwsConfig(region="us-east-1"))

# Provider creates TWO types of resources:

# 1. STORAGE resources (where data lives)
bucket = provider.bucket(
    bucket="my-data",
    path="file.parquet",
    config=S3Config(versioning=True, encryption="AES256")
)

# 2. EXECUTION resources (where code runs)
local_exec = provider.local()
lambda_exec = provider.serverless(config=LambdaConfig(memory=1024))
databricks_exec = provider.cluster(config=DatabricksConfig(...))
spark_exec = provider.cluster(config=SparkConfig(...))
vm_exec = provider.vm(config=EC2Config(...))

# Tasks bound to execution resources
@local_exec.task()
def process_data(source) -> pl.LazyFrame:
    return source.scan().filter(pl.col("value") > 0)

# Pipelines orchestrate tasks
@pipeline(name="my_pipeline")
def my_pipeline():
    data = process_data(bucket)
    return data
```

### Key Principles

1. **Single Provider class** - Config determines behavior (AWS, Azure, GCP, Local)
2. **Resources are objects** - Both storage and execution are first-class resources
3. **Tasks bound to executors** - `@executor.task()`, not `@env.task(executor=...)`
4. **Cloud-agnostic** - Same code, different configs = different clouds
5. **NO GlacierEnv** - No DI container concept in user-facing API

---

## Resource Types

### Storage Resources (Where Data Lives)

**Generic method:** `provider.bucket()`

**Config determines backend:**
- `S3Config` → AWS S3
- `AzureBlobConfig` → Azure Blob Storage
- `GCSConfig` → Google Cloud Storage
- `None` → Default based on provider config

```python
# AWS S3
provider = Provider(config=AwsConfig(region="us-east-1"))
bucket = provider.bucket(
    bucket="my-bucket",
    path="data.parquet",
    config=S3Config(
        storage_class="INTELLIGENT_TIERING",
        encryption="AES256",
        versioning=True
    )
)

# Azure Blob Storage
provider = Provider(config=AzureConfig(...))
bucket = provider.bucket(
    bucket="my-container",
    path="data.parquet",
    config=AzureBlobConfig(
        tier="hot",
        encryption=True
    )
)

# Same bucket interface, different backend!
data = bucket.scan()
```

### Execution Resources (Where Code Runs)

**Generic methods:**
- `provider.local()` → Local Python process
- `provider.serverless(config=...)` → Lambda/Cloud Functions/Azure Functions
- `provider.vm(config=...)` → EC2/Compute Engine/Azure VM
- `provider.cluster(config=...)` → Databricks/EMR/Dataproc/Spark

**Config determines backend:**

```python
# Local execution
local_exec = provider.local()

# Serverless execution
lambda_exec = provider.serverless(
    config=LambdaConfig(
        memory=1024,
        timeout=300,
        runtime="python3.11"
    )
)

# AWS: Creates Lambda
# Azure: Creates Azure Function
# GCP: Creates Cloud Function
# Config determines actual backend!

# Cluster execution
databricks_exec = provider.cluster(
    config=DatabricksConfig(
        cluster_id="cluster-123",
        instance_type="i3.xlarge",
        num_workers=4
    )
)

# Databricks/EMR/Dataproc determined by provider + config

# VM execution
ec2_exec = provider.vm(
    config=EC2Config(
        instance_type="t3.large",
        ami="ami-12345"
    )
)

# EC2/Compute Engine/Azure VM determined by provider + config
```

---

## Task Binding Pattern

**Tasks are bound to execution resources, NOT to environments or via string parameters.**

### Correct Pattern

```python
from glacier import Provider, pipeline
from glacier.config import AwsConfig, DatabricksConfig
import polars as pl

provider = Provider(config=AwsConfig(region="us-east-1"))

# Create execution resources
local_exec = provider.local()
databricks_exec = provider.cluster(config=DatabricksConfig(...))

# Bind tasks to execution resources
@local_exec.task()
def load_data(source) -> pl.LazyFrame:
    """Runs on local Python process."""
    return source.scan()

@databricks_exec.task()
def ml_inference(df: pl.LazyFrame) -> pl.LazyFrame:
    """Runs on Databricks cluster."""
    return df.with_columns(pl.lit(0.85).alias("prediction"))

@local_exec.task()
def save_results(df: pl.LazyFrame) -> None:
    """Runs on local Python process."""
    df.collect().write_parquet("output.parquet")
```

### Incorrect Patterns (DO NOT USE)

```python
# ❌ WRONG: String-based executor
@task(executor="databricks")
def my_task():
    pass

# ❌ WRONG: Environment-based binding with string executor
@env.task(executor="databricks")
def my_task():
    pass

# ❌ WRONG: GlacierEnv concept
env = GlacierEnv(provider=provider)
@env.task()
def my_task():
    pass
```

---

## Pipeline Pattern

**Pipelines orchestrate tasks and define data flow.**

```python
from glacier import Provider, pipeline
import polars as pl

provider = Provider(config=AwsConfig(region="us-east-1"))

# Execution resources
local_exec = provider.local()
spark_exec = provider.cluster(config=SparkConfig(...))

# Storage resources
raw_data = provider.bucket(bucket="data", path="raw.parquet")
output_bucket = provider.bucket(bucket="data", path="output.parquet")

# Tasks
@local_exec.task()
def extract(source) -> pl.LazyFrame:
    return source.scan()

@spark_exec.task()
def transform(df: pl.LazyFrame) -> pl.LazyFrame:
    return df.filter(pl.col("value") > 0)

@local_exec.task()
def load(df: pl.LazyFrame) -> None:
    df.collect().write_parquet(output_bucket.get_uri())

# Pipeline
@pipeline(name="etl")
def etl_pipeline():
    """ETL pipeline with heterogeneous execution."""
    data = extract(raw_data)          # Runs on local_exec
    transformed = transform(data)     # Runs on spark_exec
    load(transformed)                 # Runs on local_exec
    return transformed

# Execute
result = etl_pipeline.run(mode="local")
```

---

## Cloud Portability

**Same code works with ALL cloud providers by changing only the provider configuration.**

```python
import os
from glacier import Provider
from glacier.config import AwsConfig, AzureConfig, GcpConfig, LocalConfig

# Dynamic provider selection
def create_provider():
    cloud = os.getenv("GLACIER_CLOUD", "local")

    if cloud == "aws":
        return Provider(config=AwsConfig(region="us-east-1"))
    elif cloud == "azure":
        return Provider(config=AzureConfig(...))
    elif cloud == "gcp":
        return Provider(config=GcpConfig(...))
    else:
        return Provider(config=LocalConfig(base_path="./data"))

provider = create_provider()

# Rest of code is IDENTICAL regardless of provider!
local_exec = provider.local()
bucket = provider.bucket(bucket="data", path="file.parquet")

@local_exec.task()
def process(source):
    return source.scan()

# Works on AWS S3, Azure Blob, GCS, or local filesystem!
```

---

## Complete Examples

### Example 1: Simple Local Pipeline

```python
from glacier import Provider, pipeline
from glacier.config import LocalConfig
import polars as pl

# Provider
provider = Provider(config=LocalConfig(base_path="./data"))

# Resources
local_exec = provider.local()
data_source = provider.bucket(bucket="data", path="input.parquet")

# Tasks
@local_exec.task()
def load(source) -> pl.LazyFrame:
    return source.scan()

@local_exec.task()
def transform(df: pl.LazyFrame) -> pl.LazyFrame:
    return df.filter(pl.col("value") > 0)

# Pipeline
@pipeline(name="simple")
def simple_pipeline():
    data = load(data_source)
    result = transform(data)
    return result

# Execute
result = simple_pipeline.run(mode="local")
print(result.collect())
```

### Example 2: Heterogeneous Execution on AWS

```python
from glacier import Provider, pipeline
from glacier.config import AwsConfig, LambdaConfig, DatabricksConfig
import polars as pl

# Provider
provider = Provider(config=AwsConfig(region="us-east-1"))

# Execution resources
local_exec = provider.local()
lambda_exec = provider.serverless(config=LambdaConfig(memory=1024))
databricks_exec = provider.cluster(config=DatabricksConfig(...))

# Storage resources
raw_data = provider.bucket(bucket="data-lake", path="raw/data.parquet")
features = provider.bucket(bucket="data-lake", path="features/features.parquet")

# Tasks on different executors
@local_exec.task()
def extract(source) -> pl.LazyFrame:
    return source.scan()

@lambda_exec.task()
def clean(df: pl.LazyFrame) -> pl.LazyFrame:
    return df.filter(pl.col("value").is_not_null())

@databricks_exec.task()
def ml_predict(df: pl.LazyFrame) -> pl.LazyFrame:
    return df.with_columns(pl.lit(0.9).alias("prediction"))

@local_exec.task()
def save(df: pl.LazyFrame) -> None:
    df.collect().write_parquet("output.parquet")

# Pipeline
@pipeline(name="ml_inference")
def ml_pipeline():
    data = extract(raw_data)          # Local
    cleaned = clean(data)             # Lambda
    predictions = ml_predict(cleaned) # Databricks
    save(predictions)                 # Local
    return predictions

result = ml_pipeline.run(mode="local")
```

---

## Summary

### Core Patterns

1. **Provider creates resources:**
   - Storage: `provider.bucket(config=S3Config/AzureBlobConfig/GCSConfig)`
   - Execution: `provider.local()`, `provider.serverless()`, `provider.vm()`, `provider.cluster()`

2. **Tasks bound to execution resources:**
   - `@executor.task()` where executor is a resource object

3. **Pipelines orchestrate tasks:**
   - `@pipeline(name="...")` decorator

4. **Cloud portability:**
   - Same code, different provider configs

5. **NO deployment environment:**
   - Glacier does not handle dev/staging/prod
   - Use infrastructure tools (Terraform workspaces, separate accounts)

### What Changed from Old Design

| Old (WRONG) | New (CORRECT) |
|-------------|---------------|
| `@env.task(executor="databricks")` | `@databricks_exec.task()` |
| `GlacierEnv` as DI container | No GlacierEnv in user API |
| String-based executors | Execution resources as objects |
| `env.get("resource")` registry | Resources passed directly |
| Deployment env in library | No deployment env concept |

---

**END OF DOCUMENT**
