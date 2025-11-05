# Glacier Library - UX Design Document

**Version:** 2.1
**Date:** 2025-11-05
**Status:** Living Document | Alpha Software

---

## ⚠️ Alpha Status Notice

**Glacier is currently in ALPHA**. This means:

- **No Backwards Compatibility Guarantees**: The API may change significantly between releases
- **Breaking Changes Expected**: We prioritize getting the design right over maintaining compatibility
- **Clean Slate Approach**: Old patterns are removed in favor of better designs
- **Production Use**: Not recommended until we reach v1.0

This document describes the **current recommended approach** - the environment-first pattern with dependency injection. Previous patterns (global decorators, string-based dependencies) have been removed.

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Design Philosophy](#design-philosophy)
3. [Core Architecture Principles](#core-architecture-principles)
4. [Configuration Hierarchy](#configuration-hierarchy)
5. [Environment-Based Design](#environment-based-design)
6. [Dependency Injection Patterns](#dependency-injection-patterns)
7. [Task Binding Approaches](#task-binding-approaches)
8. [Resource Creation Patterns](#resource-creation-patterns)
9. [Recommended Design](#recommended-design)
10. [Example Usage Scenarios](#example-usage-scenarios)
11. [Testing and Mocking](#testing-and-mocking)
12. [Alpha Status - No Migration Path](#alpha-status---no-migration-path)
13. [Future Enhancements](#future-enhancements)

---

## Executive Summary

Glacier is a **cloud-agnostic data pipeline library** built on **dependency injection** and **environment-based configuration**. The library prioritizes:

- **Explicit dependencies** - Clear configuration injection at every level
- **Environment-first** - Tasks bound to environments, not global state
- **Type safety** - Leverage Python type hints for correctness
- **Cloud portability** - Switch providers via configuration injection
- **Infrastructure from code** - Auto-generate Terraform from pipeline definitions
- **Testability** - Easy mocking via dependency injection

This document outlines the **DI/registry-based architecture** where configuration cascades from provider through resources to tasks, all managed through explicit environment contexts.

---

## Design Philosophy

### Core Tenets

1. **Dependency Injection First**
   - Configuration flows explicitly through the system
   - No global state or singletons
   - Every dependency is visible and testable

2. **Environment as Context**
   - Tasks bound to environments, not global decorators
   - Multiple environments can coexist (dev, staging, prod)
   - Environment encapsulates provider, config, and execution context

3. **Configuration Cascade**
   - Provider-level config (AwsConfig, GcpConfig)
   - Resource-level config (S3Config, LambdaConfig)
   - Task-level config (execution settings)
   - Each level inherits and refines parent config

4. **Explicit Over Implicit**
   - Clear dependency declarations
   - Obvious resource relationships
   - Configuration injection visible in code

5. **Cloud Agnostic by Design**
   - Same code structure across all providers
   - Provider swapped via config injection
   - Abstract cloud differences, expose when needed

6. **Testability Built-In**
   - Easy to inject mock configs and providers
   - Environment isolation for unit tests
   - Clear boundaries for integration tests

---

## Core Architecture Principles

### 1. Everything is Injected

**Bad (global state):**
```python
# Global provider - hard to test, unclear dependencies
provider = AWSProvider()

@task
def my_task():
    # Where does this come from?
    source = provider.bucket("data")
```

**Good (dependency injection):**
```python
# Provider injected via environment
env = GlacierEnv(provider=AWSProvider(config=AwsConfig(...)))

@env.task()
def my_task(source: Bucket):
    # Dependencies explicit in signature
    return source.scan()
```

### 2. Environments Manage Scope

**Principle:** Tasks, resources, and execution context belong to an environment.

```python
# Development environment
dev_env = GlacierEnv(
    provider=LocalProvider(config=LocalConfig(base_path="./data"))
)

# Production environment
prod_env = GlacierEnv(
    provider=AWSProvider(config=AwsConfig(region="us-east-1", profile="prod"))
)

# Same task definition works in both
@dev_env.task()
def process_data(source: Bucket) -> pl.LazyFrame:
    return source.scan()

# Can also bind to prod
@prod_env.task()
def process_data_prod(source: Bucket) -> pl.LazyFrame:
    return source.scan()
```

### 3. Configuration Flows Top-Down

**Hierarchy:**
```
ProviderConfig (AwsConfig, GcpConfig, AzureConfig)
    ↓
Provider (AWSProvider, GCPProvider, AzureProvider)
    ↓
ResourceConfig (S3Config, GCSConfig, LambdaConfig)
    ↓
Resource (Bucket, Serverless)
    ↓
TaskConfig (executor, timeout, retries)
    ↓
Task (functions bound to environment)
```

**Example:**
```python
# Provider config
aws_config = AwsConfig(
    region="us-east-1",
    profile="prod",
    tags={"environment": "production", "team": "data"}
)

# Provider with config
provider = AWSProvider(config=aws_config)

# Environment with provider
env = GlacierEnv(provider=provider)

# Resource with provider-specific config
bucket = provider.bucket(
    "sales-data",
    path="transactions.parquet",
    config=S3Config(
        versioning=True,
        encryption="AES256",
        storage_class="INTELLIGENT_TIERING"
    )
)

# Task with execution config
@env.task(executor="local", timeout=300, retries=3)
def process_sales(source: Bucket) -> pl.LazyFrame:
    return source.scan()
```

### 4. Registry vs Pure DI

Glacier uses a **hybrid approach**:

- **Registry pattern** for environment-scoped resources
- **Pure DI** for task dependencies

```python
# Registry: environment tracks resources
env = GlacierEnv(provider=provider)
env.register("sales_data", provider.bucket("sales", path="data.parquet"))
env.register("customer_data", provider.bucket("customers", path="data.parquet"))

# Pure DI: tasks receive dependencies via function parameters
@env.task()
def load_sales(source: Bucket) -> pl.LazyFrame:
    return source.scan()

# Pipeline wires dependencies
@env.pipeline()
def sales_pipeline():
    sales_bucket = env.get("sales_data")
    customer_bucket = env.get("customer_data")

    sales = load_sales(sales_bucket)
    customers = load_customers(customer_bucket)
    return join_data(sales, customers)
```

---

## Configuration Hierarchy

### Provider-Level Configuration

Each provider has its own config class with provider-specific settings.

**AWS Configuration:**
```python
from glacier.config import AwsConfig

aws_config = AwsConfig(
    region="us-east-1",              # AWS region
    profile="production",             # AWS profile name
    account_id="123456789012",        # AWS account ID
    tags={                            # Default tags for all resources
        "environment": "production",
        "managed_by": "glacier",
        "team": "data-engineering"
    },
    assume_role_arn=None,             # Optional role to assume
    session_duration=3600             # Session duration in seconds
)

provider = AWSProvider(config=aws_config)
```

**GCP Configuration:**
```python
from glacier.config import GcpConfig

gcp_config = GcpConfig(
    project_id="my-project",
    region="us-central1",
    credentials_path="/path/to/service-account.json",
    labels={
        "environment": "production",
        "managed_by": "glacier"
    }
)

provider = GCPProvider(config=gcp_config)
```

**Azure Configuration:**
```python
from glacier.config import AzureConfig

azure_config = AzureConfig(
    subscription_id="...",
    resource_group="data-engineering",
    location="eastus",
    tags={"environment": "production"}
)

provider = AzureProvider(config=azure_config)
```

**Local Configuration:**
```python
from glacier.config import LocalConfig

local_config = LocalConfig(
    base_path="./data",              # Base directory for data
    create_dirs=True                  # Auto-create directories
)

provider = LocalProvider(config=local_config)
```

### Resource-Level Configuration

Resources can have provider-specific configurations.

**Bucket Configuration:**
```python
from glacier.config import S3Config, GCSConfig, AzureBlobConfig

# S3-specific config
s3_config = S3Config(
    versioning=True,
    encryption="AES256",
    storage_class="INTELLIGENT_TIERING",
    lifecycle_rules=[
        {"days": 30, "transition": "GLACIER"},
        {"days": 90, "expiration": True}
    ],
    public_access_block=True,
    replication_config=None
)

bucket = provider.bucket(
    "sales-data",
    path="transactions.parquet",
    config=s3_config
)

# GCS-specific config
gcs_config = GCSConfig(
    storage_class="NEARLINE",
    versioning=True,
    lifecycle_rules=[...]
)

# Azure-specific config
azure_config = AzureBlobConfig(
    tier="Hot",
    replication_type="LRS",
    versioning=True
)
```

**Serverless Configuration:**
```python
from glacier.config import LambdaConfig, CloudFunctionConfig, AzureFunctionConfig

# Lambda-specific config
lambda_config = LambdaConfig(
    memory=1024,                      # MB
    timeout=300,                      # seconds
    runtime="python3.11",
    environment_vars={
        "LOG_LEVEL": "INFO"
    },
    layers=[],
    vpc_config=None,
    reserved_concurrent_executions=10
)

fn = provider.serverless(
    "data-processor",
    handler="process.handler",
    config=lambda_config
)
```

### Task-Level Configuration

Tasks can have execution-specific configuration.

```python
from glacier.config import TaskConfig

@env.task(
    executor="local",           # Execution engine
    timeout=300,                # Timeout in seconds
    retries=3,                  # Number of retries
    retry_delay=5,              # Delay between retries
    cache=True,                 # Enable result caching
    tags={"priority": "high"}   # Task-specific tags
)
def expensive_task(df: pl.LazyFrame) -> pl.LazyFrame:
    return df.filter(...)
```

---

## Environment-Based Design

### The GlacierEnv Class

The `GlacierEnv` class is the central orchestrator that manages:
- Provider configuration
- Resource registry
- Task binding
- Execution context

**Basic Usage:**
```python
from glacier import GlacierEnv
from glacier.providers import AWSProvider
from glacier.config import AwsConfig

# Create environment with provider
env = GlacierEnv(
    provider=AWSProvider(config=AwsConfig(region="us-east-1")),
    name="production",
    debug=False
)

# Bind tasks to environment
@env.task()
def my_task(source: Bucket) -> pl.LazyFrame:
    return source.scan()

# Bind pipelines to environment
@env.pipeline()
def my_pipeline():
    source = env.provider.bucket("data", path="sales.parquet")
    return my_task(source)
```

### Alternative: Direct Environment Creation

**Option 1: Provider factory method**
```python
provider = AWSProvider(config=AwsConfig(region="us-east-1"))
env = provider.env(name="production")

@env.task()
def my_task(source: Bucket) -> pl.LazyFrame:
    return source.scan()
```

**Option 2: Environment factory method**
```python
# Create environment from provider type and config
env = GlacierEnv.from_provider(
    provider_type="aws",
    config=AwsConfig(region="us-east-1"),
    name="production"
)
```

**Option 3: Environment from environment variables**
```python
# Reads from GLACIER_PROVIDER, AWS_REGION, etc.
env = GlacierEnv.from_env()
```

### Multiple Environments

**Key benefit:** Different environments can coexist without conflicts.

```python
# Development environment (local)
dev = GlacierEnv(
    provider=LocalProvider(config=LocalConfig(base_path="./data")),
    name="development"
)

# Staging environment (AWS)
staging = GlacierEnv(
    provider=AWSProvider(config=AwsConfig(region="us-east-1", profile="staging")),
    name="staging"
)

# Production environment (AWS)
prod = GlacierEnv(
    provider=AWSProvider(config=AwsConfig(region="us-east-1", profile="prod")),
    name="production"
)

# Same task logic, different environments
def define_task(env: GlacierEnv):
    @env.task()
    def process_data(source: Bucket) -> pl.LazyFrame:
        return source.scan().filter(pl.col("amount") > 0)

    return process_data

# Bind to each environment
dev_task = define_task(dev)
staging_task = define_task(staging)
prod_task = define_task(prod)

# Run in different environments
dev_task.run(mode="local")
staging_task.run(mode="local")
prod_task.run(mode="generate", output_dir="./infra/prod")
```

---

## Dependency Injection Patterns

### Pattern 1: Constructor Injection (Recommended)

**Configuration flows through constructors:**

```python
# Provider receives config via constructor
provider = AWSProvider(config=AwsConfig(region="us-east-1"))

# Resource receives provider and config via constructor
bucket = Bucket(
    provider=provider,
    bucket_name="data",
    path="sales.parquet",
    config=S3Config(versioning=True)
)

# Or use provider factory (preferred)
bucket = provider.bucket(
    "data",
    path="sales.parquet",
    config=S3Config(versioning=True)
)
```

### Pattern 2: Environment Registry

**Resources registered in environment scope:**

```python
env = GlacierEnv(provider=provider)

# Register resources
env.register("sales", provider.bucket("sales", path="data.parquet"))
env.register("customers", provider.bucket("customers", path="data.parquet"))

# Tasks retrieve from registry
@env.task()
def load_sales() -> pl.LazyFrame:
    source = env.get("sales")
    return source.scan()

# Or use dependency injection in signature
@env.task()
def load_sales_di(sales: Bucket) -> pl.LazyFrame:
    return sales.scan()

@env.pipeline()
def my_pipeline():
    sales_bucket = env.get("sales")
    return load_sales_di(sales_bucket)
```

### Pattern 3: Factory Pattern

**Providers are factories for resources:**

```python
# Provider factory
provider = AWSProvider(config=AwsConfig(region="us-east-1"))

# Resource factory methods
bucket = provider.bucket("name", path="...", config=S3Config(...))
fn = provider.serverless("name", handler="...", config=LambdaConfig(...))

# Environment factory
env = provider.env(name="production")
```

### Pattern 4: Hybrid DI + Registry

**Best of both worlds:**

```python
env = GlacierEnv(provider=provider)

# Register commonly used resources
env.register("sales_raw", provider.bucket("sales", path="raw/data.parquet"))
env.register("sales_processed", provider.bucket("sales", path="processed/data.parquet"))

# Tasks receive dependencies explicitly
@env.task()
def extract(source: Bucket) -> pl.LazyFrame:
    return source.scan()

@env.task()
def transform(df: pl.LazyFrame) -> pl.LazyFrame:
    return df.filter(pl.col("amount") > 0)

@env.task()
def load(df: pl.LazyFrame, target: Bucket) -> None:
    df.collect().write_parquet(target.get_uri())

# Pipeline wires everything together
@env.pipeline()
def etl_pipeline():
    # Get from registry
    source = env.get("sales_raw")
    target = env.get("sales_processed")

    # Pure data flow
    df = extract(source)
    df = transform(df)
    load(df, target)
```

---

## Task Binding Approaches

### Approach 1: `@env.task()` (Recommended)

**Tasks as methods of environment:**

```python
env = GlacierEnv(provider=provider)

@env.task()
def my_task(source: Bucket) -> pl.LazyFrame:
    return source.scan()

# Task is bound to environment
assert my_task.env == env
```

**Pros:**
- ✅ Clear ownership (task belongs to env)
- ✅ Pythonic (similar to `@classmethod`, `@staticmethod`)
- ✅ Easy to discover (IDE autocomplete on `env.`)
- ✅ Multiple environments don't conflict

**Cons:**
- ❌ Slightly more typing than global `@task`

### Approach 2: `@task(env)` (Alternative)

**Environment passed as parameter:**

```python
from glacier import task

env = GlacierEnv(provider=provider)

@task(env)
def my_task(source: Bucket) -> pl.LazyFrame:
    return source.scan()

# Task is bound to environment
assert my_task.env == env
```

**Pros:**
- ✅ Familiar pattern (parameterized decorators)
- ✅ Can use global `task` import

**Cons:**
- ❌ Less clear ownership
- ❌ Easy to forget environment parameter

### Approach 3: Deferred Binding (Advanced)

**Define tasks first, bind to environment later:**

```python
from glacier import task

# Define task without environment
@task
def my_task(source: Bucket) -> pl.LazyFrame:
    return source.scan()

# Bind to environment(s) later
dev_env = GlacierEnv(provider=LocalProvider(...))
prod_env = GlacierEnv(provider=AWSProvider(...))

# Bind same task to multiple environments
dev_task = dev_env.bind(my_task)
prod_task = prod_env.bind(my_task)

# Or use task.bind()
dev_task = my_task.bind(dev_env)
prod_task = my_task.bind(prod_env)
```

**Pros:**
- ✅ Maximum flexibility
- ✅ Reuse task logic across environments
- ✅ Good for libraries/shared code

**Cons:**
- ❌ More complex
- ❌ Two-step process

### Comparison

| Approach | Clarity | Flexibility | Simplicity | Recommended For |
|----------|---------|-------------|------------|-----------------|
| `@env.task()` | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Most use cases |
| `@task(env)` | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | Familiar with parameterized decorators |
| Deferred binding | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | Shared libraries, multi-env deployment |

**Recommendation:** Use `@env.task()` for most cases. Use deferred binding only when you need to deploy the same task logic to multiple environments.

---

## Resource Creation Patterns

### Pattern 1: Provider Factory (Recommended)

**Resources created via provider methods:**

```python
provider = AWSProvider(config=AwsConfig(region="us-east-1"))

# Simple case: defaults
bucket = provider.bucket("data", path="sales.parquet")

# Advanced case: custom config
bucket = provider.bucket(
    "data",
    path="sales.parquet",
    format="parquet",
    config=S3Config(
        versioning=True,
        encryption="AES256"
    )
)

# Serverless function
fn = provider.serverless(
    "processor",
    handler="process.handler",
    runtime="python3.11",
    config=LambdaConfig(memory=1024, timeout=300)
)
```

**Pros:**
- ✅ Provider manages resource lifecycle
- ✅ Type-safe (IDE autocomplete)
- ✅ Cloud-agnostic (same API for all providers)
- ✅ Sensible defaults with opt-in configuration

### Pattern 2: Direct Construction

**Resources created directly:**

```python
from glacier.resources import Bucket
from glacier.providers import AWSProvider
from glacier.config import S3Config

provider = AWSProvider(config=AwsConfig(region="us-east-1"))

# Direct construction
bucket = Bucket(
    provider=provider,
    bucket_name="data",
    path="sales.parquet",
    format="parquet",
    config=S3Config(versioning=True)
)
```

**Pros:**
- ✅ Explicit construction
- ✅ Full control over parameters

**Cons:**
- ❌ More verbose
- ❌ Must know resource class names
- ❌ Breaks abstraction slightly

**When to use:** Only when you need full control or when subclassing resources.

### Pattern 3: Environment Registry

**Resources registered in environment:**

```python
env = GlacierEnv(provider=provider)

# Register at environment creation
env = GlacierEnv(
    provider=provider,
    resources={
        "sales": provider.bucket("sales", path="data.parquet"),
        "customers": provider.bucket("customers", path="data.parquet")
    }
)

# Or register later
env.register("products", provider.bucket("products", path="data.parquet"))

# Retrieve in tasks/pipelines
@env.pipeline()
def my_pipeline():
    sales = env.get("sales")
    customers = env.get("customers")
    products = env.get("products")

    # Use resources...
```

**Pros:**
- ✅ Centralized resource management
- ✅ Easy to mock entire environment
- ✅ Resources shared across tasks

**Cons:**
- ❌ String-based lookup (not type-safe without stubs)
- ❌ Global registry within environment

**When to use:** When you have many shared resources used across multiple tasks.

### Pattern 4: Pipeline-Scoped Resources

**Resources created within pipeline:**

```python
@env.pipeline()
def my_pipeline():
    # Resources scoped to this pipeline
    source = env.provider.bucket("data", path="sales.parquet")
    target = env.provider.bucket("output", path="results.parquet")

    df = extract(source)
    df = transform(df)
    load(df, target)
```

**Pros:**
- ✅ Clear scope (resources belong to pipeline)
- ✅ Easy to understand lifecycle
- ✅ No global state

**Cons:**
- ❌ Resources not reusable across pipelines

**When to use:** Default pattern for most pipelines.

### Recommended Approach

**Combine patterns based on use case:**

```python
from glacier import GlacierEnv
from glacier.providers import AWSProvider
from glacier.config import AwsConfig, S3Config

# 1. Create provider with config
provider = AWSProvider(config=AwsConfig(region="us-east-1", profile="prod"))

# 2. Create environment
env = GlacierEnv(provider=provider, name="production")

# 3. Register shared resources (if any)
env.register("common_config", provider.bucket("config", path="common.json"))

# 4. Define tasks
@env.task()
def extract(source: Bucket) -> pl.LazyFrame:
    return source.scan()

@env.task()
def transform(df: pl.LazyFrame) -> pl.LazyFrame:
    return df.filter(pl.col("amount") > 0)

# 5. Pipeline creates pipeline-specific resources
@env.pipeline()
def etl_pipeline():
    # Pipeline-specific resources via provider factory
    source = env.provider.bucket(
        "sales",
        path="transactions.parquet",
        config=S3Config(versioning=True)
    )
    target = env.provider.bucket("processed", path="output.parquet")

    # Use shared resource from registry
    config = env.get("common_config")

    # Data flow
    df = extract(source)
    df = transform(df)
    return df
```

---

## Recommended Design

### Complete Example: Environment-First Pattern

This is the **recommended approach** combining all best practices:

```python
from glacier import GlacierEnv
from glacier.providers import AWSProvider
from glacier.config import AwsConfig, S3Config, LambdaConfig
import polars as pl

# ============================================================================
# 1. CONFIGURATION: Define provider config
# ============================================================================

aws_config = AwsConfig(
    region="us-east-1",
    profile="production",
    tags={"environment": "prod", "team": "data-eng"}
)

# ============================================================================
# 2. PROVIDER: Create provider with config (DI)
# ============================================================================

provider = AWSProvider(config=aws_config)

# ============================================================================
# 3. ENVIRONMENT: Create environment with provider
# ============================================================================

env = GlacierEnv(provider=provider, name="production")

# Alternative: env = provider.env(name="production")

# ============================================================================
# 4. TASKS: Define tasks bound to environment
# ============================================================================

@env.task()
def extract_sales(source: Bucket) -> pl.LazyFrame:
    """Extract sales data from S3."""
    return source.scan()

@env.task()
def extract_customers(source: Bucket) -> pl.LazyFrame:
    """Extract customer data from S3."""
    return source.scan()

@env.task()
def join_data(sales: pl.LazyFrame, customers: pl.LazyFrame) -> pl.LazyFrame:
    """Join sales with customer information."""
    return sales.join(customers, on="customer_id", how="left")

@env.task(timeout=600, retries=3)
def aggregate_by_segment(df: pl.LazyFrame) -> pl.DataFrame:
    """Aggregate sales by customer segment."""
    return (
        df.group_by("customer_segment")
        .agg([
            pl.sum("amount").alias("total_revenue"),
            pl.count("order_id").alias("order_count"),
            pl.mean("amount").alias("avg_order_value")
        ])
        .collect()
    )

# ============================================================================
# 5. PIPELINE: Wire everything together
# ============================================================================

@env.pipeline(name="sales_analysis")
def sales_analysis_pipeline():
    """
    Sales analysis pipeline with customer segmentation.

    Resources created with provider factory pattern.
    Tasks wired via explicit data flow.
    """
    # Create resources with progressive disclosure
    sales_bucket = env.provider.bucket(
        "sales-data",
        path="transactions.parquet",
        config=S3Config(
            versioning=True,
            encryption="AES256",
            storage_class="INTELLIGENT_TIERING"
        )
    )

    # Simple resource with defaults
    customer_bucket = env.provider.bucket(
        "customer-data",
        path="customers.parquet"
    )

    # Data flow defines dependencies
    sales_df = extract_sales(sales_bucket)
    customer_df = extract_customers(customer_bucket)
    joined_df = join_data(sales_df, customer_df)
    result = aggregate_by_segment(joined_df)

    return result

# ============================================================================
# 6. EXECUTION: Run in different modes
# ============================================================================

if __name__ == "__main__":
    # Local execution
    result = sales_analysis_pipeline.run(mode="local")
    print(result)

    # Analyze pipeline structure
    analysis = sales_analysis_pipeline.run(mode="analyze")
    print(f"Tasks: {analysis['tasks']}")
    print(f"DAG: {analysis['dag']}")

    # Generate infrastructure
    infra = sales_analysis_pipeline.run(
        mode="generate",
        output_dir="./terraform/production"
    )
    print(f"Generated: {infra['files']}")
```

### Key Design Principles

1. **Configuration Cascade**
   ```python
   AwsConfig → AWSProvider → GlacierEnv → Tasks & Resources
   ```

2. **Explicit Dependency Injection**
   - Config injected into Provider
   - Provider injected into Environment
   - Environment binds tasks
   - Resources created via provider factory

3. **Type-Safe Throughout**
   - All functions have type hints
   - IDE autocomplete works everywhere
   - Static type checking catches errors

4. **Cloud Portability**
   ```python
   # Switch from AWS to GCP: change 3 lines
   from glacier.providers import GCPProvider
   from glacier.config import GcpConfig

   gcp_config = GcpConfig(project_id="my-project", region="us-central1")
   provider = GCPProvider(config=gcp_config)
   env = GlacierEnv(provider=provider, name="production")

   # Everything else stays the same!
   ```

5. **Progressive Disclosure**
   - Simple: `provider.bucket("name", path="...")`
   - Advanced: `provider.bucket("name", path="...", config=S3Config(...))`

---


### Scenario 1: Simple ETL with Environment

```python
from glacier import GlacierEnv
from glacier.providers import LocalProvider
from glacier.config import LocalConfig
import polars as pl

# Create local environment for development
env = GlacierEnv(
    provider=LocalProvider(config=LocalConfig(base_path="./data")),
    name="development"
)

@env.task()
def extract(source: Bucket) -> pl.LazyFrame:
    """Extract data from source."""
    return source.scan()

@env.task()
def transform(df: pl.LazyFrame) -> pl.LazyFrame:
    """Apply transformations."""
    return (
        df.filter(pl.col("amount") > 0)
        .with_columns(pl.col("date").str.to_date())
    )

@env.task()
def load(df: pl.LazyFrame, target: Bucket) -> None:
    """Load data to target."""
    df.collect().write_parquet(target.get_uri())

@env.pipeline(name="simple_etl")
def etl_pipeline():
    """Simple ETL pipeline."""
    source = env.provider.bucket("raw", path="data.csv", format="csv")
    target = env.provider.bucket("processed", path="data.parquet")

    df = extract(source)
    df = transform(df)
    load(df, target)

# Run pipeline
if __name__ == "__main__":
    etl_pipeline.run(mode="local")
```

### Scenario 2: Multi-Environment Deployment

```python
import os
from glacier import GlacierEnv
from glacier.providers import AWSProvider, LocalProvider
from glacier.config import AwsConfig, LocalConfig
import polars as pl

# ============================================================================
# DEFINE TASKS (environment-agnostic)
# ============================================================================

def create_tasks(env: GlacierEnv):
    """Create tasks bound to given environment."""

    @env.task()
    def extract(source: Bucket) -> pl.LazyFrame:
        return source.scan()

    @env.task()
    def transform(df: pl.LazyFrame) -> pl.LazyFrame:
        return df.filter(pl.col("amount") > 100)

    @env.task()
    def aggregate(df: pl.LazyFrame) -> pl.DataFrame:
        return df.group_by("category").agg(pl.sum("amount")).collect()

    return extract, transform, aggregate

# ============================================================================
# CREATE ENVIRONMENTS
# ============================================================================

# Development: local
dev_env = GlacierEnv(
    provider=LocalProvider(config=LocalConfig(base_path="./data")),
    name="development"
)

# Staging: AWS
staging_env = GlacierEnv(
    provider=AWSProvider(config=AwsConfig(region="us-east-1", profile="staging")),
    name="staging"
)

# Production: AWS
prod_env = GlacierEnv(
    provider=AWSProvider(config=AwsConfig(region="us-east-1", profile="prod")),
    name="production"
)

# ============================================================================
# BIND TASKS TO ENVIRONMENTS
# ============================================================================

dev_extract, dev_transform, dev_aggregate = create_tasks(dev_env)
staging_extract, staging_transform, staging_aggregate = create_tasks(staging_env)
prod_extract, prod_transform, prod_aggregate = create_tasks(prod_env)

# ============================================================================
# DEFINE PIPELINE (same logic for all environments)
# ============================================================================

def create_pipeline(env: GlacierEnv, extract, transform, aggregate):
    """Create pipeline for given environment."""

    @env.pipeline(name="data_pipeline")
    def pipeline():
        source = env.provider.bucket("data", path="sales.parquet")
        df = extract(source)
        df = transform(df)
        result = aggregate(df)
        return result

    return pipeline

# Create pipeline instances
dev_pipeline = create_pipeline(dev_env, dev_extract, dev_transform, dev_aggregate)
staging_pipeline = create_pipeline(staging_env, staging_extract, staging_transform, staging_aggregate)
prod_pipeline = create_pipeline(prod_env, prod_extract, prod_transform, prod_aggregate)

# ============================================================================
# RUN BASED ON ENVIRONMENT VARIABLE
# ============================================================================

if __name__ == "__main__":
    env_name = os.getenv("GLACIER_ENV", "development")

    if env_name == "development":
        result = dev_pipeline.run(mode="local")
    elif env_name == "staging":
        result = staging_pipeline.run(mode="local")
    elif env_name == "production":
        # Generate infrastructure for production
        prod_pipeline.run(mode="generate", output_dir="./terraform/prod")
    else:
        raise ValueError(f"Unknown environment: {env_name}")
```

### Scenario 3: Registry Pattern for Shared Resources

```python
from glacier import GlacierEnv
from glacier.providers import AWSProvider
from glacier.config import AwsConfig, S3Config
import polars as pl

# Create environment
provider = AWSProvider(config=AwsConfig(region="us-east-1"))
env = GlacierEnv(provider=provider, name="production")

# ============================================================================
# REGISTER SHARED RESOURCES
# ============================================================================

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
    path="customers.parquet",
    config=S3Config(versioning=True, encryption="AES256")
))

env.register("config", provider.bucket(
    "config",
    path="app_config.json",
    format="json"
))

# ============================================================================
# TASKS USE REGISTRY
# ============================================================================

@env.task()
def extract_sales() -> pl.LazyFrame:
    """Extract sales from registry."""
    source = env.get("sales_raw")
    return source.scan()

@env.task()
def extract_customers() -> pl.LazyFrame:
    """Extract customers from registry."""
    source = env.get("customers")
    return source.scan()

@env.task()
def load_config() -> dict:
    """Load configuration from registry."""
    config_bucket = env.get("config")
    return config_bucket.read().to_dicts()[0]

@env.task()
def join_data(sales: pl.LazyFrame, customers: pl.LazyFrame) -> pl.LazyFrame:
    """Join sales with customers."""
    return sales.join(customers, on="customer_id", how="left")

@env.task()
def save_results(df: pl.LazyFrame) -> None:
    """Save results using registry."""
    target = env.get("sales_processed")
    df.collect().write_parquet(target.get_uri())

# ============================================================================
# PIPELINE
# ============================================================================

@env.pipeline(name="sales_enrichment")
def sales_enrichment_pipeline():
    """Enrich sales data with customer information."""
    # Load config
    config = load_config()

    # Extract data
    sales = extract_sales()
    customers = extract_customers()

    # Join
    enriched = join_data(sales, customers)

    # Filter based on config (example of using config)
    if config.get("filter_threshold"):
        enriched = enriched.filter(pl.col("amount") > config["filter_threshold"])

    # Save
    save_results(enriched)

    return enriched
```

### Scenario 4: Advanced Configuration Cascade

```python
from glacier import GlacierEnv
from glacier.providers import AWSProvider
from glacier.config import AwsConfig, S3Config, LambdaConfig
import polars as pl

# ============================================================================
# LEVEL 1: Provider Configuration
# ============================================================================

aws_config = AwsConfig(
    region="us-east-1",
    profile="production",
    account_id="123456789012",
    tags={
        "environment": "production",
        "team": "data-engineering",
        "cost-center": "analytics",
        "managed-by": "glacier"
    }
)

provider = AWSProvider(config=aws_config)
env = GlacierEnv(provider=provider, name="production")

# ============================================================================
# LEVEL 2: Resource-Level Configuration
# ============================================================================

# High-durability storage config
critical_storage_config = S3Config(
    versioning=True,
    encryption="AES256",
    storage_class="STANDARD",
    lifecycle_rules=[],
    public_access_block=True,
    replication_config={
        "destination_bucket": "sales-data-backup",
        "destination_region": "us-west-2"
    }
)

# Cost-optimized storage config
archive_storage_config = S3Config(
    versioning=False,
    encryption="AES256",
    storage_class="INTELLIGENT_TIERING",
    lifecycle_rules=[
        {"days": 30, "transition": "GLACIER"},
        {"days": 365, "expiration": True}
    ]
)

# High-performance Lambda config
intensive_lambda_config = LambdaConfig(
    memory=3008,  # Max memory
    timeout=900,  # 15 minutes
    runtime="python3.11",
    environment_vars={
        "LOG_LEVEL": "INFO",
        "ENABLE_PROFILING": "true"
    },
    reserved_concurrent_executions=10
)

# ============================================================================
# LEVEL 3: Task-Level Configuration
# ============================================================================

@env.task(executor="local", timeout=300, retries=3, cache=True)
def extract_critical_data(source: Bucket) -> pl.LazyFrame:
    """Extract critical business data with caching."""
    return source.scan()

@env.task(executor="local", timeout=60, retries=1, cache=False)
def quick_validation(df: pl.LazyFrame) -> bool:
    """Quick validation with minimal retries."""
    return df.select(pl.count()).collect()[0, 0] > 0

@env.task(executor="lambda", timeout=900, retries=5)
def intensive_transformation(df: pl.LazyFrame, fn: Serverless) -> pl.LazyFrame:
    """Computationally intensive transformation via Lambda."""
    # Serialize and invoke Lambda
    result = fn.invoke(payload={"data": df.collect().to_dicts()})
    return pl.DataFrame(result["data"]).lazy()

# ============================================================================
# PIPELINE WITH CASCADING CONFIGS
# ============================================================================

@env.pipeline(name="advanced_pipeline")
def advanced_pipeline():
    """Pipeline demonstrating configuration cascade."""

    # Critical data with high-durability config
    critical_bucket = env.provider.bucket(
        "critical-sales-data",
        path="transactions.parquet",
        config=critical_storage_config
    )

    # Archive data with cost-optimized config
    archive_bucket = env.provider.bucket(
        "archive-sales-data",
        path="historical.parquet",
        config=archive_storage_config
    )

    # High-performance Lambda function
    transformer = env.provider.serverless(
        "intensive-transformer",
        handler="transform.handler",
        config=intensive_lambda_config
    )

    # Execute pipeline
    df = extract_critical_data(critical_bucket)

    if quick_validation(df):
        df = intensive_transformation(df, transformer)

    return df
```

### Scenario 5: Testing with Mock Environment

```python
from glacier import GlacierEnv
from glacier.providers import LocalProvider
from glacier.config import LocalConfig
import polars as pl
import pytest

# ============================================================================
# PRODUCTION CODE
# ============================================================================

def create_tasks(env: GlacierEnv):
    """Factory function to create tasks for any environment."""

    @env.task()
    def extract(source: Bucket) -> pl.LazyFrame:
        return source.scan()

    @env.task()
    def validate(df: pl.LazyFrame) -> bool:
        return df.select(pl.count()).collect()[0, 0] > 0

    @env.task()
    def transform(df: pl.LazyFrame) -> pl.LazyFrame:
        return df.filter(pl.col("amount") > 100)

    return extract, validate, transform

# ============================================================================
# TEST CODE
# ============================================================================

def test_pipeline_with_mock_data():
    """Test pipeline using local mock environment."""

    # Create test environment with local provider
    test_env = GlacierEnv(
        provider=LocalProvider(config=LocalConfig(base_path="./test_data")),
        name="test"
    )

    # Bind tasks to test environment
    extract, validate, transform = create_tasks(test_env)

    # Create test data
    test_df = pl.DataFrame({
        "id": [1, 2, 3],
        "amount": [50, 150, 200],
        "date": ["2024-01-01", "2024-01-02", "2024-01-03"]
    })

    # Write test data to local file
    test_df.write_parquet("./test_data/test_input.parquet")

    # Create mock bucket
    test_bucket = test_env.provider.bucket("test", path="test_input.parquet")

    # Run tasks
    df = extract(test_bucket)
    assert validate(df), "Validation should pass"

    result = transform(df)
    result_df = result.collect()

    # Assertions
    assert len(result_df) == 2, "Should filter to 2 rows"
    assert all(result_df["amount"] > 100), "All amounts should be > 100"


def test_pipeline_with_mock_provider():
    """Test pipeline using a fully mocked provider."""

    # Create mock provider class
    class MockProvider:
        def __init__(self, config):
            self.config = config

        def bucket(self, name, path, format="parquet", config=None):
            # Return mock bucket that returns test data
            class MockBucket:
                def scan(self):
                    return pl.DataFrame({
                        "id": [1, 2, 3],
                        "amount": [50, 150, 200]
                    }).lazy()

            return MockBucket()

        def env(self, name):
            return GlacierEnv(provider=self, name=name)

    # Create test environment with mock provider
    mock_provider = MockProvider(config={})
    test_env = GlacierEnv(provider=mock_provider, name="test")

    # Bind tasks
    extract, validate, transform = create_tasks(test_env)

    # Run tasks with mock data
    mock_bucket = mock_provider.bucket("test", path="test.parquet")
    df = extract(mock_bucket)
    result = transform(df).collect()

    # Assertions
    assert len(result) == 2
    assert all(result["amount"] > 100)
```

---

## Testing and Mocking

### Testability Benefits of DI/Environment Pattern

The environment-based design makes testing significantly easier:

1. **Inject Test Providers**
2. **Isolate Environments**
3. **Mock Resources**
4. **Deterministic Tests**

### Pattern 1: Local Environment for Integration Tests

```python
import pytest
from glacier import GlacierEnv
from glacier.providers import LocalProvider
from glacier.config import LocalConfig
import polars as pl

@pytest.fixture
def test_env():
    """Create isolated test environment."""
    return GlacierEnv(
        provider=LocalProvider(config=LocalConfig(base_path="./test_data")),
        name="test"
    )

@pytest.fixture
def sample_data(test_env):
    """Create sample data in test environment."""
    df = pl.DataFrame({
        "customer_id": [1, 2, 3],
        "amount": [100, 200, 300],
        "date": ["2024-01-01", "2024-01-02", "2024-01-03"]
    })
    df.write_parquet("./test_data/sales.parquet")

    return test_env.provider.bucket("test", path="sales.parquet")

def test_extract_task(test_env, sample_data):
    """Test extract task with fixture data."""

    @test_env.task()
    def extract(source: Bucket) -> pl.LazyFrame:
        return source.scan()

    result = extract(sample_data).collect()

    assert len(result) == 3
    assert list(result.columns) == ["customer_id", "amount", "date"]
```

### Pattern 2: Mock Provider for Unit Tests

```python
from unittest.mock import Mock
from glacier import GlacierEnv
import polars as pl

def test_transform_task_with_mock_provider():
    """Test task logic without real provider."""

    # Create mock provider
    mock_provider = Mock()
    mock_provider.get_provider_type.return_value = "mock"

    # Create test environment
    test_env = GlacierEnv(provider=mock_provider, name="test")

    # Define task
    @test_env.task()
    def transform(df: pl.LazyFrame) -> pl.LazyFrame:
        return df.filter(pl.col("amount") > 150)

    # Test with in-memory data (no provider needed)
    test_df = pl.DataFrame({
        "customer_id": [1, 2, 3],
        "amount": [100, 200, 300]
    }).lazy()

    result = transform(test_df).collect()

    assert len(result) == 2
    assert all(result["amount"] > 150)
```

### Pattern 3: Environment Swapping for E2E Tests

```python
import os
from glacier import GlacierEnv
from glacier.providers import AWSProvider, LocalProvider
from glacier.config import AwsConfig, LocalConfig

def get_test_environment():
    """Get environment based on test mode."""
    if os.getenv("TEST_MODE") == "e2e":
        # Use real AWS resources for E2E tests
        return GlacierEnv(
            provider=AWSProvider(config=AwsConfig(
                region="us-east-1",
                profile="test"
            )),
            name="e2e-test"
        )
    else:
        # Use local environment for unit tests
        return GlacierEnv(
            provider=LocalProvider(config=LocalConfig(base_path="./test_data")),
            name="unit-test"
        )

def test_full_pipeline():
    """Test that works in both unit and E2E modes."""
    env = get_test_environment()

    @env.task()
    def extract(source: Bucket) -> pl.LazyFrame:
        return source.scan()

    @env.pipeline()
    def test_pipeline():
        source = env.provider.bucket("test-data", path="input.parquet")
        return extract(source)

    # Run pipeline (uses local or AWS based on TEST_MODE)
    result = test_pipeline.run(mode="local")
    assert result is not None
```

### Pattern 4: Registry Mocking

```python
from glacier import GlacierEnv
from unittest.mock import Mock
import polars as pl

def test_with_registry_mocking():
    """Test using environment registry with mocks."""

    # Create environment
    mock_provider = Mock()
    env = GlacierEnv(provider=mock_provider, name="test")

    # Register mock resources
    mock_bucket = Mock()
    mock_bucket.scan.return_value = pl.DataFrame({
        "id": [1, 2],
        "value": [10, 20]
    }).lazy()

    env.register("test_data", mock_bucket)

    # Task uses registry
    @env.task()
    def process_data() -> pl.LazyFrame:
        source = env.get("test_data")
        return source.scan()

    # Execute
    result = process_data().collect()

    assert len(result) == 2
    mock_bucket.scan.assert_called_once()
```

---

## Alpha Status - No Migration Path

**Glacier is in alpha and does not maintain backwards compatibility.**

The library has transitioned to the environment-first pattern exclusively:

### ✅ Current Design (Only Supported Pattern)

**Environment-first with dependency injection:**
```python
from glacier import GlacierEnv
from glacier.providers import AWSProvider
from glacier.config import AwsConfig

# Create provider with config
provider = AWSProvider(config=AwsConfig(region="us-east-1"))

# Create environment
env = GlacierEnv(provider=provider, name="production")

# Tasks bound to environment
@env.task()
def my_task(source) -> pl.LazyFrame:
    return source.scan()

# Pipelines bound to environment
@env.pipeline()
def my_pipeline():
    source = env.provider.bucket("data", path="file.parquet")
    return my_task(source)
```

### ❌ Removed Patterns (No Longer Supported)

The following patterns have been **removed** from the codebase:

1. **Global decorators** - `@task` and `@pipeline` without environment
2. **String-based dependencies** - `depends_on=["task_name"]`
3. **Untyped provider constructors** - Must use config classes
4. **Direct source imports** - Use provider factories instead

Since we're in alpha, we prioritize design correctness over backwards compatibility. Users should expect breaking changes between releases until we reach v1.0.

---

## Future Enhancements

### 1. Smart Dependency Injection

**Vision:** Automatic dependency resolution based on type hints.

```python
@env.task()
def extract(source: Bucket = Inject("sales_data")) -> pl.LazyFrame:
    """Automatically inject 'sales_data' from registry."""
    return source.scan()

@env.pipeline()
def auto_pipeline():
    # Task automatically gets dependency from registry
    df = extract()  # No need to pass sales_data explicitly
    return df
```

### 2. Environment Composition

**Vision:** Compose environments from multiple providers.

```python
# Multi-cloud environment
env = GlacierEnv.compose(
    storage=AWSProvider(config=AwsConfig(region="us-east-1")),
    compute=GCPProvider(config=GcpConfig(project_id="my-project")),
    name="hybrid"
)

# Storage from AWS, compute from GCP
@env.pipeline()
def hybrid_pipeline():
    # Bucket from AWS
    source = env.storage.bucket("data", path="input.parquet")

    # Function from GCP
    processor = env.compute.serverless("process", handler="main")

    df = extract(source)
    result = transform_via_cloud(df, processor)
    return result
```

### 3. Environment Templates

**Vision:** Pre-configured environment templates.

```python
from glacier.templates import ProductionAWSEnvironment, DevelopmentLocalEnvironment

# Production template with best practices
prod = ProductionAWSEnvironment(
    region="us-east-1",
    profile="prod",
    enable_encryption=True,
    enable_versioning=True,
    enable_monitoring=True
)

# Development template
dev = DevelopmentLocalEnvironment(base_path="./data")
```

### 4. Configuration Validation

**Vision:** Validate configurations at creation time.

```python
from glacier.config import AwsConfig

# Validation catches errors early
try:
    config = AwsConfig(
        region="invalid-region",  # Error: invalid region
        memory=999999  # Error: exceeds AWS limits
    )
except ValidationError as e:
    print(f"Configuration error: {e}")
```

### 5. Environment State Management

**Vision:** Track environment state and resources.

```python
env = GlacierEnv(provider=provider, name="production")

# Track all resources created
env.register("sales", provider.bucket(...))
env.register("customers", provider.bucket(...))

# Get environment state
state = env.get_state()
# {
#   "resources": ["sales", "customers"],
#   "tasks": ["extract", "transform"],
#   "pipelines": ["etl_pipeline"]
# }

# Export state for infrastructure generation
env.export_state("./state/production.json")
```

### 6. Interactive Environment Shell

**Vision:** REPL for exploring environments.

```bash
$ glacier shell --env production

glacier> env.list_resources()
['sales_data', 'customer_data', 'processed_data']

glacier> env.get("sales_data").scan().head()
shape: (5, 4)
┌────────────┬─────────┬──────────────┬─────────┐
│ order_id   │ amount  │ date         │ status  │
│ ---        │ ---     │ ---          │ ---     │
│ i64        │ f64     │ str          │ str     │
╞════════════╪═════════╪══════════════╪═════════╡
│ 1          │ 150.0   │ 2024-01-01   │ paid    │
└────────────┴─────────┴──────────────┴─────────┘

glacier> env.tasks
['extract_sales', 'transform_sales', 'aggregate_sales']
```

---

## Conclusion

The **environment-first, DI-based design** for Glacier provides:

### ✅ Core Benefits

1. **Explicit Dependencies**
   - Configuration flows clearly through the system
   - Every dependency is visible and testable
   - No hidden global state

2. **Environment Isolation**
   - Multiple environments coexist without conflicts
   - Clear boundaries for dev/staging/prod
   - Easy to switch between environments

3. **Configuration Cascade**
   - Provider → Resource → Task hierarchy
   - Progressive disclosure (simple by default, advanced when needed)
   - Type-safe configuration at every level

4. **Cloud Portability**
   - Change provider by swapping config
   - Same pipeline code across all clouds
   - Provider-specific optimizations available

5. **Testability**
   - Easy to inject mock providers
   - Environment isolation for tests
   - Unit and integration tests with same code

6. **Type Safety**
   - Full type hints throughout
   - IDE autocomplete works perfectly
   - Static type checking catches errors

### 🎯 Recommended Patterns

1. **`@env.task()`** for task binding
2. **Provider factory** for resource creation
3. **Hybrid DI + Registry** for dependency management
4. **Configuration cascade** from provider to tasks
5. **Environment per deployment** stage

### 📊 Design Summary

```
User Code (Pythonic, type-safe)
    ↓
GlacierEnv (Dependency injection container)
    ↓
Provider (Factory for resources)
    ↓
Resources (Cloud-agnostic abstractions)
    ↓
Adapters (Cloud-specific implementations)
    ↓
Infrastructure (Terraform, CDK, Pulumi)
```

### 🚀 Next Steps

1. Implement `GlacierEnv` class
2. Add configuration classes (AwsConfig, S3Config, etc.)
3. Update providers to support `env()` method
4. Add registry pattern (`env.register()`, `env.get()`)
5. Create comprehensive examples
6. Write testing guide
7. Update documentation

---

**Document Status:** Ready for Implementation
**Version:** 2.1
**Last Updated:** 2025-11-05
