# Pipeline Composition Design: Builder Pattern

**Status:** Design Document - v3.0 (Builder Pattern)
**Date:** 2025-11-06
**Related:** DESIGN_UX.md

---

## Executive Summary

This document defines a **builder pattern** for composing pipelines in Glacier. The key principle: **pipelines are built using a PipelineBuilder that explicitly manages task creation and dependency tracking**.

**Core Design:**
- **PipelineBuilder** manages task creation and tracks the DAG
- **Tasks are objects** that wrap functions (taking and returning LazyFrames)
- **Dependencies are explicit** - passed as Task objects in the `inputs` dict
- **No static analysis needed** - the builder maintains the DAG structure

---

## Table of Contents

1. [Design Principles](#design-principles)
2. [Core Pattern](#core-pattern)
3. [PipelineBuilder API](#pipelinebuilder-api)
4. [Task Objects](#task-objects)
5. [Composition Patterns](#composition-patterns)
6. [Implementation Specification](#implementation-specification)

---

## Design Principles

### 1. Builder Pattern

The PipelineBuilder is the central object for constructing pipelines:

```python
@pipeline(name="etl")
def build_etl():
    builder = PipelineBuilder()

    # Builder creates and tracks tasks
    extract = builder.task(extract_fn, executor=local_exec, inputs={"source": raw_data})
    transform = builder.task(transform_fn, executor=lambda_exec, inputs={"df": extract})

    return builder
```

### 2. Tasks Are Objects

Tasks wrap functions and track their dependencies:

```python
# extract and transform are Task objects
assert isinstance(extract, Task)
assert isinstance(transform, Task)

# Dependencies are explicit
assert transform.dependencies == [extract]
```

### 3. Explicit Dependencies

Dependencies declared through the `inputs` dict:

```python
# transform depends on extract
transform = builder.task(
    transform_fn,
    executor=lambda_exec,
    inputs={"df": extract}  # ← extract is a Task object
)
```

### 4. No Magic

- Clear task creation via builder
- Explicit dependency wiring
- No AST parsing
- No hidden context tracking

---

## Core Pattern

### Complete Example

```python
from glacier import Provider, pipeline
from glacier.config import AwsConfig, LambdaConfig
import polars as pl

# 1. Create provider and resources
provider = Provider(config=AwsConfig(region="us-east-1"))
local_exec = provider.local()
lambda_exec = provider.serverless(config=LambdaConfig(memory=1024))
raw_data = provider.bucket(bucket="data", path="input.parquet")
output = provider.bucket(bucket="data", path="output.parquet")

# 2. Define task functions (pure: LazyFrame -> LazyFrame)
def extract_fn(source) -> pl.LazyFrame:
    """Extract data from source."""
    return source.scan()

def transform_fn(df: pl.LazyFrame) -> pl.LazyFrame:
    """Transform data."""
    return df.filter(pl.col("value") > 0)

def load_fn(df: pl.LazyFrame, destination) -> None:
    """Load data to destination."""
    df.collect().write_parquet(destination.get_uri())

# 3. Build pipeline using builder pattern
@pipeline(name="etl")
def build_etl():
    """
    Build the ETL pipeline using PipelineBuilder.

    The builder:
    - Creates Task objects
    - Tracks all tasks
    - Wires dependencies
    - Builds the final DAG
    """
    # Create builder
    builder = PipelineBuilder()

    # Add tasks - builder tracks them automatically
    extract = builder.task(
        extract_fn,
        executor=local_exec,
        inputs={"source": raw_data},
        name="extract"
    )

    transform = builder.task(
        transform_fn,
        executor=lambda_exec,
        inputs={"df": extract},  # Depends on extract task
        name="transform"
    )

    load = builder.task(
        load_fn,
        executor=local_exec,
        inputs={"df": transform, "destination": output},  # Depends on transform
        name="load"
    )

    # Return the builder (or could return final task)
    return builder

# 4. Execute the pipeline
etl_pipeline = build_etl()  # Returns PipelineBuilder or Pipeline
result = etl_pipeline.run(mode="local")
```

### Key Points

1. **PipelineBuilder** is the central orchestrator
2. **builder.task()** creates Task objects and tracks them
3. **Tasks reference each other** via `inputs` dict
4. **Builder maintains the DAG** - knows all tasks and their relationships
5. **No execution during build** - just DAG construction
6. **Run happens separately** - `.run(mode="local")` executes

---

## PipelineBuilder API

### Core Methods

```python
class PipelineBuilder:
    """
    Builder for constructing Glacier pipelines.

    Manages task creation and dependency tracking.
    """

    def __init__(self):
        """Initialize empty builder."""
        self._tasks: list[Task] = []

    def task(
        self,
        func: Callable,
        executor: ExecutionResource,
        inputs: dict[str, Any] | None = None,
        name: str | None = None,
        **config
    ) -> Task:
        """
        Create a task and add it to the pipeline.

        Args:
            func: Function to execute (LazyFrame -> LazyFrame)
            executor: Execution resource (where this runs)
            inputs: Dict mapping param names to values or Tasks
            name: Optional task name (defaults to func.__name__)
            **config: Additional config (timeout, retries, etc.)

        Returns:
            Task object that can be used as input to other tasks

        Example:
            extract = builder.task(extract_fn, executor=local_exec, inputs={"source": bucket})
            transform = builder.task(transform_fn, executor=lambda_exec, inputs={"df": extract})
        """
        task = Task(
            func=func,
            executor=executor,
            inputs=inputs or {},
            name=name,
            **config
        )
        self._tasks.append(task)
        return task

    def build(self) -> DAG:
        """
        Build the final DAG from all tasks.

        Returns:
            DAG object with all tasks and their dependencies
        """
        return DAG(self._tasks)

    def get_tasks(self) -> list[Task]:
        """Get all tasks in the pipeline."""
        return self._tasks.copy()
```

### Usage Patterns

**Option 1: Return builder**

```python
@pipeline(name="etl")
def build_etl():
    builder = PipelineBuilder()

    extract = builder.task(extract_fn, executor=local_exec, inputs={"source": raw_data})
    transform = builder.task(transform_fn, executor=lambda_exec, inputs={"df": extract})

    return builder  # Builder tracks all tasks
```

**Option 2: Return final task**

```python
@pipeline(name="etl")
def build_etl():
    builder = PipelineBuilder()

    extract = builder.task(extract_fn, executor=local_exec, inputs={"source": raw_data})
    transform = builder.task(transform_fn, executor=lambda_exec, inputs={"df": extract})

    return transform  # Builder inferred from task
```

**Option 3: Explicit build()**

```python
@pipeline(name="etl")
def build_etl():
    builder = PipelineBuilder()

    extract = builder.task(extract_fn, executor=local_exec, inputs={"source": raw_data})
    transform = builder.task(transform_fn, executor=lambda_exec, inputs={"df": extract})

    return builder.build()  # Returns DAG directly
```

### Alternative: Provided Builder

The decorator could provide the builder:

```python
@pipeline(name="etl")
def build_etl(p):  # p is PipelineBuilder
    """Pipeline function receives builder as parameter."""
    extract = p.task(extract_fn, executor=local_exec, inputs={"source": raw_data})
    transform = p.task(transform_fn, executor=lambda_exec, inputs={"df": extract})
    # No need to return - builder is managed by decorator
```

**Recommendation:** Use Option 1 (return builder) for explicitness and flexibility.

---

## Task Objects

### Task Class

```python
class Task:
    """
    A task in a Glacier pipeline.

    Tasks wrap functions and track dependencies.
    Created by PipelineBuilder, not directly by users.
    """

    def __init__(
        self,
        func: Callable,
        executor: ExecutionResource,
        inputs: dict[str, Any] | None = None,
        name: str | None = None,
        timeout: int | None = None,
        retries: int = 0,
        cache: bool = False,
        **kwargs
    ):
        """
        Create a Task.

        Typically called by PipelineBuilder.task(), not directly.

        Args:
            func: Function to execute
            executor: Execution resource
            inputs: Dict mapping param names to values or Tasks
            name: Task name
            timeout: Task timeout in seconds
            retries: Number of retries on failure
            cache: Enable result caching
            **kwargs: Additional config
        """
        self.func = func
        self.executor = executor
        self.inputs = inputs or {}
        self.name = name or func.__name__
        self.timeout = timeout
        self.retries = retries
        self.cache = cache
        self.config = kwargs

        # Extract dependencies from inputs
        self.dependencies = self._extract_dependencies()

    def _extract_dependencies(self) -> list["Task"]:
        """Extract upstream Task dependencies from inputs."""
        deps = []
        for value in self.inputs.values():
            if isinstance(value, Task):
                deps.append(value)
            elif isinstance(value, TaskOutput):
                deps.append(value.task)
            elif isinstance(value, (list, tuple)):
                # Handle lists/tuples of tasks
                for v in value:
                    if isinstance(v, Task):
                        deps.append(v)
                    elif isinstance(v, TaskOutput):
                        deps.append(v.task)
        return deps

    def execute(self, context: "ExecutionContext") -> Any:
        """
        Execute this task with resolved inputs.

        Args:
            context: Execution context with task outputs

        Returns:
            Result of executing the function
        """
        # Resolve inputs (replace Tasks with their outputs)
        resolved_inputs = {}

        for param_name, value in self.inputs.items():
            if isinstance(value, Task):
                resolved_inputs[param_name] = context.get_output(value)
            elif isinstance(value, TaskOutput):
                resolved_inputs[param_name] = value.resolve(context)
            elif isinstance(value, (list, tuple)):
                # Handle lists/tuples of tasks
                resolved_inputs[param_name] = [
                    context.get_output(v) if isinstance(v, Task)
                    else v.resolve(context) if isinstance(v, TaskOutput)
                    else v
                    for v in value
                ]
            else:
                # Use value directly (e.g., storage resource)
                resolved_inputs[param_name] = value

        # Execute function
        return self.func(**resolved_inputs)

    def output(self, index: int = 0) -> "TaskOutput":
        """
        Get a specific output from this task (for multi-output tasks).

        Args:
            index: Output index (0, 1, 2, ...)

        Returns:
            TaskOutput that can be used as input to other tasks

        Example:
            split = builder.task(split_fn, ...)
            train_task = builder.task(train_fn, inputs={"data": split.output(0)})
            test_task = builder.task(test_fn, inputs={"data": split.output(1)})
        """
        return TaskOutput(task=self, index=index)

    def __getitem__(self, key: str | int) -> "TaskOutput":
        """Support task[0] or task["name"] syntax."""
        if isinstance(key, int):
            return self.output(key)
        return TaskOutput(task=self, key=key)

    def __repr__(self) -> str:
        deps = [t.name for t in self.dependencies]
        return f"Task(name='{self.name}', executor={self.executor}, deps={deps})"


class TaskOutput:
    """
    Represents a specific output from a multi-output task.

    Used when a task returns multiple values (tuple) and you need
    to reference a specific one.
    """

    def __init__(
        self,
        task: Task,
        index: int | None = None,
        key: str | None = None
    ):
        self.task = task
        self.index = index
        self.key = key

    def resolve(self, context: "ExecutionContext") -> Any:
        """Resolve this output from execution context."""
        result = context.get_output(self.task)

        if self.index is not None:
            return result[self.index]
        elif self.key is not None:
            return result[self.key]
        else:
            return result

    def __repr__(self) -> str:
        if self.index is not None:
            return f"TaskOutput({self.task.name}[{self.index}])"
        elif self.key is not None:
            return f"TaskOutput({self.task.name}['{self.key}'])"
        return f"TaskOutput({self.task.name})"
```

---

## Composition Patterns

### 1. Sequential Pipeline

```python
@pipeline(name="sequential")
def build_sequential():
    """Linear chain of tasks."""
    builder = PipelineBuilder()

    task1 = builder.task(fn1, executor=local_exec, inputs={"source": raw_data})
    task2 = builder.task(fn2, executor=lambda_exec, inputs={"df": task1})
    task3 = builder.task(fn3, executor=local_exec, inputs={"df": task2})

    return builder

# DAG: task1 -> task2 -> task3
```

### 2. Parallel Pipeline (Fan-Out)

```python
@pipeline(name="parallel")
def build_parallel():
    """Multiple tasks depend on same input - can run in parallel."""
    builder = PipelineBuilder()

    extract = builder.task(extract_fn, executor=local_exec, inputs={"source": raw_data})

    # All three depend on extract - can run in parallel
    stats = builder.task(stats_fn, executor=lambda_exec, inputs={"df": extract})
    features = builder.task(features_fn, executor=lambda_exec, inputs={"df": extract})
    validation = builder.task(validate_fn, executor=lambda_exec, inputs={"df": extract})

    # Wait for all three
    report = builder.task(
        report_fn,
        executor=local_exec,
        inputs={"stats": stats, "features": features, "validation": validation}
    )

    return builder

# DAG:
#           -> stats ------\
#          /                \
# extract --> features ----> report
#          \                /
#           -> validation -/

# Execution stages:
# Stage 1: [extract]
# Stage 2: [stats, features, validation]  ← parallel
# Stage 3: [report]
```

### 3. Join Pipeline (Fan-In)

```python
@pipeline(name="join")
def build_join():
    """Multiple independent tasks join into one."""
    builder = PipelineBuilder()

    # Three independent extracts
    sales = builder.task(load_sales_fn, executor=local_exec, inputs={"source": sales_bucket})
    customers = builder.task(load_customers_fn, executor=local_exec, inputs={"source": customer_bucket})
    products = builder.task(load_products_fn, executor=local_exec, inputs={"source": product_bucket})

    # Join all three
    joined = builder.task(
        join_fn,
        executor=spark_exec,
        inputs={"sales": sales, "customers": customers, "products": products}
    )

    return builder

# DAG:
# load_sales -----\
# load_customers --> join
# load_products --/

# Execution stages:
# Stage 1: [load_sales, load_customers, load_products]  ← parallel
# Stage 2: [join]
```

### 4. Diamond Pipeline

```python
@pipeline(name="diamond")
def build_diamond():
    """Fork and join pattern."""
    builder = PipelineBuilder()

    extract = builder.task(extract_fn, executor=local_exec, inputs={"source": raw_data})

    # Fork - two parallel branches
    branch1 = builder.task(transform1_fn, executor=lambda_exec, inputs={"df": extract})
    branch2 = builder.task(transform2_fn, executor=lambda_exec, inputs={"df": extract})

    # Join - merge both branches
    merged = builder.task(
        merge_fn,
        executor=local_exec,
        inputs={"df1": branch1, "df2": branch2}
    )

    return builder

# DAG:
#         -> branch1 --\
#        /              \
# extract               -> merged
#        \              /
#         -> branch2 --/
```

### 5. Multi-Output Tasks

```python
def split_fn(df: pl.LazyFrame) -> tuple[pl.LazyFrame, pl.LazyFrame]:
    """Split data into train and test sets."""
    train = df.filter(pl.col("split") == "train")
    test = df.filter(pl.col("split") == "test")
    return train, test

@pipeline(name="ml")
def build_ml_pipeline():
    """Pipeline with multi-output task."""
    builder = PipelineBuilder()

    load = builder.task(load_fn, executor=local_exec, inputs={"source": data})

    # Task produces tuple of outputs
    split = builder.task(split_fn, executor=local_exec, inputs={"df": load})

    # Use specific outputs
    train_model = builder.task(
        train_fn,
        executor=databricks_exec,
        inputs={"data": split.output(0)}  # First output (train)
    )

    evaluate = builder.task(
        eval_fn,
        executor=local_exec,
        inputs={
            "model": train_model,
            "test_data": split.output(1)  # Second output (test)
        }
    )

    return builder
```

### 6. Conditional Logic

```python
@pipeline(name="conditional")
def build_conditional(mode: str):
    """Different pipeline based on mode parameter."""
    builder = PipelineBuilder()

    extract = builder.task(extract_fn, executor=local_exec, inputs={"source": raw_data})

    # Conditional task creation
    if mode == "full":
        transform = builder.task(
            full_transform_fn,
            executor=spark_exec,
            inputs={"df": extract}
        )
    else:
        transform = builder.task(
            quick_transform_fn,
            executor=lambda_exec,
            inputs={"df": extract}
        )

    load = builder.task(load_fn, executor=local_exec, inputs={"df": transform})

    return builder
```

### 7. Dynamic Task Generation

```python
@pipeline(name="dynamic")
def build_dynamic(files: list[str]):
    """Process multiple files in parallel."""
    builder = PipelineBuilder()

    # Create a task for each file
    process_tasks = []
    for i, file_path in enumerate(files):
        task = builder.task(
            process_file_fn,
            executor=lambda_exec,
            inputs={"file_path": file_path},
            name=f"process_file_{i}"
        )
        process_tasks.append(task)

    # Combine all results
    combine = builder.task(
        combine_fn,
        executor=local_exec,
        inputs={"results": process_tasks}  # List of tasks
    )

    return builder

# DAG (for 3 files):
# process_file_0 --\
# process_file_1 --> combine
# process_file_2 --/

# All process_file tasks can run in parallel
```

### 8. Complex Multi-Stage Pipeline

```python
@pipeline(name="complex_etl")
def build_complex_etl():
    """Complex pipeline with multiple stages and patterns."""
    builder = PipelineBuilder()

    # Stage 1: Parallel extracts
    raw_sales = builder.task(extract_sales_fn, executor=local_exec, inputs={"source": sales_bucket})
    raw_customers = builder.task(extract_customers_fn, executor=local_exec, inputs={"source": customer_bucket})

    # Stage 2: Independent cleaning (parallel)
    clean_sales = builder.task(clean_sales_fn, executor=lambda_exec, inputs={"df": raw_sales})
    clean_customers = builder.task(clean_customers_fn, executor=lambda_exec, inputs={"df": raw_customers})

    # Stage 3: Join
    joined = builder.task(
        join_fn,
        executor=spark_exec,
        inputs={"sales": clean_sales, "customers": clean_customers}
    )

    # Stage 4: Parallel transformations
    aggregates = builder.task(aggregate_fn, executor=spark_exec, inputs={"df": joined})
    features = builder.task(feature_fn, executor=spark_exec, inputs={"df": joined})

    # Stage 5: ML inference
    predictions = builder.task(
        ml_predict_fn,
        executor=databricks_exec,
        inputs={"data": joined, "aggs": aggregates, "features": features}
    )

    # Stage 6: Save
    save = builder.task(
        save_fn,
        executor=local_exec,
        inputs={"df": predictions, "dest": output_bucket}
    )

    return builder

# DAG automatically determines execution stages:
# Stage 1: [extract_sales, extract_customers]
# Stage 2: [clean_sales, clean_customers]
# Stage 3: [join]
# Stage 4: [aggregates, features]
# Stage 5: [ml_predict]
# Stage 6: [save]
```

---

## Implementation Specification

### 1. PipelineBuilder Class

**File:** `glacier/core/builder.py`

```python
from typing import Callable, Any
from glacier.core.task import Task
from glacier.core.dag import DAG

class PipelineBuilder:
    """
    Builder for constructing Glacier pipelines.

    Manages task creation and tracks the DAG structure.
    """

    def __init__(self):
        """Initialize an empty builder."""
        self._tasks: list[Task] = []

    def task(
        self,
        func: Callable,
        executor: "ExecutionResource",
        inputs: dict[str, Any] | None = None,
        name: str | None = None,
        **config
    ) -> Task:
        """
        Create a task and add it to the pipeline.

        Args:
            func: Function to execute (LazyFrame -> LazyFrame)
            executor: Execution resource (where this runs)
            inputs: Dict mapping param names to values or Tasks
            name: Optional task name (defaults to func.__name__)
            **config: Additional config (timeout, retries, etc.)

        Returns:
            Task object that can be used as input to other tasks
        """
        task_obj = Task(
            func=func,
            executor=executor,
            inputs=inputs or {},
            name=name,
            **config
        )
        self._tasks.append(task_obj)
        return task_obj

    def build(self) -> DAG:
        """
        Build the final DAG from all tasks.

        Returns:
            DAG object with all tasks and their dependencies
        """
        if not self._tasks:
            raise ValueError("Pipeline has no tasks")

        return DAG(self._tasks)

    def get_tasks(self) -> list[Task]:
        """Get all tasks in the pipeline."""
        return self._tasks.copy()

    def visualize(self) -> str:
        """Generate a Mermaid visualization of the pipeline."""
        dag = self.build()
        return dag.to_mermaid()

    def __repr__(self) -> str:
        return f"PipelineBuilder(tasks={len(self._tasks)})"
```

### 2. Pipeline Decorator

**File:** `glacier/core/pipeline.py`

```python
from typing import Callable, Any
from functools import wraps
import inspect
from glacier.core.builder import PipelineBuilder
from glacier.core.task import Task
from glacier.core.dag import DAG

def pipeline(name: str, description: str | None = None, **config) -> Callable:
    """
    Decorator for defining pipelines.

    The decorated function should:
    1. Create a PipelineBuilder
    2. Use builder.task() to create tasks
    3. Return the builder

    Usage:
        @pipeline(name="etl")
        def build_etl():
            builder = PipelineBuilder()
            extract = builder.task(extract_fn, executor=local_exec, inputs={...})
            transform = builder.task(transform_fn, executor=lambda_exec, inputs={"df": extract})
            return builder

    Args:
        name: Pipeline name
        description: Optional description
        **config: Additional configuration

    Returns:
        Pipeline object
    """
    def decorator(func: Callable) -> "Pipeline":
        return Pipeline(
            name=name,
            builder_func=func,
            description=description,
            config=config
        )

    return decorator


class Pipeline:
    """
    A Glacier pipeline - a DAG of tasks.

    Created by the @pipeline decorator.
    """

    def __init__(
        self,
        name: str,
        builder_func: Callable,
        description: str | None = None,
        config: dict | None = None
    ):
        """
        Create a Pipeline.

        Args:
            name: Pipeline name
            builder_func: Function that builds the pipeline
            description: Optional description
            config: Optional configuration
        """
        self.name = name
        self.builder_func = builder_func
        self.description = description or inspect.getdoc(builder_func)
        self.config = config or {}
        self._dag: DAG | None = None

    def build(self) -> DAG:
        """
        Build the DAG by calling the builder function.

        Returns:
            DAG object with all tasks and dependencies
        """
        if self._dag is not None:
            return self._dag

        # Call the builder function
        result = self.builder_func()

        # Handle different return types
        if isinstance(result, PipelineBuilder):
            # Builder was returned - build DAG from it
            self._dag = result.build()
        elif isinstance(result, Task):
            # Task was returned - build DAG from it
            self._dag = DAG.from_task(result)
        elif isinstance(result, DAG):
            # DAG was returned directly
            self._dag = result
        elif isinstance(result, list) and all(isinstance(t, Task) for t in result):
            # List of tasks
            self._dag = DAG.from_tasks(result)
        else:
            raise ValueError(
                f"Pipeline builder must return PipelineBuilder, Task, DAG, or list[Task]. "
                f"Got {type(result)}"
            )

        return self._dag

    def run(self, mode: str = "local", **kwargs) -> Any:
        """
        Execute the pipeline.

        Args:
            mode: Execution mode (local, cloud, analyze, generate)
            **kwargs: Mode-specific arguments

        Returns:
            Execution result (mode-dependent)
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

    def visualize(self) -> str:
        """Generate a visualization of the pipeline."""
        dag = self.build()
        return dag.to_mermaid()

    def __repr__(self) -> str:
        return f"Pipeline(name='{self.name}')"

    def __call__(self, *args, **kwargs):
        """Allow calling pipeline as a function."""
        return self.run(*args, **kwargs)
```

### 3. Task Class (Updated)

**File:** `glacier/core/task.py`

Already defined in previous section - no changes needed.

### 4. DAG Class (Updated)

**File:** `glacier/core/dag.py`

```python
from typing import Any
from glacier.core.task import Task

class DAG:
    """
    Directed Acyclic Graph of tasks.

    Represents the structure of a pipeline.
    """

    def __init__(self, tasks: list[Task]):
        """
        Create a DAG from a list of tasks.

        Args:
            tasks: List of all tasks in the pipeline
        """
        self.tasks = tasks
        self._validate()

    @classmethod
    def from_task(cls, final_task: Task) -> "DAG":
        """
        Build DAG by traversing backwards from final task.

        Args:
            final_task: The final task in the pipeline

        Returns:
            DAG containing all reachable tasks
        """
        tasks = []
        visited = set()

        def traverse(task: Task):
            if task in visited:
                return
            visited.add(task)
            tasks.append(task)
            for dep in task.dependencies:
                traverse(dep)

        traverse(final_task)
        return cls(tasks)

    @classmethod
    def from_tasks(cls, tasks: list[Task]) -> "DAG":
        """
        Build DAG from explicit list of tasks.

        Collects all tasks and their transitive dependencies.
        """
        all_tasks = set()

        def collect(task: Task):
            if task in all_tasks:
                return
            all_tasks.add(task)
            for dep in task.dependencies:
                collect(dep)

        for task in tasks:
            collect(task)

        return cls(list(all_tasks))

    def _validate(self):
        """Validate that the graph is acyclic."""
        visited = set()
        rec_stack = set()

        def has_cycle(task: Task) -> bool:
            visited.add(task)
            rec_stack.add(task)

            for dep in task.dependencies:
                if dep not in visited:
                    if has_cycle(dep):
                        return True
                elif dep in rec_stack:
                    return True

            rec_stack.remove(task)
            return False

        for task in self.tasks:
            if task not in visited:
                if has_cycle(task):
                    raise ValueError("Pipeline contains a cycle")

    def topological_sort(self) -> list[Task]:
        """
        Return tasks in execution order (topologically sorted).

        Returns:
            List of tasks in order where dependencies come before dependents
        """
        # Kahn's algorithm
        in_degree = {task: len(task.dependencies) for task in self.tasks}
        queue = [task for task in self.tasks if in_degree[task] == 0]
        result = []

        while queue:
            task = queue.pop(0)
            result.append(task)

            # Find tasks that depend on this one
            for other in self.tasks:
                if task in other.dependencies:
                    in_degree[other] -= 1
                    if in_degree[other] == 0:
                        queue.append(other)

        if len(result) != len(self.tasks):
            raise ValueError("Pipeline contains a cycle")

        return result

    def get_stages(self) -> list[list[Task]]:
        """
        Group tasks into execution stages for parallel execution.

        Tasks in the same stage have no dependencies on each other
        and can be executed in parallel.

        Returns:
            List of stages, where each stage is a list of tasks
        """
        stages = []
        remaining = set(self.tasks)

        while remaining:
            # Find tasks with no dependencies in remaining set
            stage = []
            for task in list(remaining):
                if all(dep not in remaining for dep in task.dependencies):
                    stage.append(task)

            if not stage:
                raise ValueError("Pipeline contains a cycle")

            stages.append(stage)
            remaining -= set(stage)

        return stages

    def to_mermaid(self) -> str:
        """Generate Mermaid diagram of the DAG."""
        lines = ["graph TD"]
        for task in self.tasks:
            node_id = task.name.replace(" ", "_")
            executor_type = getattr(task.executor, 'type', 'unknown')
            lines.append(f"    {node_id}[\"{task.name}<br/>({executor_type})\"]")
            for dep in task.dependencies:
                dep_id = dep.name.replace(" ", "_")
                lines.append(f"    {dep_id} --> {node_id}")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"DAG(tasks={len(self.tasks)})"
```

### 5. Export from glacier/__init__.py

```python
from glacier.providers import Provider
from glacier.core.pipeline import pipeline
from glacier.core.builder import PipelineBuilder
from glacier.core.task import Task

__all__ = ["Provider", "pipeline", "PipelineBuilder", "Task"]
```

---

## Summary

### Core Pattern

```python
# 1. Define pure functions
def extract_fn(source) -> pl.LazyFrame: ...
def transform_fn(df) -> pl.LazyFrame: ...

# 2. Build pipeline using PipelineBuilder
@pipeline(name="etl")
def build_etl():
    builder = PipelineBuilder()

    extract = builder.task(extract_fn, executor=local_exec, inputs={"source": raw_data})
    transform = builder.task(transform_fn, executor=lambda_exec, inputs={"df": extract})
    load = builder.task(load_fn, executor=local_exec, inputs={"df": transform})

    return builder

# 3. Execute
etl = build_etl()
result = etl.run(mode="local")
```

### Benefits

✅ **Builder pattern** - Clean, standard design pattern
✅ **Explicit** - Clear task creation and dependency wiring
✅ **No magic** - No AST parsing, no hidden tracking
✅ **Flexible** - Easy conditionals, loops, dynamic tasks
✅ **Type safe** - All objects are properly typed
✅ **Debuggable** - Can inspect builder and tasks
✅ **Testable** - Can test individual functions easily

### Key Classes

- **PipelineBuilder** - Manages task creation and tracks DAG
- **Task** - Wraps functions, tracks dependencies
- **Pipeline** - Executes pipelines in different modes
- **DAG** - Represents task graph, provides topological sort

---

**END OF DOCUMENT**
