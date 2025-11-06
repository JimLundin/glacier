# Pipeline Composition Design: Storage-First Pattern

**Status:** Design Document - Final
**Date:** 2025-11-06
**Related:** DESIGN_UX.md

---

## Executive Summary

This document defines a **storage-first** pattern for composing pipelines in Glacier. The key principle: **storage is the fundamental unit - every transform reads from storage and writes to storage**.

**Core Design:**
- **Storage is explicit** - Every data materialization point is visible
- **Transforms go storage → storage** - Read from bucket, write to bucket
- **No hidden serialization** - All storage writes are explicit in pipeline definition
- **Simple pattern** - `.source(bucket).transform(task).to(bucket)`

---

## Table of Contents

1. [Design Principles](#design-principles)
2. [Core Pattern](#core-pattern)
3. [Pipeline Builder API](#pipeline-builder-api)
4. [Why Storage-First](#why-storage-first)
5. [Composition Patterns](#composition-patterns)
6. [Implementation Specification](#implementation-specification)

---

## Design Principles

### 1. Storage is Explicit

Every data materialization point is visible in the pipeline:

```python
pipeline = (
    Pipeline(name="etl")
    .source(raw_data)          # Read from storage
    .transform(extract)         # Transform in memory
    .to(intermediate1)          # Write to storage (EXPLICIT)
    .transform(transform)       # Read from intermediate1, transform
    .to(output)                 # Write to storage (EXPLICIT)
)
```

### 2. Transforms Read/Write Storage

Every transform:
- **Reads** from a storage resource (bucket)
- **Writes** to a storage resource (bucket)

```python
# This is the reality:
# raw_data → extract → intermediate1 → transform → output
#   (S3)      (local)      (S3)         (lambda)    (S3)
```

### 3. No Hidden Magic

User explicitly declares:
- Where data is read from
- Where data is written to
- When serialization happens (at every `.to()`)

### 4. Execution Boundaries Are Storage Boundaries

Different executors can't directly share data - they share via storage:

```python
.source(raw_data)      # S3
.transform(extract)    # Local executor reads from S3
.to(intermediate)      # Local writes back to S3
.transform(process)    # Lambda reads from S3
.to(output)            # Lambda writes to S3
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

# 2. Define storage resources
raw_data = provider.bucket(bucket="data-lake", path="raw/data.parquet")
intermediate1 = provider.bucket(bucket="data-lake", path="intermediate/step1.parquet")
intermediate2 = provider.bucket(bucket="data-lake", path="intermediate/step2.parquet")
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

@local_exec.task()
def aggregate(df: pl.LazyFrame) -> pl.LazyFrame:
    """Aggregate by category."""
    return df.group_by("category").agg(pl.col("value").sum())

# 4. Build pipeline: storage → transform → storage → transform → storage
pipeline = (
    Pipeline(name="etl")
    .source(raw_data)          # Read from S3
    .transform(extract)         # Process locally
    .to(intermediate1)          # Write to S3 (EXPLICIT)
    .transform(transform)       # Lambda reads from S3
    .to(intermediate2)          # Write to S3 (EXPLICIT)
    .transform(aggregate)       # Process locally, reads from S3
    .to(output)                 # Write to S3 (EXPLICIT)
)

# 5. Execute
result = pipeline.run(mode="local")
```

### Key Points

1. **`.source(bucket)`** - Start by reading from storage
2. **`.transform(task)`** - Apply transformation (reads from last storage)
3. **`.to(bucket)`** - Write result to storage (materializes data, explicit serialization)
4. **Chaining** - Next `.transform()` automatically reads from the previous `.to()` bucket
5. **No hidden writes** - All storage writes are explicit via `.to()`

---

## Pipeline Builder API

### Pipeline Class

```python
class Pipeline:
    """
    Builder for composing Glacier pipelines.

    Pattern: source → transform → to → transform → to → ...
    """

    def __init__(self, name: str, description: str | None = None):
        """Create a new pipeline."""
        self.name = name
        self.description = description
        self._steps: list[PipelineStep] = []
        self._current_source: Bucket | None = None

    def source(self, bucket: Bucket) -> "Pipeline":
        """
        Start pipeline by reading from a storage resource.

        Args:
            bucket: Storage resource to read from

        Returns:
            Self (for chaining)

        Example:
            pipeline.source(raw_data)
        """
        if self._current_source is not None:
            raise ValueError("Pipeline already has a source for current step")
        self._current_source = bucket
        return self

    def transform(self, task: Task) -> "Pipeline":
        """
        Apply a transformation.

        The transform reads from the current source (set by .source() or previous .to())

        Args:
            task: Task to execute (created with @executor.task())

        Returns:
            Self (for chaining)

        Example:
            pipeline.transform(extract_task)
        """
        if self._current_source is None:
            raise ValueError("Must call .source() before .transform()")

        self._steps.append(TransformStep(
            source=self._current_source,
            task=task
        ))
        # After transform, we need .to() to set next source
        self._current_source = None
        return self

    def to(self, bucket: Bucket) -> "Pipeline":
        """
        Write transform output to storage.

        This materializes the data and makes it available for the next transform.

        Args:
            bucket: Storage resource to write to

        Returns:
            Self (for chaining)

        Example:
            pipeline.to(intermediate_bucket)
        """
        if not self._steps:
            raise ValueError("Must call .transform() before .to()")

        last_step = self._steps[-1]
        if last_step.target is not None:
            raise ValueError("Transform already has a target")

        # Set target on last step
        last_step.target = bucket

        # This becomes the source for the next transform
        self._current_source = bucket

        return self

    def build(self) -> DAG:
        """Build the DAG from pipeline steps."""
        if not self._steps:
            raise ValueError("Pipeline has no steps")

        # Validate all steps have targets
        for step in self._steps:
            if step.target is None:
                raise ValueError(
                    f"Transform '{step.task.name}' has no target. "
                    "Use .to(bucket) after each .transform()"
                )

        # Build TaskInstances
        instances = []
        for step in self._steps:
            instance = TaskInstance(
                task=step.task,
                source=step.source,
                target=step.target,
                name=step.task.name
            )
            instances.append(instance)

        return DAG(instances)

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
        else:
            raise ValueError(f"Unknown mode: {mode}")
```

### PipelineStep

```python
@dataclass
class TransformStep:
    """A step in the pipeline: source → transform → target."""
    source: Bucket
    task: Task
    target: Bucket | None = None
```

---

## Why Storage-First?

### The Physical Reality

Different execution environments cannot directly share in-memory data:

```
┌─────────┐         ┌─────────┐         ┌─────────────┐
│  Local  │  ────>  │ Lambda  │  ────>  │ Databricks  │
└─────────┘         └─────────┘         └─────────────┘
     ❌ Cannot directly pass LazyFrame ❌
```

They must communicate via shared storage:

```
┌─────────┐         ┌─────────┐         ┌─────────────┐
│  Local  │         │ Lambda  │         │ Databricks  │
└────┬────┘         └────┬────┘         └──────┬──────┘
     │                   │                      │
     ↓ write       read ↓ write           read ↓
┌────────────────────────────────────────────────────┐
│                      S3 Buckets                    │
│  raw.parquet  intermediate1.parquet  output.parquet│
└────────────────────────────────────────────────────┘
```

### Why Make It Explicit?

**Option A: Hidden (Bad)**
```python
pipeline = (
    Pipeline(name="etl")
    .source(raw_data)
    .transform(extract)    # local
    .transform(process)    # lambda - WHERE is intermediate storage???
    .target(output)
)
```
- User doesn't see intermediate storage
- Surprise storage costs
- Hard to debug
- No control over data location

**Option B: Explicit (Good)**
```python
pipeline = (
    Pipeline(name="etl")
    .source(raw_data)
    .transform(extract)        # local
    .to(intermediate)          # EXPLICIT: data written here
    .transform(process)        # lambda reads from intermediate
    .to(output)                # EXPLICIT: final output here
)
```
- Clear where data is stored
- No surprises
- Easy to debug (check intermediate data)
- Full control over storage locations
- Matches physical reality

---

## Composition Patterns

### 1. Sequential Pipeline

```python
# Define storage
raw_data = provider.bucket(bucket="data", path="raw.parquet")
intermediate1 = provider.bucket(bucket="data", path="intermediate1.parquet")
intermediate2 = provider.bucket(bucket="data", path="intermediate2.parquet")
output = provider.bucket(bucket="data", path="output.parquet")

# Define tasks
@local_exec.task()
def extract(df): ...

@lambda_exec.task()
def transform(df): ...

@local_exec.task()
def aggregate(df): ...

# Build pipeline
pipeline = (
    Pipeline(name="sequential")
    .source(raw_data)
    .transform(extract)
    .to(intermediate1)
    .transform(transform)
    .to(intermediate2)
    .transform(aggregate)
    .to(output)
)
```

### 2. Same Executor (Multiple Transforms)

When transforms run on the same executor, you might still want intermediate storage for checkpointing:

```python
@local_exec.task()
def step1(df): ...

@local_exec.task()
def step2(df): ...

@local_exec.task()
def step3(df): ...

pipeline = (
    Pipeline(name="local_pipeline")
    .source(raw_data)
    .transform(step1)
    .to(checkpoint1)    # Optional checkpoint
    .transform(step2)
    .to(checkpoint2)    # Optional checkpoint
    .transform(step3)
    .to(output)
)
```

Or skip intermediate storage if all on same executor and you don't want checkpoints:

```python
# For this, we'd need a different pattern... maybe .chain()?
```

Actually, with this pattern, **you always write to storage**. If you want to skip intermediate storage, you'd need to use a different executor pattern (future optimization).

### 3. Multiple Sources (Join)

For joins, you need multiple source → transform flows:

```python
# Define sources
sales = provider.bucket(bucket="data", path="sales.parquet")
customers = provider.bucket(bucket="data", path="customers.parquet")
joined_output = provider.bucket(bucket="data", path="joined.parquet")

# Define tasks
@local_exec.task()
def load_sales(df): ...

@local_exec.task()
def load_customers(df): ...

@spark_exec.task()
def join_data(sales_df, customers_df): ...

# Build pipeline - needs different pattern for multiple sources
# Option A: Multiple pipelines
sales_pipeline = (
    Pipeline(name="load_sales")
    .source(sales)
    .transform(load_sales)
    .to(sales_prepared)
)

customers_pipeline = (
    Pipeline(name="load_customers")
    .source(customers)
    .transform(load_customers)
    .to(customers_prepared)
)

join_pipeline = (
    Pipeline(name="join")
    .sources({"sales_df": sales_prepared, "customers_df": customers_prepared})
    .transform(join_data)
    .to(joined_output)
)

# Option B: Single pipeline with branches (more complex API)
```

For multi-source, the API would need extension. Keep it simple for now: **one source per pipeline**.

### 4. Conditional Pipelines

```python
def build_pipeline(mode: str):
    pipeline = Pipeline(name=f"etl_{mode}")
    pipeline.source(raw_data).transform(extract)

    if mode == "full":
        pipeline.to(intermediate).transform(full_process).to(output)
    else:
        pipeline.to(output)  # Skip processing

    return pipeline
```

### 5. Dynamic Pipelines

```python
def build_pipeline(steps: list[Task], checkpoints: list[Bucket]):
    pipeline = Pipeline(name="dynamic").source(raw_data)

    for task, checkpoint in zip(steps, checkpoints):
        pipeline.transform(task).to(checkpoint)

    return pipeline
```

---

## Implementation Specification

### 1. Pipeline Class

**File:** `glacier/core/pipeline.py`

```python
from typing import Any
from dataclasses import dataclass
from glacier.core.task import Task, TaskInstance
from glacier.core.dag import DAG
from glacier.resources.bucket import Bucket

@dataclass
class TransformStep:
    """A step in the pipeline: source → transform → target."""
    source: Bucket
    task: Task
    target: Bucket | None = None

class Pipeline:
    """
    Builder for composing Glacier pipelines.

    Pattern: source → transform → to → transform → to → ...
    """

    def __init__(self, name: str, description: str | None = None, **config):
        self.name = name
        self.description = description
        self.config = config
        self._steps: list[TransformStep] = []
        self._current_source: Bucket | None = None
        self._dag: DAG | None = None

    def source(self, bucket: Bucket) -> "Pipeline":
        """Start pipeline by reading from storage."""
        if self._current_source is not None:
            raise ValueError("Pipeline already has a source for current step")
        self._current_source = bucket
        return self

    def transform(self, task: Task) -> "Pipeline":
        """Apply a transformation (reads from current source)."""
        if self._current_source is None:
            raise ValueError("Must call .source() before .transform()")

        step = TransformStep(
            source=self._current_source,
            task=task,
            target=None
        )
        self._steps.append(step)
        self._current_source = None  # Must call .to() next
        self._dag = None
        return self

    def to(self, bucket: Bucket) -> "Pipeline":
        """Write transform output to storage."""
        if not self._steps:
            raise ValueError("Must call .transform() before .to()")

        last_step = self._steps[-1]
        if last_step.target is not None:
            raise ValueError("Transform already has a target")

        last_step.target = bucket
        self._current_source = bucket  # Becomes source for next transform
        self._dag = None
        return self

    def build(self) -> DAG:
        """Build DAG from pipeline steps."""
        if self._dag is not None:
            return self._dag

        if not self._steps:
            raise ValueError("Pipeline has no steps")

        # Validate all steps have targets
        for i, step in enumerate(self._steps):
            if step.target is None:
                raise ValueError(
                    f"Step {i+1} (transform '{step.task.name}') has no target. "
                    "Use .to(bucket) after .transform()"
                )

        # Build TaskInstances
        instances = []
        for step in self._steps:
            instance = TaskInstance(
                task=step.task,
                source=step.source,
                target=step.target,
                name=step.task.name
            )
            instances.append(instance)

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
        return f"Pipeline(name='{self.name}', steps={len(self._steps)})"
```

### 2. TaskInstance

**File:** `glacier/core/task.py`

```python
import inspect
from typing import Callable, Any

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

    Represents: source → transform → target
    """

    def __init__(
        self,
        task: Task,
        source: "Bucket",
        target: "Bucket",
        name: str
    ):
        self.task = task
        self.source = source
        self.target = target
        self.name = name
        self.dependencies = []  # Set during DAG building

    def execute(self, context: "ExecutionContext") -> Any:
        """
        Execute this task instance.

        1. Read from source (scan as LazyFrame)
        2. Execute task function
        3. Write to target (materialize to parquet)
        """
        # Read from source
        df = self.source.scan()

        # Execute task
        result = self.task.func(df=df)

        # Write to target
        result.collect().write_parquet(self.target.get_uri())

        return result

    def __repr__(self) -> str:
        return f"TaskInstance(name='{self.name}', source={self.source}, target={self.target})"
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

### 4. Bucket (Storage Resource)

**File:** `glacier/resources/bucket.py`

```python
import polars as pl

class Bucket:
    """Storage resource for reading/writing data."""

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
        """Scan the data source as a LazyFrame."""
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
        self._build_dependencies()
        self._validate()

    def _build_dependencies(self):
        """Build dependencies based on source/target relationships."""
        # Task B depends on Task A if Task B's source == Task A's target
        for i, instance in enumerate(self.instances):
            instance.dependencies = []
            for prev_instance in self.instances[:i]:
                if prev_instance.target == instance.source:
                    instance.dependencies.append(prev_instance)

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

    def to_mermaid(self) -> str:
        """Generate Mermaid diagram."""
        lines = ["graph LR"]

        for inst in self.instances:
            # Show: source → task → target
            source_id = inst.source.path.replace("/", "_").replace(".", "_")
            task_id = inst.name.replace(" ", "_")
            target_id = inst.target.path.replace("/", "_").replace(".", "_")

            lines.append(f"    {source_id}[({inst.source.path})]")
            lines.append(f"    {task_id}[\"{inst.name}<br/>({inst.task.executor.type})\"]")
            lines.append(f"    {target_id}[({inst.target.path})]")
            lines.append(f"    {source_id} --> {task_id}")
            lines.append(f"    {task_id} --> {target_id}")

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
# 1. Define storage
raw_data = provider.bucket(bucket="data", path="raw.parquet")
intermediate = provider.bucket(bucket="data", path="intermediate.parquet")
output = provider.bucket(bucket="data", path="output.parquet")

# 2. Define tasks
@local_exec.task()
def extract(df): ...

@lambda_exec.task()
def transform(df): ...

# 3. Build pipeline: storage → transform → storage
pipeline = (
    Pipeline(name="etl")
    .source(raw_data)          # Read from storage
    .transform(extract)         # Process
    .to(intermediate)           # Write to storage (EXPLICIT)
    .transform(transform)       # Read from intermediate
    .to(output)                 # Write to storage (EXPLICIT)
)

# 4. Execute
result = pipeline.run(mode="local")
```

### Benefits

✅ **Storage is explicit** - All serialization points visible
✅ **Matches physical reality** - Executors communicate via storage
✅ **No hidden costs** - User sees all storage writes
✅ **Debuggable** - Can inspect intermediate data
✅ **Clear boundaries** - Every `.to()` is a materialization point
✅ **Simple pattern** - `.source().transform().to()`

### Key Classes

- **Pipeline** - Builder with `.source()`, `.transform()`, `.to()`
- **Task** - Reusable task definition (from decorator)
- **TaskInstance** - Represents source → transform → target
- **Bucket** - Storage resource (source/target)
- **DAG** - Dependencies based on source/target relationships

---

**END OF DOCUMENT**
