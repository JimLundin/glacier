# Glacier Code Structure Reference

## Current File Organization

```
glacier/
├── __init__.py                    # Main exports (Dataset, task, Task, Pipeline, compute)
│
├── core/                          # Core pipeline logic
│   ├── __init__.py
│   ├── dataset.py                # Dataset class (storage slot + schema + metadata)
│   ├── task.py                   # Task decorator & signature inspection
│   └── pipeline.py               # Pipeline with automatic DAG inference
│
└── compute/                       # Compute resources (FULLY IMPLEMENTED)
    ├── __init__.py               # Exports (ComputeResource, Local, Container, Serverless)
    └── resources.py              # ComputeResource ABC + 3 implementations
```

## Key File Locations & Contents

### 1. Dataset Abstraction
**File**: `/home/user/glacier/glacier/core/dataset.py` (116 lines)

**Key Classes**:
- `Dataset` - Named data artifacts
  - `name: str`
  - `storage: Optional['StorageResource']` - Forward reference (not yet implemented)
  - `schema: Optional[Any]`
  - `metadata: Optional[Dict[str, Any]]`
  - Methods: `set_value()`, `get_value()`, `validate()`, `is_materialized`

- `DatasetReference` - Internal DAG reference tracking

**Design Pattern**: Placeholder for storage abstraction
- Storage interface NOT YET DEFINED
- Expected from README/NEW_DESIGN: S3, GCS, AzureBlob, Local implementations
- Follows same pattern as compute resources (capability-based)

### 2. Task Declaration
**File**: `/home/user/glacier/glacier/core/task.py` (166 lines)

**Key Classes**:
- `Task` - Wraps user functions
  - `fn: Callable` - Wrapped function
  - `config: dict` - Stores decorator parameters (includes compute)
  - `inputs: List[DatasetParameter]` - Extracted from function parameters
  - `outputs: List[Dataset]` - Extracted from return annotation
  - Method: `_extract_datasets()` - Type hint inspection
  - Method: `execute(**input_datasets)` - Runs function with validation

- `DatasetParameter` - Represents input parameters
  - `name: str`
  - `dataset: Dataset`

**Key Function**:
- `task()` decorator - Creates Task instances
  - Accepts `fn` and `**config` (including `compute`)
  - Returns Task wrapping the function
  - Supports `@task` and `@task(compute=...)` syntax

**Design Pattern**: Type signature as data flow declaration
- Parameters with Dataset type hints = inputs
- Return type with Dataset annotation = outputs
- Decorator parameters (compute, etc.) = execution context

### 3. Pipeline (DAG Inference)
**File**: `/home/user/glacier/glacier/core/pipeline.py` (289 lines)

**Key Classes**:
- `Pipeline` - Automatic DAG construction
  - `tasks: List[Task]`
  - `edges: List[PipelineEdge]`
  - `name: str`
  - Method: `_build_dag()` - Two-pass algorithm
    1. Map datasets to producer tasks
    2. Connect producers to consumers
  - Method: `validate()` - Cycle detection
  - Method: `get_execution_order()` - Topological sort (Kahn's)
  - Method: `visualize()` - Text-based DAG visualization
  - Methods: `get_source_tasks()`, `get_sink_tasks()`
  - Methods: `get_dependencies()`, `get_consumers()`

- `PipelineEdge` - DAG edge representation
  - `from_task: Task`
  - `to_task: Task`
  - `dataset: Dataset`
  - `param_name: str`

**Design Pattern**: Automatic DAG from type annotations
- No explicit edge definitions needed
- DAG emerges from dataset type matching

### 4. Compute Resources
**File**: `/home/user/glacier/glacier/compute/resources.py` (210 lines)

**Key Classes**:

1. **ComputeResource (ABC)** - Base class
   - `to_dict() -> Dict[str, Any]` - For infrastructure generation
   - `get_type() -> str` - Resource type identifier

2. **Local** - Local execution
   - `workers: int = 1` - Parallel worker count
   - Maps to: local process execution

3. **Container** - Container execution
   - `image: str` - Container image
   - `cpu: float = 1.0` - CPU cores
   - `memory: int = 512` - Memory in MB
   - `gpu: int = 0` - GPU count
   - `env: Optional[Dict[str, str]]` - Environment variables
   - Maps to: Docker, K8s, ECS, Cloud Run, Container Instances

4. **Serverless** - Serverless/FaaS execution
   - `memory: int = 512` - Memory in MB
   - `timeout: int = 300` - Timeout in seconds
   - `runtime: Optional[str]` - Runtime (e.g., 'python3.11')
   - `env: Optional[Dict[str, str]]` - Environment variables
   - Maps to: Lambda, Cloud Functions, Azure Functions

**Factory Functions**:
- `local(workers=1)` - Create Local instance
- `container(image, cpu, memory, gpu, env)` - Create Container instance
- `serverless(memory, timeout, runtime, env)` - Create Serverless instance

**Design Pattern**: Capability-based abstraction
- Describe needs (memory, CPU), not specific services
- Actual provider determined at compile/execution time

### 5. Compute Module Exports
**File**: `/home/user/glacier/glacier/compute/__init__.py` (27 lines)

**Exports**:
```python
ComputeResource     # ABC
Local, Container, Serverless  # Implementations
local, container, serverless  # Factory functions
```

### 6. Main Module Exports
**File**: `/home/user/glacier/glacier/__init__.py` (51 lines)

**Exports**:
```python
Dataset, task, Task, Pipeline  # Core classes
compute                        # Compute module
```

## Missing Components (Not Yet Implemented)

### Storage Module (Planned)
**Location**: `glacier/storage/` (does not exist yet)

**Expected Structure**:
```
glacier/storage/
├── __init__.py
├── resources.py        # StorageResource ABC
├── s3.py              # S3 implementation
├── gcs.py             # GCS implementation
├── azure.py           # Azure Blob implementation
└── local.py           # Local filesystem implementation
```

**Expected Classes**:
```python
class StorageResource(ABC):
    @abstractmethod
    def read(self): pass
    
    @abstractmethod
    def write(self, data): pass
    
    @abstractmethod
    def get_uri(self): pass

class S3(StorageResource):
    def __init__(self, bucket: str, prefix: str, region: str = None): ...

class GCS(StorageResource):
    def __init__(self, bucket: str, path: str, project_id: str = None): ...

class AzureBlob(StorageResource):
    def __init__(self, container: str, path: str, account: str): ...

class LocalFS(StorageResource):
    def __init__(self, base_path: str): ...
```

### Execution Engines (Planned)
**Location**: `glacier/executors/` (does not exist yet)

**Expected Classes**:
- `LocalExecutor` - Local process execution
- `AWSExecutor` - AWS Lambda execution
- `KubernetesExecutor` - Kubernetes execution
- `GCPExecutor` - Google Cloud execution
- `AzureExecutor` - Azure execution

### Compilation Targets (Planned)
**Location**: `glacier/compilers/` (does not exist yet)

**Expected Classes**:
- `TerraformTarget` - Base Terraform generation
- `AWSTarget(TerraformTarget)` - AWS-specific
- `GCPTarget(TerraformTarget)` - GCP-specific
- `AzureTarget(TerraformTarget)` - Azure-specific
- `KubernetesTarget` - K8s manifest generation

## Data Flow Example

### Code
```python
from glacier import Dataset, task, Pipeline, compute

# 1. Define datasets
users = Dataset("users")
processed = Dataset("processed")

# 2. Define tasks with compute config
@task(compute=compute.serverless(memory=1024))
def extract() -> users:
    return fetch_users()

@task(compute=compute.local(workers=4))
def process_data(data: users) -> processed:
    return clean(data)

# 3. Create pipeline (DAG auto-inferred)
pipeline = Pipeline([extract, process_data])
```

### What Happens at Each Step

**Step 1: Dataset Creation**
```
Dataset("users")
  └─> __init__
      ├─ name="users"
      ├─ storage=None  # Optional StorageResource
      ├─ schema=None
      └─ metadata={}
```

**Step 2: Task Creation**
```
@task(compute=compute.serverless(...))
  └─> Task.__init__
      ├─ fn = extract
      ├─ config = {"compute": Serverless(...)}
      └─ _extract_datasets()
         ├─ inputs = []  # No parameters
         └─ outputs = [Dataset("users")]

@task(compute=compute.local(...))
  └─> Task.__init__
      ├─ fn = process_data
      ├─ config = {"compute": Local(...)}
      └─ _extract_datasets()
         ├─ inputs = [DatasetParameter("data", Dataset("users"))]
         └─ outputs = [Dataset("processed")]
```

**Step 3: Pipeline Creation**
```
Pipeline([extract, process_data])
  └─> __init__
      └─> _build_dag()
          ├─ Pass 1: Map datasets to producers
          │  ├─ Dataset("users") → extract
          │  └─ Dataset("processed") → process_data
          ├─ Pass 2: Connect producers to consumers
          │  └─ extract → process_data (via Dataset("users"))
          └─ edges = [PipelineEdge(...)]
```

**Step 4: DAG Visualization**
```
extract[serverless] ──users──> process_data[local]
```

## References to Compute Configuration

### During Task Definition
```python
task.config["compute"]  # Returns ComputeResource instance
task.get_compute()       # Wrapper method
```

### During Pipeline Compilation (Planned)
```python
for task in pipeline.tasks:
    compute_config = task.get_compute()
    resource_type = compute_config.get_type()  # "serverless", "container", "local"
    metadata = compute_config.to_dict()        # Dict for infrastructure generation
```

### Expected Compilation Flow
```python
# Planned API (not yet implemented)
compiled = pipeline.compile(target=AWSTarget())
# For each task:
#   1. Get compute resource: task.get_compute()
#   2. Get type: compute_resource.get_type()
#   3. Get metadata: compute_resource.to_dict()
#   4. Route to provider adapter based on type
#   5. Generate infrastructure (Terraform, CloudFormation, etc.)
```

## Key Design Locations

| Concern | File | Location |
|---------|------|----------|
| Provider agnosticism | core/dataset.py | Storage parameter (forward ref) |
| Type-driven DAG | core/task.py | _extract_datasets() method |
| DAG inference | core/pipeline.py | _build_dag() algorithm |
| Compute abstraction | compute/resources.py | ComputeResource ABC |
| Resource types | compute/resources.py | Local, Container, Serverless |
| No cloud deps | glacier/__init__.py | Only core imports |

## Configuration Flow

```
User Code
  ├─ Dataset(name, storage=..., schema=..., metadata=...)
  ├─ @task(compute=..., other_config=...)
  └─ Pipeline(tasks, name)
  
Compile Time (Planned)
  ├─ Extract compute configs: task.get_compute()
  ├─ Extract storage configs: dataset.storage
  ├─ Route to target: compile(target=AWSTarget())
  └─ Generate infrastructure: to_terraform(), to_yaml(), etc.

Execution Time (Planned)
  ├─ Instantiate executors from compute configs
  ├─ Instantiate storage adapters from storage configs
  └─ Run pipeline tasks in DAG order
```

---

*For architectural details, see PROVIDER_ABSTRACTION_ANALYSIS.md*  
*For quick summary, see PROVIDER_STRATEGY_SUMMARY.md*
