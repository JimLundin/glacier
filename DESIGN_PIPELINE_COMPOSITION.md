# Pipeline Composition Design

**Status:** Design Document
**Date:** 2025-11-06
**Related:** DESIGN_UX.md

---

## Executive Summary

This document defines how pipelines are composed in Glacier. Pipelines orchestrate multiple tasks, define data flow, express dependencies, and enable heterogeneous execution across different compute resources.

**Key Principle:** Pipelines are Python functions that compose tasks. The DAG is built automatically by analyzing data flow within the pipeline function.

---

## Table of Contents

1. [Problem Statement](#problem-statement)
2. [Design Goals](#design-goals)
3. [Core Pattern](#core-pattern)
4. [Composition Patterns](#composition-patterns)
5. [DAG Building](#dag-building)
6. [Execution Modes](#execution-modes)
7. [Implementation Requirements](#implementation-requirements)

---

## Problem Statement

### Current Issues

The current approach has several problems:

1. **Conflicting Patterns**:
   - DESIGN_UX.md specifies `@pipeline(name="...")` global decorator
   - Implementation uses `@env.pipeline()` environment-bound decorator
   - Examples show desired pattern, but code doesn't support it

2. **String-Based Executors**:
   - Current: `@env.task(executor="databricks")` (string identifier)
   - Desired: `@databricks_exec.task()` (first-class resource object)

3. **No Clear DAG Building Strategy**:
   - How are dependencies discovered?
   - How are tasks tracked within pipelines?
   - How is data flow analyzed?

4. **Limited Composition Expressiveness**:
   - Just function calls with return values
   - No explicit parallel execution
   - No conditional branching
   - No dynamic task generation

### What We Need

A pipeline composition pattern that:

- **Feels like Python** - Natural function composition
- **Builds DAGs automatically** - No manual dependency wiring
- **Enables heterogeneous execution** - Mix local, Lambda, Spark, Databricks, etc.
- **Supports parallelism** - Express when tasks can run concurrently
- **Is analyzable** - Can be inspected without execution
- **Generates infrastructure** - Can produce Terraform/CloudFormation from pipeline definitions

---

## Design Goals

### 1. Pythonic Composition

Pipelines should look and feel like normal Python code:

```python
@pipeline(name="etl")
def etl_pipeline():
    raw = extract(source)
    cleaned = clean(raw)
    result = transform(cleaned)
    save(result)
    return result
```

### 2. Explicit Execution Binding

Tasks are bound to execution resources, not string identifiers:

```python
local_exec = provider.local()
lambda_exec = provider.serverless(config=LambdaConfig(...))

@local_exec.task()
def extract(source):
    return source.scan()

@lambda_exec.task()
def clean(df):
    return df.filter(...)
```

### 3. Automatic DAG Construction

The DAG is built by analyzing:
- Function calls within the pipeline
- Data dependencies (what data flows where)
- Task execution resources (where each task runs)

### 4. Static Analysis

Pipelines can be analyzed WITHOUT execution:

```python
# Analyze without running
analysis = etl_pipeline.analyze()
print(analysis.dag)           # Task dependency graph
print(analysis.executors)     # Execution resources used
print(analysis.data_sources)  # Storage resources accessed
```

### 5. Multiple Execution Modes

Same pipeline, different modes:

```python
# Local execution (for development/testing)
result = etl_pipeline.run(mode="local")

# Generate infrastructure code
etl_pipeline.run(mode="generate", output_dir="./infra")

# Deploy to cloud orchestrator
etl_pipeline.run(mode="deploy", orchestrator="airflow")
```

---

## Core Pattern

### Components

A Glacier pipeline consists of:

1. **Provider** - Creates resources (storage + execution)
2. **Execution Resources** - Where code runs (local, serverless, vm, cluster)
3. **Storage Resources** - Where data lives (buckets)
4. **Tasks** - Functions bound to execution resources
5. **Pipeline** - Function that orchestrates tasks
6. **DAG** - Automatically built from pipeline function

### Complete Example

```python
from glacier import Provider, pipeline
from glacier.config import AwsConfig, LambdaConfig, DatabricksConfig
import polars as pl

# 1. Create provider
provider = Provider(config=AwsConfig(region="us-east-1"))

# 2. Create execution resources (first-class objects)
local_exec = provider.local()
lambda_exec = provider.serverless(config=LambdaConfig(memory=1024))
databricks_exec = provider.cluster(config=DatabricksConfig(cluster_id="cluster-123"))

# 3. Create storage resources
raw_data = provider.bucket(bucket="data-lake", path="raw/data.parquet")
output = provider.bucket(bucket="data-lake", path="output/result.parquet")

# 4. Define tasks bound to execution resources
@local_exec.task()
def extract(source) -> pl.LazyFrame:
    """Extract data from S3. Runs on local Python."""
    return source.scan()

@lambda_exec.task()
def clean(df: pl.LazyFrame) -> pl.LazyFrame:
    """Clean data. Runs on Lambda."""
    return df.filter(pl.col("value").is_not_null())

@databricks_exec.task()
def ml_predict(df: pl.LazyFrame) -> pl.LazyFrame:
    """ML inference. Runs on Databricks cluster."""
    return df.with_columns(pl.lit(0.85).alias("prediction"))

@local_exec.task()
def save(df: pl.LazyFrame, destination) -> None:
    """Save results to S3. Runs on local Python."""
    df.collect().write_parquet(destination.get_uri())

# 5. Define pipeline - compose tasks
@pipeline(name="ml_inference")
def ml_pipeline():
    """
    ML inference pipeline with heterogeneous execution.

    DAG is built automatically from data flow:
    extract -> clean -> ml_predict -> save
    """
    # Data flows through tasks
    raw = extract(raw_data)
    cleaned = clean(raw)
    predictions = ml_predict(cleaned)
    save(predictions, output)

    return predictions

# 6. Execute
result = ml_pipeline.run(mode="local")
```

### Key Design Decisions

#### 1. Tasks Return Data

Tasks return data (LazyFrames), not Task objects:

```python
# ✅ CORRECT: Returns data
@local_exec.task()
def extract(source) -> pl.LazyFrame:
    return source.scan()

raw = extract(source)  # raw is pl.LazyFrame
cleaned = clean(raw)   # Pass data, not task

# ❌ WRONG: Returns task object
@task
def extract(source):
    return source.scan()

task1 = extract(source)  # task1 is Task object
task2 = clean(task1)     # Pass task, not data
```

**Rationale:**
- More Pythonic - functions return their actual results
- Type hints work correctly
- IDE autocomplete works
- Easier to test individual tasks
- DAG is built by intercepting calls, not from task objects

#### 2. DAG Built via Call Interception

When `ml_pipeline.run()` is called, Glacier:

1. Enters "pipeline context" mode
2. Tracks all task calls within the pipeline function
3. Records data dependencies between tasks
4. Builds DAG from the call graph
5. Executes tasks in topological order (respecting dependencies)

```python
# Execution flow:
# 1. ml_pipeline.run() enters pipeline context
# 2. extract(raw_data) is called -> tracked
# 3. clean(raw) is called -> tracked (depends on extract)
# 4. ml_predict(cleaned) is called -> tracked (depends on clean)
# 5. save(predictions, output) is called -> tracked (depends on ml_predict)
# 6. DAG built: extract -> clean -> ml_predict -> save
# 7. Tasks executed in order
```

#### 3. Global @pipeline Decorator

Pipelines use a global `@pipeline` decorator, NOT `@env.pipeline()`:

```python
# ✅ CORRECT: Global decorator
from glacier import pipeline

@pipeline(name="etl")
def etl_pipeline():
    return process(data)

# ❌ WRONG: Environment-bound (old pattern)
env = GlacierEnv(provider=provider)

@env.pipeline()  # NO - GlacierEnv should not exist in user API
def etl_pipeline():
    return process(data)
```

**Rationale:**
- Aligns with DESIGN_UX.md
- Resources (both storage and execution) passed directly, no registry needed
- Simpler API
- No GlacierEnv in user-facing code

---

## Composition Patterns

### 1. Sequential Composition (Basic)

Default pattern - tasks run in sequence:

```python
@pipeline(name="sequential")
def sequential_pipeline():
    a = task_a(input1)
    b = task_b(a)
    c = task_c(b)
    return c

# DAG: task_a -> task_b -> task_c
```

### 2. Parallel Composition (Fan-Out)

Multiple tasks depend on same input:

```python
@pipeline(name="parallel")
def parallel_pipeline():
    raw = extract(source)

    # These can run in parallel - no dependencies between them
    stats = compute_stats(raw)
    features = compute_features(raw)
    validation = validate_data(raw)

    # Wait for all to complete
    report = generate_report(stats, features, validation)
    return report

# DAG:
#           -> compute_stats ----\
#          /                      \
# extract  --> compute_features --> generate_report
#          \                      /
#           -> validate_data ----/
```

### 3. Join Composition (Fan-In)

Multiple inputs to one task:

```python
@pipeline(name="join")
def join_pipeline():
    sales = load_sales(sales_bucket)
    customers = load_customers(customer_bucket)
    products = load_products(product_bucket)

    # Join all three
    enriched = join_data(sales, customers, products)
    return enriched

# DAG:
# load_sales -----\
# load_customers --> join_data
# load_products --/
```

### 4. Conditional Composition

Use Python conditionals:

```python
@pipeline(name="conditional")
def conditional_pipeline(mode: str):
    raw = extract(source)

    if mode == "full":
        result = full_transform(raw)
    else:
        result = quick_transform(raw)

    save(result)
    return result

# DAG depends on runtime mode parameter
# mode="full": extract -> full_transform -> save
# mode="quick": extract -> quick_transform -> save
```

### 5. Dynamic Task Generation

Generate tasks based on data:

```python
@pipeline(name="dynamic")
def dynamic_pipeline():
    # Get list of files to process
    files = list_files(bucket)

    # Process each file in parallel
    results = []
    for file in files:
        result = process_file(file)
        results.append(result)

    # Combine results
    final = combine_results(results)
    return final

# DAG has dynamic number of process_file tasks
# All process_file tasks can run in parallel
# combine_results waits for all
```

### 6. Multi-Output Tasks

Tasks that produce multiple outputs:

```python
@local_exec.task()
def split_data(df: pl.LazyFrame) -> tuple[pl.LazyFrame, pl.LazyFrame]:
    """Split data into train and test sets."""
    train = df.filter(pl.col("split") == "train")
    test = df.filter(pl.col("split") == "test")
    return train, test

@pipeline(name="multi_output")
def ml_pipeline():
    raw = load_data(source)
    train, test = split_data(raw)

    # Use both outputs
    model = train_model(train)
    metrics = evaluate_model(model, test)

    return metrics

# DAG:
# load_data -> split_data -> train_model -> evaluate_model
#                       \                 /
#                        `-------------->/
```

---

## DAG Building

### Static Analysis (Preferred)

Analyze pipeline function WITHOUT execution:

```python
@pipeline(name="etl")
def etl_pipeline():
    raw = extract(source)
    cleaned = clean(raw)
    result = transform(cleaned)
    return result

# Analyze without running
analysis = etl_pipeline.analyze()

print(analysis.dag.nodes)      # [extract, clean, transform]
print(analysis.dag.edges)      # [(extract, clean), (clean, transform)]
print(analysis.executors)      # {extract: local_exec, clean: lambda_exec, ...}
print(analysis.data_sources)   # [source]
```

**How it works:**

1. Parse pipeline function AST
2. Identify all task calls (functions decorated with `@executor.task()`)
3. Build dependency graph from data flow
4. Extract metadata (executors, sources, types)

**Benefits:**
- No execution needed
- Can validate before running
- Can generate infrastructure without data
- Works with conditional logic (all branches analyzed)

### Dynamic Tracking (Fallback)

If static analysis can't determine structure, use runtime tracking:

```python
# Complex dynamic logic
@pipeline(name="dynamic")
def complex_pipeline():
    tasks = get_tasks_from_database()  # Can't analyze statically

    results = []
    for task_config in tasks:
        result = dynamic_task(task_config)
        results.append(result)

    return combine(results)

# Run with tracking to build DAG
analysis = complex_pipeline.run(mode="analyze")
```

**How it works:**

1. Enter "tracking mode"
2. Execute pipeline function
3. Intercept all task calls
4. Record dependencies
5. Build DAG from tracked calls

### DAG Representation

```python
@dataclass
class DAGNode:
    """Represents a task in the DAG."""
    task: Task                    # The task object
    executor: ExecutionResource   # Where it runs
    inputs: List[DAGNode]         # Upstream dependencies
    outputs: List[DAGNode]        # Downstream consumers

@dataclass
class PipelineDAG:
    """Represents the complete pipeline DAG."""
    nodes: List[DAGNode]
    edges: List[Tuple[DAGNode, DAGNode]]
    sources: List[StorageResource]  # Data sources (buckets)
    sinks: List[StorageResource]    # Data destinations

    def topological_sort(self) -> List[DAGNode]:
        """Return tasks in execution order."""
        ...

    def parallelize(self) -> List[List[DAGNode]]:
        """Return tasks grouped by execution stage (parallelizable groups)."""
        ...

    def visualize(self) -> str:
        """Generate DOT/Mermaid visualization."""
        ...
```

---

## Execution Modes

### 1. Local Execution (`mode="local"`)

Execute all tasks locally (ignoring executors):

```python
result = ml_pipeline.run(mode="local")
```

**Behavior:**
- All tasks run in current Python process
- Executors are ignored (everything runs locally)
- Good for development and testing
- Fast iteration

### 2. Cloud Execution (`mode="cloud"`)

Execute tasks on their designated executors:

```python
result = ml_pipeline.run(mode="cloud")
```

**Behavior:**
- `@local_exec.task()` runs locally
- `@lambda_exec.task()` runs on Lambda
- `@databricks_exec.task()` runs on Databricks
- Data transferred between executors automatically
- Glacier handles serialization and data movement

### 3. Analysis (`mode="analyze"`)

Analyze pipeline structure without execution:

```python
analysis = ml_pipeline.run(mode="analyze")

print(f"Tasks: {analysis.dag.nodes}")
print(f"Dependencies: {analysis.dag.edges}")
print(f"Execution resources: {analysis.executors}")
print(f"Estimated cost: ${analysis.estimate_cost()}")
```

**Outputs:**
- DAG structure
- Execution resources used
- Data sources/sinks
- Estimated compute costs
- Infrastructure requirements

### 4. Infrastructure Generation (`mode="generate"`)

Generate infrastructure-as-code from pipeline:

```python
output = ml_pipeline.run(
    mode="generate",
    output_dir="./infra",
    format="terraform"  # or "cloudformation", "pulumi"
)

print(f"Generated: {output.files}")
# infra/
#   main.tf
#   lambda.tf
#   databricks.tf
#   s3.tf
```

**Generates:**
- Lambda functions (from `@lambda_exec.task()`)
- Databricks jobs (from `@databricks_exec.task()`)
- S3 buckets (from storage resources)
- IAM roles and policies
- Orchestration (Airflow/Step Functions DAG)

### 5. Deployment (`mode="deploy"`)

Deploy pipeline to orchestrator:

```python
deployment = ml_pipeline.run(
    mode="deploy",
    orchestrator="airflow",  # or "step_functions", "prefect", "dagster"
    schedule="0 0 * * *"     # Daily at midnight
)

print(f"Deployed to: {deployment.url}")
```

**Creates:**
- Airflow DAG definition
- AWS Step Functions state machine
- Prefect flow
- Dagster pipeline
- Includes all infrastructure

---

## Implementation Requirements

### 1. Global @pipeline Decorator

```python
# glacier/core/pipeline.py

def pipeline(
    name: str,
    description: str | None = None,
    config: dict[str, Any] | None = None
) -> Callable:
    """
    Decorator for defining pipelines.

    Creates a Pipeline object that can be analyzed and executed.
    """
    def decorator(func: Callable) -> Pipeline:
        pipeline_obj = Pipeline(
            func=func,
            name=name,
            description=description,
            config=config or {}
        )
        return pipeline_obj

    return decorator
```

Export from `glacier/__init__.py`:

```python
from glacier.core.pipeline import pipeline

__all__ = ["Provider", "pipeline", ...]
```

### 2. Execution Resource `.task()` Methods

```python
# glacier/resources/base.py

class ExecutionResource:
    """Base class for execution resources."""

    def task(
        self,
        func: Callable | None = None,
        *,
        name: str | None = None,
        timeout: int | None = None,
        retries: int = 0,
        cache: bool = False
    ) -> Callable:
        """
        Decorator to bind a task to this execution resource.

        @local_exec.task()
        def my_task(df):
            return df.filter(...)
        """
        def decorator(f: Callable) -> Callable:
            task_obj = Task(
                func=f,
                name=name or f.__name__,
                executor=self  # Bind to THIS execution resource
            )

            @wraps(f)
            def wrapper(*args, **kwargs):
                # Check if we're in pipeline context
                ctx = PipelineContext.get_current()
                if ctx:
                    # Track this task call in the pipeline
                    ctx.track_task_call(task_obj, args, kwargs)

                # Execute the task
                return task_obj(*args, **kwargs)

            wrapper._glacier_task = task_obj
            wrapper.task = task_obj

            return wrapper

        if func is None:
            return decorator
        return decorator(func)
```

### 3. Provider Creates Execution Resources

```python
# glacier/providers/provider.py

class Provider:
    """Single provider class - config determines behavior."""

    def local(self) -> LocalExecution:
        """Create local execution resource."""
        return LocalExecution(provider=self)

    def serverless(
        self,
        config: LambdaConfig | AzureFunctionConfig | CloudFunctionConfig
    ) -> ServerlessExecution:
        """Create serverless execution resource."""
        return ServerlessExecution(provider=self, config=config)

    def vm(
        self,
        config: EC2Config | ComputeEngineConfig | AzureVMConfig
    ) -> VMExecution:
        """Create VM execution resource."""
        return VMExecution(provider=self, config=config)

    def cluster(
        self,
        config: DatabricksConfig | SparkConfig | DataprocConfig | EMRConfig
    ) -> ClusterExecution:
        """Create cluster execution resource."""
        return ClusterExecution(provider=self, config=config)
```

### 4. Pipeline Context Tracking

```python
# glacier/core/context.py

class PipelineContext:
    """Context manager for tracking task calls within pipelines."""

    _current: Optional['PipelineContext'] = None

    def __init__(self, pipeline: Pipeline):
        self.pipeline = pipeline
        self.task_calls: List[TaskCall] = []
        self.dag: Optional[PipelineDAG] = None

    def track_task_call(
        self,
        task: Task,
        args: tuple,
        kwargs: dict
    ) -> None:
        """Track a task call and its dependencies."""
        call = TaskCall(task=task, args=args, kwargs=kwargs)
        self.task_calls.append(call)

    def build_dag(self) -> PipelineDAG:
        """Build DAG from tracked task calls."""
        # Analyze task_calls to build dependency graph
        ...

    @classmethod
    def get_current(cls) -> Optional['PipelineContext']:
        """Get the current pipeline context, if any."""
        return cls._current

    def __enter__(self):
        PipelineContext._current = self
        return self

    def __exit__(self, *args):
        PipelineContext._current = None
```

### 5. Pipeline.run() Implementation

```python
# glacier/core/pipeline.py

class Pipeline:
    def run(self, mode: str = "local", **kwargs) -> Any:
        """Execute pipeline in specified mode."""

        if mode == "local":
            return self._run_local(**kwargs)
        elif mode == "cloud":
            return self._run_cloud(**kwargs)
        elif mode == "analyze":
            return self._analyze(**kwargs)
        elif mode == "generate":
            return self._generate(**kwargs)
        elif mode == "deploy":
            return self._deploy(**kwargs)
        else:
            raise ValueError(f"Unknown mode: {mode}")

    def _run_local(self, **kwargs) -> Any:
        """Execute all tasks locally."""
        with PipelineContext(self) as ctx:
            # Execute pipeline function
            result = self.func(**kwargs)

            # Build DAG from tracked calls
            ctx.build_dag()

        return result

    def _analyze(self, **kwargs) -> PipelineAnalysis:
        """Analyze pipeline structure."""
        # Try static analysis first
        try:
            return self._static_analyze()
        except StaticAnalysisError:
            # Fall back to dynamic tracking
            return self._dynamic_analyze(**kwargs)
```

### 6. Static Analysis

```python
# glacier/codegen/analyzer.py

class PipelineAnalyzer:
    """Analyzes pipeline structure without execution."""

    def analyze(self, pipeline: Pipeline) -> PipelineAnalysis:
        """Analyze pipeline function using AST."""

        # 1. Parse function AST
        tree = ast.parse(inspect.getsource(pipeline.func))

        # 2. Find all task calls
        task_calls = self._find_task_calls(tree)

        # 3. Build dependency graph
        dag = self._build_dag(task_calls)

        # 4. Extract metadata
        executors = self._extract_executors(dag)
        sources = self._extract_sources(dag)

        return PipelineAnalysis(
            dag=dag,
            executors=executors,
            sources=sources,
            ...
        )
```

---

## Summary

### Core Principles

1. **Pipelines are Python functions** that compose tasks
2. **Tasks are bound to execution resources** via `@executor.task()`
3. **DAG is built automatically** from data flow analysis
4. **Resources are first-class objects** passed directly (no string names)
5. **Global @pipeline decorator** (no GlacierEnv in user API)
6. **Multiple execution modes** (local, cloud, analyze, generate, deploy)

### Pattern Overview

```python
# 1. Provider creates resources
provider = Provider(config=AwsConfig(...))
local_exec = provider.local()
lambda_exec = provider.serverless(config=LambdaConfig(...))
bucket = provider.bucket(bucket="data", path="file.parquet")

# 2. Tasks bound to execution resources
@local_exec.task()
def extract(source):
    return source.scan()

@lambda_exec.task()
def transform(df):
    return df.filter(...)

# 3. Pipeline composes tasks
@pipeline(name="etl")
def etl_pipeline():
    raw = extract(bucket)
    result = transform(raw)
    return result

# 4. Execute in different modes
etl_pipeline.run(mode="local")      # Local testing
etl_pipeline.run(mode="cloud")      # Cloud execution
etl_pipeline.run(mode="analyze")    # Analyze structure
etl_pipeline.run(mode="generate")   # Generate infrastructure
```

### Next Steps

1. ✅ Design completed (this document)
2. ⬜ Implement global `@pipeline` decorator
3. ⬜ Add `.task()` methods to execution resources
4. ⬜ Implement pipeline context tracking
5. ⬜ Build static analyzer
6. ⬜ Remove `GlacierEnv` from user-facing API
7. ⬜ Update examples to use new pattern
8. ⬜ Add tests for composition patterns

---

**END OF DOCUMENT**
