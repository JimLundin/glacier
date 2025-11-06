# Glacier Pipeline Examples - Chainable Storage Pattern

This directory contains complete examples demonstrating how to build data pipelines using Glacier's **chainable storage pattern**.

## Overview

Glacier uses a **chainable storage pattern** where:
- **Storage (Buckets) are the fundamental units** - all buckets are treated equally
- **Single-source**: Chain buckets directly with `.transform().to()`
- **Multi-source**: Use `Pipeline()` for joins, which returns chainable Buckets
- **Pipeline definition**: The final Bucket with lineage IS the pipeline definition for code generation

## New Examples (Chainable Storage Pattern)

### 1. Simple Pipeline (`simple_pipeline_example.py`)

**What it shows**: Basic single-source pipeline with data cleaning and aggregation.

**Key concepts**:
- Provider and execution resource setup
- Storage bucket definitions
- Task definitions using decorators
- Chainable bucket pattern: `bucket.transform(task).to(bucket)`
- Pipeline execution

**Pattern**:
```python
my_pipeline = (
    raw_data
    .transform(clean_data)
    .to(cleaned_data)
    .transform(calculate_metrics)
    .to(output_data)
)

my_pipeline.run(mode="local")
```

**Run it**:
```bash
python examples/simple_pipeline_example.py
```

---

### 2. Complete Pipeline (`complete_pipeline_example.py`)

**What it shows**: Full-featured production pipeline with multiple stages, execution resources, and modes.

**Key concepts**:
- Multiple execution resources (local, Lambda, Spark)
- Complex multi-stage pipelines
- Both single-source and multi-source patterns
- Pipeline dependencies and staging
- Different execution modes (run, generate, visualize, analyze)

**Components**:
- **Execution resources**: Local, AWS Lambda (serverless), Spark (distributed)
- **Storage**: Raw → Cleaned → Enriched → Output
- **Tasks**: Data cleaning, joins, aggregations
- **Pipelines**: Data cleaning, enrichment (joins), analytics

**Run it**:
```bash
# Execute all pipelines
python examples/complete_pipeline_example.py run

# Generate Terraform infrastructure code
python examples/complete_pipeline_example.py generate

# Visualize pipeline structure
python examples/complete_pipeline_example.py visualize

# Analyze costs and performance
python examples/complete_pipeline_example.py analyze
```

---

### 3. Multi-Source Join (`multi_source_join_example.py`)

**What it shows**: How to handle multiple data sources (joins) using the `Pipeline()` builder.

**Key concepts**:
- Multi-source transforms using `Pipeline()`
- Mixing multi-source and single-source patterns
- Chaining after joins (Pipeline.to() returns Bucket)
- Multi-stage pipelines with dependencies

**Patterns demonstrated**:

#### Pattern 1: Multi-source join
```python
# Use Pipeline() for joins
pipeline = (
    Pipeline(orders_df=orders, customers_df=customers)  # Multi-source
    .transform(join_task)                                # Join transform
    .to(joined_data)                                     # Returns Bucket!
)
```

#### Pattern 2: Chaining multi-source operations
```python
# First join
step1 = (
    Pipeline(orders_df=orders, customers_df=customers)
    .transform(join_orders_customers)
    .to(orders_with_customers)  # Returns Bucket
)

# Second join using result from first join
step2 = (
    Pipeline(orders_df=orders_with_customers, products_df=products)
    .transform(enrich_with_products)
    .to(fully_enriched)  # Returns Bucket
)
```

#### Pattern 3: Single-source after multi-source
```python
# After joins, you have a single Bucket - chain directly!
final = (
    fully_enriched              # Single bucket
    .transform(aggregate)       # Single-source transform
    .to(output)
)
```

**Important**:
- Task parameter names must match Pipeline kwargs
- Example: `Pipeline(sales_df=x, customers_df=y)` → `def join(sales_df, customers_df)`

**Run it**:
```bash
# Execute the pipeline
python examples/multi_source_join_example.py run

# Visualize the pipeline
python examples/multi_source_join_example.py visualize
```

---

## Core Pattern Reference

### 1. Setup

```python
from glacier import Provider, Pipeline
from glacier.config import AwsConfig

# Create provider
provider = Provider(config=AwsConfig(region="us-east-1"))

# Create execution resources
local_exec = provider.local()
lambda_exec = provider.serverless(config=LambdaConfig(...))
spark_exec = provider.spark(config=SparkConfig(...))
```

### 2. Define Storage

```python
# All buckets are equal - no special "source" vs "target"
raw_data = provider.bucket(bucket="my-bucket", path="raw/data.parquet")
processed = provider.bucket(bucket="my-bucket", path="processed/data.parquet")
output = provider.bucket(bucket="my-bucket", path="output/data.parquet")
```

### 3. Define Tasks

```python
# Single-source task (one DataFrame parameter)
@local_exec.task()
def process_data(df: pl.LazyFrame) -> pl.LazyFrame:
    return df.filter(pl.col("value") > 0)

# Multi-source task (multiple DataFrame parameters)
@spark_exec.task()
def join_data(left_df: pl.LazyFrame, right_df: pl.LazyFrame) -> pl.LazyFrame:
    return left_df.join(right_df, on="id")
```

### 4. Build Pipeline

```python
# Single-source: Chain buckets directly
pipeline = (
    raw_data
    .transform(process_data)
    .to(processed)
    .transform(aggregate)
    .to(output)
    .with_name("my_pipeline")  # Optional: add metadata
)

# Multi-source: Use Pipeline()
pipeline = (
    Pipeline(left_df=bucket1, right_df=bucket2)
    .transform(join_data)
    .to(output)  # Returns Bucket - can continue chaining!
)
```

### 5. Execute Pipeline

```python
# Run locally
pipeline.run(mode="local")

# Run in cloud (distributed)
pipeline.run(mode="cloud")

# Generate infrastructure code (Terraform, etc.)
pipeline.run(mode="generate", output_dir="./terraform")

# Analyze pipeline
analysis = pipeline.run(mode="analyze")
print(analysis.estimated_cost())

# Visualize pipeline
print(pipeline.visualize())
```

---

## Pipeline Definition Capture

The key insight: **The Bucket with lineage IS the pipeline definition**.

```python
# When you write this:
my_pipeline = (
    raw_data
    .transform(process)
    .to(output)
    .with_name("my_pipeline")
)

# my_pipeline is a Bucket that contains:
# - Complete pipeline definition in my_pipeline._lineage
# - All transform steps (source → task → target)
# - Can be executed, analyzed, or used for code generation
```

### How Code Generation Works

1. **Execute Python file** - Run your pipeline definition file
2. **Find pipelines** - Scan for Buckets with lineage
3. **Extract definition** - Read the TransformSteps from lineage
4. **Generate infrastructure** - Convert to Terraform, CloudFormation, etc.

```python
# Code generator (simplified)
import importlib

# Load user's pipeline module
module = load_module("my_pipelines.py")

# Find all pipeline definitions
pipelines = [
    (name, obj) for name, obj in vars(module).items()
    if hasattr(obj, '_lineage') and obj._lineage
]

# Generate infrastructure
for name, pipeline in pipelines:
    pipeline.run(mode="generate", output_dir=f"./terraform/{name}")
```

---

## Design Principles

1. **Storage is fundamental** - Buckets are the primary abstraction
2. **No special-cased "source"** - All storage is treated equally
3. **Explicit materialization** - Every `.to()` writes to storage (visible in code)
4. **Lineage tracking** - Buckets track how they're produced
5. **Clean and readable** - Fluent API for pipeline composition
6. **Capturable** - Pipeline definitions can be extracted for code generation
7. **Physical reality** - Matches how distributed systems actually work (storage boundaries)

---

## Best Practices

### 1. Name Your Pipelines

```python
pipeline = (
    raw_data
    .transform(process)
    .to(output)
    .with_name("my_etl", "Daily ETL process")  # Add name and description
)
```

### 2. Use Appropriate Execution Resources

- **Local**: Small data, development, testing
- **Lambda/Serverless**: Auto-scaling, unpredictable workloads
- **Spark/Distributed**: Large data, complex joins

### 3. Explicit Intermediate Storage

```python
# Good: Explicit checkpoints
pipeline = (
    raw
    .transform(expensive_operation)
    .to(checkpoint)  # Explicit checkpoint
    .transform(next_step)
    .to(output)
)

# Also valid: Skip checkpoint if not needed
pipeline = (
    raw
    .transform(cheap_operation)
    .to(output)  # Direct to output
)
```

### 4. Multi-Source Task Parameters

```python
# Task parameter names MUST match Pipeline kwargs
@task()
def join(sales_df, customers_df):  # Parameter names
    ...

# Must match:
Pipeline(sales_df=sales, customers_df=customers)  # Kwarg names
```

### 5. Build Multi-Stage Pipelines

```python
# For multiple multi-source operations, build stages:
stage1 = Pipeline(a=x, b=y).transform(join1).to(result1)
stage2 = Pipeline(c=result1, d=z).transform(join2).to(result2)
stage3 = result2.transform(aggregate).to(final)

# Execute in order:
stage1.run()
stage2.run()
stage3.run()
```

---

## Common Patterns

### Pattern: ETL Pipeline
```python
etl = (
    raw_data
    .transform(extract)    # Extract and clean
    .to(cleaned)
    .transform(transform)  # Transform business logic
    .to(transformed)
    .transform(load)       # Aggregate and load
    .to(output)
)
```

### Pattern: Join and Aggregate
```python
joined = (
    Pipeline(orders=orders, customers=customers)
    .transform(join_data)
    .to(joined_data)  # Returns Bucket
)

aggregated = (
    joined_data           # Single-source from here
    .transform(aggregate)
    .to(summary)
)
```

### Pattern: Branching Analytics
```python
# Enrich data once
enriched = (
    Pipeline(a=source_a, b=source_b)
    .transform(enrich)
    .to(enriched_data)
)

# Create multiple outputs from same enriched data
regional = enriched_data.transform(regional_agg).to(regional_output)
product = enriched_data.transform(product_agg).to(product_output)
customer = enriched_data.transform(customer_agg).to(customer_output)

# Run them all
regional.run()
product.run()
customer.run()
```

---

## Next Steps

1. **Start with `simple_pipeline_example.py`** - Understand the basic pattern
2. **Explore `complete_pipeline_example.py`** - See production patterns
3. **Study `multi_source_join_example.py`** - Learn multi-source handling
4. **Build your own pipeline** - Apply the patterns to your use case
5. **Generate infrastructure** - Use `mode="generate"` to create Terraform

---

## Questions?

Refer to the main design document: `../DESIGN_PIPELINE_COMPOSITION.md`
