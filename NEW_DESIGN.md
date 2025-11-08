# Glacier: New Design - Infrastructure from Code

## Overview

We've redesigned Glacier from first principles based on the fundamental building blocks of data pipelines:
- **Input**: Data coming in
- **Logic**: Functions that transform data
- **Output**: Data going out

The key insight: a pipeline is just functions where the output of one becomes the input to another. The DAG emerges naturally from these connections.

## Core Principles

1. **Datasets in Signatures**: Type hints declare what data flows through the pipeline
2. **Provider-Agnostic**: No cloud dependencies in the core API
3. **Functions as Tasks**: Decorated Python functions are the building blocks
4. **Automatic DAG Inference**: Pipeline structure inferred from type annotations
5. **Declarative**: Declare what you want, not how to build it

## The Three Elements

### 1. Dataset - Named Data Artifacts

```python
from glacier import Dataset

# Datasets are named data artifacts
raw_data = Dataset("raw_data")
clean_data = Dataset("clean_data")
metrics = Dataset("metrics")
```

Datasets can optionally include storage and schema information:

```python
from glacier.storage import S3

raw_data = Dataset(
    name="raw_data",
    storage=S3(bucket="my-bucket", prefix="raw/"),
    schema=RawSchema
)
```

### 2. Task - Functions with Type Hints

```python
from glacier import task, compute

@task(compute=compute.local())
def extract() -> raw_data:
    """Functions declare what they produce via return type"""
    return fetch_from_api()

@task(compute=compute.serverless(memory=1024))
def transform(data: raw_data) -> clean_data:
    """Functions declare what they consume via parameters"""
    return process(data)

@task(compute=compute.container(image="analytics:latest", cpu=4))
def analyze(data: clean_data) -> metrics:
    """Heavy computation in containers"""
    return calculate(data)
```

The decorator specifies **execution context** (where/how to run), while the signature specifies **data dependencies** (what data flows through).

### 3. Pipeline - Automatic DAG Construction

```python
from glacier import Pipeline

# Just list the tasks - DAG is inferred from signatures!
pipeline = Pipeline(
    tasks=[extract, transform, analyze],
    name="analytics-pipeline"
)

# The pipeline knows:
# extract() -> raw_data -> transform() -> clean_data -> analyze()
```

## Complex DAG Support

The design naturally handles any DAG structure:

### Fan-In (Multiple Inputs)

```python
users = Dataset("users")
orders = Dataset("orders")
merged = Dataset("merged")

@task
def extract_users() -> users:
    return fetch_users()

@task
def extract_orders() -> orders:
    return fetch_orders()

@task
def merge(user_data: users, order_data: orders) -> merged:
    """Takes TWO inputs - DAG infers both dependencies"""
    return join(user_data, order_data)

pipeline = Pipeline([extract_users, extract_orders, merge])
# Infers: extract_users -> users ----\
#                                      +-> merge
#         extract_orders -> orders ---/
```

### Fan-Out (One Output to Multiple Tasks)

```python
raw = Dataset("raw")
summary = Dataset("summary")
details = Dataset("details")

@task
def extract() -> raw:
    return fetch_data()

@task
def summarize(data: raw) -> summary:
    return create_summary(data)

@task
def detail_report(data: raw) -> details:
    return create_details(data)

pipeline = Pipeline([extract, summarize, detail_report])
# Infers: extract -> raw --> summarize
#                       \--> detail_report
```

### Diamond Pattern

```python
@task
def source() -> a:
    return data

@task
def left(data: a) -> b:
    return process_left(data)

@task
def right(data: a) -> c:
    return process_right(data)

@task
def merge(l: b, r: c) -> d:
    return combine(l, r)

pipeline = Pipeline([source, left, right, merge])
# Infers:      source
#             /      \
#          left      right
#             \      /
#              merge
```

## Provider-Agnostic Compute

Compute resources are abstract - the provider is chosen at compile/execution time:

```python
from glacier import compute

# Local execution (for development)
@task(compute=compute.local(workers=4))
def my_task(data: input_data) -> output_data:
    return process(data)

# Container execution (maps to Docker, K8s, ECS, etc.)
@task(compute=compute.container(
    image="python:3.11",
    cpu=2.0,
    memory=4096
))
def heavy_task(data: input_data) -> output_data:
    return expensive_operation(data)

# Serverless execution (maps to Lambda, Cloud Functions, etc.)
@task(compute=compute.serverless(
    memory=1024,
    timeout=300
))
def light_task(data: input_data) -> output_data:
    return quick_operation(data)
```

## Pipeline Operations

```python
# Create pipeline
pipeline = Pipeline(tasks=[...], name="my-pipeline")

# Validate structure
pipeline.validate()  # Checks for cycles, missing producers, etc.

# Visualize
print(pipeline.visualize())

# Get execution order
for task in pipeline.get_execution_order():
    print(task.name)

# Analyze structure
source_tasks = pipeline.get_source_tasks()  # No dependencies
sink_tasks = pipeline.get_sink_tasks()      # No consumers

# Get dependencies
deps = pipeline.get_dependencies(some_task)
consumers = pipeline.get_consumers(some_task)
```

## Complete Example

```python
from glacier import Dataset, task, Pipeline, compute

# 1. Declare datasets
raw_users = Dataset("raw_users")
raw_orders = Dataset("raw_orders")
clean_users = Dataset("clean_users")
clean_orders = Dataset("clean_orders")
merged = Dataset("merged")
metrics = Dataset("metrics")

# 2. Define tasks
@task(compute=compute.serverless(memory=512))
def extract_users() -> raw_users:
    return fetch_users_from_api()

@task(compute=compute.serverless(memory=512))
def extract_orders() -> raw_orders:
    return fetch_orders_from_db()

@task(compute=compute.local())
def clean_users(users: raw_users) -> clean_users:
    return clean(users)

@task(compute=compute.local())
def clean_orders(orders: raw_orders) -> clean_orders:
    return clean(orders)

@task(compute=compute.container(image="spark:latest", cpu=4, memory=8192))
def merge_data(users: clean_users, orders: clean_orders) -> merged:
    return join(users, orders)

@task(compute=compute.container(image="analytics:latest", cpu=8))
def compute_metrics(data: merged) -> metrics:
    return calculate(data)

# 3. Create pipeline - DAG inferred automatically!
pipeline = Pipeline(
    tasks=[
        extract_users, extract_orders,
        clean_users, clean_orders,
        merge_data, compute_metrics
    ],
    name="analytics"
)

# 4. Validate
pipeline.validate()

# 5. Run or compile
# pipeline.run(executor=LocalExecutor())
# pipeline.compile(target=AWSTarget()).to_terraform("./infra")
```

The inferred DAG:
```
extract_users ──> clean_users ──┐
                                 ├─> merge_data ─> compute_metrics
extract_orders ─> clean_orders ─┘
```

## Benefits

1. **Ergonomic**: Natural Python with type hints
2. **Declarative**: Declare data flow, DAG inferred automatically
3. **Type-Safe**: IDEs can validate dataset references
4. **No Manual Wiring**: No explicit `connect()` or `depends_on`
5. **Provider-Agnostic**: Works locally or in any cloud
6. **Infrastructure from Code**: Datasets carry storage config, tasks carry compute config
7. **Handles Complex DAGs**: Fan-in, fan-out, diamonds all work naturally

## What's Next

This is the foundation. Still needed:
- Execution engine (local and distributed)
- Infrastructure compilation (Terraform, K8s, etc.)
- Storage resource implementations
- Provider adapters (AWS, GCP, Azure, local)
- Schema validation
- Data lineage tracking
- Testing utilities

But the core pattern is solid and extensible!
