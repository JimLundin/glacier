# Glacier Library - UX Design Document

**Version:** 2.0
**Date:** 2025-11-05
**Status:** Living Document

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Design Philosophy](#design-philosophy)
3. [UX Principles](#ux-principles)
4. [Architecture Overview](#architecture-overview)
5. [Dependency Management Patterns](#dependency-management-patterns)
6. [Resource Creation UX](#resource-creation-ux)
7. [Comparison of Approaches](#comparison-of-approaches)
8. [Recommended Design](#recommended-design)
9. [Example Usage Scenarios](#example-usage-scenarios)
10. [Migration Path](#migration-path)
11. [Future Enhancements](#future-enhancements)

---

## Executive Summary

Glacier is a **cloud-agnostic data pipeline library** that enables developers to write Python code once and deploy it anywhere. The library prioritizes **developer experience** through:

- **Minimal boilerplate** - Simple, intuitive API
- **Type safety** - Leverage Python type hints for correctness
- **Cloud portability** - Switch providers with one line change
- **Infrastructure from code** - Auto-generate Terraform from pipeline definitions
- **Polars-first** - Optimized for modern data processing

This document outlines the UX design philosophy, explores different dependency management patterns (decorators, DI, method chaining), and recommends the optimal approach for Glacier's use cases.

---

## Design Philosophy

### Core Tenets

1. **Python-First, Infrastructure-Second**
   - Write clean Python code, infrastructure is derived automatically
   - Avoid YAML/JSON configuration files
   - Type hints drive code generation

2. **Explicit Over Implicit**
   - Clear dependency declarations
   - Obvious resource relationships
   - No magic unless it saves significant effort

3. **Progressive Disclosure**
   - Simple use cases should be trivial
   - Advanced features available when needed
   - Sensible defaults, override when necessary

4. **Cloud Agnostic by Design**
   - Same code works on AWS, GCP, Azure, Local
   - Provider-specific optimizations available but optional
   - Abstract cloud differences, expose when needed

5. **Developer Ergonomics**
   - Familiar patterns (decorators, context managers)
   - IDE autocomplete and type checking
   - Clear error messages

---

## UX Principles

### 1. Simplicity for Common Cases

**Good:**
```python
from glacier import pipeline, task
from glacier.providers import LocalProvider

provider = LocalProvider()

@task
def load_data(source: Bucket) -> pl.LazyFrame:
    return source.scan()

@pipeline
def my_pipeline():
    source = provider.bucket("data", path="sales.parquet")
    return load_data(source)
```

**Bad (too verbose):**
```python
# Avoid this pattern
from glacier.core.pipeline import PipelineBuilder
from glacier.core.task import TaskBuilder
from glacier.providers.factory import ProviderFactory

builder = PipelineBuilder()
factory = ProviderFactory.create("local")
task_builder = TaskBuilder()
task_builder.add_dependency(...)
# ... too much ceremony
```

### 2. Type Safety

**Good:**
```python
@task
def transform(df: pl.LazyFrame) -> pl.LazyFrame:  # Clear types
    return df.filter(pl.col("amount") > 100)

@task
def aggregate(df: pl.LazyFrame) -> pl.DataFrame:  # Return concrete DataFrame
    return df.group_by("category").agg(pl.sum("amount")).collect()
```

**Bad:**
```python
@task
def transform(data):  # What type is data?
    return data.filter(...)  # IDE can't help
```

### 3. Discoverability

**Good:**
```python
# IDE can autocomplete all provider methods
provider = AWSProvider(region="us-east-1")
provider.bucket(...)      # Discover via autocomplete
provider.serverless(...)  # Clear API surface
```

**Bad:**
```python
# String-based discovery is hard
provider.create_resource("bucket", ...)  # What are valid types?
```

### 4. Flexibility Without Complexity

**Good:**
```python
# Simple case: use defaults
bucket = provider.bucket("data", path="sales.parquet")

# Advanced case: provider-specific config
from glacier.config import S3Config

bucket = provider.bucket(
    "data",
    path="sales.parquet",
    config=S3Config(
        versioning=True,
        encryption="AES256",
        lifecycle_rules=[...]
    )
)
```

### 5. Cloud Portability

**Good:**
```python
# Change provider, everything else stays the same
# provider = LocalProvider()
# provider = AWSProvider(region="us-east-1")
provider = GCPProvider(project_id="my-project", region="us-central1")

bucket = provider.bucket("data", path="sales.parquet")  # Same API!
```

---

## Architecture Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        User Code                            │
│  @pipeline and @task decorators + Provider abstraction      │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Core Abstractions                        │
│  Pipeline, Task, DAG, Context, ExecutionMode                │
└─────────────────────────────────────────────────────────────┘
                            │
         ┌──────────────────┼──────────────────┐
         ▼                  ▼                  ▼
┌─────────────────┐ ┌──────────────┐ ┌─────────────────┐
│   Providers     │ │  Resources   │ │   Execution     │
│  (Factory)      │ │ (Bucket, SF) │ │   Engines       │
│  AWS, GCP,      │ │ Generic API  │ │  Local, Cloud   │
│  Azure, Local   │ │              │ │  Analyze, Gen   │
└─────────────────┘ └──────────────┘ └─────────────────┘
         │                  │
         └────────┬─────────┘
                  ▼
        ┌──────────────────┐
        │    Adapters      │
        │ (Implementation) │
        │  S3, GCS, Blob,  │
        │  Lambda, Cloud   │
        │  Functions, etc  │
        └──────────────────┘
                  │
                  ▼
        ┌──────────────────┐
        │   Code Gen       │
        │  Terraform, CDK  │
        │  Pulumi, etc     │
        └──────────────────┘
```

### Key Components

1. **Decorators** (`@pipeline`, `@task`)
   - Minimal syntax overhead
   - Attach metadata without changing function behavior
   - Enable static analysis and code generation

2. **Provider Factory**
   - Single entry point for creating resources
   - Encapsulates cloud-specific details
   - Swappable without code changes

3. **Resource Abstractions** (`Bucket`, `Serverless`)
   - Cloud-agnostic API
   - Polars integration (LazyFrame)
   - Delegate to adapters for implementation

4. **Adapters**
   - Cloud-specific implementations
   - Hidden from users
   - Extensible for new providers

5. **DAG Builder**
   - Automatic from task dependencies
   - Topological sorting for execution
   - Parallelization opportunities

6. **Code Generator**
   - Terraform, CDK, Pulumi support
   - Infrastructure from Python code
   - Environment-specific configurations

---

## Dependency Management Patterns

### Pattern 1: Explicit Dependencies (Current Approach)

**How it works:**
```python
@task
def task1(source: Bucket) -> pl.LazyFrame:
    return source.scan()

@task(depends_on=[task1])  # Explicit dependency
def task2(df: pl.LazyFrame) -> pl.LazyFrame:
    return df.filter(pl.col("amount") > 100)

@task(depends_on=[task2])
def task3(df: pl.LazyFrame) -> pl.DataFrame:
    return df.collect()

@pipeline
def my_pipeline():
    source = provider.bucket("data", path="sales.parquet")
    result = task3()  # Dependencies handled by DAG
    return result
```

**Pros:**
- ✅ Clear dependency graph
- ✅ Type-safe function signatures
- ✅ Easy to analyze statically
- ✅ Good for code generation

**Cons:**
- ❌ Dependencies declared separately from usage
- ❌ Manual wiring in depends_on list
- ❌ Data flow not obvious from pipeline function

---

### Pattern 2: Implicit Dependencies via Data Flow

**How it works:**
```python
@task
def task1(source: Bucket) -> pl.LazyFrame:
    return source.scan()

@task
def task2(df: pl.LazyFrame) -> pl.LazyFrame:
    return df.filter(pl.col("amount") > 100)

@task
def task3(df: pl.LazyFrame) -> pl.DataFrame:
    return df.collect()

@pipeline
def my_pipeline():
    source = provider.bucket("data", path="sales.parquet")
    df1 = task1(source)      # Implicit: task1 depends on source
    df2 = task2(df1)         # Implicit: task2 depends on task1
    result = task3(df2)      # Implicit: task3 depends on task2
    return result
```

**Pros:**
- ✅ Natural Python data flow
- ✅ Dependencies obvious from code
- ✅ No manual depends_on needed
- ✅ Easier to refactor

**Cons:**
- ❌ Requires runtime tracing or AST analysis
- ❌ Harder to analyze statically
- ❌ Complex for conditional flows

---

### Pattern 3: Dependency Injection Container

**How it works:**
```python
from glacier import Container

@task
def task1(source: Bucket = Inject("sales_data")) -> pl.LazyFrame:
    return source.scan()

@task
def task2(df: pl.LazyFrame = Inject(task1)) -> pl.LazyFrame:
    return df.filter(pl.col("amount") > 100)

@pipeline
def my_pipeline():
    container = Container()
    container.register("sales_data", provider.bucket("data", path="sales.parquet"))
    container.register(task1, task1)
    container.register(task2, task2)

    result = container.resolve(task2)
    return result
```

**Pros:**
- ✅ Explicit dependency registry
- ✅ Testability (easy to mock)
- ✅ Clear separation of concerns

**Cons:**
- ❌ Verbose boilerplate
- ❌ Unfamiliar pattern for data engineers
- ❌ Complex for simple use cases
- ❌ Harder to understand data flow

---

### Pattern 4: Fluent/Method Chaining

**How it works:**
```python
@pipeline
def my_pipeline():
    result = (
        provider.bucket("data", path="sales.parquet")
        .scan()
        .task(transform, name="transform")  # Each task is a method
        .task(aggregate, name="aggregate")
        .collect()
    )
    return result
```

**Pros:**
- ✅ Very concise
- ✅ Clear linear flow
- ✅ Popular in some ecosystems (Spark, dplyr)

**Cons:**
- ❌ Limited to linear pipelines
- ❌ Hard to handle branching/merging
- ❌ Hides task abstraction
- ❌ Not Pythonic

---

### Pattern 5: Context Manager for Resources

**How it works:**
```python
@pipeline
def my_pipeline():
    with provider.bucket("data", path="sales.parquet") as source:
        df = task1(source)
        df = task2(df)
        result = task3(df)
    return result
```

**Pros:**
- ✅ Pythonic resource management
- ✅ Clear resource lifecycle

**Cons:**
- ❌ Not necessary for cloud resources
- ❌ Adds nesting complexity
- ❌ Doesn't help with dependencies

---

### Pattern 6: Graph Builder API

**How it works:**
```python
@pipeline
def my_pipeline():
    graph = PipelineGraph()

    source = provider.bucket("data", path="sales.parquet")
    t1 = graph.add_task(task1, inputs=[source])
    t2 = graph.add_task(task2, inputs=[t1])
    t3 = graph.add_task(task3, inputs=[t2])

    return graph.execute()
```

**Pros:**
- ✅ Explicit graph construction
- ✅ Complex DAGs easy to express
- ✅ Clear visualization

**Cons:**
- ❌ Very verbose
- ❌ Unfamiliar pattern
- ❌ Removes function call semantics

---

## Comparison of Approaches

### Evaluation Criteria

| Pattern | Simplicity | Flexibility | Pythonic | Type Safety | Static Analysis | Testability |
|---------|-----------|-------------|----------|-------------|-----------------|-------------|
| **Explicit deps (current)** | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Implicit deps (data flow)** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| **DI Container** | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Method chaining** | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| **Context managers** | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Graph builder** | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |

### Use Case Fit

**Simple linear pipeline:** Implicit deps (data flow) wins
**Complex DAG with branches:** Explicit deps or Graph builder
**Testing/mocking:** DI Container
**API exploration:** Implicit deps (autocomplete works best)

---

## Recommended Design

### Hybrid Approach: Implicit + Optional Explicit

**Core Philosophy:**
- **Default to implicit dependencies** via data flow (most intuitive)
- **Optional explicit dependencies** when needed for complex DAGs
- **Provider factory** for resource creation
- **Type hints** for everything

### Recommended API

```python
from glacier import pipeline, task
from glacier.providers import AWSProvider

provider = AWSProvider(region="us-east-1")

# ====================================================================
# SIMPLE CASE: Implicit dependencies from data flow
# ====================================================================

@task
def load_sales(source: Bucket) -> pl.LazyFrame:
    """Load sales data from bucket."""
    return source.scan()

@task
def load_customers(source: Bucket) -> pl.LazyFrame:
    """Load customer data from bucket."""
    return source.scan()

@task
def join_data(sales: pl.LazyFrame, customers: pl.LazyFrame) -> pl.LazyFrame:
    """Join sales with customer data."""
    return sales.join(customers, on="customer_id", how="left")

@task
def aggregate(df: pl.LazyFrame) -> pl.DataFrame:
    """Aggregate sales by customer segment."""
    return (
        df.group_by("segment")
        .agg([
            pl.sum("amount").alias("total_sales"),
            pl.count("order_id").alias("order_count")
        ])
        .collect()
    )

@pipeline(name="sales_analysis")
def sales_pipeline():
    """
    Sales analysis pipeline with implicit dependencies.

    DAG is automatically inferred:
    - load_sales and load_customers can run in parallel
    - join_data depends on both
    - aggregate depends on join_data
    """
    # Create resources
    sales_bucket = provider.bucket("sales", path="transactions.parquet")
    customer_bucket = provider.bucket("customers", path="customers.parquet")

    # Data flow defines dependencies automatically
    sales_df = load_sales(sales_bucket)
    customers_df = load_customers(customer_bucket)
    joined = join_data(sales_df, customers_df)
    result = aggregate(joined)

    return result


# ====================================================================
# ADVANCED CASE: Explicit dependencies for complex control flow
# ====================================================================

@task
def validate_schema(source: Bucket) -> bool:
    """Validate data schema before processing."""
    df = source.scan()
    # Check schema...
    return True

@task(depends_on=[validate_schema])  # Explicit: must run after validation
def process_data(source: Bucket) -> pl.LazyFrame:
    """Process data only if validation passed."""
    return source.scan().filter(pl.col("valid") == True)

@task
def send_notification(status: bool) -> None:
    """Send notification about pipeline status."""
    # Send email/slack/etc
    pass

@pipeline(name="validated_pipeline")
def validated_pipeline():
    """
    Pipeline with validation step.

    Uses explicit depends_on because validate_schema returns bool,
    not data that flows to process_data.
    """
    source = provider.bucket("data", path="input.parquet")

    # Validation must complete first
    valid = validate_schema(source)

    # Processing depends on validation (explicit via depends_on)
    result = process_data(source)

    # Notification runs after everything (explicit)
    send_notification(valid)

    return result


# ====================================================================
# RESOURCE CONFIGURATION: Progressive disclosure
# ====================================================================

from glacier.config import S3Config

@pipeline(name="production_pipeline")
def production_pipeline():
    """Production pipeline with provider-specific configs."""

    # Simple: use defaults
    source_simple = provider.bucket("data", path="simple.parquet")

    # Advanced: provider-specific configuration
    source_advanced = provider.bucket(
        "data",
        path="advanced.parquet",
        format="parquet",
        config=S3Config(
            versioning=True,
            encryption="AES256",
            storage_class="INTELLIGENT_TIERING",
            lifecycle_rules=[
                {"days": 30, "transition": "GLACIER"},
                {"days": 90, "expiration": True}
            ]
        )
    )

    df = load_sales(source_advanced)
    return aggregate(df)
```

### Key Design Decisions

1. **Implicit Dependencies by Default**
   - Analyze `@pipeline` function AST to extract data flow
   - Build DAG from variable assignments and task calls
   - Fallback to execution tracing if AST analysis fails

2. **Explicit Dependencies When Needed**
   - Use `depends_on=[...]` for non-data dependencies
   - Examples: validation gates, notifications, side effects

3. **Provider Factory Pattern**
   - Single entry point: `provider.bucket()`, `provider.serverless()`
   - Type-safe, discoverable API
   - Cloud-agnostic code

4. **Progressive Disclosure**
   - Simple cases use defaults
   - Advanced cases expose provider-specific config
   - Optional `config=` parameter

5. **Type Hints Everywhere**
   - Enable IDE autocomplete
   - Static type checking
   - Drive code generation

---

## Resource Creation UX

### Current Pattern (Recommended)

```python
# Provider factory creates resources
provider = AWSProvider(region="us-east-1")

# Method 1: Inline in pipeline
@pipeline
def my_pipeline():
    source = provider.bucket("data", path="sales.parquet")
    df = load_data(source)
    return df

# Method 2: Module-level resources (reusable)
sales_bucket = provider.bucket("sales", path="transactions.parquet")
customer_bucket = provider.bucket("customers", path="customers.parquet")

@pipeline
def my_pipeline():
    sales = load_sales(sales_bucket)
    customers = load_customers(customer_bucket)
    return join_data(sales, customers)
```

**Pros:**
- ✅ Clear ownership (provider creates resources)
- ✅ Type-safe
- ✅ Reusable resource definitions
- ✅ Works with any provider

### Alternative: Resource Registry (Not Recommended)

```python
# Alternative: Global registry pattern
from glacier import register_resource

register_resource("sales_data", provider.bucket("sales", path="transactions.parquet"))
register_resource("customer_data", provider.bucket("customers", path="customers.parquet"))

@task
def load_sales(source: Bucket = Resource("sales_data")) -> pl.LazyFrame:
    return source.scan()
```

**Why not:**
- ❌ Global state
- ❌ String-based lookup (not type-safe)
- ❌ Harder to test
- ❌ Not idiomatic Python

### Alternative: Declarative Class-Based (Not Recommended)

```python
# Alternative: Class-based pipeline definition
class SalesPipeline(Pipeline):
    name = "sales_analysis"

    sales_source = BucketResource("sales", path="transactions.parquet")
    customer_source = BucketResource("customers", path="customers.parquet")

    @task
    def load_sales(self) -> pl.LazyFrame:
        return self.sales_source.scan()

    @task
    def load_customers(self) -> pl.LazyFrame:
        return self.customer_source.scan()

    @task
    def join_data(self, sales: pl.LazyFrame, customers: pl.LazyFrame) -> pl.LazyFrame:
        return sales.join(customers, on="customer_id")
```

**Why not:**
- ❌ More boilerplate
- ❌ Class complexity for simple pipelines
- ❌ Harder to compose pipelines
- ❌ Less flexible

---

## Example Usage Scenarios

### Scenario 1: Simple ETL

```python
from glacier import pipeline, task
from glacier.providers import LocalProvider
import polars as pl

provider = LocalProvider()

@task
def extract(source: Bucket) -> pl.LazyFrame:
    return source.scan()

@task
def transform(df: pl.LazyFrame) -> pl.LazyFrame:
    return (
        df.filter(pl.col("amount") > 0)
        .with_columns(pl.col("date").str.to_date())
    )

@task
def load(df: pl.LazyFrame, target: Bucket) -> None:
    df.collect().write_parquet(target.get_uri())

@pipeline
def simple_etl():
    source = provider.bucket("raw", path="data.csv", format="csv")
    target = provider.bucket("processed", path="data.parquet")

    df = extract(source)
    df = transform(df)
    load(df, target)

# Run locally
simple_etl.run(mode="local")

# Generate infrastructure
simple_etl.run(mode="generate", output_dir="./terraform")
```

### Scenario 2: Multi-Source Analytics

```python
from glacier import pipeline, task
from glacier.providers import AWSProvider
import polars as pl

provider = AWSProvider(region="us-east-1")

@task
def load_sales(source: Bucket) -> pl.LazyFrame:
    return source.scan()

@task
def load_inventory(source: Bucket) -> pl.LazyFrame:
    return source.scan()

@task
def load_customers(source: Bucket) -> pl.LazyFrame:
    return source.scan()

@task
def enrich_sales(
    sales: pl.LazyFrame,
    inventory: pl.LazyFrame,
    customers: pl.LazyFrame
) -> pl.LazyFrame:
    """Join all data sources."""
    return (
        sales
        .join(inventory, on="product_id", how="left")
        .join(customers, on="customer_id", how="left")
    )

@task
def compute_metrics(df: pl.LazyFrame) -> pl.DataFrame:
    """Calculate business metrics."""
    return (
        df.group_by("customer_segment", "product_category")
        .agg([
            pl.sum("revenue").alias("total_revenue"),
            pl.mean("margin").alias("avg_margin"),
            pl.count("order_id").alias("order_count")
        ])
        .collect()
    )

@pipeline(name="sales_analytics")
def sales_analytics():
    """
    Multi-source analytics pipeline.

    DAG automatically inferred:
    - 3 parallel loads (sales, inventory, customers)
    - enrich_sales waits for all 3
    - compute_metrics waits for enrich_sales
    """
    sales = load_sales(provider.bucket("sales", path="transactions.parquet"))
    inventory = load_inventory(provider.bucket("inventory", path="products.parquet"))
    customers = load_customers(provider.bucket("customers", path="customers.parquet"))

    enriched = enrich_sales(sales, inventory, customers)
    metrics = compute_metrics(enriched)

    return metrics

# Analyze pipeline structure
analysis = sales_analytics.run(mode="analyze")
print(f"Tasks: {len(analysis['tasks'])}")
print(f"Execution levels: {analysis['execution_levels']}")
# Output:
# Tasks: 5
# Execution levels: [
#   [load_sales, load_inventory, load_customers],  # Parallel
#   [enrich_sales],
#   [compute_metrics]
# ]
```

### Scenario 3: Data Quality Validation

```python
from glacier import pipeline, task
from glacier.providers import GCPProvider
import polars as pl

provider = GCPProvider(project_id="my-project", region="us-central1")

@task
def validate_schema(source: Bucket) -> dict:
    """Validate data schema and return validation results."""
    df = source.scan()

    required_columns = {"order_id", "customer_id", "amount", "date"}
    actual_columns = set(df.columns)

    return {
        "valid": required_columns.issubset(actual_columns),
        "missing": list(required_columns - actual_columns),
        "extra": list(actual_columns - required_columns)
    }

@task
def validate_quality(source: Bucket) -> dict:
    """Check data quality metrics."""
    df = source.scan()

    total = df.select(pl.count()).collect()[0, 0]
    nulls = df.select(pl.col("amount").is_null().sum()).collect()[0, 0]
    negatives = df.select((pl.col("amount") < 0).sum()).collect()[0, 0]

    return {
        "total_rows": total,
        "null_count": nulls,
        "negative_count": negatives,
        "quality_score": 1 - (nulls + negatives) / total
    }

@task(depends_on=[validate_schema, validate_quality])
def process_data(source: Bucket) -> pl.LazyFrame:
    """Process data only after validations pass."""
    return (
        source.scan()
        .filter(pl.col("amount").is_not_null())
        .filter(pl.col("amount") > 0)
    )

@task
def send_alert(schema_result: dict, quality_result: dict) -> None:
    """Send alert if validation fails."""
    if not schema_result["valid"]:
        print(f"Schema validation failed: {schema_result}")

    if quality_result["quality_score"] < 0.95:
        print(f"Quality below threshold: {quality_result}")

@pipeline(name="validated_processing")
def validated_processing():
    """
    Pipeline with validation gates.

    Uses explicit depends_on because validations return metadata,
    not data that flows through.
    """
    source = provider.bucket("raw-data", path="orders.parquet")

    # Run validations
    schema_result = validate_schema(source)
    quality_result = validate_quality(source)

    # Process only after validations complete
    processed = process_data(source)

    # Send alerts based on validation results
    send_alert(schema_result, quality_result)

    return processed
```

### Scenario 4: Serverless Transformation

```python
from glacier import pipeline, task
from glacier.providers import AWSProvider
from glacier.config import LambdaConfig
import polars as pl

provider = AWSProvider(region="us-east-1")

@task
def load_raw_data(source: Bucket) -> pl.LazyFrame:
    return source.scan()

@task
def prepare_for_processing(df: pl.LazyFrame, output: Bucket) -> str:
    """Write data for serverless processing."""
    output_path = output.get_uri()
    df.collect().write_parquet(output_path)
    return output_path

@task(depends_on=[prepare_for_processing])
def invoke_processing(fn: Serverless, input_path: str) -> dict:
    """Invoke serverless function to process data."""
    return fn.invoke(payload={"input_path": input_path})

@task
def load_results(source: Bucket) -> pl.DataFrame:
    """Load processed results."""
    return source.read()

@pipeline(name="serverless_pipeline")
def serverless_pipeline():
    """
    Hybrid pipeline with serverless processing.
    """
    # Resources
    raw = provider.bucket("raw", path="input.parquet")
    staging = provider.bucket("staging", path="prepared.parquet")
    results = provider.bucket("results", path="output.parquet")

    # Serverless function
    processor = provider.serverless(
        "data-processor",
        handler="process.handler",
        runtime="python3.11",
        config=LambdaConfig(memory=3008, timeout=900)
    )

    # Pipeline flow
    df = load_raw_data(raw)
    input_path = prepare_for_processing(df, staging)
    invoke_processing(processor, input_path)
    final_results = load_results(results)

    return final_results
```

### Scenario 5: Environment-Based Provider Selection

```python
import os
from glacier import pipeline, task
from glacier.providers import AWSProvider, GCPProvider, LocalProvider
import polars as pl

# Select provider based on environment
def get_provider():
    env = os.getenv("GLACIER_ENV", "local")

    if env == "aws":
        return AWSProvider(region=os.getenv("AWS_REGION", "us-east-1"))
    elif env == "gcp":
        return GCPProvider(
            project_id=os.getenv("GCP_PROJECT_ID"),
            region=os.getenv("GCP_REGION", "us-central1")
        )
    else:
        return LocalProvider(base_path="./data")

provider = get_provider()

@task
def load_data(source: Bucket) -> pl.LazyFrame:
    return source.scan()

@task
def transform(df: pl.LazyFrame) -> pl.DataFrame:
    return df.filter(pl.col("amount") > 100).collect()

@pipeline(name="portable_pipeline")
def portable_pipeline():
    """
    Completely cloud-agnostic pipeline.

    Same code runs on:
    - Local: GLACIER_ENV=local
    - AWS: GLACIER_ENV=aws AWS_REGION=us-east-1
    - GCP: GLACIER_ENV=gcp GCP_PROJECT_ID=my-project
    """
    source = provider.bucket("data", path="sales.parquet")
    df = load_data(source)
    result = transform(df)
    return result

# Run in any environment
if __name__ == "__main__":
    result = portable_pipeline.run(mode="local")
    print(result)
```

---

## Migration Path

### Phase 1: Enhance Current Design (Immediate)

**Add implicit dependency inference:**

1. Implement AST-based analysis in `PipelineAnalyzer`
   - Parse pipeline function AST
   - Extract variable assignments
   - Build dependency graph from data flow

2. Make `depends_on` optional
   - Infer from task calls when possible
   - Explicit `depends_on` for non-data dependencies

3. Improve error messages
   - Detect circular dependencies
   - Suggest fixes for common issues

**Example enhancement:**
```python
# Before (explicit)
@task(depends_on=[task1])
def task2(df: pl.LazyFrame) -> pl.LazyFrame:
    return df.filter(...)

@pipeline
def my_pipeline():
    df = task2()  # Must remember to call task1 first

# After (implicit)
@task
def task2(df: pl.LazyFrame) -> pl.LazyFrame:
    return df.filter(...)

@pipeline
def my_pipeline():
    df1 = task1(source)  # Automatically detected
    df2 = task2(df1)     # Dependency inferred from data flow
    return df2
```

### Phase 2: Progressive Enhancements (3-6 months)

1. **Resource lifecycle management**
   - Add `cleanup()` methods to resources
   - Optional context manager support

2. **Advanced provider configs**
   - More granular cloud-specific options
   - Validation and defaults

3. **Execution optimizations**
   - Parallel task execution based on DAG levels
   - Caching for repeated computations

4. **Better testing support**
   - Mock providers for unit tests
   - Fixture utilities

### Phase 3: Advanced Features (6-12 months)

1. **Dynamic pipelines**
   - Conditional task execution
   - Loop constructs

2. **Multi-cloud pipelines**
   - Tasks can use different providers
   - Cross-cloud data transfer

3. **Observability**
   - Task execution metrics
   - Resource usage tracking
   - Integration with monitoring tools

4. **Additional code generators**
   - Pulumi support
   - CDK support
   - Kubernetes manifests

---

## Future Enhancements

### 1. Smart Dependency Inference

**Vision:** Automatically infer all dependencies without manual `depends_on`.

```python
@task
def validate(source: Bucket) -> bool:
    # Returns validation result
    return True

@task
def process(source: Bucket) -> pl.LazyFrame:
    # Should wait for validate() even though no data flows
    return source.scan()

@pipeline
def smart_pipeline():
    source = provider.bucket("data", path="input.parquet")

    # Glacier infers: process should wait for validate
    # because both use the same source resource
    valid = validate(source)
    df = process(source)

    return df
```

**Implementation:**
- Track resource access patterns
- Infer side-effect dependencies
- Allow manual override when needed

### 2. Resource Composition

**Vision:** Compose complex resources from simpler ones.

```python
from glacier import composite_resource

@composite_resource
def create_data_lake(provider, name: str):
    """Create a complete data lake with multiple buckets."""
    return {
        "raw": provider.bucket(f"{name}-raw", path="data.parquet"),
        "processed": provider.bucket(f"{name}-processed", path="data.parquet"),
        "analytics": provider.bucket(f"{name}-analytics", path="data.parquet"),
    }

@pipeline
def data_lake_pipeline():
    lake = create_data_lake(provider, "sales")

    raw_df = load_data(lake["raw"])
    processed_df = transform(raw_df)
    # ... write to lake["processed"]
```

### 3. Pipeline Composition

**Vision:** Compose larger pipelines from smaller ones.

```python
@pipeline
def ingestion_pipeline() -> pl.LazyFrame:
    source = provider.bucket("raw", path="data.parquet")
    return extract_and_validate(source)

@pipeline
def analytics_pipeline(df: pl.LazyFrame) -> pl.DataFrame:
    return compute_metrics(df)

@pipeline
def end_to_end():
    """Compose multiple pipelines."""
    df = ingestion_pipeline.run(mode="local")
    result = analytics_pipeline.run(mode="local", inputs={"df": df})
    return result
```

### 4. Interactive Development

**Vision:** REPL-friendly development experience.

```python
# In Jupyter notebook or IPython
from glacier import interactive_mode

with interactive_mode():
    # Resources created in interactive mode persist
    source = provider.bucket("data", path="sales.parquet")

    # Tasks can be called directly for testing
    df = load_sales(source)
    print(df.head())  # Immediate feedback

    # Incremental pipeline building
    transformed = transform(df)
    print(transformed.head())

    # When ready, wrap in @pipeline
    @pipeline
    def final_pipeline():
        df = load_sales(source)
        return transform(df)
```

### 5. Built-in Observability

**Vision:** First-class observability without external tools.

```python
from glacier import pipeline, task, observe

@task
@observe(metrics=["duration", "memory", "rows_processed"])
def expensive_task(df: pl.LazyFrame) -> pl.LazyFrame:
    return df.filter(...)  # Automatically tracked

@pipeline
def monitored_pipeline():
    df = expensive_task(source)
    return df

# After execution
result = monitored_pipeline.run(mode="local")
print(monitored_pipeline.get_metrics())
# Output:
# {
#   "expensive_task": {
#     "duration_ms": 1234,
#     "memory_mb": 512,
#     "rows_processed": 1000000
#   }
# }
```

---

## Conclusion

The **recommended design** for Glacier is:

1. **Implicit dependency inference** from data flow (Pythonic, intuitive)
2. **Optional explicit dependencies** for complex cases (flexible)
3. **Provider factory pattern** for cloud-agnostic resources (portable)
4. **Type hints everywhere** (safe, discoverable)
5. **Progressive disclosure** (simple defaults, advanced config available)

This design balances:
- **Simplicity** for common cases (just write Python!)
- **Flexibility** for complex scenarios (explicit control when needed)
- **Type safety** for correctness (catch errors early)
- **Discoverability** for developer productivity (IDE autocomplete)
- **Cloud portability** for business value (no vendor lock-in)

The UX principle is: **"Write Python code, get cloud infrastructure."**

---

## Appendix: Design Principles Summary

1. **Python-first** - Infrastructure is derived from code, not config files
2. **Explicit over implicit** - Unless implicit is obviously better
3. **Progressive disclosure** - Simple by default, powerful when needed
4. **Cloud agnostic** - Same code, any cloud
5. **Type safe** - Leverage Python's type system
6. **Composable** - Build complex from simple
7. **Testable** - Easy to unit test and mock
8. **Analyzable** - Enable static analysis and code generation
9. **Familiar** - Use Python idioms, not custom DSL
10. **Ergonomic** - Optimize for developer happiness

---

**Document Status:** Draft for Review
**Next Steps:**
1. Team review and feedback
2. Prototype implicit dependency inference
3. Update examples and documentation
4. Implement Phase 1 enhancements
