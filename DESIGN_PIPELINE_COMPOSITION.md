# Pipeline Composition Design (Explicit & Declarative)

**Status:** Design Document - v2.0
**Date:** 2025-11-06
**Related:** DESIGN_UX.md

---

## Executive Summary

This document defines an **explicit and declarative** pattern for composing pipelines in Glacier. The key principle: **users explicitly build the DAG** - no AST analysis or implicit inference required.

**Core Design:**
- **Tasks are objects** that wrap functions (taking and returning LazyFrames)
- **Pipeline composition is explicit** - dependencies are declared, not inferred
- **Task calls return Task objects** (or TaskOutput objects) that form the DAG
- **No static analysis needed** - the DAG is built explicitly by the user

---

## Table of Contents

1. [Problem with Previous Design](#problem-with-previous-design)
2. [Design Principles](#design-principles)
3. [Core Pattern](#core-pattern)
4. [Task Objects](#task-objects)
5. [Pipeline Composition](#pipeline-composition)
6. [Composition Patterns](#composition-patterns)
7. [Implementation Specification](#implementation-specification)

---

## Problem with Previous Design

The previous design required **AST analysis** to infer the DAG from Python code:

```python
# Previous design - requires AST parsing
@pipeline(name="etl")
def etl_pipeline():
    raw = extract(bucket)      # How do we know extract is a task?
    result = transform(raw)    # How do we know raw depends on extract?
    return result              # Parse AST to find calls and dependencies
```

**Problems:**
- Complex static analysis required
- Difficult to handle dynamic logic (loops, conditionals)
- Magic/implicit behavior
- Hard to debug
- Doesn't work with all Python constructs

**What we need:** An explicit, declarative pattern where users tell us the DAG structure directly.

---

## Design Principles

### 1. Explicit Over Implicit

Users explicitly declare task dependencies - no inference:

```python
# ✅ Explicit - clear what depends on what
extract_task = local_exec.task(extract_fn)
transform_task = lambda_exec.task(transform_fn, inputs=[extract_task])

# ❌ Implicit - requires analysis
raw = extract(bucket)  # Is this a task call or function call?
result = transform(raw)  # Does transform depend on extract?
```

### 2. Tasks Are Objects

Tasks are first-class objects that:
- Wrap functions (that take/return LazyFrames)
- Are bound to execution resources
- Track their inputs/dependencies
- Can be composed to form a DAG

```python
# Task object wraps a function
def extract_fn(source) -> pl.LazyFrame:
    return source.scan()

# Create Task object bound to executor
extract = local_exec.task(extract_fn)

# extract is a Task object, not a function
assert isinstance(extract, Task)
```

### 3. Declarative Composition

Pipelines are built by declaring tasks and their relationships:

```python
@pipeline(name="etl")
def build_pipeline():
    # Declare tasks with explicit inputs
    extract = Task(extract_fn, executor=local_exec, inputs=[raw_data])
    transform = Task(transform_fn, executor=lambda_exec, inputs=[extract])
    load = Task(load_fn, executor=local_exec, inputs=[transform, output])

    # Return the DAG (list of tasks or final task)
    return load
```

### 4. No Magic

Behavior should be obvious and debuggable:
- Clear what's a task vs a function
- Clear what depends on what
- No hidden context tracking
- No AST parsing

---

## Core Pattern

### Complete Example

```python
from glacier import Provider, pipeline, Task
from glacier.config import AwsConfig, LambdaConfig
import polars as pl

# 1. Create provider and resources
provider = Provider(config=AwsConfig(region="us-east-1"))
local_exec = provider.local()
lambda_exec = provider.serverless(config=LambdaConfig(memory=1024))
raw_data = provider.bucket(bucket="data", path="input.parquet")
output = provider.bucket(bucket="data", path="output.parquet")

# 2. Define task functions (pure functions: LazyFrame -> LazyFrame)
def extract_fn(source) -> pl.LazyFrame:
    """Extract data from source."""
    return source.scan()

def transform_fn(df: pl.LazyFrame) -> pl.LazyFrame:
    """Transform data."""
    return df.filter(pl.col("value") > 0)

def load_fn(df: pl.LazyFrame, destination) -> None:
    """Load data to destination."""
    df.collect().write_parquet(destination.get_uri())

# 3. Build pipeline explicitly
@pipeline(name="etl")
def build_etl_pipeline():
    """
    Build the ETL pipeline DAG explicitly.

    This function declares tasks and their dependencies.
    No execution happens here - just DAG construction.
    """
    # Create Task objects with explicit inputs
    extract = Task(
        func=extract_fn,
        executor=local_exec,
        inputs={"source": raw_data},
        name="extract"
    )

    transform = Task(
        func=transform_fn,
        executor=lambda_exec,
        inputs={"df": extract},  # Depends on extract task
        name="transform"
    )

    load = Task(
        func=load_fn,
        executor=local_exec,
        inputs={"df": transform, "destination": output},  # Depends on transform
        name="load"
    )

    # Return the final task (or list of tasks)
    return load  # Or: return [extract, transform, load]

# 4. Execute the pipeline
pipeline_instance = build_etl_pipeline()
result = pipeline_instance.run(mode="local")
```

### Key Points

1. **Task functions are pure** - just functions that transform data
2. **Task objects wrap functions** - created with `Task(func, executor, inputs)`
3. **Inputs are explicit** - dict of `{param_name: value_or_task}`
4. **Pipeline function builds the DAG** - returns Task or list of Tasks
5. **No execution during build** - just DAG construction
6. **Run happens separately** - `.run(mode="local")` executes the DAG

---

## Task Objects

### Task Class Design

```python
class Task:
    """
    A task in a Glacier pipeline.

    Tasks wrap functions and bind them to execution resources.
    They track inputs (dependencies) to form the DAG.
    """

    def __init__(
        self,
        func: Callable,
        executor: ExecutionResource,
        inputs: dict[str, Any] | None = None,
        name: str | None = None,
        **config
    ):
        """
        Create a Task.

        Args:
            func: Function to execute (takes LazyFrames, returns LazyFrame)
            executor: Execution resource (where this runs)
            inputs: Dict mapping param names to values or other Tasks
            name: Optional task name (defaults to func.__name__)
            **config: Additional config (timeout, retries, etc.)
        """
        self.func = func
        self.executor = executor
        self.inputs = inputs or {}
        self.name = name or func.__name__
        self.config = config

        # Extracted at init
        self.dependencies = self._extract_dependencies()

    def _extract_dependencies(self) -> list[Task]:
        """Extract upstream Task dependencies from inputs."""
        deps = []
        for value in self.inputs.values():
            if isinstance(value, Task):
                deps.append(value)
        return deps

    def execute(self, context: ExecutionContext) -> Any:
        """
        Execute this task.

        Args:
            context: Execution context with resolved input values

        Returns:
            Result of executing the function
        """
        # Resolve inputs (replace Task objects with their outputs)
        resolved_inputs = {}
        for param_name, value in self.inputs.items():
            if isinstance(value, Task):
                # Get the output of the upstream task from context
                resolved_inputs[param_name] = context.get_output(value)
            else:
                # Use the value directly (e.g., storage resource)
                resolved_inputs[param_name] = value

        # Execute the function
        return self.func(**resolved_inputs)

    def __repr__(self) -> str:
        deps = [t.name for t in self.dependencies]
        return f"Task(name='{self.name}', executor={self.executor}, deps={deps})"
```

### Creating Tasks

**Option 1: Direct instantiation**

```python
extract = Task(
    func=extract_fn,
    executor=local_exec,
    inputs={"source": raw_data},
    name="extract"
)
```

**Option 2: Via executor (convenience method)**

```python
@local_exec.task(inputs={"source": raw_data})
def extract(source) -> pl.LazyFrame:
    return source.scan()

# extract is now a Task object
```

**Option 3: Separate definition and binding**

```python
# Define function
def extract_fn(source) -> pl.LazyFrame:
    return source.scan()

# Create task later
extract = local_exec.task(extract_fn, inputs={"source": raw_data})
```

---

## Pipeline Composition

### Pipeline Function

The pipeline function is a **builder** that constructs the DAG:

```python
@pipeline(name="etl")
def build_pipeline():
    """
    Build the pipeline DAG.

    This function:
    1. Creates Task objects
    2. Wires them together via inputs
    3. Returns the task graph

    No execution happens here - just DAG construction.
    """
    task1 = Task(fn1, executor=exec1, inputs={...})
    task2 = Task(fn2, executor=exec2, inputs={"data": task1})
    task3 = Task(fn3, executor=exec3, inputs={"data": task2})

    return task3  # or return [task1, task2, task3]
```

### Pipeline Object

```python
class Pipeline:
    """
    A Glacier pipeline.

    Represents a DAG of tasks that can be executed, analyzed,
    or used to generate infrastructure.
    """

    def __init__(self, name: str, builder: Callable):
        """
        Create a Pipeline.

        Args:
            name: Pipeline name
            builder: Function that builds the task DAG
        """
        self.name = name
        self.builder = builder
        self._dag = None

    def build(self) -> DAG:
        """
        Build the DAG by calling the builder function.

        Returns:
            DAG object with all tasks and dependencies
        """
        if self._dag is None:
            # Call the builder function
            result = self.builder()

            # Convert result to DAG
            if isinstance(result, Task):
                # Single task - traverse backwards to get all tasks
                self._dag = DAG.from_task(result)
            elif isinstance(result, list):
                # List of tasks
                self._dag = DAG.from_tasks(result)
            else:
                raise ValueError(f"Pipeline must return Task or list[Task], got {type(result)}")

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
        # Build DAG
        dag = self.build()

        # Execute based on mode
        if mode == "local":
            return self._run_local(dag, **kwargs)
        elif mode == "cloud":
            return self._run_cloud(dag, **kwargs)
        elif mode == "analyze":
            return self._analyze(dag, **kwargs)
        elif mode == "generate":
            return self._generate(dag, **kwargs)
        else:
            raise ValueError(f"Unknown mode: {mode}")

    def _run_local(self, dag: DAG, **kwargs) -> Any:
        """Execute all tasks locally in topological order."""
        from glacier.runtime.local import LocalExecutor
        executor = LocalExecutor(dag)
        return executor.execute(**kwargs)
```

### DAG Object

```python
class DAG:
    """
    Directed Acyclic Graph of tasks.

    Represents the structure of a pipeline.
    """

    def __init__(self, tasks: list[Task]):
        self.tasks = tasks
        self._validate()

    @classmethod
    def from_task(cls, final_task: Task) -> 'DAG':
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

            # Traverse dependencies
            for dep in task.dependencies:
                traverse(dep)

        traverse(final_task)
        return cls(tasks)

    @classmethod
    def from_tasks(cls, tasks: list[Task]) -> 'DAG':
        """Build DAG from explicit list of tasks."""
        return cls(tasks)

    def _validate(self):
        """Validate that the graph is acyclic."""
        # Check for cycles using DFS
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
            List of tasks in order such that all dependencies come before dependents
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
        Group tasks into execution stages.

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
```

---

## Composition Patterns

### 1. Sequential Pipeline

```python
@pipeline(name="sequential")
def build_sequential():
    """Linear chain of tasks."""
    task1 = Task(fn1, executor=local_exec, inputs={"source": raw_data})
    task2 = Task(fn2, executor=lambda_exec, inputs={"df": task1})
    task3 = Task(fn3, executor=local_exec, inputs={"df": task2})
    return task3

# DAG: task1 -> task2 -> task3
```

### 2. Parallel Pipeline (Fan-Out)

```python
@pipeline(name="parallel")
def build_parallel():
    """Multiple tasks depend on same input."""
    extract = Task(extract_fn, executor=local_exec, inputs={"source": raw_data})

    # All three depend on extract, can run in parallel
    stats = Task(stats_fn, executor=lambda_exec, inputs={"df": extract})
    features = Task(features_fn, executor=lambda_exec, inputs={"df": extract})
    validation = Task(validate_fn, executor=lambda_exec, inputs={"df": extract})

    # Wait for all three
    report = Task(
        report_fn,
        executor=local_exec,
        inputs={"stats": stats, "features": features, "validation": validation}
    )

    return report

# DAG:
#           -> stats ------\
#          /                \
# extract --> features ----> report
#          \                /
#           -> validation -/
```

### 3. Join Pipeline (Fan-In)

```python
@pipeline(name="join")
def build_join():
    """Multiple inputs to one task."""
    sales = Task(load_sales_fn, executor=local_exec, inputs={"source": sales_bucket})
    customers = Task(load_customers_fn, executor=local_exec, inputs={"source": customer_bucket})
    products = Task(load_products_fn, executor=local_exec, inputs={"source": product_bucket})

    # Join all three
    joined = Task(
        join_fn,
        executor=spark_exec,
        inputs={"sales": sales, "customers": customers, "products": products}
    )

    return joined

# DAG:
# load_sales -----\
# load_customers --> join
# load_products --/
```

### 4. Diamond Pipeline

```python
@pipeline(name="diamond")
def build_diamond():
    """Fork and join pattern."""
    extract = Task(extract_fn, executor=local_exec, inputs={"source": raw_data})

    # Fork
    branch1 = Task(transform1_fn, executor=lambda_exec, inputs={"df": extract})
    branch2 = Task(transform2_fn, executor=lambda_exec, inputs={"df": extract})

    # Join
    merged = Task(
        merge_fn,
        executor=local_exec,
        inputs={"df1": branch1, "df2": branch2}
    )

    return merged

# DAG:
#         -> branch1 --\
#        /              \
# extract               -> merged
#        \              /
#         -> branch2 --/
```

### 5. Multi-Output Tasks

For tasks that produce multiple outputs, use a wrapper:

```python
def split_data_fn(df: pl.LazyFrame) -> tuple[pl.LazyFrame, pl.LazyFrame]:
    """Split into train and test."""
    train = df.filter(pl.col("split") == "train")
    test = df.filter(pl.col("split") == "test")
    return train, test

@pipeline(name="ml")
def build_ml_pipeline():
    load = Task(load_fn, executor=local_exec, inputs={"source": data})

    # Task that produces multiple outputs
    split = Task(split_data_fn, executor=local_exec, inputs={"df": load})

    # Access outputs by index or attribute
    train_model = Task(
        train_fn,
        executor=databricks_exec,
        inputs={"df": split.output(0)}  # or split["train"]
    )

    evaluate = Task(
        eval_fn,
        executor=local_exec,
        inputs={"model": train_model, "test_df": split.output(1)}  # or split["test"]
    )

    return evaluate
```

### 6. Conditional Logic

Use Python conditionals in the builder:

```python
@pipeline(name="conditional")
def build_conditional(mode: str):
    """Different pipeline structure based on mode."""
    extract = Task(extract_fn, executor=local_exec, inputs={"source": raw_data})

    if mode == "full":
        transform = Task(full_transform_fn, executor=spark_exec, inputs={"df": extract})
    else:
        transform = Task(quick_transform_fn, executor=lambda_exec, inputs={"df": extract})

    load = Task(load_fn, executor=local_exec, inputs={"df": transform})
    return load
```

### 7. Dynamic Task Generation

Generate tasks in loops:

```python
@pipeline(name="dynamic")
def build_dynamic(file_list: list[str]):
    """Process multiple files in parallel."""
    # Load task
    load = Task(list_files_fn, executor=local_exec, inputs={"bucket": data_bucket})

    # Create a task for each file
    process_tasks = []
    for i, file_path in enumerate(file_list):
        task = Task(
            process_file_fn,
            executor=lambda_exec,
            inputs={"file_path": file_path},
            name=f"process_{i}"
        )
        process_tasks.append(task)

    # Combine results
    combine = Task(
        combine_fn,
        executor=local_exec,
        inputs={"results": process_tasks}  # List of tasks as input
    )

    return combine
```

---

## Implementation Specification

### 1. Task Class

**File:** `glacier/core/task.py`

```python
from typing import Callable, Any
from dataclasses import dataclass

class Task:
    """
    A task in a Glacier pipeline.

    Tasks wrap functions and track dependencies to form a DAG.
    """

    def __init__(
        self,
        func: Callable,
        executor: "ExecutionResource",
        inputs: dict[str, Any] | None = None,
        name: str | None = None,
        timeout: int | None = None,
        retries: int = 0,
        cache: bool = False,
        **kwargs
    ):
        self.func = func
        self.executor = executor
        self.inputs = inputs or {}
        self.name = name or func.__name__
        self.timeout = timeout
        self.retries = retries
        self.cache = cache
        self.config = kwargs

        # Extract dependencies
        self.dependencies = self._extract_dependencies()

        # Store signature for validation
        self.signature = inspect.signature(func)

    def _extract_dependencies(self) -> list["Task"]:
        """Extract upstream Task dependencies from inputs."""
        deps = []
        for value in self.inputs.values():
            if isinstance(value, Task):
                deps.append(value)
            elif isinstance(value, (list, tuple)):
                # Handle list/tuple of tasks
                deps.extend(v for v in value if isinstance(v, Task))
        return deps

    def execute(self, context: "ExecutionContext") -> Any:
        """Execute this task with resolved inputs."""
        resolved_inputs = {}

        for param_name, value in self.inputs.items():
            if isinstance(value, Task):
                # Get upstream task output
                resolved_inputs[param_name] = context.get_output(value)
            elif isinstance(value, (list, tuple)):
                # Handle lists of tasks
                resolved_inputs[param_name] = [
                    context.get_output(v) if isinstance(v, Task) else v
                    for v in value
                ]
            else:
                # Use value directly
                resolved_inputs[param_name] = value

        # Execute function
        return self.func(**resolved_inputs)

    def output(self, index: int = 0) -> "TaskOutput":
        """
        Get a specific output from this task (for multi-output tasks).

        Args:
            index: Output index (0 for first output, 1 for second, etc.)

        Returns:
            TaskOutput object that can be used as input to other tasks
        """
        return TaskOutput(task=self, index=index)

    def __getitem__(self, key: str | int) -> "TaskOutput":
        """Support task["output_name"] or task[0] syntax."""
        if isinstance(key, int):
            return self.output(key)
        return TaskOutput(task=self, key=key)

    def __repr__(self) -> str:
        deps = [t.name for t in self.dependencies]
        return f"Task(name='{self.name}', executor={self.executor.type}, deps={deps})"


@dataclass
class TaskOutput:
    """
    Represents a specific output from a task.

    Used when a task produces multiple outputs and you need to
    reference a specific one.
    """
    task: Task
    index: int | None = None
    key: str | None = None

    def resolve(self, context: "ExecutionContext") -> Any:
        """Resolve this output from the execution context."""
        result = context.get_output(self.task)

        if self.index is not None:
            return result[self.index]
        elif self.key is not None:
            return result[self.key]
        else:
            return result
```

### 2. Pipeline Decorator and Class

**File:** `glacier/core/pipeline.py`

```python
from typing import Callable
from functools import wraps

def pipeline(name: str, description: str | None = None, **config) -> Callable:
    """
    Decorator for defining pipelines.

    The decorated function should build and return a Task DAG.

    Usage:
        @pipeline(name="etl")
        def build_etl():
            task1 = Task(fn1, ...)
            task2 = Task(fn2, inputs={"data": task1})
            return task2

    Args:
        name: Pipeline name
        description: Optional description
        **config: Additional configuration

    Returns:
        Pipeline object
    """
    def decorator(func: Callable) -> Pipeline:
        return Pipeline(
            name=name,
            builder=func,
            description=description,
            config=config
        )

    return decorator


class Pipeline:
    """A Glacier pipeline - a DAG of tasks."""

    def __init__(
        self,
        name: str,
        builder: Callable,
        description: str | None = None,
        config: dict | None = None
    ):
        self.name = name
        self.builder = builder
        self.description = description or inspect.getdoc(builder)
        self.config = config or {}
        self._dag = None

    def build(self) -> "DAG":
        """Build the DAG by calling the builder function."""
        if self._dag is None:
            result = self.builder()

            if isinstance(result, Task):
                self._dag = DAG.from_task(result)
            elif isinstance(result, list):
                self._dag = DAG.from_tasks(result)
            else:
                raise ValueError(
                    f"Pipeline builder must return Task or list[Task], got {type(result)}"
                )

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
            return PipelineAnalysis(dag)

        elif mode == "generate":
            from glacier.codegen.terraform import TerraformGenerator
            generator = TerraformGenerator(dag)
            return generator.generate(**kwargs)

        else:
            raise ValueError(f"Unknown mode: {mode}")

    def visualize(self) -> str:
        """Generate a visualization of the pipeline DAG."""
        dag = self.build()
        return dag.to_mermaid()

    def __repr__(self) -> str:
        return f"Pipeline(name='{self.name}')"
```

### 3. ExecutionResource.task() Method

**File:** `glacier/resources/base.py`

```python
class ExecutionResource:
    """Base class for execution resources."""

    def task(
        self,
        func: Callable | None = None,
        *,
        inputs: dict[str, Any] | None = None,
        name: str | None = None,
        **config
    ) -> Task | Callable:
        """
        Create a Task bound to this execution resource.

        Can be used as:
        1. Decorator: @executor.task(inputs={...})
        2. Direct call: executor.task(func, inputs={...})

        Args:
            func: Function to wrap
            inputs: Dict of inputs (param_name -> value or Task)
            name: Optional task name
            **config: Additional config (timeout, retries, etc.)

        Returns:
            Task object or decorator function
        """
        def create_task(f: Callable) -> Task:
            return Task(
                func=f,
                executor=self,
                inputs=inputs or {},
                name=name or f.__name__,
                **config
            )

        if func is None:
            # Used as decorator: @executor.task(inputs={...})
            return create_task
        else:
            # Direct call: executor.task(func, inputs={...})
            return create_task(func)
```

### 4. DAG Class

**File:** `glacier/core/dag.py`

```python
class DAG:
    """Directed Acyclic Graph of tasks."""

    def __init__(self, tasks: list[Task]):
        self.tasks = tasks
        self._validate()

    @classmethod
    def from_task(cls, final_task: Task) -> "DAG":
        """Build DAG by traversing from final task."""
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
        """Build DAG from list of tasks."""
        # Collect all tasks and their dependencies
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
        """Validate that graph is acyclic."""
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
        """Return tasks in execution order."""
        in_degree = {task: len(task.dependencies) for task in self.tasks}
        queue = [task for task in self.tasks if in_degree[task] == 0]
        result = []

        while queue:
            task = queue.pop(0)
            result.append(task)

            for other in self.tasks:
                if task in other.dependencies:
                    in_degree[other] -= 1
                    if in_degree[other] == 0:
                        queue.append(other)

        return result

    def get_stages(self) -> list[list[Task]]:
        """Group tasks into parallel execution stages."""
        stages = []
        remaining = set(self.tasks)

        while remaining:
            stage = []
            for task in list(remaining):
                if all(dep not in remaining for dep in task.dependencies):
                    stage.append(task)

            stages.append(stage)
            remaining -= set(stage)

        return stages

    def to_mermaid(self) -> str:
        """Generate Mermaid diagram."""
        lines = ["graph TD"]
        for task in self.tasks:
            node_id = task.name.replace(" ", "_")
            lines.append(f"    {node_id}[\"{task.name}<br/>({task.executor.type})\"]")
            for dep in task.dependencies:
                dep_id = dep.name.replace(" ", "_")
                lines.append(f"    {dep_id} --> {node_id}")
        return "\n".join(lines)
```

### 5. Execution Context

**File:** `glacier/runtime/context.py`

```python
class ExecutionContext:
    """
    Context for executing a pipeline.

    Stores task outputs and manages execution state.
    """

    def __init__(self):
        self._outputs: dict[Task, Any] = {}

    def set_output(self, task: Task, output: Any):
        """Store the output of a task."""
        self._outputs[task] = output

    def get_output(self, task: Task) -> Any:
        """Get the output of a task."""
        if task not in self._outputs:
            raise ValueError(f"Task '{task.name}' has not been executed yet")
        return self._outputs[task]

    def has_output(self, task: Task) -> bool:
        """Check if a task has been executed."""
        return task in self._outputs
```

### 6. Export from glacier/__init__.py

```python
from glacier.providers import Provider
from glacier.core.pipeline import pipeline
from glacier.core.task import Task

__all__ = ["Provider", "pipeline", "Task"]
```

---

## Summary

### Core Principles

1. **Tasks are objects** - wrap functions, track dependencies
2. **Explicit composition** - users declare the DAG structure
3. **No AST analysis** - DAG is built from explicit Task objects
4. **Declarative builders** - pipeline functions construct and return DAGs
5. **Clear execution model** - build DAG, then execute it

### Usage Pattern

```python
# 1. Define functions (pure: LazyFrame -> LazyFrame)
def extract_fn(source): ...
def transform_fn(df): ...

# 2. Build pipeline - create Task objects with explicit inputs
@pipeline(name="etl")
def build_etl():
    extract = Task(extract_fn, executor=local_exec, inputs={"source": raw_data})
    transform = Task(transform_fn, executor=lambda_exec, inputs={"df": extract})
    return transform

# 3. Execute
result = build_etl().run(mode="local")
```

### Benefits

- ✅ **No magic** - clear what depends on what
- ✅ **No AST parsing** - explicit DAG construction
- ✅ **Type safe** - tasks, executors, and inputs are typed
- ✅ **Debuggable** - can inspect Task objects before execution
- ✅ **Flexible** - easy to handle conditionals, loops, dynamic tasks
- ✅ **Analyzable** - DAG is explicit before execution
- ✅ **Testable** - can test individual tasks easily

---

**END OF DOCUMENT**
