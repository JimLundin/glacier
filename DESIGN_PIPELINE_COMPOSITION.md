# Pipeline Composition Design: Source → Transform → Target Pattern

**Status:** Design Document - Final
**Date:** 2025-11-06
**Related:** DESIGN_UX.md

---

## Executive Summary

This document defines the **source → transform → target** pattern for composing pipelines in Glacier. The key principle: **pipelines start with a source, chain transforms, and end with a target**.

**Core Design:**
- **Pipelines start with a source** - `.source(bucket)` defines where data comes from
- **Tasks defined with decorators** - `@executor.task()` on execution resources
- **Transforms chained together** - `.transform(task)` chains processing steps
- **Pipelines end with a target** - `.target(bucket)` defines where data goes
- **Simple and declarative** - clear data flow from source through transforms to target

---

## Table of Contents

1. [Design Principles](#design-principles)
2. [Core Pattern](#core-pattern)
3. [Pipeline Builder API](#pipeline-builder-api)
4. [Sources and Targets](#sources-and-targets)
5. [Composition Patterns](#composition-patterns)
6. [Implementation Specification](#implementation-specification)

---

## Design Principles

### 1. Clear Data Flow

Pipelines have a clear structure: **Source → Transforms → Target**

```python
pipeline = (
    Pipeline(name="etl")
    .source(raw_data)           # Where data comes from
    .transform(extract)         # Processing steps
    .transform(transform)
    .target(output)             # Where data goes
)
```

### 2. Tasks Defined with Decorators

Tasks are created using decorators on execution resources:

```python
@local_exec.task()
def extract(df: pl.LazyFrame) -> pl.LazyFrame:
    return df.filter(...)

@lambda_exec.task()
def transform(df: pl.LazyFrame) -> pl.LazyFrame:
    return df.with_columns(...)
```

### 3. Explicit Sources and Targets

Sources and targets are first-class concepts:
- **Source**: Storage resource where input data lives
- **Target**: Storage resource where output data goes

```python
# Sources and targets are storage resources
raw_data = provider.bucket(bucket="data", path="input.parquet")
output = provider.bucket(bucket="data", path="output.parquet")

pipeline.source(raw_data).transform(process).target(output)
```

### 4. Fluent Builder Interface

Use method chaining to build pipelines:

```python
pipeline = (
    Pipeline(name="etl")
    .source(raw_data)
    .transform(extract)
    .transform(clean)
    .transform(aggregate)
    .target(output)
)
```

---

## Core Pattern

### Complete Example

```python
from glacier import Provider, Pipeline
from glacier.config import AwsConfig, LambdaConfig
import polars as pl

# 1. Create provider and resources
provider = Provider(config=AwsConfig(region="us-east-1"))
local_exec = provider.local()
lambda_exec = provider.serverless(config=LambdaConfig(memory=1024))

# 2. Define sources and targets
raw_data = provider.bucket(bucket="data-lake", path="raw/data.parquet")
output = provider.bucket(bucket="data-lake", path="output/result.parquet")

# 3. Define tasks with decorators
@local_exec.task()
def extract(df: pl.LazyFrame) -> pl.LazyFrame:
    """Extract and initial filtering."""
    return df.filter(pl.col("value").is_not_null())

@lambda_exec.task()
def transform(df: pl.LazyFrame) -> pl.LazyFrame:
    """Transform data."""
    return df.with_columns([
        (pl.col("value") * 2).alias("doubled"),
        pl.col("date").cast(pl.Date).alias("date")
    ])

@local_exec.task()
def aggregate(df: pl.LazyFrame) -> pl.LazyFrame:
    """Aggregate by category."""
    return df.group_by("category").agg([
        pl.col("value").sum().alias("total"),
        pl.count().alias("count")
    ])

# 4. Build pipeline: source → transforms → target
etl_pipeline = (
    Pipeline(name="etl")
    .source(raw_data)
    .transform(extract)
    .transform(transform)
    .transform(aggregate)
    .target(output)
)

# 5. Execute
result = etl_pipeline.run(mode="local")
```

### Key Points

1. **Pipeline starts with .source()** - defines input data
2. **Chain .transform()** calls - each transform takes output of previous
3. **Pipeline ends with .target()** - defines output destination
4. **Tasks are Task objects** - created by `@executor.task()` decorator
5. **Clear data flow** - source → transform₁ → transform₂ → ... → target

---

## Pipeline Builder API

### Pipeline Class

```python
class Pipeline:
    """
    Builder for composing Glacier pipelines.

    Pipelines follow the pattern: source → transforms → target
    """

    def __init__(self, name: str, description: str | None = None):
        """
        Create a new pipeline.

        Args:
            name: Pipeline name
            description: Optional description
        """
        self.name = name
        self.description = description
        self._source: StorageResource | None = None
        self._transforms: list[Task] = []
        self._target: StorageResource | None = None

    def source(self, resource: StorageResource) -> "Pipeline":
        """
        Set the source for this pipeline.

        Args:
            resource: Storage resource (bucket) to read from

        Returns:
            Self (for method chaining)

        Example:
            pipeline.source(raw_data_bucket)
        """
        self._source = resource
        return self

    def transform(self, task: Task) -> "Pipeline":
        """
        Add a transformation task to the pipeline.

        Transforms are chained - each receives the output of the previous.

        Args:
            task: Task to execute (created with @executor.task())

        Returns:
            Self (for method chaining)

        Example:
            pipeline.transform(extract).transform(clean).transform(aggregate)
        """
        self._transforms.append(task)
        return self

    def target(self, resource: StorageResource) -> "Pipeline":
        """
        Set the target for this pipeline.

        Args:
            resource: Storage resource (bucket) to write to

        Returns:
            Self (for method chaining)

        Example:
            pipeline.target(output_bucket)
        """
        self._target = resource
        return self

    def build(self) -> DAG:
        """
        Build the DAG from source, transforms, and target.

        Returns:
            DAG object representing the pipeline

        Raises:
            ValueError: If source or target not set
        """
        if self._source is None:
            raise ValueError("Pipeline must have a source")
        if self._target is None:
            raise ValueError("Pipeline must have a target")

        # Build DAG from the chain
        instances = []
        prev_output = self._source

        for task in self._transforms:
            instance = TaskInstance(
                task=task,
                inputs={"df": prev_output},  # Output of previous becomes input
                name=task.name
            )
            instances.append(instance)
            prev_output = instance

        # Final step: write to target
        # We need a built-in "write" task or handle this specially
        write_instance = TaskInstance(
            task=_create_write_task(),
            inputs={"df": prev_output, "target": self._target},
            name="write_to_target"
        )
        instances.append(write_instance)

        return DAG(instances)

    def run(self, mode: str = "local", **kwargs) -> Any:
        """
        Execute the pipeline.

        Args:
            mode: Execution mode (local, cloud, analyze, generate)
            **kwargs: Mode-specific arguments

        Returns:
            Execution result
        """
        dag = self.build()

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
```

### Alternative: Constructor-based

Could also set source and target in constructor:

```python
pipeline = Pipeline(
    name="etl",
    source=raw_data,
    target=output
)

pipeline.transform(extract).transform(transform)
```

Or:

```python
pipeline = (
    Pipeline(name="etl", source=raw_data, target=output)
    .transform(extract)
    .transform(transform)
)
```

---

## Sources and Targets

### Sources

**Sources** are storage resources where input data comes from:

```python
# S3 bucket
raw_data = provider.bucket(
    bucket="data-lake",
    path="raw/transactions.parquet"
)

# Use as source
pipeline.source(raw_data)
```

Sources can be:
- S3 buckets (parquet files)
- Azure Blob Storage
- GCS buckets
- Local files (for development)
- Database tables (future)

### Targets

**Targets** are storage resources where output data is written:

```python
# S3 bucket
output = provider.bucket(
    bucket="data-lake",
    path="processed/aggregated.parquet"
)

# Use as target
pipeline.target(output)
```

Targets can be:
- S3 buckets
- Azure Blob Storage
- GCS buckets
- Local files
- Database tables (future)

### Reading from Source

The first transform in the pipeline automatically receives data from the source:

```python
@local_exec.task()
def extract(df: pl.LazyFrame) -> pl.LazyFrame:
    """
    First transform receives data from source.

    df is a LazyFrame scanning the source.
    """
    return df.filter(pl.col("value") > 0)

pipeline = (
    Pipeline(name="etl")
    .source(raw_data)       # Source provides df
    .transform(extract)      # extract receives df from source
    .transform(clean)        # clean receives df from extract
    .target(output)
)
```

### Writing to Target

The last transform's output is automatically written to the target:

```python
@local_exec.task()
def aggregate(df: pl.LazyFrame) -> pl.LazyFrame:
    """
    Last transform returns final result.

    Result is automatically written to target.
    """
    return df.group_by("category").agg(pl.col("value").sum())

pipeline = (
    Pipeline(name="etl")
    .source(raw_data)
    .transform(extract)
    .transform(aggregate)    # Output written to target
    .target(output)
)
```

---

## Composition Patterns

### 1. Sequential Pipeline

```python
# Define tasks
@local_exec.task()
def extract(df): ...

@lambda_exec.task()
def clean(df): ...

@local_exec.task()
def aggregate(df): ...

# Build pipeline
pipeline = (
    Pipeline(name="sequential")
    .source(raw_data)
    .transform(extract)
    .transform(clean)
    .transform(aggregate)
    .target(output)
)
```

### 2. Multi-Source Pipeline (Join)

For pipelines with multiple sources, use a special join pattern:

```python
# Define sources
sales = provider.bucket(bucket="data", path="sales.parquet")
customers = provider.bucket(bucket="data", path="customers.parquet")
products = provider.bucket(bucket="data", path="products.parquet")

# Define join task
@spark_exec.task()
def join_all(sales_df, customers_df, products_df):
    return (
        sales_df
        .join(customers_df, on="customer_id")
        .join(products_df, on="product_id")
    )

# Build pipeline with multiple sources
pipeline = (
    Pipeline(name="join")
    .sources({
        "sales_df": sales,
        "customers_df": customers,
        "products_df": products
    })
    .transform(join_all)
    .transform(aggregate)
    .target(output)
)
```

Or use a simpler pattern with explicit inputs:

```python
pipeline = Pipeline(name="join")

# Load each source separately
load_sales = pipeline.load_source(sales, name="load_sales")
load_customers = pipeline.load_source(customers, name="load_customers")
load_products = pipeline.load_source(products, name="load_products")

# Join them
pipeline.transform(join_all, inputs={
    "sales_df": load_sales,
    "customers_df": load_customers,
    "products_df": load_products
})

pipeline.transform(aggregate).target(output)
```

### 3. Multi-Target Pipeline (Split)

For pipelines that write to multiple targets:

```python
# Define targets
summary_output = provider.bucket(bucket="data", path="summary.parquet")
detail_output = provider.bucket(bucket="data", path="detail.parquet")

# Define split task
@local_exec.task()
def split_data(df):
    summary = df.group_by("category").agg(pl.col("value").sum())
    detail = df  # Keep detail
    return summary, detail

# Build pipeline with multiple targets
pipeline = (
    Pipeline(name="split")
    .source(raw_data)
    .transform(extract)
    .transform(split_data)
    .targets({
        0: summary_output,  # First output to summary
        1: detail_output    # Second output to detail
    })
)
```

Or simpler with explicit writes:

```python
pipeline = (
    Pipeline(name="split")
    .source(raw_data)
    .transform(extract)
    .transform(create_summary)
    .target(summary_output)
    .branch()  # Start a new branch
    .transform(create_detail)
    .target(detail_output)
)
```

### 4. Simple Pattern: Single Source, Single Target

Most common case - keep it simple:

```python
pipeline = (
    Pipeline(name="etl")
    .source(raw_data)
    .transform(extract)
    .transform(clean)
    .transform(aggregate)
    .target(output)
)
```

### 5. Conditional Transforms

Use Python conditionals to add different transforms:

```python
def build_pipeline(mode: str):
    pipeline = Pipeline(name=f"etl_{mode}").source(raw_data)

    pipeline.transform(extract)

    if mode == "full":
        pipeline.transform(full_transform)
    else:
        pipeline.transform(quick_transform)

    pipeline.transform(aggregate).target(output)

    return pipeline
```

### 6. Dynamic Transforms

Add transforms in a loop:

```python
def build_pipeline(transform_steps: list[Task]):
    pipeline = Pipeline(name="dynamic").source(raw_data)

    for step in transform_steps:
        pipeline.transform(step)

    pipeline.target(output)
    return pipeline
```

---

## Implementation Specification

### 1. Pipeline Class

**File:** `glacier/core/pipeline.py`

```python
from typing import Any
from glacier.core.task import Task, TaskInstance
from glacier.core.dag import DAG
from glacier.resources.bucket import Bucket

class Pipeline:
    """
    Builder for composing Glacier pipelines.

    Pipelines follow: source → transforms → target
    """

    def __init__(self, name: str, description: str | None = None, **config):
        """
        Create a new pipeline.

        Args:
            name: Pipeline name
            description: Optional description
            **config: Additional configuration
        """
        self.name = name
        self.description = description
        self.config = config
        self._source: Bucket | None = None
        self._transforms: list[Task] = []
        self._target: Bucket | None = None
        self._dag: DAG | None = None

    def source(self, resource: Bucket) -> "Pipeline":
        """
        Set the source for this pipeline.

        Args:
            resource: Storage resource (bucket) to read from

        Returns:
            Self (for method chaining)
        """
        if self._source is not None:
            raise ValueError("Pipeline already has a source")
        self._source = resource
        return self

    def transform(self, task: Task) -> "Pipeline":
        """
        Add a transformation task to the pipeline.

        Args:
            task: Task to execute (created with @executor.task())

        Returns:
            Self (for method chaining)
        """
        self._transforms.append(task)
        self._dag = None  # Invalidate cached DAG
        return self

    def target(self, resource: Bucket) -> "Pipeline":
        """
        Set the target for this pipeline.

        Args:
            resource: Storage resource (bucket) to write to

        Returns:
            Self (for method chaining)
        """
        if self._target is not None:
            raise ValueError("Pipeline already has a target")
        self._target = resource
        return self

    def build(self) -> DAG:
        """
        Build the DAG from source, transforms, and target.

        Returns:
            DAG object

        Raises:
            ValueError: If source or target not set
        """
        if self._dag is not None:
            return self._dag

        if self._source is None:
            raise ValueError("Pipeline must have a source. Use .source(bucket)")
        if self._target is None:
            raise ValueError("Pipeline must have a target. Use .target(bucket)")
        if not self._transforms:
            raise ValueError("Pipeline must have at least one transform")

        # Build chain of TaskInstances
        instances = []

        # First task reads from source
        first_task = self._transforms[0]
        first_instance = TaskInstance(
            task=first_task,
            inputs={"df": self._source},  # Source provides LazyFrame
            name=first_task.name
        )
        instances.append(first_instance)
        prev_instance = first_instance

        # Chain subsequent transforms
        for task in self._transforms[1:]:
            instance = TaskInstance(
                task=task,
                inputs={"df": prev_instance},  # Previous output
                name=task.name
            )
            instances.append(instance)
            prev_instance = instance

        # Last task writes to target (handled by executor)
        # Store target on the last instance for executor to use
        prev_instance.target = self._target

        self._dag = DAG(instances)
        return self._dag

    def run(self, mode: str = "local", **kwargs) -> Any:
        """Execute the pipeline."""
        dag = self.build()

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

    def visualize(self) -> str:
        """Generate Mermaid visualization."""
        dag = self.build()
        return dag.to_mermaid()

    def __repr__(self) -> str:
        return f"Pipeline(name='{self.name}', transforms={len(self._transforms)})"
```

### 2. Task and TaskInstance

**File:** `glacier/core/task.py`

```python
import inspect
from typing import Callable, Any

class Task:
    """
    A reusable task definition.

    Created by @executor.task() decorator.
    """

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
    An instance of a Task in a pipeline with specific inputs.
    """

    def __init__(
        self,
        task: Task,
        inputs: dict[str, Any],
        name: str
    ):
        self.task = task
        self.inputs = inputs
        self.name = name
        self.target = None  # Set by pipeline if this is the last task
        self.dependencies = self._extract_dependencies()

    def _extract_dependencies(self) -> list["TaskInstance"]:
        """Extract TaskInstance dependencies from inputs."""
        deps = []
        for value in self.inputs.values():
            if isinstance(value, TaskInstance):
                deps.append(value)
        return deps

    def execute(self, context: "ExecutionContext") -> Any:
        """Execute this task instance."""
        resolved_inputs = {}

        for param_name, value in self.inputs.items():
            if isinstance(value, TaskInstance):
                # Get output from previous task
                resolved_inputs[param_name] = context.get_output(value)
            elif hasattr(value, 'scan'):
                # It's a storage resource (Bucket) - scan it
                resolved_inputs[param_name] = value.scan()
            else:
                resolved_inputs[param_name] = value

        # Execute task
        result = self.task.func(**resolved_inputs)

        # If this task has a target, write result to it
        if self.target is not None:
            result.collect().write_parquet(self.target.get_uri())

        return result

    def __repr__(self) -> str:
        return f"TaskInstance(name='{self.name}', task={self.task.name})"
```

### 3. ExecutionResource.task() Decorator

**File:** `glacier/resources/base.py`

```python
from typing import Callable
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
    ) -> Task | Callable:
        """
        Decorator to create a Task bound to this execution resource.

        Usage:
            @local_exec.task()
            def my_task(df: pl.LazyFrame) -> pl.LazyFrame:
                return df.filter(...)
        """
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

### 4. Storage Resource (Bucket)

**File:** `glacier/resources/bucket.py`

```python
import polars as pl

class Bucket:
    """
    Storage resource (bucket) for reading/writing data.
    """

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
        """
        Scan the data source as a LazyFrame.

        Returns:
            LazyFrame for lazy reading
        """
        uri = self.get_uri()
        return pl.scan_parquet(uri)

    def get_uri(self) -> str:
        """Get the full URI for this bucket."""
        # Implementation depends on provider (S3, GCS, Azure, local)
        return f"s3://{self.bucket}/{self.path}"

    def __repr__(self) -> str:
        return f"Bucket(bucket='{self.bucket}', path='{self.path}')"
```

### 5. DAG Class

**File:** `glacier/core/dag.py`

```python
from glacier.core.task import TaskInstance

class DAG:
    """Directed Acyclic Graph of task instances."""

    def __init__(self, instances: list[TaskInstance]):
        self.instances = instances
        self._validate()

    def _validate(self):
        """Validate that graph is acyclic."""
        visited = set()
        rec_stack = set()

        def has_cycle(instance: TaskInstance) -> bool:
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

    def topological_sort(self) -> list[TaskInstance]:
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

    def get_stages(self) -> list[list[TaskInstance]]:
        """Group instances into parallel execution stages."""
        stages = []
        remaining = set(self.instances)

        while remaining:
            stage = []
            for inst in list(remaining):
                if all(dep not in remaining for dep in inst.dependencies):
                    stage.append(inst)

            stages.append(stage)
            remaining -= set(stage)

        return stages

    def to_mermaid(self) -> str:
        """Generate Mermaid diagram."""
        lines = ["graph TD"]
        for inst in self.instances:
            node_id = inst.name.replace(" ", "_")
            executor_type = getattr(inst.task.executor, 'type', 'unknown')
            lines.append(f"    {node_id}[\"{inst.name}<br/>({executor_type})\"]")
            for dep in inst.dependencies:
                dep_id = dep.name.replace(" ", "_")
                lines.append(f"    {dep_id} --> {node_id}")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"DAG(instances={len(self.instances)})"
```

### 6. Export from glacier/__init__.py

```python
from glacier.providers import Provider
from glacier.core.pipeline import Pipeline

__all__ = ["Provider", "Pipeline"]
```

---

## Summary

### Core Pattern

```python
# 1. Define resources
raw_data = provider.bucket(bucket="data", path="input.parquet")
output = provider.bucket(bucket="data", path="output.parquet")

# 2. Define tasks with decorators
@local_exec.task()
def extract(df): ...

@lambda_exec.task()
def transform(df): ...

# 3. Build pipeline: source → transforms → target
pipeline = (
    Pipeline(name="etl")
    .source(raw_data)
    .transform(extract)
    .transform(transform)
    .target(output)
)

# 4. Execute
result = pipeline.run(mode="local")
```

### Benefits

✅ **Clear data flow** - Source → Transforms → Target
✅ **Simple builder pattern** - `.source().transform().target()`
✅ **First-class sources and targets** - Storage resources
✅ **Tasks defined with decorators** - On execution resources
✅ **Fluent interface** - Natural method chaining
✅ **No magic** - Explicit and declarative

### Key Classes

- **Pipeline** - Builder with `.source()`, `.transform()`, `.target()`
- **Task** - Reusable task definition (from decorator)
- **TaskInstance** - Task with inputs in pipeline
- **Bucket** - Storage resource (source/target)
- **DAG** - Directed acyclic graph

---

**END OF DOCUMENT**
