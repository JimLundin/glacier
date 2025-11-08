# Glacier 🏔️

**Infrastructure-from-code data pipeline library**

Define data pipelines using pure Python with type hints. The infrastructure emerges from your code.

**⚠️ ALPHA SOFTWARE** - API may change. No backwards compatibility guarantees until v1.0.

---

## Philosophy

**Type-Driven Pipeline Definition** - Declare your datasets and annotate your functions with what data they consume and produce. The DAG builds itself from your type hints. No manual wiring, no magic strings, no boilerplate.

**Infrastructure from Code** - Your pipeline definition IS your infrastructure definition. Datasets carry storage configuration, tasks carry compute configuration. Generate Terraform, Kubernetes manifests, or run locally from the same code.

**Provider-Agnostic Core** - The core API has zero cloud dependencies. Choose your provider (AWS, GCP, Azure, local) at compile/execution time, not in your pipeline code.

---

## Core Concepts

A data pipeline is fundamentally: **input → logic → output**

Glacier models this with three elements:

### 1. Dataset - Named Data Artifacts

```python
from glacier import Dataset

# Datasets are named data artifacts that flow through your pipeline
raw_data = Dataset("raw_data")
clean_data = Dataset("clean_data")
metrics = Dataset("metrics")
```

Optionally attach storage and schema configuration:

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
    """Type hint declares this produces raw_data"""
    return fetch_from_api()

@task(compute=compute.serverless(memory=1024))
def transform(data: raw_data) -> clean_data:
    """Type hints declare: consumes raw_data, produces clean_data"""
    return process(data)

@task(compute=compute.container(image="analytics:latest", cpu=4))
def analyze(data: clean_data) -> metrics:
    """Heavy computation in containers"""
    return calculate(data)
```

**Type hints declare data dependencies. Decorators declare execution context.**

### 3. Pipeline - Automatic DAG Inference

```python
from glacier import Pipeline

# Just list your tasks - the DAG is inferred from type hints!
pipeline = Pipeline(
    tasks=[extract, transform, analyze],
    name="analytics"
)

# Glacier infers: extract() -> raw_data -> transform() -> clean_data -> analyze()
```

The pipeline automatically knows:
- `extract` has no inputs (it's a source)
- `transform` needs `raw_data` (produced by `extract`)
- `analyze` needs `clean_data` (produced by `transform`)

**No manual wiring. The DAG emerges from your type annotations.**

---

## Quick Start

### Simple Linear Pipeline

```python
from glacier import Dataset, task, Pipeline, compute

# 1. Declare your datasets
raw_users = Dataset("raw_users")
clean_users = Dataset("clean_users")
metrics = Dataset("metrics")

# 2. Define tasks - type hints declare data flow
@task(compute=compute.local())
def extract() -> raw_users:
    return fetch_users_from_api()

@task(compute=compute.local())
def clean(users: raw_users) -> clean_users:
    return [
        {**user, "name": user["name"].upper()}
        for user in users
    ]

@task(compute=compute.serverless(memory=512))
def compute_metrics(users: clean_users) -> metrics:
    return {
        "total": len(users),
        "avg_age": sum(u["age"] for u in users) / len(users)
    }

# 3. Create pipeline - DAG inferred automatically
pipeline = Pipeline(
    tasks=[extract, clean, compute_metrics],
    name="user-analytics"
)

# 4. Validate and visualize
pipeline.validate()
print(pipeline.visualize())

# The inferred DAG:
# extract() -> raw_users -> clean() -> clean_users -> compute_metrics()
```

### Complex DAG with Fan-In and Fan-Out

```python
from glacier import Dataset, task, Pipeline, compute

# Datasets
raw_users = Dataset("raw_users")
raw_orders = Dataset("raw_orders")
clean_users = Dataset("clean_users")
clean_orders = Dataset("clean_orders")
merged = Dataset("merged")
summary = Dataset("summary")
details = Dataset("details")

# Source tasks (parallel)
@task(compute=compute.serverless(memory=512))
def extract_users() -> raw_users:
    return fetch_users()

@task(compute=compute.serverless(memory=512))
def extract_orders() -> raw_orders:
    return fetch_orders()

# Transform tasks (parallel)
@task(compute=compute.local())
def clean_users(users: raw_users) -> clean_users:
    return clean(users)

@task(compute=compute.local())
def clean_orders(orders: raw_orders) -> clean_orders:
    return clean(orders)

# Fan-in: Multiple inputs → one output
@task(compute=compute.container(image="spark:latest", cpu=4, memory=8192))
def merge(users: clean_users, orders: clean_orders) -> merged:
    """Takes TWO inputs - DAG infers both dependencies automatically!"""
    return join(users, orders)

# Fan-out: One input → multiple outputs
@task(compute=compute.local())
def summarize(data: merged) -> summary:
    return create_summary(data)

@task(compute=compute.local())
def detail_report(data: merged) -> details:
    return create_details(data)

# Pipeline infers this DAG:
#
# extract_users  -> clean_users  ──┐
#                                   ├─> merge ──┬─> summarize
# extract_orders -> clean_orders ──┘            └─> detail_report

pipeline = Pipeline(
    tasks=[
        extract_users, extract_orders,
        clean_users, clean_orders,
        merge, summarize, detail_report
    ],
    name="complex-analytics"
)
```

**No `connect()` calls. No manual edge definitions. The DAG is implicit in your type hints.**

---

## Provider-Agnostic Compute

Compute resources are abstract. The actual provider is chosen at compile/execution time:

```python
from glacier import compute

# Local process (for development)
@task(compute=compute.local(workers=4))
def my_task(data: input_data) -> output_data:
    return process(data)

# Container (maps to Docker, Kubernetes, ECS, Cloud Run, etc.)
@task(compute=compute.container(
    image="python:3.11",
    cpu=2.0,
    memory=4096
))
def heavy_task(data: input_data) -> output_data:
    return expensive_operation(data)

# Serverless (maps to Lambda, Cloud Functions, Azure Functions, etc.)
@task(compute=compute.serverless(
    memory=1024,
    timeout=300
))
def light_task(data: input_data) -> output_data:
    return quick_operation(data)
```

The same task definitions work everywhere. Choose your target when you compile or execute:

```python
# Run locally
pipeline.run(executor=LocalExecutor())

# Generate AWS infrastructure
pipeline.compile(target=AWSTarget()).to_terraform("./infra")

# Generate Kubernetes manifests
pipeline.compile(target=KubernetesTarget()).to_yaml("./k8s")
```

---

## Pipeline Operations

```python
# Create pipeline
pipeline = Pipeline(tasks=[...], name="my-pipeline")

# Validate structure (checks for cycles, missing producers, etc.)
pipeline.validate()

# Visualize the DAG
print(pipeline.visualize())

# Get topological execution order
for task in pipeline.get_execution_order():
    print(f"Execute: {task.name}")

# Analyze structure
sources = pipeline.get_source_tasks()  # Tasks with no dependencies
sinks = pipeline.get_sink_tasks()      # Tasks with no consumers

# Get task relationships
deps = pipeline.get_dependencies(some_task)
consumers = pipeline.get_consumers(some_task)
```

---

## Examples

See [examples/](./examples/) for complete working examples:

- **simple_pipeline.py** - Basic linear ETL pipeline
- **complex_dag.py** - Fan-in, fan-out, diamond patterns, multiple sources

Run them:

```bash
python examples/simple_pipeline.py
python examples/complex_dag.py
```

---

## What Makes Glacier Different

**1. Type-Driven DAG Construction**
- No manual `depends_on` or `connect()` calls
- DAG emerges from function signatures
- IDE autocomplete and type checking for datasets

**2. Functions are Tasks**
- No special task classes to learn
- Just Python functions with decorators
- Natural composition

**3. Truly Provider-Agnostic**
- Zero cloud dependencies in your pipeline code
- Same code runs locally or in any cloud
- Provider chosen at compile/execution time

**4. Infrastructure from Code**
- Datasets carry storage configuration
- Tasks carry compute configuration
- Generate Terraform/K8s from pipeline definitions

**5. Handles Complex DAGs Naturally**
- Fan-in: `def merge(a: dataset_a, b: dataset_b) -> merged`
- Fan-out: Multiple tasks depend on same dataset
- Diamonds: Any arbitrary DAG structure

---

## Architecture

For detailed design documentation, see [NEW_DESIGN.md](./NEW_DESIGN.md)

Key components:

- `glacier/core/dataset.py` - Dataset abstraction
- `glacier/core/task.py` - Task decorator and signature inspection
- `glacier/core/pipeline.py` - Pipeline with DAG inference
- `glacier/compute/` - Provider-agnostic compute resources

---

## Installation

```bash
# Clone the repository
git clone https://github.com/JimLundin/glacier.git
cd glacier

# Install in development mode
pip install -e .
```

---

## Current Status

**Implemented:**
- ✅ Dataset abstraction with storage/schema support
- ✅ Task decorator with type hint inspection
- ✅ Automatic DAG inference from signatures
- ✅ Complex DAG support (fan-in, fan-out, diamonds)
- ✅ Cycle detection and validation
- ✅ Topological sorting
- ✅ Provider-agnostic compute resources

**Coming Soon:**
- 🚧 Local execution engine
- 🚧 Distributed execution
- 🚧 Infrastructure compilation (Terraform, K8s)
- 🚧 Storage resource implementations
- 🚧 Provider adapters (AWS, GCP, Azure)
- 🚧 Schema validation
- 🚧 Data lineage tracking

---

## License

MIT License - see [LICENSE](./LICENSE) for details.
