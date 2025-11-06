# Glacier Codebase Architecture Summary

## Current Status: ALPHA - Design vs Implementation Mismatch

**Key Finding**: The design documents (DESIGN_UX.md, README.md, examples) show the INTENDED/DESIRED architecture, but the implementation is INCOMPLETE. The last commit (7e9420a) was "Update all documentation to match correct architecture" to document the breaking redesign.

---

## 1. DESIRED ARCHITECTURE (From Design Documents)

### Core Design Principles

**Single Provider Class with Dependency Injection:**
```python
from glacier import Provider
from glacier.config import AwsConfig, LocalConfig

# Same Provider class, different behavior via config injection
aws_provider = Provider(config=AwsConfig(region="us-east-1"))
local_provider = Provider(config=LocalConfig(base_path="./data"))
```

**NO provider-specific classes** - Configuration determines behavior, not inheritance.

### Resource Types: Two First-Class Abstractions

**1. Storage Resources (Where Data Lives)**
```python
bucket = provider.bucket(
    bucket="my-data",
    path="file.parquet",
    config=S3Config(versioning=True)  # optional provider-specific config
)
```

**2. Execution Resources (Where Code Runs)**
```python
local_exec = provider.local()
lambda_exec = provider.serverless(config=LambdaConfig(memory=1024))
databricks_exec = provider.cluster(config=DatabricksConfig(...))
ec2_exec = provider.vm(config=EC2Config(...))
```

### Task Binding Pattern: Direct to Execution Resources

```python
@local_exec.task()
def load_data(source) -> pl.LazyFrame:
    return source.scan()

@lambda_exec.task()
def process(df: pl.LazyFrame) -> pl.LazyFrame:
    return df.filter(pl.col("value") > 0)

@databricks_exec.task()
def ml_inference(df: pl.LazyFrame) -> pl.LazyFrame:
    return df.with_columns(pl.lit(0.85).alias("prediction"))
```

**Key**: Tasks bound to EXECUTION RESOURCE OBJECTS, not strings or environments.

### Pipeline Pattern

```python
@pipeline(name="my_pipeline")
def my_pipeline():
    data = load_data(bucket)           # runs on local_exec
    processed = process(data)           # runs on lambda_exec
    predictions = ml_inference(processed)  # runs on databricks_exec
    return predictions

# Execute
result = my_pipeline.run(mode="local")
```

### Critical Design Points

1. **NO GlacierEnv in User API** - Environment orchestrator exists internally but shouldn't be user-facing
2. **NO Deployment Environment** - Glacier handles EXECUTION environment only (where code runs, where data lives)
   - Dev/staging/prod should be handled via: separate Terraform workspaces, different cloud accounts, CI/CD configs
3. **Cloud Portability** - Same code, different provider configs = works on AWS/Azure/GCP/local
4. **Heterogeneous Execution** - Mix local, Lambda, Databricks, Spark in ONE pipeline
5. **Infrastructure from Code** - Auto-generate Terraform from pipeline definitions

---

## 2. CURRENT IMPLEMENTATION

### What's Implemented Correctly ✓

**Provider and Config System** - `/home/user/glacier/glacier/providers/provider.py`
- Single Provider class with config injection ✓
- Detects provider type from config class name ✓
- bucket() method to create Bucket resources ✓
- serverless() method to create Serverless resources ✓
- Config validation ✓
- From environment factory method ✓

**Resource Abstractions** - `/home/user/glacier/glacier/resources/`
- Bucket class (generic, cloud-agnostic) ✓
- Serverless class (generic, cloud-agnostic) ✓
- Adapter pattern for cloud-specific implementations ✓

**Core Classes** - `/home/user/glacier/glacier/core/`
- Task class for wrapping functions ✓
- Pipeline class for orchestrating tasks ✓
- DAG class for dependency resolution ✓
- GlacierEnv for environment management ✓

**Examples** - `/home/user/glacier/examples/`
- simple_pipeline.py - shows correct pattern ✓
- cloud_agnostic_pipeline.py - shows provider portability ✓
- heterogeneous_pipeline.py - shows multiple executors ✓

---

### What's Incomplete/Wrong ✗

**1. Task Binding to Execution Resources**
   - **Current**: Tasks bound via `@env.task()` in GlacierEnv
   - **Desired**: Tasks bound via `@executor.task()` directly on execution resources
   - **Missing**: Execution resources (local, serverless, etc.) don't have `task()` methods!

**2. Execution Resources Don't Have task() Methods**
   - File: `/home/user/glacier/glacier/resources/serverless.py`
   - The Serverless class has NO `task()` method
   - Same for local execution resources
   - Examples show `@lambda_exec.task()` but this method doesn't exist

**3. No local(), serverless(), vm(), cluster() Methods on Provider**
   - File: `/home/user/glacier/glacier/providers/provider.py`
   - Has: `bucket()` and `serverless()`
   - Missing: `local()`, `vm()`, `cluster()` methods
   - serverless() takes function_name and handler, not named config - doesn't match design
   - These should return execution resource objects with task() methods

**4. Provider-Specific Classes Still Exist**
   - Files: 
     - `/home/user/glacier/glacier/providers/aws.py` - AWSProvider class
     - `/home/user/glacier/glacier/providers/gcp.py` - GCPProvider class
     - `/home/user/glacier/glacier/providers/azure.py` - AzureProvider class
     - `/home/user/glacier/glacier/providers/local.py` - LocalProvider class
   - Design says: NO provider-specific classes, only single Provider
   - These should NOT exist in new design

**5. GlacierEnv Exposed in User API**
   - File: `/home/user/glacier/glacier/core/env.py`
   - __init__.py exports GlacierEnv
   - Design says: GlacierEnv exists internally but NOT in user-facing API
   - Users should only use: `Provider` + execution resources with `task()` decorator

**6. Global task/pipeline Decorators Missing**
   - Examples import: `from glacier import Provider, pipeline`
   - But glacier/__init__.py doesn't export `pipeline` or `task`
   - Comments in code say "Global pipeline decorator has been removed"
   - Tests import `from glacier import task, pipeline` but they're not exported

**7. Pipeline Decorator Pattern Unclear**
   - Examples show: `@pipeline(name="...")`
   - But no global `pipeline` decorator is exported
   - Pipeline class exists but no decorator wrapper

**8. Serverless Resource Creation Parameters Wrong**
   - Current: `provider.serverless(function_name, handler, runtime, config=...)`
   - Desired: `provider.serverless(config=LambdaConfig(memory=...))`
   - Should derive name from function context, not require explicit function_name

---

## 3. FILE STRUCTURE

### Core Implementation
```
/home/user/glacier/glacier/
├── __init__.py                 # Main exports (GlacierEnv, Provider, config, resources)
├── core/
│   ├── __init__.py
│   ├── pipeline.py             # Pipeline class (no global decorator)
│   ├── task.py                 # Task class (no global decorator)
│   ├── dag.py                  # DAG builder and analysis
│   ├── env.py                  # GlacierEnv (should not be user-facing)
│   └── context.py              # GlacierContext for execution
├── providers/
│   ├── __init__.py             # Exports only Provider (correct!)
│   ├── provider.py             # Single Provider class (correct design!)
│   ├── base.py                 # Base Provider ABC (legacy, should remove)
│   ├── aws.py                  # AWSProvider (SHOULD NOT EXIST)
│   ├── gcp.py                  # GCPProvider (SHOULD NOT EXIST)
│   ├── azure.py                # AzureProvider (SHOULD NOT EXIST)
│   └── local.py                # LocalProvider (SHOULD NOT EXIST)
├── resources/
│   ├── __init__.py             # Exports Bucket, Serverless
│   ├── bucket.py               # Bucket resource (✓ correct)
│   └── serverless.py           # Serverless resource (missing task() method)
├── config/
│   ├── __init__.py
│   ├── provider.py             # Provider config classes
│   ├── bucket.py               # Bucket-specific configs
│   └── serverless.py           # Serverless-specific configs
├── adapters/
│   ├── bucket.py               # Cloud-specific bucket implementations
│   └── serverless.py           # Cloud-specific serverless implementations
├── sources/
│   ├── base.py                 # Base Source class
│   ├── bucket.py               # Bucket source
│   ├── s3.py                   # S3 source
│   ├── gcs.py                  # GCS source
│   ├── azure.py                # Azure Blob source
│   └── local.py                # Local source
├── runtime/
│   └── local.py                # LocalExecutor for running pipelines
└── codegen/
    ├── analyzer.py             # PipelineAnalyzer for DAG building
    └── terraform.py            # TerraformGenerator for IaC
```

### Documentation & Examples
```
/home/user/glacier/
├── DESIGN_UX.md               # CORRECT architecture (breaking redesign)
├── README.md                  # Quick overview (matches DESIGN_UX.md)
├── QUICKSTART.md              # Tutorial (matches DESIGN_UX.md)
├── CONTRIBUTING.md
├── examples/
│   ├── simple_pipeline.py           # ✓ Shows correct pattern
│   ├── cloud_agnostic_pipeline.py   # ✓ Shows correct pattern
│   ├── heterogeneous_pipeline.py    # ✓ Shows correct pattern
│   └── generate_sample_data.py      # Test data generation
└── tests/
    ├── test_decorators.py      # Tests for @task and @pipeline decorators
    ├── test_dag.py
    ├── test_cloud_agnostic.py
    └── test_sources.py
```

---

## 4. PIPELINE COMPOSITION PATTERNS

### Current (What Examples Show - DESIRED)

**Define execution resources as first-class objects:**
```python
provider = Provider(config=AwsConfig(region="us-east-1"))
local_exec = provider.local()
lambda_exec = provider.serverless(config=LambdaConfig(memory=1024))
databricks_exec = provider.cluster(config=DatabricksConfig(...))
```

**Bind tasks directly to execution resources:**
```python
@local_exec.task()
def extract():
    ...

@lambda_exec.task()
def transform(df):
    ...

@databricks_exec.task()
def ml_predict(df):
    ...
```

**Compose in pipeline:**
```python
@pipeline(name="etl")
def etl_pipeline():
    data = extract(bucket)
    cleaned = transform(data)
    predictions = ml_predict(cleaned)
    return predictions
```

### Old Pattern (What Was Removed - WRONG)

```python
@env.task(executor="databricks")  # String executor - WRONG!
def my_task():
    pass

@env.pipeline()
def my_pipeline():
    pass

env = GlacierEnv(provider=provider)  # User-facing GlacierEnv - WRONG!
result = my_pipeline.run()
```

---

## 5. RESOURCE GENERATION SYSTEM

### How It Works

**Storage Resources**: `/home/user/glacier/glacier/resources/bucket.py`
- Generic Bucket class wraps provider-specific adapters
- Adapters created via: `provider._create_bucket_adapter(bucket)`
- Supports: scan(), read(), get_uri(), exists(), get_metadata()

**Execution Resources**: `/home/user/glacier/glacier/resources/serverless.py`
- Generic Serverless class wraps provider-specific adapters
- Adapters created via: `provider._create_serverless_adapter(serverless)`
- Has: invoke(), get_metadata(), get_arn_or_id()
- **MISSING**: task() method for binding functions!

### Adapter Pattern

Each cloud provider has adapters for:
- Bucket operations: `/home/user/glacier/glacier/adapters/bucket.py`
  - S3BucketAdapter
  - AzureBlobAdapter
  - GCSBucketAdapter
  - LocalBucketAdapter

- Serverless operations: `/home/user/glacier/glacier/adapters/serverless.py`
  - LambdaAdapter
  - AzureFunctionAdapter
  - CloudFunctionAdapter
  - LocalServerlessAdapter

---

## 6. DAG & DEPENDENCY RESOLUTION

### DAG Implementation: `/home/user/glacier/glacier/core/dag.py`

**DAGNode**: Represents a task node with:
- name, task, dependencies, dependents, metadata

**DAG Class**:
- `add_node()` - add task node
- `add_edge()` - add dependency edge
- `topological_sort()` - execution order
- `detect_cycles()` - validate no circular deps
- `get_execution_levels()` - parallel execution groups
- `to_dict()` - serialize for analysis

### PipelineAnalyzer: `/home/user/glacier/glacier/codegen/analyzer.py`

**What it does**:
1. Analyzes pipeline function code
2. Extracts task and source dependencies
3. Builds DAG from dependencies
4. Returns analysis metadata

**The Problem**: How does it discover tasks?
- Examples show tasks bound via `@executor.task()` 
- But analyzer needs to discover these tasks from pipeline function
- Current implementation uses GlacierEnv._tasks registry
- New design needs to discover tasks from execution resource decorators

---

## 7. CONFIGURATION SYSTEM

### Config Classes: `/home/user/glacier/glacier/config/`

**Provider Configs**:
- `AwsConfig(region, profile, account_id, assume_role_arn, session_duration, tags)`
- `GcpConfig(project_id, region, labels, credentials_path)`
- `AzureConfig(subscription_id, resource_group, location, tags)`
- `LocalConfig(base_path)`

**Resource-Specific Configs**:
- `S3Config(storage_class, encryption, versioning)`
- `LambdaConfig(memory, timeout, runtime, layers, ephemeral_storage)`
- `DatabricksConfig(cluster_id, instance_type, num_workers, spark_version)`
- `SparkConfig(master, num_executors, executor_memory)`
- `EC2Config(instance_type, ami, security_group)`

**Pattern**: Config classes determine cloud backend behavior!

---

## 8. DESIGN VS IMPLEMENTATION DISCREPANCIES

| Aspect | Design Says | Current Implementation |
|--------|------------|------------------------|
| Provider Classes | Single `Provider` class | Multiple: AWSProvider, GCPProvider, AzureProvider, LocalProvider |
| Behavior | Config injection determines behavior | Some still using subclasses |
| Task Binding | `@executor.task()` on resource objects | `@env.task()` on GlacierEnv |
| Execution Resources | Methods return objects: `provider.local()`, `provider.serverless(config=...)` | Only `bucket()` and `serverless(function_name, ...)` exist |
| Resource task() | Execution resources have `.task()` method | Missing! |
| GlacierEnv in API | Internal only, NOT user-facing | Exported in __init__.py, examples show users shouldn't use it |
| Pipeline Decorator | Global `@pipeline(name=...)` | No global decorator exported |
| Deployment Env | NO deployment env concept | Not relevant to current state |

---

## 9. KEY FILES TO UNDERSTAND CURRENT STATE

### Must Read:
1. **DESIGN_UX.md** (Line 1-512) - The correct/desired architecture
2. **README.md** - Overview with examples of desired pattern  
3. **examples/simple_pipeline.py** - Shows desired @executor.task() pattern
4. **glacier/providers/provider.py** - Single Provider class (correct!)
5. **glacier/core/env.py** - GlacierEnv (should be internal-only)
6. **glacier/resources/serverless.py** - Missing task() method!

### Implementation Files:
- `/home/user/glacier/glacier/core/task.py` - Task class
- `/home/user/glacier/glacier/core/pipeline.py` - Pipeline class
- `/home/user/glacier/glacier/core/dag.py` - DAG builder
- `/home/user/glacier/glacier/core/context.py` - Execution context
- `/home/user/glacier/glacier/providers/aws.py`, gcp.py, azure.py, local.py - Should NOT exist

---

## 10. SUMMARY: WHAT'S INSUFFICIENT ABOUT CURRENT COMPOSITION

### The Core Problem: Execution Resources Are Not First-Class with Task Binding

**Current System**:
- Uses GlacierEnv as central orchestrator
- Tasks bound via `@env.task(executor="string")`
- Pipelines bound via `@env.pipeline()`
- Resources retrieved via `env.get("name")`

**Desired System**:
- Provider creates execution resource OBJECTS
- Tasks bound via `@executor.task()` (e.g., `@local_exec.task()`)
- Pipelines are simple functions with `@pipeline(name=...)` decorator
- Resources passed directly as parameters

### Why This Matters

1. **Type Safety** - Passing resource objects vs retrieving by string
2. **IDE Support** - Auto-complete for `.task()` on resource objects
3. **Explicit Dependencies** - Clear which executor each task uses
4. **Cleaner API** - No environment registry to manage
5. **Flexibility** - Can create multiple executors of same type with different configs

### Example of the Gap

**Desired (in examples):**
```python
local_exec = provider.local()
@local_exec.task()
def my_task():
    pass
```

**Current (in implementation):**
```python
env = GlacierEnv(provider=provider)
@env.task()  # No binding to specific executor!
def my_task():
    pass
```

The examples show the design intent, but the implementation doesn't support it yet!

---

## Conclusion

Glacier is in **ALPHA** with a **documented breaking redesign** (commit fbbab18). The design documents are comprehensive and show a clean architecture, but the implementation is incomplete. Key missing pieces:

1. ✗ Execution resources lacking `task()` method
2. ✗ No `local()`, `vm()`, `cluster()` methods on Provider
3. ✗ Outdated provider-specific classes still present
4. ✗ Global `@pipeline` decorator missing
5. ✗ GlacierEnv still exposed in public API

The path forward is clear: complete the transition to first-class execution resources with direct task binding.

