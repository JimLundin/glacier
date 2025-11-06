# Pipeline Composition Design: Simple Builder Pattern

**Status:** Design Document - v4.0 (Simple Builder)
**Date:** 2025-11-06
**Related:** DESIGN_UX.md

---

## Executive Summary

This document defines a **simple builder pattern** for composing pipelines in Glacier. The key principle: **tasks are defined with decorators, pipelines are built with a fluent builder API**.

**Core Design:**
- **Tasks defined with decorators** - `@executor.task()` on execution resources
- **Pipelines built with builder** - `Pipeline().step(task1).step(task2)`
- **Dependencies are explicit** - passed as Task objects in the `inputs` dict
- **Simple and declarative** - no AST parsing, no complex patterns

---

## Table of Contents

1. [Design Principles](#design-principles)
2. [Core Pattern](#core-pattern)
3. [Pipeline Builder API](#pipeline-builder-api)
4. [Task Definition](#task-definition)
5. [Composition Patterns](#composition-patterns)
6. [Implementation Specification](#implementation-specification)

---

## Design Principles

### 1. Tasks Defined with Decorators

Tasks are created using decorators on execution resources:

```python
@local_exec.task()
def extract(source) -> pl.LazyFrame:
    return source.scan()

@lambda_exec.task()
def transform(df: pl.LazyFrame) -> pl.LazyFrame:
    return df.filter(pl.col("value") > 0)
```

### 2. Pipelines Built with Builder

Pipelines use a simple fluent builder pattern:

```python
pipeline = (
    Pipeline(name="etl")
    .step(extract, inputs={"source": raw_data})
    .step(transform, inputs={"df": extract})
)
```

### 3. Explicit Dependencies

Dependencies declared through the `inputs` dict:

```python
.step(transform, inputs={"df": extract})  # transform depends on extract
```

### 4. No Magic

- Tasks are objects
- Pipeline composition is explicit
- Dependencies are clear
- No AST parsing needed

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
raw_data = provider.bucket(bucket="data", path="input.parquet")
output = provider.bucket(bucket="data", path="output.parquet")

# 2. Define tasks with decorators
@local_exec.task()
def extract(source) -> pl.LazyFrame:
    """Extract data from source."""
    return source.scan()

@lambda_exec.task()
def transform(df: pl.LazyFrame) -> pl.LazyFrame:
    """Transform data."""
    return df.filter(pl.col("value") > 0)

@local_exec.task()
def load(df: pl.LazyFrame, destination) -> None:
    """Load data to destination."""
    df.collect().write_parquet(destination.get_uri())

# 3. Build pipeline with builder pattern
etl_pipeline = (
    Pipeline(name="etl")
    .step(extract, inputs={"source": raw_data})
    .step(transform, inputs={"df": extract})
    .step(load, inputs={"df": transform, "destination": output})
)

# 4. Execute
result = etl_pipeline.run(mode="local")
```

### Key Points

1. **Tasks are Task objects** - created by `@executor.task()` decorator
2. **Pipeline.step()** adds tasks to the pipeline and returns self (for chaining)
3. **Tasks reference each other** in `inputs` dict
4. **Pipeline tracks all tasks** internally
5. **Dependencies extracted** from Task objects in inputs
6. **Fluent interface** - chain `.step()` calls

---

## Pipeline Builder API

### Pipeline Class

```python
class Pipeline:
    """
    Builder for composing Glacier pipelines.

    Uses fluent interface for pipeline construction.
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
        self._steps: list[tuple[Task, dict]] = []

    def step(
        self,
        task: Task,
        inputs: dict[str, Any] | None = None,
        name: str | None = None
    ) -> "Pipeline":
        """
        Add a task to the pipeline.

        Args:
            task: Task to execute (created with @executor.task())
            inputs: Dict mapping param names to values or other Tasks
            name: Optional step name (overrides task name)

        Returns:
            Self (for method chaining)

        Example:
            pipeline = (
                Pipeline(name="etl")
                .step(extract, inputs={"source": raw_data})
                .step(transform, inputs={"df": extract})
            )
        """
        self._steps.append((task, inputs or {}, name))
        return self

    def build(self) -> DAG:
        """
        Build the DAG from all steps.

        Returns:
            DAG object with all tasks and their dependencies
        """
        # Create TaskInstance for each step with its specific inputs
        instances = []
        for task, inputs, name in self._steps:
            instance = TaskInstance(
                task=task,
                inputs=inputs,
                name=name or task.name
            )
            instances.append(instance)

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

### Alternative: Method Syntax

Could also support non-chaining syntax:

```python
pipeline = Pipeline(name="etl")
pipeline.step(extract, inputs={"source": raw_data})
pipeline.step(transform, inputs={"df": extract})
pipeline.step(load, inputs={"df": transform, "destination": output})

result = pipeline.run(mode="local")
```

Both work since `.step()` returns `self`.

---

## Task Definition

### Task Decorator

Tasks are defined using decorators on execution resources:

```python
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

        Args:
            func: Function to wrap (auto-provided by decorator)
            name: Optional task name
            timeout: Task timeout in seconds
            retries: Number of retries on failure
            cache: Enable result caching
            **config: Additional configuration

        Returns:
            Task object (or decorator function)
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

### Task Object

```python
class Task:
    """
    A task in a Glacier pipeline.

    Tasks wrap functions and are bound to execution resources.
    Created by @executor.task() decorator, not directly by users.
    """

    def __init__(
        self,
        func: Callable,
        executor: ExecutionResource,
        name: str,
        timeout: int | None = None,
        retries: int = 0,
        cache: bool = False,
        config: dict | None = None
    ):
        """
        Create a Task.

        Typically created by @executor.task() decorator.

        Args:
            func: Function to execute (LazyFrame -> LazyFrame)
            executor: Execution resource (where this runs)
            name: Task name
            timeout: Task timeout in seconds
            retries: Number of retries
            cache: Enable caching
            config: Additional configuration
        """
        self.func = func
        self.executor = executor
        self.name = name
        self.timeout = timeout
        self.retries = retries
        self.cache = cache
        self.config = config or {}

        # Store signature
        self.signature = inspect.signature(func)

    def __call__(self, **inputs) -> Any:
        """
        Execute the task function directly (for testing).

        Args:
            **inputs: Input arguments

        Returns:
            Result of function execution
        """
        return self.func(**inputs)

    def __repr__(self) -> str:
        return f"Task(name='{self.name}', executor={self.executor})"
```

### TaskInstance

When a task is added to a pipeline, we create a TaskInstance that captures the specific inputs:

```python
class TaskInstance:
    """
    An instance of a Task in a pipeline with specific inputs.

    TaskInstances are created when tasks are added to pipelines via .step()
    They capture the specific inputs for this usage of the task.
    """

    def __init__(
        self,
        task: Task,
        inputs: dict[str, Any],
        name: str | None = None
    ):
        """
        Create a TaskInstance.

        Args:
            task: The Task object
            inputs: Dict mapping param names to values or other Tasks/TaskInstances
            name: Optional instance name
        """
        self.task = task
        self.inputs = inputs
        self.name = name or task.name

        # Extract dependencies
        self.dependencies = self._extract_dependencies()

    def _extract_dependencies(self) -> list["TaskInstance"]:
        """Extract upstream TaskInstance dependencies from inputs."""
        deps = []
        for value in self.inputs.values():
            if isinstance(value, Task):
                # If a bare Task is referenced, we need to find its instance
                # This is handled during DAG building
                pass
            elif isinstance(value, TaskInstance):
                deps.append(value)
            elif isinstance(value, (list, tuple)):
                for v in value:
                    if isinstance(v, (Task, TaskInstance)):
                        # Handle later
                        pass
        return deps

    def execute(self, context: "ExecutionContext") -> Any:
        """
        Execute this task instance.

        Args:
            context: Execution context with resolved outputs

        Returns:
            Result of function execution
        """
        # Resolve inputs
        resolved_inputs = {}
        for param_name, value in self.inputs.items():
            if isinstance(value, Task):
                # Find the instance of this task in the pipeline
                resolved_inputs[param_name] = context.get_output_for_task(value)
            elif isinstance(value, TaskInstance):
                resolved_inputs[param_name] = context.get_output(value)
            elif isinstance(value, (list, tuple)):
                resolved_inputs[param_name] = [
                    context.get_output(v) if isinstance(v, (Task, TaskInstance)) else v
                    for v in value
                ]
            else:
                resolved_inputs[param_name] = value

        # Execute
        return self.task.func(**resolved_inputs)

    def __repr__(self) -> str:
        return f"TaskInstance(name='{self.name}', task={self.task.name})"
```

---

## Composition Patterns

### 1. Sequential Pipeline

```python
# Define tasks
@local_exec.task()
def task1(source): ...

@lambda_exec.task()
def task2(df): ...

@local_exec.task()
def task3(df): ...

# Build pipeline
pipeline = (
    Pipeline(name="sequential")
    .step(task1, inputs={"source": raw_data})
    .step(task2, inputs={"df": task1})
    .step(task3, inputs={"df": task2})
)
```

### 2. Parallel Pipeline (Fan-Out)

```python
# Define tasks
@local_exec.task()
def extract(source): ...

@lambda_exec.task()
def compute_stats(df): ...

@lambda_exec.task()
def compute_features(df): ...

@lambda_exec.task()
def validate(df): ...

@local_exec.task()
def generate_report(stats, features, validation): ...

# Build pipeline
pipeline = (
    Pipeline(name="parallel")
    .step(extract, inputs={"source": raw_data})
    .step(compute_stats, inputs={"df": extract})
    .step(compute_features, inputs={"df": extract})
    .step(validate, inputs={"df": extract})
    .step(generate_report, inputs={
        "stats": compute_stats,
        "features": compute_features,
        "validation": validate
    })
)

# All three (compute_stats, compute_features, validate) can run in parallel
```

### 3. Join Pipeline (Fan-In)

```python
# Define tasks
@local_exec.task()
def load_sales(source): ...

@local_exec.task()
def load_customers(source): ...

@local_exec.task()
def load_products(source): ...

@spark_exec.task()
def join_all(sales, customers, products): ...

# Build pipeline
pipeline = (
    Pipeline(name="join")
    .step(load_sales, inputs={"source": sales_bucket})
    .step(load_customers, inputs={"source": customer_bucket})
    .step(load_products, inputs={"source": product_bucket})
    .step(join_all, inputs={
        "sales": load_sales,
        "customers": load_customers,
        "products": load_products
    })
)
```

### 4. Diamond Pipeline

```python
# Define tasks
@local_exec.task()
def extract(source): ...

@lambda_exec.task()
def branch1(df): ...

@lambda_exec.task()
def branch2(df): ...

@local_exec.task()
def merge(df1, df2): ...

# Build pipeline
pipeline = (
    Pipeline(name="diamond")
    .step(extract, inputs={"source": raw_data})
    .step(branch1, inputs={"df": extract})
    .step(branch2, inputs={"df": extract})
    .step(merge, inputs={"df1": branch1, "df2": branch2})
)
```

### 5. Multi-Output Tasks

For tasks that return multiple values:

```python
# Define task that returns tuple
@local_exec.task()
def split_data(df):
    train = df.filter(pl.col("split") == "train")
    test = df.filter(pl.col("split") == "test")
    return train, test

@databricks_exec.task()
def train_model(data): ...

@local_exec.task()
def evaluate(model, test_data): ...

# Build pipeline
pipeline = Pipeline(name="ml")

# Add split step
pipeline.step(split_data, inputs={"df": load_task})

# Reference specific outputs using indexing
# We need a way to reference tuple outputs...
# Option: Use a helper or special syntax
```

For multi-output, we might need a helper:

```python
train, test = split_data.outputs(2)  # Returns tuple of TaskOutput objects

pipeline = (
    Pipeline(name="ml")
    .step(split_data, inputs={"df": load_task})
    .step(train_model, inputs={"data": train})
    .step(evaluate, inputs={"model": train_model, "test_data": test})
)
```

Or simpler - just reference the task and use indexing in inputs:

```python
pipeline = (
    Pipeline(name="ml")
    .step(split_data, inputs={"df": load_task})
    .step(train_model, inputs={"data": (split_data, 0)})  # Tuple (task, index)
    .step(evaluate, inputs={"model": train_model, "test_data": (split_data, 1)})
)
```

### 6. Conditional Pipelines

Use Python conditionals to build different pipelines:

```python
def build_etl_pipeline(mode: str):
    """Build pipeline based on mode."""
    pipeline = Pipeline(name=f"etl_{mode}")
    pipeline.step(extract, inputs={"source": raw_data})

    if mode == "full":
        pipeline.step(full_transform, inputs={"df": extract})
        pipeline.step(load, inputs={"df": full_transform})
    else:
        pipeline.step(quick_transform, inputs={"df": extract})
        pipeline.step(load, inputs={"df": quick_transform})

    return pipeline
```

### 7. Dynamic Task Generation

Build pipelines dynamically:

```python
def build_multi_file_pipeline(files: list[str]):
    """Process multiple files in parallel."""
    pipeline = Pipeline(name="multi_file")

    # Define a task that can process any file
    @lambda_exec.task()
    def process_file(file_path):
        return pl.scan_parquet(file_path).filter(...)

    # Add a step for each file
    process_tasks = []
    for i, file_path in enumerate(files):
        pipeline.step(process_file, inputs={"file_path": file_path}, name=f"process_{i}")
        process_tasks.append(process_file)  # Track for later reference

    # Combine results
    pipeline.step(combine, inputs={"results": process_tasks})

    return pipeline
```

---

## Implementation Specification

### 1. Pipeline Class

**File:** `glacier/core/pipeline.py`

```python
from typing import Any, Callable
from glacier.core.task import Task, TaskInstance
from glacier.core.dag import DAG

class Pipeline:
    """
    Builder for composing Glacier pipelines using fluent interface.

    Pipelines are built by chaining .step() calls.
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
        self._steps: list[tuple[Task, dict, str | None]] = []
        self._dag: DAG | None = None

    def step(
        self,
        task: Task,
        inputs: dict[str, Any] | None = None,
        name: str | None = None
    ) -> "Pipeline":
        """
        Add a task step to the pipeline.

        Args:
            task: Task to execute (created with @executor.task())
            inputs: Dict mapping param names to values or Tasks
            name: Optional step name (overrides task name)

        Returns:
            Self (for method chaining)

        Example:
            pipeline = (
                Pipeline(name="etl")
                .step(extract, inputs={"source": raw_data})
                .step(transform, inputs={"df": extract})
            )
        """
        self._steps.append((task, inputs or {}, name))
        self._dag = None  # Invalidate cached DAG
        return self

    def build(self) -> DAG:
        """
        Build the DAG from all steps.

        Returns:
            DAG object with all task instances
        """
        if self._dag is not None:
            return self._dag

        # Create TaskInstance for each step
        instances = []
        task_to_instance = {}  # Map Task -> TaskInstance for dependency resolution

        for task, inputs, name in self._steps:
            # Resolve inputs: replace bare Task objects with their TaskInstances
            resolved_inputs = {}
            for param_name, value in inputs.items():
                if isinstance(value, Task):
                    # Find the TaskInstance for this Task
                    if value in task_to_instance:
                        resolved_inputs[param_name] = task_to_instance[value]
                    else:
                        raise ValueError(
                            f"Task '{value.name}' used in inputs but not added to pipeline"
                        )
                elif isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], Task):
                    # Multi-output: (task, index)
                    ref_task, index = value
                    if ref_task in task_to_instance:
                        resolved_inputs[param_name] = (task_to_instance[ref_task], index)
                    else:
                        raise ValueError(
                            f"Task '{ref_task.name}' used in inputs but not added to pipeline"
                        )
                else:
                    resolved_inputs[param_name] = value

            # Create TaskInstance
            instance = TaskInstance(
                task=task,
                inputs=resolved_inputs,
                name=name or task.name
            )
            instances.append(instance)
            task_to_instance[task] = instance

        self._dag = DAG(instances)
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
        """Generate Mermaid visualization of the pipeline."""
        dag = self.build()
        return dag.to_mermaid()

    def __repr__(self) -> str:
        return f"Pipeline(name='{self.name}', steps={len(self._steps)})"
```

### 2. Task and TaskInstance Classes

**File:** `glacier/core/task.py`

```python
import inspect
from typing import Callable, Any

class Task:
    """
    A reusable task definition.

    Tasks are created by @executor.task() decorator and represent
    a function bound to an execution resource.
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
        """Execute the task directly (for testing)."""
        return self.func(**inputs)

    def __repr__(self) -> str:
        return f"Task(name='{self.name}', executor={self.executor})"


class TaskInstance:
    """
    An instance of a Task in a pipeline with specific inputs.

    Created when a task is added to a pipeline via Pipeline.step()
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
        self.dependencies = self._extract_dependencies()

    def _extract_dependencies(self) -> list["TaskInstance"]:
        """Extract TaskInstance dependencies from inputs."""
        deps = []
        for value in self.inputs.values():
            if isinstance(value, TaskInstance):
                deps.append(value)
            elif isinstance(value, tuple) and len(value) == 2:
                # Multi-output: (TaskInstance, index)
                if isinstance(value[0], TaskInstance):
                    deps.append(value[0])
            elif isinstance(value, (list, tuple)):
                for v in value:
                    if isinstance(v, TaskInstance):
                        deps.append(v)
                    elif isinstance(v, tuple) and len(v) == 2 and isinstance(v[0], TaskInstance):
                        deps.append(v[0])
        return deps

    def execute(self, context: "ExecutionContext") -> Any:
        """Execute this task instance."""
        resolved_inputs = {}

        for param_name, value in self.inputs.items():
            if isinstance(value, TaskInstance):
                resolved_inputs[param_name] = context.get_output(value)
            elif isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], TaskInstance):
                # Multi-output: (TaskInstance, index)
                instance, index = value
                output = context.get_output(instance)
                resolved_inputs[param_name] = output[index]
            elif isinstance(value, (list, tuple)):
                resolved_inputs[param_name] = [
                    context.get_output(v) if isinstance(v, TaskInstance)
                    else v[1](context.get_output(v[0])) if isinstance(v, tuple) and len(v) == 2
                    else v
                    for v in value
                ]
            else:
                resolved_inputs[param_name] = value

        return self.task.func(**resolved_inputs)

    def __repr__(self) -> str:
        return f"TaskInstance(name='{self.name}', task={self.task.name}, deps={len(self.dependencies)})"
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

        Args:
            func: Function to wrap (auto-provided by decorator)
            name: Optional task name
            timeout: Task timeout
            retries: Number of retries
            cache: Enable caching
            **config: Additional config

        Returns:
            Task object (or decorator function)
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

### 4. DAG Class

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

### 5. Export from glacier/__init__.py

```python
from glacier.providers import Provider
from glacier.core.pipeline import Pipeline

__all__ = ["Provider", "Pipeline"]
```

---

## Summary

### Core Pattern

```python
# 1. Define tasks with decorators
@local_exec.task()
def extract(source): ...

@lambda_exec.task()
def transform(df): ...

# 2. Build pipeline with simple builder
pipeline = (
    Pipeline(name="etl")
    .step(extract, inputs={"source": raw_data})
    .step(transform, inputs={"df": extract})
)

# 3. Execute
result = pipeline.run(mode="local")
```

### Benefits

✅ **Simple and clean** - Just `.step()` chaining
✅ **Tasks defined with decorators** - On execution resources
✅ **Explicit dependencies** - Via inputs dict
✅ **Fluent interface** - Natural method chaining
✅ **No magic** - No AST parsing needed
✅ **Type safe** - Tasks and inputs are typed
✅ **Flexible** - Easy conditionals and dynamic pipelines

### Key Classes

- **Pipeline** - Fluent builder for composing pipelines
- **Task** - Reusable task definition (from decorator)
- **TaskInstance** - Task with specific inputs in a pipeline
- **DAG** - Directed acyclic graph of task instances

---

**END OF DOCUMENT**
