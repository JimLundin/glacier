# Pipeline Composition Design: Final Pattern

**Status:** Design Document - CORRECTED
**Date:** 2025-11-06
**Related:** DESIGN_UX.md

---

## Executive Summary

This document defines the pipeline composition pattern for Glacier. The key principle: **Pipeline() factory is the starting point for all pipeline definitions**.

**Core Design:**
- **Pipeline factory is the starting point** - Always start with `Pipeline(name=..., config=...)`
- **Sources are added to pipeline** - `.source()` for single, `.sources()` for multi-source
- **Transforms chain from sources** - `.transform(task)` applies transformations
- **Output to predefined buckets** - `.to(bucket)` writes and continues chain
- **Returns Pipeline object** - For DAG generation and infrastructure deployment
- **No execution in definition script** - Script defines pipeline, deployment runs it
- **Focus on DX** - Clean, readable pipeline composition for code generation

---

## Table of Contents

1. [Design Principles](#design-principles)
2. [Core Pattern](#core-pattern)
3. [Pipeline API](#pipeline-api)
4. [Implementation Specification](#implementation-specification)
5. [Examples](#examples)

---

## Design Principles

### 1. Pipeline Factory is the Starting Point

All pipelines start with the `Pipeline()` factory function with a name:

```python
pipeline = (
    Pipeline(name="my_etl")
    .source(raw_data)
    .transform(clean)
    .to(output)
)
```

### 2. Sources Are Added to Pipeline

Use `.source()` for single source or `.sources()` for multiple sources:

```python
# Single source
pipeline = Pipeline(name="cleaning").source(raw_data)

# Multiple sources (for joins)
pipeline = Pipeline(name="join").sources(
    sales_df=sales,
    customers_df=customers
)
```

### 3. Transforms Chain Naturally

Transformations chain using `.transform()` and `.to()`:

```python
pipeline = (
    Pipeline(name="etl")
    .source(raw)
    .transform(clean)       # Apply transformation
    .to(intermediate)       # Write to bucket
    .transform(aggregate)   # Next transform (reads from intermediate)
    .to(output)            # Write to final bucket
)
```

### 4. No Execution in Definition Script

The script **only defines** the pipeline structure:

```python
# This script DEFINES the pipeline (NO EXECUTION)
my_pipeline = (
    Pipeline(name="daily_etl")
    .source(raw_data)
    .transform(process_data)
    .to(output)
)

# Pipeline object is used for:
# ✓ DAG generation
# ✓ Infrastructure code generation (Terraform, CloudFormation)
# ✓ Deployment to cloud infrastructure

# NO .run() in definition script - execution happens in deployed infrastructure
```

---

## Core Pattern

### Single-Source Pipeline

```python
from glacier import Provider, Pipeline
from glacier.config import AwsConfig
import polars as pl

# 1. Setup
provider = Provider(config=AwsConfig(region="us-east-1"))
local_exec = provider.local()
lambda_exec = provider.serverless()

# 2. Define storage
raw_data = provider.bucket(bucket="data-lake", path="raw/data.parquet")
cleaned = provider.bucket(bucket="data-lake", path="processed/cleaned.parquet")
output = provider.bucket(bucket="data-lake", path="output/result.parquet")

# 3. Define tasks
@local_exec.task()
def clean(df: pl.LazyFrame) -> pl.LazyFrame:
    return df.filter(pl.col("value").is_not_null())

@lambda_exec.task()
def aggregate(df: pl.LazyFrame) -> pl.LazyFrame:
    return df.group_by("category").agg(pl.col("value").sum())

# 4. Build pipeline - START WITH Pipeline()
etl_pipeline = (
    Pipeline(name="etl_pipeline")
    .source(raw_data)
    .transform(clean)
    .to(cleaned)
    .transform(aggregate)
    .to(output)
)

# etl_pipeline is a Pipeline object for code generation
```

### Multi-Source Pipeline (Joins)

```python
# Setup (same as above)

# Define storage
sales = provider.bucket(bucket="data", path="sales.parquet")
customers = provider.bucket(bucket="data", path="customers.parquet")
joined = provider.bucket(bucket="data", path="joined.parquet")
summary = provider.bucket(bucket="data", path="summary.parquet")

# Define multi-source task
@spark_exec.task()
def join_data(sales_df: pl.LazyFrame, customers_df: pl.LazyFrame) -> pl.LazyFrame:
    """
    Parameter names must match .sources() kwargs!
    """
    return sales_df.join(customers_df, on="customer_id")

@local_exec.task()
def summarize(df: pl.LazyFrame) -> pl.LazyFrame:
    return df.group_by("region").agg(pl.col("amount").sum())

# Build multi-source pipeline
join_pipeline = (
    Pipeline(name="sales_join")
    .sources(sales_df=sales, customers_df=customers)  # Multi-source
    .transform(join_data)                              # Join
    .to(joined)                                        # Write
    .transform(summarize)                              # Single-source from here
    .to(summary)                                       # Final output
)
```

---

## Pipeline API

### Pipeline Class

```python
class Pipeline:
    """
    Pipeline builder for composing data transformations.

    Start all pipelines with Pipeline(name=...) and chain methods.
    """

    def __init__(
        self,
        name: str,
        description: str | None = None,
        config: dict | None = None
    ):
        """
        Create a new pipeline.

        Args:
            name: Pipeline name (required)
            description: Optional description
            config: Optional configuration

        Example:
            Pipeline(name="my_etl", description="Daily ETL process")
        """
        self.name = name
        self.description = description
        self.config = config or {}
        self._steps: list[TransformStep] = []
        self._current_sources: dict[str, Bucket] | None = None

    def source(self, bucket: Bucket) -> "Pipeline":
        """
        Add a single source to the pipeline.

        Args:
            bucket: Source bucket to read from

        Returns:
            Self (for chaining)

        Example:
            Pipeline(name="etl").source(raw_data)
        """
        self._current_sources = {"df": bucket}  # Default param name
        return self

    def sources(self, **buckets: Bucket) -> "Pipeline":
        """
        Add multiple sources to the pipeline (for joins).

        Args:
            **buckets: Named source buckets (names must match task parameters)

        Returns:
            Self (for chaining)

        Example:
            Pipeline(name="join").sources(sales_df=sales, customers_df=customers)
        """
        self._current_sources = buckets
        return self

    def transform(self, task: Task) -> "Pipeline":
        """
        Apply a transformation.

        Args:
            task: Task to execute

        Returns:
            Self (for chaining)

        Example:
            pipeline.transform(clean_data)
        """
        if self._current_sources is None:
            raise ValueError("Must call .source() or .sources() before .transform()")

        # Validate task signature matches sources
        import inspect
        sig = inspect.signature(task.func)
        task_params = set(sig.parameters.keys())
        source_names = set(self._current_sources.keys())

        if task_params != source_names:
            raise ValueError(
                f"Task parameters {task_params} do not match sources {source_names}"
            )

        # Create pending step (needs .to() to complete)
        self._pending_step = PendingStep(
            sources=self._current_sources,
            task=task
        )
        self._current_sources = None  # Must call .to() next
        return self

    def to(self, bucket: Bucket) -> "Pipeline":
        """
        Write transform output to a bucket.

        Args:
            bucket: Target bucket to write to

        Returns:
            Self (for chaining)

        Example:
            pipeline.to(output_bucket)
        """
        if not hasattr(self, '_pending_step'):
            raise ValueError("Must call .transform() before .to()")

        # Complete the step
        step = TransformStep(
            sources=self._pending_step.sources,
            task=self._pending_step.task,
            target=bucket
        )
        self._steps.append(step)
        del self._pending_step

        # Set target as source for next transform
        self._current_sources = {"df": bucket}

        return self

    def to_dag(self) -> "DAG":
        """
        Build DAG from pipeline steps.

        Returns:
            DAG object

        Example:
            dag = pipeline.to_dag()
        """
        if hasattr(self, '_pending_step'):
            raise ValueError("Pipeline has incomplete step. Use .to() to complete it.")

        if not self._steps:
            raise ValueError("Pipeline has no steps")

        # Build TaskInstances
        instances = []
        for step in self._steps:
            instance = step.to_task_instance()
            instances.append(instance)

        return DAG(instances)

    def __repr__(self) -> str:
        return f"Pipeline(name='{self.name}', steps={len(self._steps)})"
```

### Supporting Classes

```python
@dataclass
class TransformStep:
    """A step in the pipeline: sources → task → target."""
    sources: dict[str, Bucket]
    task: Task
    target: Bucket

    def to_task_instance(self) -> TaskInstance:
        """Convert to TaskInstance for execution."""
        return TaskInstance(
            task=self.task,
            sources=self.sources,
            target=self.target,
            name=self.task.name
        )


@dataclass
class PendingStep:
    """A transformation awaiting .to() to complete."""
    sources: dict[str, Bucket]
    task: Task
```

---

## Implementation Specification

### File Structure

```
glacier/
├── core/
│   ├── pipeline.py      # Pipeline, TransformStep, PendingStep
│   ├── task.py          # Task, TaskInstance
│   ├── dag.py           # DAG
│   └── __init__.py
├── resources/
│   ├── bucket.py        # Bucket
│   ├── base.py          # ExecutionResource
│   └── __init__.py
├── codegen/
│   ├── terraform.py     # TerraformGenerator
│   ├── analyzer.py      # Pipeline analysis
│   └── __init__.py
└── __init__.py          # Exports: Provider, Pipeline
```

### Bucket Class (Simplified)

```python
class Bucket:
    """Storage resource - holds data location information."""

    def __init__(
        self,
        provider: "Provider",
        bucket: str,
        path: str,
        config: dict | None = None
    ):
        self.provider = provider
        self.bucket = bucket
        self.path = path
        self.config = config or {}

    def scan(self) -> pl.LazyFrame:
        """Scan data as LazyFrame (used during execution)."""
        uri = self.get_uri()
        return pl.scan_parquet(uri)

    def get_uri(self) -> str:
        """Get full URI."""
        return f"s3://{self.bucket}/{self.path}"

    def __repr__(self) -> str:
        return f"Bucket(bucket='{self.bucket}', path='{self.path}')"
```

### Task and TaskInstance

```python
class Task:
    """Task definition (from @executor.task() decorator)."""

    def __init__(
        self,
        func: Callable,
        executor: "ExecutionResource",
        name: str,
        **config
    ):
        self.func = func
        self.executor = executor
        self.name = name
        self.config = config
        self.signature = inspect.signature(func)


class TaskInstance:
    """
    Executable instance of a task.
    Represents: sources → transform → target
    """

    def __init__(
        self,
        task: Task,
        sources: dict[str, Bucket],
        target: Bucket,
        name: str
    ):
        self.task = task
        self.sources = sources
        self.target = target
        self.name = name
        self.dependencies: list["TaskInstance"] = []

    def execute(self, context: Any = None) -> Any:
        """
        Execute this task instance.
        1. Read from source(s)
        2. Execute task function
        3. Write to target
        """
        # Load all sources as LazyFrames
        source_dfs = {
            name: bucket.scan()
            for name, bucket in self.sources.items()
        }

        # Call task with named arguments
        result = self.task.func(**source_dfs)

        # Write to target
        result.collect().write_parquet(self.target.get_uri())

        return result
```

---

## Examples

### Example 1: Simple ETL

```python
# pipelines.py

from glacier import Provider, Pipeline
import polars as pl

# Setup
provider = Provider(config=AwsConfig(region="us-east-1"))
local_exec = provider.local()

# Storage
raw = provider.bucket("data", "raw.parquet")
output = provider.bucket("data", "output.parquet")

# Task
@local_exec.task()
def process(df: pl.LazyFrame) -> pl.LazyFrame:
    return df.filter(pl.col("value") > 0)

# Pipeline
simple_etl = (
    Pipeline(name="simple_etl")
    .source(raw)
    .transform(process)
    .to(output)
)
```

### Example 2: Multi-Stage Pipeline

```python
# Multi-stage with intermediate storage

raw = provider.bucket("data", "raw.parquet")
cleaned = provider.bucket("data", "cleaned.parquet")
aggregated = provider.bucket("data", "aggregated.parquet")
output = provider.bucket("data", "output.parquet")

@local_exec.task()
def clean(df): ...

@local_exec.task()
def aggregate(df): ...

@local_exec.task()
def finalize(df): ...

multi_stage = (
    Pipeline(name="multi_stage_etl")
    .source(raw)
    .transform(clean)
    .to(cleaned)
    .transform(aggregate)
    .to(aggregated)
    .transform(finalize)
    .to(output)
)
```

### Example 3: Join Pipeline

```python
# Multi-source join

sales = provider.bucket("data", "sales.parquet")
customers = provider.bucket("data", "customers.parquet")
products = provider.bucket("data", "products.parquet")
joined1 = provider.bucket("data", "joined1.parquet")
joined2 = provider.bucket("data", "joined2.parquet")
output = provider.bucket("data", "output.parquet")

@spark_exec.task()
def join_sales_customers(sales_df, customers_df):
    return sales_df.join(customers_df, on="customer_id")

@spark_exec.task()
def join_products(df, products_df):
    return df.join(products_df, on="product_id")

@local_exec.task()
def summarize(df):
    return df.group_by("region").agg(pl.col("amount").sum())

# First join
step1 = (
    Pipeline(name="join_step1")
    .sources(sales_df=sales, customers_df=customers)
    .transform(join_sales_customers)
    .to(joined1)
)

# Second join
step2 = (
    Pipeline(name="join_step2")
    .sources(df=joined1, products_df=products)
    .transform(join_products)
    .to(joined2)
)

# Summarize
step3 = (
    Pipeline(name="summarize")
    .source(joined2)
    .transform(summarize)
    .to(output)
)
```

---

## Code Generation

The code generator executes the pipeline definition file and finds Pipeline objects:

```python
# generator.py

import importlib.util

# Load user's pipeline module
spec = importlib.util.spec_from_file_location("pipelines", "pipelines.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

# Find all Pipeline objects
pipelines = []
for name, obj in vars(module).items():
    if isinstance(obj, Pipeline):
        pipelines.append((name, obj))

# Generate infrastructure for each
for var_name, pipeline in pipelines:
    print(f"Generating infrastructure for: {pipeline.name}")
    generator = TerraformGenerator(pipeline)
    generator.generate(output_dir=f"./terraform/{pipeline.name}")
```

---

## Summary

### Pattern

```python
pipeline = (
    Pipeline(name="my_etl")     # Start with Pipeline factory
    .source(raw)                # or .sources() for multi-source
    .transform(task1)           # Apply transformation
    .to(intermediate)           # Write to bucket
    .transform(task2)           # Apply transformation (reads from intermediate)
    .to(output)                 # Write to final bucket
)
# Returns Pipeline object for code generation
```

### Key Points

✅ **Start with Pipeline()** - Factory function with name
✅ **Add sources** - `.source()` or `.sources()`
✅ **Chain transforms** - `.transform().to()` pattern
✅ **No execution** - Script only defines, deployment runs
✅ **Clean DX** - Readable, fluent API
✅ **Capturable** - Pipeline objects found by code generator

---

**END OF DOCUMENT**
