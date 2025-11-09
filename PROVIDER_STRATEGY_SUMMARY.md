# Provider Abstraction Strategy - Quick Summary

## Current State: Dataset-Centric Type-Driven Design

### Core Architecture
```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  User Code (Provider-Agnostic)                                 │
│  ├── Datasets (with optional storage config)                   │
│  ├── Tasks (with compute config)                               │
│  └── Pipeline (DAG auto-inferred from signatures)              │
│                                                                 │
│  ↓ Configuration carries through...                            │
│                                                                 │
│  Compile/Execution Phase (Provider Selection)                  │
│  ├── Local Execution                                           │
│  ├── AWS Compilation (Terraform/CloudFormation)               │
│  ├── GCP Compilation (Terraform/GCP-specific)                 │
│  └── Azure Compilation (Terraform/ARM templates)              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Storage Abstraction Strategy

### Design Pattern (Not Yet Implemented)
```
Dataset
├── name: str
├── storage: StorageResource (OPTIONAL)
│   ├── S3(bucket, prefix, region)
│   ├── GCS(bucket, path, project_id)
│   ├── AzureBlob(container, path, account)
│   └── LocalFS(base_path)
├── schema: Any
└── metadata: Dict
```

### Key Principle: Late Binding
- **Definition Time**: Declare datasets with optional storage
- **Compile Time**: Select target provider
- **Runtime**: Provider adapter materializes actual storage operations

## Compute Abstraction Strategy

### Fully Implemented Resource Hierarchy
```
ComputeResource (ABC)
│
├── Local(workers=1)
│   └── Maps to: local process execution
│
├── Container(image, cpu, memory, gpu, env)
│   └── Maps to: Docker, K8s, ECS, Cloud Run, Container Instances
│
└── Serverless(memory, timeout, runtime, env)
    └── Maps to: Lambda, Cloud Functions, Azure Functions
```

### Provider Mapping
| Compute Type | Local | AWS | GCP | Azure |
|---|---|---|---|---|
| Local | ✓ | ✗ | ✗ | ✗ |
| Container | Docker | ECS | Cloud Run | Container Inst. |
| Serverless | Local Func. | Lambda | Functions | Functions |

## Evolution: Old vs. New Design

### Old Design (Provider Factory Pattern)
```python
# Explicit provider instantiation
provider = AWSProvider(region="us-east-1")
bucket = provider.bucket("data", path="file.parquet")
serverless = provider.serverless("process", handler=fn)

# Cloud knowledge in pipeline code
@task
def process(source: Bucket) -> Bucket:
    return source.scan().filter(...)
```

**Characteristics**:
- Requires provider instantiation before pipeline definition
- DAG implicit in pipeline builder pattern
- Tight coupling to execution phase
- Resource objects tied to provider instance

### New Design (Type-Driven)
```python
# Zero provider imports
raw_data = Dataset("raw_data", 
    storage=S3(bucket="data", prefix="raw/"))
clean_data = Dataset("clean_data")

@task(compute=compute.serverless(memory=1024))
def extract() -> raw_data:
    return fetch_from_api()

@task(compute=compute.local())
def clean(data: raw_data) -> clean_data:
    return process(data)

pipeline = Pipeline([extract, clean])
```

**Characteristics**:
- Zero provider imports in user code
- DAG explicit from type annotations
- Deferred provider selection (compile/execution time)
- Type-safe dataset references

## Configuration Entry Points

### 1. Dataset Configuration
```python
dataset = Dataset(
    name="data",
    storage=S3(bucket="...", prefix="..."),  # Storage
    schema=DataSchema,                         # Schema validation
    metadata={...}                             # Custom metadata
)
```

### 2. Task Configuration
```python
@task(
    compute=compute.serverless(memory=1024, timeout=300),
    # Future: retries, alerts, monitoring
)
def my_task(data: input_data) -> output_data:
    pass
```

### 3. Execution Configuration (Planned)
```python
# At execution time
result = pipeline.run(executor=AWSExecutor(region="us-east-1"))

# Or compile to infrastructure
compiled = pipeline.compile(target=AWSTarget())
compiled.to_terraform("./infra")
```

## Implementation Status

### Completed (✅)
- Dataset class with storage/schema/metadata slots
- Task decorator with signature inspection
- Pipeline with automatic DAG inference (DAG from type hints)
- ComputeResource ABC
- Local, Container, Serverless implementations
- Complex DAG support (fan-in, fan-out, diamonds)
- Pipeline validation & visualization

### In Progress (🚧)
- StorageResource interface definition
- Storage implementations (S3, GCS, Azure, Local)
- Execution engines (local, distributed)
- Infrastructure compilation targets

### Future (⚠️)
- Terraform generation
- Kubernetes manifest generation
- Schema validation
- Data lineage tracking
- Cost optimization
- Multi-tenant support

## Key Strategic Decisions

### 1. Type-Driven Over API-Driven
```python
# Type hints declare data dependencies automatically
def task(users: users_dataset, orders: orders_dataset) -> merged_dataset:
    # Python type system is the contract language
    pass
```

### 2. Declaration Over Configuration
```python
# Declare what you want, not how to implement it
compute=compute.serverless(memory=1024)  # Need: 1GB memory serverless execution
# Not: LambdaConfig(FunctionName=..., Role=..., ...)
```

### 3. Late Binding of Providers
```python
# Write once, run everywhere
pipeline = Pipeline([tasks...])  # Provider-agnostic

# Different providers selected at execution time
pipeline.run(executor=LocalExecutor())      # Local development
pipeline.compile(target=AWSTarget())        # AWS production
pipeline.compile(target=KubernetesTarget()) # K8s production
```

### 4. Minimal Core
```python
# Core library has ZERO cloud dependencies
from glacier import Dataset, task, Pipeline, compute
# All three compute types work with any cloud provider
```

## Architecture Patterns

### Storage Pattern (Planned)
```
User Code
  ↓
Dataset(storage=S3(...))
  ↓ (compile time)
S3Config → S3BucketResource
  ↓ (execution time)
S3BucketAdapter → boto3 calls
```

### Compute Pattern (Implemented)
```
User Code
  ↓
@task(compute=compute.serverless(...))
  ↓ (compile time, examine get_type())
ServerlessDescriptor → Terraform/K8s template
  ↓ (execution time)
LambdaExecutor/CloudFunctionExecutor → actual invocation
```

## Benefits of Current Design

1. **True Provider Agnosticism** - Same code, any cloud
2. **Type Safety** - IDE autocompletion for datasets
3. **Declarative** - Declare what, not how
4. **Testability** - Can test without cloud provider
5. **Natural Python** - Type hints are already a language feature
6. **Infrastructure from Code** - Config embedded in definitions
7. **Flexible Deployment** - dev (local) → test (cloud) → prod (cloud)

## Next Implementation Steps

1. Define StorageResource ABC
2. Implement S3, GCS, Azure, Local storage adapters
3. Create execution engines (local, distributed)
4. Build compilation targets (Terraform, K8s, etc.)
5. Add schema validation
6. Implement data lineage tracking

---

*For detailed analysis, see PROVIDER_ABSTRACTION_ANALYSIS.md*
