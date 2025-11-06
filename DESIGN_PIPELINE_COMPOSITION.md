# Pipeline Composition Design: Chainable Storage Pattern

**Status:** Design Document - Final v2
**Date:** 2025-11-06
**Related:** DESIGN_UX.md

---

## Executive Summary

This document defines a **chainable storage** pattern for composing pipelines in Glacier. The key principle: **storage resources (Buckets) are the chainable units, not pipelines**.

**Core Design:**
- **Storage is the fundamental unit** - Buckets are chainable
- **No special-cased "source"** - All storage is treated equally
- **Transforms are operations on storage** - `bucket.transform(task).to(bucket)`
- **Lineage tracking** - Each bucket knows how it's produced
- **Bucket with lineage IS the pipeline** - The final bucket IS the pipeline definition for code generation
- **Single-source: Chain buckets directly** - `raw.transform(task).to(output)`
- **Multi-source: Use Pipeline** - `Pipeline(s1=bucket1, s2=bucket2).transform(join).to(output)`

---

## Table of Contents

1. [Design Principles](#design-principles)
2. [Core Pattern](#core-pattern)
3. [Pipeline Definition Capture](#pipeline-definition-capture)
4. [Chainable Storage API](#chainable-storage-api)
5. [Why Chainable Storage](#why-chainable-storage)
6. [Composition Patterns](#composition-patterns)
7. [Implementation Specification](#implementation-specification)

---

## Design Principles

### 1. Storage is the Fundamental Unit

All storage is equal - there's no distinction between "source", "intermediate", and "target":

```python
# All of these are just Bucket objects
raw_data = provider.bucket(bucket="data", path="raw.parquet")
intermediate = provider.bucket(bucket="data", path="intermediate.parquet")
output = provider.bucket(bucket="data", path="output.parquet")

# Chain them directly - start with any bucket
pipeline = (
    raw_data                    # Bucket
    .transform(extract)         # PendingTransform
    .to(intermediate)           # Bucket (with lineage)
    .transform(transform)       # PendingTransform
    .to(output)                 # Bucket (with lineage)
)

# Execute
pipeline.run()
```

### 2. Buckets Are Chainable

Every bucket can be transformed, creating a chain:

```python
bucket.transform(task)          # Returns PendingTransform
pending.to(target_bucket)       # Returns target bucket with lineage
```

### 3. Lineage Tracking

Each bucket tracks the transformations that produce it:

```python
# output bucket knows:
# 1. raw_data → extract → intermediate
# 2. intermediate → transform → output
output._lineage = [step1, step2]
```

### 4. Single-Source vs Multi-Source

For single-source transforms (most common), chain buckets directly. For multi-source transforms (joins, unions), use Pipeline:

```python
# Single source - chain buckets directly
pipeline = raw.transform(extract).to(output)

# Multi-source - use Pipeline factory
pipeline = (
    Pipeline(sales=sales_bucket, customers=customers_bucket)
    .transform(join_task)
    .to(joined_output)
)

# Pipeline.to() returns a Bucket, so you can continue chaining
pipeline = (
    Pipeline(sales=sales_bucket, customers=customers_bucket)
    .transform(join_task)
    .to(joined)              # Returns Bucket
    .transform(aggregate)     # Back to single-source chaining
    .to(output)
)
```

---

## Core Pattern

### Complete Example

```python
from glacier import Provider
from glacier.config import AwsConfig, LambdaConfig
import polars as pl

# 1. Create provider and resources
provider = Provider(config=AwsConfig(region="us-east-1"))
local_exec = provider.local()
lambda_exec = provider.serverless(config=LambdaConfig(memory=1024))

# 2. Define storage resources (all equal - no special "source")
raw_data = provider.bucket(bucket="data-lake", path="raw/data.parquet")
intermediate = provider.bucket(bucket="data-lake", path="intermediate/step1.parquet")
output = provider.bucket(bucket="data-lake", path="output/result.parquet")

# 3. Define tasks with decorators
@local_exec.task()
def extract(df: pl.LazyFrame) -> pl.LazyFrame:
    """Extract and filter."""
    return df.filter(pl.col("value").is_not_null())

@lambda_exec.task()
def transform(df: pl.LazyFrame) -> pl.LazyFrame:
    """Transform data."""
    return df.with_columns((pl.col("value") * 2).alias("doubled"))

# 4. Build pipeline: chain storage directly
pipeline = (
    raw_data                    # Start with any bucket
    .transform(extract)         # Apply transformation
    .to(intermediate)           # Write to storage (explicit)
    .transform(transform)       # Apply transformation
    .to(output)                 # Write to storage (explicit)
)

# 5. Execute - pipeline is just a bucket with lineage
result = pipeline.run(mode="local")

# Can also name it for clarity
pipeline = (
    raw_data
    .transform(extract)
    .to(intermediate)
    .transform(transform)
    .to(output)
    .with_name("etl_pipeline")  # Optional: add metadata
)
```

### Multi-Source Example (Joins)

```python
from glacier import Provider, Pipeline
import polars as pl

# 1. Setup
provider = Provider(config=AwsConfig(region="us-east-1"))
local_exec = provider.local()
spark_exec = provider.spark(config=SparkConfig(workers=3))

# 2. Define storage
sales = provider.bucket(bucket="data", path="sales.parquet")
customers = provider.bucket(bucket="data", path="customers.parquet")
joined = provider.bucket(bucket="data", path="joined.parquet")
output = provider.bucket(bucket="data", path="output.parquet")

# 3. Define multi-source task
@spark_exec.task()
def join_data(sales_df: pl.LazyFrame, customers_df: pl.LazyFrame) -> pl.LazyFrame:
    """Join sales with customer data."""
    return sales_df.join(customers_df, on="customer_id", how="left")

@local_exec.task()
def aggregate(df: pl.LazyFrame) -> pl.LazyFrame:
    """Aggregate by region."""
    return df.group_by("region").agg(pl.col("revenue").sum())

# 4. Build pipeline: multi-source → single-source chaining
pipeline = (
    Pipeline(sales_df=sales, customers_df=customers)  # Multi-source start
    .transform(join_data)                              # Uses both sources
    .to(joined)                                        # Returns Bucket
    .transform(aggregate)                              # Single-source (reads joined)
    .to(output)                                        # Returns Bucket
)

# 5. Execute
result = pipeline.run(mode="cloud")
```

### Key Points

1. **Single source** - Chain buckets directly: `bucket.transform(task).to(bucket)`
2. **Multi-source** - Use Pipeline: `Pipeline(src1=b1, src2=b2).transform(task).to(bucket)`
3. **`.transform(task)`** - Creates a PendingTransform (needs a target)
4. **`.to(bucket)`** - Materializes to storage, returns that bucket (chainable!)
5. **Mixing patterns** - Pipeline.to() returns Bucket, so you can continue chaining
6. **Lineage** - Final bucket tracks all transforms that produced it
7. **Execute** - Call `.run()` on the final bucket to execute the lineage

---

## Pipeline Definition Capture

### The Bucket IS the Pipeline

A key insight: **the final Bucket with lineage IS the pipeline definition**. This is captured for code generation.

```python
# Define your pipeline using chainable buckets
etl_pipeline = (
    raw_data
    .transform(extract)
    .to(intermediate)
    .transform(transform)
    .to(output)
    .with_name("etl_pipeline")  # Optional: add metadata
)

# etl_pipeline is a Bucket, but it contains the complete pipeline definition
print(etl_pipeline._lineage)  # List of TransformSteps

# Use for execution
etl_pipeline.run(mode="local")

# Use for code generation (Terraform, etc.)
etl_pipeline.run(mode="generate", output_dir="./infrastructure")

# Use for analysis
analysis = etl_pipeline.run(mode="analyze")
print(analysis.estimated_cost())

# Visualize
print(etl_pipeline.visualize())
```

### Why This Works for Code Generation

When you write:

```python
# pipelines.py
from glacier import Provider

provider = Provider(...)
local_exec = provider.local()

# Define storage
raw = provider.bucket("data", "raw.parquet")
output = provider.bucket("data", "output.parquet")

# Define task
@local_exec.task()
def process(df): ...

# Define pipeline
my_pipeline = (
    raw
    .transform(process)
    .to(output)
    .with_name("my_pipeline")
)
```

The code generator can:

1. **Execute the Python file** - Run `pipelines.py` to instantiate the objects
2. **Find pipelines** - Scan module for Buckets with lineage (e.g., `hasattr(obj, '_lineage') and len(obj._lineage) > 0`)
3. **Extract definition** - Read the lineage to get all TransformSteps
4. **Generate infrastructure** - Convert to Terraform, CloudFormation, etc.

```python
# Code generator (simplified)
import importlib.util

# Load user's pipeline module
spec = importlib.util.spec_from_file_location("pipelines", "pipelines.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

# Find all pipeline definitions
pipelines = []
for name, obj in vars(module).items():
    if hasattr(obj, '_lineage') and obj._lineage:
        # This is a pipeline!
        pipelines.append((name, obj))

# Generate infrastructure for each pipeline
for name, pipeline in pipelines:
    print(f"Generating infrastructure for: {name}")
    pipeline.run(mode="generate", output_dir=f"./terraform/{name}")
```

### Naming Pipelines

Use `.with_name()` to add metadata for better identification:

```python
# Unnamed - uses bucket path as default
pipeline = raw.transform(process).to(output)

# Named - explicit pipeline name
pipeline = (
    raw
    .transform(process)
    .to(output)
    .with_name("my_etl", "Daily ETL process")
)

# Access metadata
print(pipeline._metadata["name"])  # "my_etl"
```

### Multi-Source Pipelines

Multi-source pipelines also return Buckets with lineage:

```python
# Multi-source pipeline
join_pipeline = (
    Pipeline(sales=sales, customers=customers)
    .transform(join_task)
    .to(joined)
    .with_name("sales_join")
)

# join_pipeline is a Bucket with MultiSourceTransformStep in lineage
join_pipeline.run(mode="generate")
```

### Pipeline as First-Class Objects

While buckets with lineage are the pipeline definitions, you can also work with explicit Pipeline objects:

```python
# Bucket-based (recommended)
pipeline_bucket = raw.transform(process).to(output).with_name("etl")

# Convert to explicit Pipeline object if needed
pipeline_obj = pipeline_bucket.to_pipeline()
print(type(pipeline_obj))  # Pipeline

# Both work the same for execution/generation
pipeline_bucket.run(mode="generate")
pipeline_obj.run(mode="generate")
```

---

## Chainable Storage API

### Bucket Class

```python
class Bucket:
    """
    Storage resource for reading/writing data.

    Buckets are chainable - transforms produce new buckets with lineage.
    """

    def __init__(
        self,
        provider: "Provider",
        bucket: str,
        path: str,
        config: dict | None = None,
        lineage: list["TransformStep"] | None = None,
        metadata: dict | None = None
    ):
        """
        Create a storage resource.

        Args:
            provider: The provider that created this bucket
            bucket: Bucket name (e.g., "my-data-bucket")
            path: Path within bucket (e.g., "raw/data.parquet")
            config: Optional configuration
            lineage: Chain of transforms producing this bucket
            metadata: Optional metadata (name, description, etc.)
        """
        self.provider = provider
        self.bucket = bucket
        self.path = path
        self.config = config or {}
        self._lineage = lineage or []
        self._metadata = metadata or {}

    def transform(self, task: Task) -> "PendingTransform":
        """
        Apply a transformation that reads from this bucket.

        Returns a PendingTransform that must be written to a target bucket
        using .to()

        Args:
            task: Task to execute (created with @executor.task())

        Returns:
            PendingTransform (requires .to(bucket) to complete)

        Example:
            raw_data.transform(extract_task)  # Returns PendingTransform
        """
        return PendingTransform(source=self, task=task)

    def scan(self) -> pl.LazyFrame:
        """
        Scan the data source as a LazyFrame.

        Used during execution to read data from storage.
        """
        uri = self.get_uri()
        return pl.scan_parquet(uri)

    def get_uri(self) -> str:
        """Get the full URI for this bucket."""
        # Implementation depends on provider (S3, GCS, Azure, local)
        return f"s3://{self.bucket}/{self.path}"

    def run(self, mode: str = "local", **kwargs):
        """
        Execute the pipeline that produces this bucket.

        Args:
            mode: Execution mode ("local", "cloud", "generate", etc.)
            **kwargs: Additional execution parameters

        Returns:
            Execution result

        Raises:
            ValueError: If bucket has no lineage (is a source bucket)

        Example:
            output.run(mode="local")
        """
        if not self._lineage:
            raise ValueError(
                f"Cannot run bucket '{self.path}' - it has no lineage. "
                "This is a source bucket with no transforms."
            )

        # Build DAG from lineage
        instances = [step.to_task_instance() for step in self._lineage]
        dag = DAG(instances)

        # Execute based on mode
        if mode == "local":
            from glacier.runtime.local import LocalExecutor
            executor = LocalExecutor(dag)
            return executor.execute(**kwargs)
        elif mode == "cloud":
            from glacier.runtime.cloud import CloudExecutor
            executor = CloudExecutor(dag)
            return executor.execute(**kwargs)
        elif mode == "analyze":
            from glacier.codegen.analyzer import PipelineAnalysis
            return PipelineAnalysis(dag)
        elif mode == "generate":
            from glacier.codegen.terraform import TerraformGenerator
            generator = TerraformGenerator(dag)
            return generator.generate(**kwargs)
        else:
            raise ValueError(f"Unknown mode: {mode}")

    def with_name(self, name: str, description: str | None = None) -> "Bucket":
        """
        Add metadata to this bucket (for documentation/visualization).

        Args:
            name: Pipeline name
            description: Optional description

        Returns:
            Self (for chaining)

        Example:
            pipeline = raw.transform(t1).to(out).with_name("my_pipeline")
        """
        self._metadata["name"] = name
        if description:
            self._metadata["description"] = description
        return self

    def visualize(self) -> str:
        """Generate Mermaid visualization of the pipeline."""
        if not self._lineage:
            raise ValueError("Cannot visualize bucket with no lineage")

        instances = [step.to_task_instance() for step in self._lineage]
        dag = DAG(instances)
        return dag.to_mermaid()

    def to_pipeline(self) -> "Pipeline":
        """
        Convert to Pipeline object (for compatibility/advanced features).

        Returns:
            Pipeline object with same lineage

        Example:
            pipeline_obj = output.to_pipeline()
        """
        name = self._metadata.get("name", f"pipeline_{self.path}")
        description = self._metadata.get("description")
        return Pipeline(
            name=name,
            description=description,
            steps=self._lineage.copy()
        )

    def __repr__(self) -> str:
        lineage_info = f", lineage={len(self._lineage)} steps" if self._lineage else ""
        return f"Bucket(bucket='{self.bucket}', path='{self.path}'{lineage_info})"
```

### PendingTransform Class

```python
class PendingTransform:
    """
    A transformation that needs a target bucket to complete.

    Created by bucket.transform(task), completed by .to(target).
    """

    def __init__(self, source: Bucket, task: Task):
        """
        Create a pending transform.

        Args:
            source: Bucket to read from
            task: Task to execute
        """
        self.source = source
        self.task = task

    def to(self, target: Bucket) -> Bucket:
        """
        Write the transform output to a target bucket.

        This materializes the transformation and returns a new Bucket
        with extended lineage.

        Args:
            target: Bucket to write to

        Returns:
            New Bucket instance with lineage extended

        Example:
            raw.transform(extract).to(intermediate)  # Returns intermediate with lineage
        """
        # Create a transform step
        step = TransformStep(
            source=self.source,
            task=self.task,
            target=target
        )

        # Return a new bucket with extended lineage
        return Bucket(
            provider=target.provider,
            bucket=target.bucket,
            path=target.path,
            config=target.config,
            lineage=self.source._lineage + [step],
            metadata=target._metadata.copy()
        )

    def run(self, **kwargs):
        """
        Execute the transform without writing to storage (ephemeral result).

        Useful for interactive exploration.

        Returns:
            LazyFrame result (not materialized to storage)

        Example:
            result = raw.transform(extract).run()  # In-memory result
        """
        df = self.source.scan()
        result = self.task.func(df=df)
        return result

    def __repr__(self) -> str:
        return f"PendingTransform(source={self.source.path}, task={self.task.name})"
```

### Pipeline Class

```python
class Pipeline:
    """
    Multi-source pipeline builder.

    Use this when you need to pass multiple storage resources to a single transform
    (e.g., joins, unions). For single-source transforms, use bucket.transform().

    Pipeline.to() returns a Bucket, so you can continue chaining after multi-source.
    """

    def __init__(self, **sources: Bucket):
        """
        Create a multi-source pipeline.

        Args:
            **sources: Named storage resources (kwarg names match task parameter names)

        Example:
            Pipeline(sales=sales_bucket, customers=customers_bucket)
        """
        if not sources:
            raise ValueError("Pipeline requires at least one source")

        self.sources = sources
        self._pending_transform: Task | None = None
        self._all_steps: list[TransformStep] = []

    def transform(self, task: Task) -> "PipelinePendingTransform":
        """
        Apply a transformation that reads from all sources.

        The task function parameters must match the source names.

        Args:
            task: Task to execute

        Returns:
            PipelinePendingTransform (requires .to(bucket) to complete)

        Example:
            Pipeline(sales=s, customers=c).transform(join_task)
        """
        # Validate task signature matches sources
        import inspect
        sig = inspect.signature(task.func)
        task_params = set(sig.parameters.keys())
        source_names = set(self.sources.keys())

        if task_params != source_names:
            raise ValueError(
                f"Task parameters {task_params} do not match sources {source_names}"
            )

        return PipelinePendingTransform(sources=self.sources, task=task)

    def __repr__(self) -> str:
        source_names = ", ".join(self.sources.keys())
        return f"Pipeline(sources=[{source_names}])"


class PipelinePendingTransform:
    """A multi-source transformation that needs a target bucket to complete."""

    def __init__(self, sources: dict[str, Bucket], task: Task):
        """
        Create a pending multi-source transform.

        Args:
            sources: Named source buckets
            task: Task to execute
        """
        self.sources = sources
        self.task = task

    def to(self, target: Bucket) -> Bucket:
        """
        Write the transform output to a target bucket.

        This materializes the transformation and returns a new Bucket with lineage.
        The returned Bucket can be chained with further single-source transforms.

        Args:
            target: Bucket to write to

        Returns:
            New Bucket instance with lineage (chainable!)

        Example:
            # Multi-source → single-source chaining
            output = (
                Pipeline(s1=b1, s2=b2)
                .transform(join)
                .to(joined)              # Returns Bucket
                .transform(aggregate)    # Single-source chaining!
                .to(output)
            )
        """
        # Create a multi-source transform step
        step = MultiSourceTransformStep(
            sources=self.sources,
            task=self.task,
            target=target
        )

        # Collect lineage from all sources
        all_lineage = []
        for source in self.sources.values():
            all_lineage.extend(source._lineage)

        # Add this step
        all_lineage.append(step)

        # Return target bucket with full lineage
        return Bucket(
            provider=target.provider,
            bucket=target.bucket,
            path=target.path,
            config=target.config,
            lineage=all_lineage,
            metadata=target._metadata.copy()
        )

    def __repr__(self) -> str:
        source_names = ", ".join(self.sources.keys())
        return f"PipelinePendingTransform(sources=[{source_names}], task={self.task.name})"
```

### TransformStep

```python
@dataclass
class TransformStep:
    """A single-source step in the pipeline: source → task → target."""
    source: Bucket
    task: Task
    target: Bucket

    def to_task_instance(self) -> TaskInstance:
        """Convert to TaskInstance for DAG execution."""
        return TaskInstance(
            task=self.task,
            source=self.source,
            target=self.target,
            name=self.task.name
        )


@dataclass
class MultiSourceTransformStep:
    """A multi-source step in the pipeline: sources → task → target."""
    sources: dict[str, Bucket]  # Named sources
    task: Task
    target: Bucket

    def to_task_instance(self) -> TaskInstance:
        """Convert to TaskInstance for DAG execution."""
        return TaskInstance(
            task=self.task,
            sources=self.sources,
            target=self.target,
            name=self.task.name
        )
```

---

## Why Chainable Storage?

### The User's Insight

From the user's feedback:

> "We are treating the source differently to the other storage. And in addition the pipeline object does not really serve a purpose here, other than acting as a factory, something that could be integrated with the initial source definition."

**Key realizations:**

1. **All storage is equal** - `raw_data`, `intermediate`, and `output` are all just Buckets. There's no fundamental difference between "source" and "target".

2. **Pipeline object was just a factory** - It didn't add value beyond being a builder. The real pattern is: storage → transform → storage.

3. **Storage should be chainable** - If storage is the fundamental unit, make it chainable directly.

### Comparison: Before vs After

**Before (Pipeline factory):**
```python
pipeline = (
    Pipeline(name="etl")        # Factory object (why?)
    .source(raw_data)           # Special-case "source"
    .transform(extract)
    .to(intermediate)           # Regular storage
    .transform(transform)
    .to(output)                 # Regular storage
)
```

**After (Chainable storage):**
```python
pipeline = (
    raw_data                    # Just a bucket
    .transform(extract)
    .to(intermediate)           # Just a bucket
    .transform(transform)
    .to(output)                 # Just a bucket
)
```

### Benefits

✅ **Simpler** - No Pipeline factory object
✅ **More consistent** - All buckets treated equally
✅ **More intuitive** - Storage naturally chains into storage
✅ **More flexible** - Can start with any bucket, not just "sources"
✅ **Clearer intent** - Code reads like data flow: bucket → transform → bucket

---

## Composition Patterns

### 1. Sequential Pipeline

```python
# Define storage (all equal)
raw = provider.bucket(bucket="data", path="raw.parquet")
intermediate1 = provider.bucket(bucket="data", path="int1.parquet")
intermediate2 = provider.bucket(bucket="data", path="int2.parquet")
output = provider.bucket(bucket="data", path="output.parquet")

# Define tasks
@local_exec.task()
def extract(df): ...

@lambda_exec.task()
def transform(df): ...

@local_exec.task()
def aggregate(df): ...

# Chain buckets
pipeline = (
    raw
    .transform(extract)
    .to(intermediate1)
    .transform(transform)
    .to(intermediate2)
    .transform(aggregate)
    .to(output)
)

result = pipeline.run()
```

### 2. Named Pipelines

```python
pipeline = (
    raw
    .transform(extract)
    .to(intermediate)
    .transform(transform)
    .to(output)
    .with_name("etl_pipeline", "Extract, transform, load data")
)

# Visualize
print(pipeline.visualize())

# Execute
pipeline.run(mode="cloud")
```

### 3. Multi-Source Pipelines (Joins)

```python
from glacier import Pipeline

# Define storage
sales = provider.bucket("data", "sales.parquet")
customers = provider.bucket("data", "customers.parquet")
products = provider.bucket("data", "products.parquet")
joined = provider.bucket("data", "joined.parquet")
enriched = provider.bucket("data", "enriched.parquet")
output = provider.bucket("data", "output.parquet")

# Define multi-source tasks
@spark_exec.task()
def join_sales_customers(sales_df: pl.LazyFrame, customers_df: pl.LazyFrame) -> pl.LazyFrame:
    """Join sales with customers."""
    return sales_df.join(customers_df, on="customer_id", how="left")

@spark_exec.task()
def enrich_with_products(joined_df: pl.LazyFrame, products_df: pl.LazyFrame) -> pl.LazyFrame:
    """Add product information."""
    return joined_df.join(products_df, on="product_id", how="left")

@local_exec.task()
def aggregate(df: pl.LazyFrame) -> pl.LazyFrame:
    """Aggregate by region."""
    return df.group_by("region").agg(pl.col("revenue").sum())

# Build pipeline: multi-source → multi-source → single-source
pipeline = (
    Pipeline(sales_df=sales, customers_df=customers)  # Multi-source
    .transform(join_sales_customers)
    .to(joined)                                        # Returns Bucket
    .transform(enrich_with_products)                   # ERROR! Single-source, but needs 2
    # ...
)

# Correct approach: chain multi-source operations
pipeline = (
    Pipeline(sales_df=sales, customers_df=customers)  # First join
    .transform(join_sales_customers)
    .to(joined)                                        # Returns Bucket
)

pipeline = (
    Pipeline(joined_df=joined, products_df=products)  # Second join
    .transform(enrich_with_products)
    .to(enriched)                                      # Returns Bucket
    .transform(aggregate)                              # Single-source from here
    .to(output)
)

# Or as one expression:
enriched = (
    Pipeline(joined_df=joined, products_df=products)
    .transform(enrich_with_products)
    .to(enriched)
)

output = enriched.transform(aggregate).to(output)
```

### 4. Reusable Bucket References

```python
# Define storage once
raw = provider.bucket("data", "raw.parquet")
clean = provider.bucket("data", "clean.parquet")
output = provider.bucket("data", "output.parquet")

# Multiple pipelines can use the same buckets
pipeline1 = raw.transform(clean_data).to(clean)
pipeline2 = clean.transform(aggregate).to(output)

# Execute separately
pipeline1.run()
pipeline2.run()

# Or chain them
full_pipeline = (
    raw
    .transform(clean_data)
    .to(clean)
    .transform(aggregate)
    .to(output)
)
```

### 4. Conditional Pipelines

```python
def build_pipeline(mode: str):
    raw = provider.bucket("data", "raw.parquet")
    output = provider.bucket("data", "output.parquet")

    if mode == "full":
        intermediate = provider.bucket("data", "intermediate.parquet")
        return (
            raw
            .transform(extract)
            .to(intermediate)
            .transform(full_process)
            .to(output)
        )
    else:
        # Skip intermediate processing
        return raw.transform(quick_process).to(output)

pipeline = build_pipeline(mode="full")
pipeline.run()
```

### 5. Dynamic Pipelines

```python
def build_pipeline(tasks: list[Task], buckets: list[Bucket]):
    """Build a pipeline from a list of tasks and buckets."""
    pipeline = buckets[0]  # Start with first bucket

    for task, target_bucket in zip(tasks, buckets[1:]):
        pipeline = pipeline.transform(task).to(target_bucket)

    return pipeline

# Define buckets
buckets = [
    provider.bucket("data", "raw.parquet"),
    provider.bucket("data", "step1.parquet"),
    provider.bucket("data", "step2.parquet"),
    provider.bucket("data", "output.parquet")
]

# Build and run
pipeline = build_pipeline([task1, task2, task3], buckets)
pipeline.run()
```

### 6. Interactive Exploration

```python
# Load and explore without writing to storage
raw = provider.bucket("data", "raw.parquet")

# Ephemeral result (not written)
df = raw.transform(extract).run()
print(df.collect())

# If you like it, materialize it
intermediate = provider.bucket("data", "intermediate.parquet")
pipeline = raw.transform(extract).to(intermediate)
pipeline.run()
```

### 7. Partial Pipeline Execution

```python
# Build full pipeline
raw = provider.bucket("data", "raw.parquet")
int1 = provider.bucket("data", "int1.parquet")
int2 = provider.bucket("data", "int2.parquet")
output = provider.bucket("data", "output.parquet")

full_pipeline = (
    raw
    .transform(task1)
    .to(int1)
    .transform(task2)
    .to(int2)
    .transform(task3)
    .to(output)
)

# Execute just the first part
partial = raw.transform(task1).to(int1)
partial.run()

# Later, continue from int1
continuation = int1.transform(task2).to(int2).transform(task3).to(output)
continuation.run()
```

---

## Implementation Specification

### 1. Bucket Class

**File:** `glacier/resources/bucket.py`

```python
import polars as pl
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from glacier.core.task import Task
    from glacier.providers import Provider

class Bucket:
    """
    Storage resource for reading/writing data.

    Buckets are chainable - transforms produce new buckets with lineage.
    """

    def __init__(
        self,
        provider: "Provider",
        bucket: str,
        path: str,
        config: dict | None = None,
        lineage: list["TransformStep"] | None = None,
        metadata: dict | None = None
    ):
        self.provider = provider
        self.bucket = bucket
        self.path = path
        self.config = config or {}
        self._lineage = lineage or []
        self._metadata = metadata or {}

    def transform(self, task: "Task") -> "PendingTransform":
        """Apply a transformation that reads from this bucket."""
        return PendingTransform(source=self, task=task)

    def scan(self) -> pl.LazyFrame:
        """Scan the data source as a LazyFrame."""
        uri = self.get_uri()
        return pl.scan_parquet(uri)

    def get_uri(self) -> str:
        """Get the full URI for this bucket."""
        # Provider-specific implementation
        if hasattr(self.provider, 'get_bucket_uri'):
            return self.provider.get_bucket_uri(self.bucket, self.path)
        # Default to S3-style
        return f"s3://{self.bucket}/{self.path}"

    def run(self, mode: str = "local", **kwargs) -> Any:
        """Execute the pipeline that produces this bucket."""
        if not self._lineage:
            raise ValueError(
                f"Cannot run bucket '{self.path}' - it has no lineage. "
                "This is a source bucket with no transforms."
            )

        # Build DAG from lineage
        from glacier.core.dag import DAG
        instances = [step.to_task_instance() for step in self._lineage]
        dag = DAG(instances)

        # Execute based on mode
        if mode == "local":
            from glacier.runtime.local import LocalExecutor
            executor = LocalExecutor(dag)
            return executor.execute(**kwargs)
        elif mode == "cloud":
            from glacier.runtime.cloud import CloudExecutor
            executor = CloudExecutor(dag)
            return executor.execute(**kwargs)
        elif mode == "analyze":
            from glacier.codegen.analyzer import PipelineAnalysis
            return PipelineAnalysis(dag)
        elif mode == "generate":
            from glacier.codegen.terraform import TerraformGenerator
            generator = TerraformGenerator(dag)
            return generator.generate(**kwargs)
        else:
            raise ValueError(f"Unknown mode: {mode}")

    def with_name(self, name: str, description: str | None = None) -> "Bucket":
        """Add metadata to this bucket."""
        self._metadata["name"] = name
        if description:
            self._metadata["description"] = description
        return self

    def visualize(self) -> str:
        """Generate Mermaid visualization of the pipeline."""
        if not self._lineage:
            raise ValueError("Cannot visualize bucket with no lineage")

        from glacier.core.dag import DAG
        instances = [step.to_task_instance() for step in self._lineage]
        dag = DAG(instances)
        return dag.to_mermaid()

    def to_pipeline(self) -> "Pipeline":
        """Convert to Pipeline object (for compatibility)."""
        from glacier.core.pipeline import Pipeline
        name = self._metadata.get("name", f"pipeline_{self.path}")
        description = self._metadata.get("description")
        return Pipeline(
            name=name,
            description=description,
            steps=self._lineage.copy()
        )

    def __repr__(self) -> str:
        lineage_info = f", lineage={len(self._lineage)} steps" if self._lineage else ""
        return f"Bucket(bucket='{self.bucket}', path='{self.path}'{lineage_info})"


class PendingTransform:
    """A transformation that needs a target bucket to complete."""

    def __init__(self, source: Bucket, task: "Task"):
        self.source = source
        self.task = task

    def to(self, target: Bucket) -> Bucket:
        """Write the transform output to a target bucket."""
        from glacier.core.pipeline import TransformStep

        step = TransformStep(
            source=self.source,
            task=self.task,
            target=target
        )

        return Bucket(
            provider=target.provider,
            bucket=target.bucket,
            path=target.path,
            config=target.config,
            lineage=self.source._lineage + [step],
            metadata=target._metadata.copy()
        )

    def run(self, **kwargs) -> Any:
        """Execute the transform without writing to storage (ephemeral)."""
        df = self.source.scan()
        result = self.task.func(df=df)
        return result

    def __repr__(self) -> str:
        return f"PendingTransform(source={self.source.path}, task={self.task.name})"
```

### 2. TransformStep

**File:** `glacier/core/pipeline.py`

```python
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from glacier.core.task import Task, TaskInstance
    from glacier.resources.bucket import Bucket

@dataclass
class TransformStep:
    """A single-source step in the pipeline: source → task → target."""
    source: "Bucket"
    task: "Task"
    target: "Bucket"

    def to_task_instance(self) -> "TaskInstance":
        """Convert to TaskInstance for DAG execution."""
        from glacier.core.task import TaskInstance
        return TaskInstance(
            task=self.task,
            source=self.source,
            target=self.target,
            name=self.task.name
        )


@dataclass
class MultiSourceTransformStep:
    """A multi-source step in the pipeline: sources → task → target."""
    sources: dict[str, "Bucket"]
    task: "Task"
    target: "Bucket"

    def to_task_instance(self) -> "TaskInstance":
        """Convert to TaskInstance for DAG execution."""
        from glacier.core.task import TaskInstance
        return TaskInstance(
            task=self.task,
            sources=self.sources,
            target=self.target,
            name=self.task.name
        )


class Pipeline:
    """
    Multi-source pipeline builder.

    Use this when you need to pass multiple storage resources to a single transform
    (e.g., joins, unions). For single-source transforms, use bucket.transform().
    """

    def __init__(self, **sources: "Bucket"):
        """Create a multi-source pipeline."""
        if not sources:
            raise ValueError("Pipeline requires at least one source")
        self.sources = sources

    def transform(self, task: "Task") -> "PipelinePendingTransform":
        """Apply a transformation that reads from all sources."""
        import inspect
        sig = inspect.signature(task.func)
        task_params = set(sig.parameters.keys())
        source_names = set(self.sources.keys())

        if task_params != source_names:
            raise ValueError(
                f"Task parameters {task_params} do not match sources {source_names}"
            )

        return PipelinePendingTransform(sources=self.sources, task=task)

    def __repr__(self) -> str:
        source_names = ", ".join(self.sources.keys())
        return f"Pipeline(sources=[{source_names}])"


class PipelinePendingTransform:
    """A multi-source transformation that needs a target bucket."""

    def __init__(self, sources: dict[str, "Bucket"], task: "Task"):
        self.sources = sources
        self.task = task

    def to(self, target: "Bucket") -> "Bucket":
        """Write the transform output to a target bucket (returns chainable Bucket)."""
        step = MultiSourceTransformStep(
            sources=self.sources,
            task=self.task,
            target=target
        )

        # Collect lineage from all sources
        all_lineage = []
        for source in self.sources.values():
            all_lineage.extend(source._lineage)
        all_lineage.append(step)

        # Return target bucket with full lineage
        from glacier.resources.bucket import Bucket
        return Bucket(
            provider=target.provider,
            bucket=target.bucket,
            path=target.path,
            config=target.config,
            lineage=all_lineage,
            metadata=target._metadata.copy()
        )

    def __repr__(self) -> str:
        source_names = ", ".join(self.sources.keys())
        return f"PipelinePendingTransform(sources=[{source_names}], task={self.task.name})"
```

### 3. TaskInstance

**File:** `glacier/core/task.py`

```python
import inspect
from typing import Callable, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from glacier.resources.base import ExecutionResource
    from glacier.resources.bucket import Bucket

class Task:
    """Reusable task definition (from @executor.task())."""

    def __init__(
        self,
        func: Callable,
        executor: "ExecutionResource",
        name: str,
        timeout: int | None = None,
        retries: int = 0,
        cache: bool = False,
        config: dict | None = None
    ):
        self.func = func
        self.executor = executor
        self.name = name
        self.timeout = timeout
        self.retries = retries
        self.cache = cache
        self.config = config or {}
        self.signature = inspect.signature(func)

    def __call__(self, **inputs) -> Any:
        """Execute directly (for testing)."""
        return self.func(**inputs)

    def __repr__(self) -> str:
        return f"Task(name='{self.name}', executor={self.executor})"


class TaskInstance:
    """
    An instance of a Task in a pipeline.

    Represents: source(s) → transform → target
    Supports both single-source and multi-source transforms.
    """

    def __init__(
        self,
        task: Task,
        target: "Bucket",
        name: str,
        source: "Bucket | None" = None,
        sources: dict[str, "Bucket"] | None = None
    ):
        """
        Create a task instance.

        Args:
            task: The task to execute
            target: Target bucket to write to
            name: Instance name
            source: Single source bucket (for single-source transforms)
            sources: Named source buckets (for multi-source transforms)
        """
        self.task = task
        self.target = target
        self.name = name

        # Either source OR sources, not both
        if source is not None and sources is not None:
            raise ValueError("Cannot specify both source and sources")
        if source is None and sources is None:
            raise ValueError("Must specify either source or sources")

        self.source = source
        self.sources = sources
        self.dependencies: list["TaskInstance"] = []

    def execute(self, context: Any = None) -> Any:
        """
        Execute this task instance.

        1. Read from source(s) - scan as LazyFrame(s)
        2. Execute task function
        3. Write to target - materialize to parquet
        """
        if self.source is not None:
            # Single-source execution
            df = self.source.scan()
            result = self.task.func(df=df)
        else:
            # Multi-source execution
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

    def __repr__(self) -> str:
        if self.source:
            return f"TaskInstance(name='{self.name}', source={self.source.path}, target={self.target.path})"
        else:
            source_paths = ", ".join(f"{k}={v.path}" for k, v in self.sources.items())
            return f"TaskInstance(name='{self.name}', sources=[{source_paths}], target={self.target.path})"
```

### 4. DAG Class

**File:** `glacier/core/dag.py`

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from glacier.core.task import TaskInstance

class DAG:
    """Directed Acyclic Graph of task instances."""

    def __init__(self, instances: list["TaskInstance"]):
        self.instances = instances
        self._build_dependencies()
        self._validate()

    def _build_dependencies(self):
        """Build dependencies based on source/target relationships."""
        for i, instance in enumerate(self.instances):
            instance.dependencies = []

            # Collect all source paths for this instance
            if instance.source:
                # Single-source
                source_paths = {instance.source.path}
            else:
                # Multi-source
                source_paths = {bucket.path for bucket in instance.sources.values()}

            # Find dependencies
            for prev_instance in self.instances[:i]:
                if prev_instance.target.path in source_paths:
                    instance.dependencies.append(prev_instance)

    def _validate(self):
        """Validate that graph is acyclic."""
        visited = set()
        rec_stack = set()

        def has_cycle(instance: "TaskInstance") -> bool:
            visited.add(instance)
            rec_stack.add(instance)

            for dep in instance.dependencies:
                if dep not in visited:
                    if has_cycle(dep):
                        return True
                elif dep in rec_stack:
                    return True

            rec_stack.remove(instance)
            return False

        for instance in self.instances:
            if instance not in visited:
                if has_cycle(instance):
                    raise ValueError("Pipeline contains a cycle")

    def topological_sort(self) -> list["TaskInstance"]:
        """Return instances in execution order."""
        in_degree = {inst: len(inst.dependencies) for inst in self.instances}
        queue = [inst for inst in self.instances if in_degree[inst] == 0]
        result = []

        while queue:
            inst = queue.pop(0)
            result.append(inst)

            for other in self.instances:
                if inst in other.dependencies:
                    in_degree[other] -= 1
                    if in_degree[other] == 0:
                        queue.append(other)

        return result

    def to_mermaid(self) -> str:
        """Generate Mermaid diagram."""
        lines = ["graph LR"]

        for inst in self.instances:
            task_id = inst.name.replace(" ", "_")
            target_id = inst.target.path.replace("/", "_").replace(".", "_")

            if inst.source:
                # Single-source: source → task → target
                source_id = inst.source.path.replace("/", "_").replace(".", "_")
                lines.append(f"    {source_id}[({inst.source.path})]")
                lines.append(f"    {task_id}[\"{inst.name}<br/>({inst.task.executor.type})\"]")
                lines.append(f"    {target_id}[({inst.target.path})]")
                lines.append(f"    {source_id} --> {task_id}")
                lines.append(f"    {task_id} --> {target_id}")
            else:
                # Multi-source: source1 → task, source2 → task, task → target
                lines.append(f"    {task_id}[\"{inst.name}<br/>({inst.task.executor.type})\"]")
                lines.append(f"    {target_id}[({inst.target.path})]")

                for name, bucket in inst.sources.items():
                    source_id = bucket.path.replace("/", "_").replace(".", "_")
                    lines.append(f"    {source_id}[({bucket.path})]")
                    lines.append(f"    {source_id} --> {task_id}")

                lines.append(f"    {task_id} --> {target_id}")

        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"DAG(instances={len(self.instances)})"
```

### 5. Provider.bucket() Method

**File:** `glacier/providers.py`

```python
from glacier.resources.bucket import Bucket

class Provider:
    """Provider for creating resources."""

    def bucket(
        self,
        bucket: str,
        path: str,
        **config
    ) -> Bucket:
        """
        Create a storage resource.

        Args:
            bucket: Bucket name
            path: Path within bucket
            **config: Additional configuration

        Returns:
            Bucket resource (chainable)

        Example:
            raw = provider.bucket(bucket="data", path="raw.parquet")
            pipeline = raw.transform(task).to(output)
        """
        return Bucket(
            provider=self,
            bucket=bucket,
            path=path,
            config=config
        )
```

### 6. ExecutionResource.task() Decorator

**File:** `glacier/resources/base.py`

```python
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from glacier.core.task import Task

class ExecutionResource:
    """Base class for execution resources."""

    def task(
        self,
        func: Callable | None = None,
        *,
        name: str | None = None,
        timeout: int | None = None,
        retries: int = 0,
        cache: bool = False,
        **config
    ) -> "Task | Callable":
        """
        Decorator to create a Task bound to this execution resource.

        Usage:
            @local_exec.task()
            def my_task(df: pl.LazyFrame) -> pl.LazyFrame:
                return df.filter(...)
        """
        from glacier.core.task import Task

        def decorator(f: Callable) -> Task:
            return Task(
                func=f,
                executor=self,
                name=name or f.__name__,
                timeout=timeout,
                retries=retries,
                cache=cache,
                config=config
            )

        if func is None:
            return decorator
        else:
            return decorator(func)
```

### 7. Export from glacier/__init__.py

```python
from glacier.providers import Provider
from glacier.core.pipeline import Pipeline  # Optional, for compatibility
from glacier.resources.bucket import Bucket

__all__ = ["Provider", "Pipeline", "Bucket"]
```

---

## Summary

### Core Pattern: Single-Source

```python
# 1. Define storage (all equal - no special "source")
raw = provider.bucket(bucket="data", path="raw.parquet")
intermediate = provider.bucket(bucket="data", path="intermediate.parquet")
output = provider.bucket(bucket="data", path="output.parquet")

# 2. Define tasks
@local_exec.task()
def extract(df): ...

@lambda_exec.task()
def transform(df): ...

# 3. Chain buckets directly
pipeline = (
    raw                         # Bucket
    .transform(extract)         # PendingTransform
    .to(intermediate)           # Bucket (with lineage)
    .transform(transform)       # PendingTransform
    .to(output)                 # Bucket (with lineage)
)

# 4. Execute
result = pipeline.run(mode="local")
```

### Core Pattern: Multi-Source

```python
from glacier import Pipeline

# 1. Define storage
sales = provider.bucket(bucket="data", path="sales.parquet")
customers = provider.bucket(bucket="data", path="customers.parquet")
joined = provider.bucket(bucket="data", path="joined.parquet")
output = provider.bucket(bucket="data", path="output.parquet")

# 2. Define multi-source task
@spark_exec.task()
def join_data(sales_df: pl.LazyFrame, customers_df: pl.LazyFrame) -> pl.LazyFrame:
    return sales_df.join(customers_df, on="customer_id")

@local_exec.task()
def aggregate(df: pl.LazyFrame) -> pl.LazyFrame:
    return df.group_by("region").agg(pl.col("revenue").sum())

# 3. Use Pipeline for multi-source, then chain normally
pipeline = (
    Pipeline(sales_df=sales, customers_df=customers)  # Multi-source
    .transform(join_data)                              # Join
    .to(joined)                                        # Returns Bucket!
    .transform(aggregate)                              # Single-source chaining
    .to(output)
)

# 4. Execute
result = pipeline.run(mode="cloud")
```

### Key Innovation

**Bucket with lineage IS the pipeline definition**:
- Clean, readable chaining API for building pipelines
- The final Bucket contains complete pipeline definition in its lineage
- Can be captured for code generation (Terraform, CloudFormation, etc.)
- Single-source uses chainable buckets, multi-source uses Pipeline (returns Bucket)

### Benefits

✅ **Clean and readable** - Fluent chaining API for pipeline composition
✅ **Capturable** - Bucket with lineage IS the pipeline definition for code generation
✅ **Simpler** - Use chainable buckets for single-source (most common case)
✅ **More consistent** - All buckets treated equally, no special "source"
✅ **More intuitive** - Data flow is clear: bucket → transform → bucket
✅ **Flexible** - Pipeline for multi-source, returns Bucket for continued chaining
✅ **Explicit storage** - Every `.to()` is a materialization point
✅ **Lineage tracking** - Buckets know how they're produced
✅ **Matches physical reality** - Storage is how executors communicate

### Key Classes

- **Bucket** - Storage resource (chainable via `.transform()`)
- **PendingTransform** - Single-source transform awaiting target (via `.to()`)
- **Pipeline** - Multi-source builder (`Pipeline(s1=b1, s2=b2)`)
- **PipelinePendingTransform** - Multi-source transform awaiting target
- **TransformStep** - Single-source lineage element (source → task → target)
- **MultiSourceTransformStep** - Multi-source lineage element (sources → task → target)
- **Task** - Reusable task definition (from decorator)
- **TaskInstance** - Executable step in DAG (supports both single and multi-source)
- **DAG** - Dependencies based on source/target relationships

---

**END OF DOCUMENT**
