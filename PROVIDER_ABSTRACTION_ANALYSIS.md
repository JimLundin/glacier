# Glacier Provider Abstraction Analysis

## Executive Summary

Glacier is undergoing a strategic redesign regarding provider abstraction. The current architecture (`claude/evaluate-provider-agnostic-strategy` branch) has shifted from a **Provider Factory Pattern** (as implemented in commit b402dd3) to a **Dataset-Centric Type-Driven Pattern** (as of commit e9f4d95 onwards). This analysis documents both approaches, the reasoning behind the shift, and current implementation status.

---

## Current Architecture (Post-Redesign)

### Overview
The new design (NEW_DESIGN.md, e9f4d95+) takes a fundamentally different approach to provider abstraction:
- **Focus**: Type-driven pipeline definition with datasets and compute resources
- **Core Principle**: Provider-agnostic core (zero cloud dependencies in API)
- **Mechanism**: Datasets carry storage configuration, Tasks carry compute configuration

### Key Components

#### 1. Dataset Abstraction (Core Storage Abstraction Point)
**Location**: `/home/user/glacier/glacier/core/dataset.py`

```python
class Dataset:
    def __init__(
        self,
        name: str,
        storage: Optional['StorageResource'] = None,
        schema: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
```

**Design Pattern**:
- Datasets are named data artifacts that flow through the pipeline
- Optional `storage` parameter accepts a `StorageResource` abstraction (forward reference, not yet implemented)
- Schema and metadata support for validation and configuration
- Datasets are used as type annotations in task function signatures

**Provider Abstraction Strategy**:
- Storage configuration is **decoupled from compute logic**
- Users optionally attach storage configuration at dataset declaration time
- Example (from README):
```python
from glacier.storage import S3  # Not yet implemented

raw_data = Dataset(
    name="raw_data",
    storage=S3(bucket="my-bucket", prefix="raw/"),
    schema=RawSchema
)
```

**Current Status**: 
- ✅ Dataset class structure ready
- ✅ Storage parameter slot exists (as forward reference)
- ❌ StorageResource interface not yet defined
- ❌ Storage implementations (S3, GCS, Azure, etc.) not yet implemented

#### 2. Compute Resource Abstraction
**Location**: `/home/user/glacier/glacier/compute/resources.py`

**Base Class Pattern**:
```python
class ComputeResource(ABC):
    @abstractmethod
    def to_dict(self) -> Dict[str, Any]: pass
    
    @abstractmethod
    def get_type(self) -> str: pass
```

**Implementations**:

1. **Local** - Development and testing
   - `workers: int = 1` - parallel worker count
   - Maps to local process execution
   
2. **Container** - Universal container execution
   - `image: str` - container image
   - `cpu: float = 1.0` - CPU cores (fractional supported)
   - `memory: int = 512` - Memory in MB
   - `gpu: int = 0` - GPU count
   - `env: Optional[Dict[str, str]]` - environment variables
   - Maps to: Docker, Kubernetes, ECS, Cloud Run, Container Instances
   
3. **Serverless** - Serverless/FaaS execution
   - `memory: int = 512` - Memory in MB
   - `timeout: int = 300` - Execution timeout in seconds
   - `runtime: Optional[str]` - Runtime version (e.g., 'python3.11')
   - `env: Optional[Dict[str, str]]` - environment variables
   - Maps to: AWS Lambda, Cloud Functions, Azure Functions

**Provider Abstraction Strategy**:
- Compute resources are **provider-agnostic descriptors**, not implementations
- Define **capability requirements**, not cloud-specific resources
- Provider selection happens at **compile/execution time**, not definition time
- Same task code works across all providers via configuration selection

**Current Status**: 
- ✅ ComputeResource ABC fully implemented
- ✅ All three resource types defined (Local, Container, Serverless)
- ✅ Factory functions for convenient instantiation
- ✅ to_dict() methods for infrastructure generation
- ✅ Type identification via get_type()
- ❌ No actual execution engines yet
- ❌ No infrastructure generation targets (Terraform, K8s, etc.)

**Example Usage**:
```python
from glacier import task, compute

@task(compute=compute.local(workers=4))
def extract() -> raw_data:
    return fetch_from_api()

@task(compute=compute.serverless(memory=1024, timeout=300))
def transform(data: raw_data) -> clean_data:
    return process(data)

@task(compute=compute.container(
    image="analytics:latest",
    cpu=4,
    memory=8192
))
def analyze(data: clean_data) -> results:
    return calculate(data)
```

#### 3. Task Declaration (Execution Context)
**Location**: `/home/user/glacier/glacier/core/task.py`

**Design**:
```python
class Task:
    def __init__(self, fn: Callable, **config):
        self.fn = fn
        self.config = config  # Contains compute, retries, timeout, etc.
        self._extract_datasets()  # Analyzes function signature
```

**Signature Inspection**:
- Extracts input datasets from function parameters (type annotations)
- Extracts output datasets from return type annotation
- Supports single outputs or tuple outputs for multiple datasets
- Example:
```python
@task(compute=compute.serverless(memory=1024))
def merge(users: clean_users, orders: clean_orders) -> merged:
    # Function parameters typed with Dataset instances = inputs
    # Return type with Dataset instance(s) = outputs
    return join(users, orders)
```

**Compute Configuration Storage**:
- Task stores compute configuration via decorator parameters
- Retrieved via `task.get_compute()`
- Contains all information needed for infrastructure generation

#### 4. Pipeline (DAG Inference)
**Location**: `/home/user/glacier/glacier/core/pipeline.py`

**Key Innovation**: Automatic DAG construction from dataset flow

```python
class Pipeline:
    def __init__(self, tasks: List[Task], name: str = "pipeline"):
        self._build_dag()  # Automatic dependency inference
```

**DAG Building Algorithm**:
1. First pass: Map datasets to producer tasks (from task outputs)
2. Second pass: Connect producers to consumers (from task inputs)
3. Create edges when dataset producer → consumer relationship exists

**Provider-Agnostic Perspective**:
- Pipeline only cares about **data flow**, not execution details
- Each task's compute configuration is preserved for later compilation/execution
- Dataset references include optional storage configuration
- The pipeline itself is **provider-neutral** - can be compiled to any target

**Example DAG Inference**:
```python
raw_users = Dataset("raw_users")
raw_orders = Dataset("raw_orders")
clean_users = Dataset("clean_users")
clean_orders = Dataset("clean_orders")
merged = Dataset("merged")

@task(compute=compute.serverless(memory=512))
def extract_users() -> raw_users: ...

@task(compute=compute.serverless(memory=512))
def extract_orders() -> raw_orders: ...

@task(compute=compute.local())
def clean_users_fn(users: raw_users) -> clean_users: ...

@task(compute=compute.local())
def clean_orders_fn(orders: raw_orders) -> clean_orders: ...

@task(compute=compute.container(image="spark:latest", cpu=4, memory=8192))
def merge_fn(users: clean_users, orders: clean_orders) -> merged: ...

pipeline = Pipeline([
    extract_users, extract_orders,
    clean_users_fn, clean_orders_fn,
    merge_fn
])

# Inferred DAG:
# extract_users ──> clean_users ──┐
#                                  ├─> merge
# extract_orders ─> clean_orders ──┘
```

---

## Previous Architecture (Provider Factory Pattern)

### Overview (Commit b402dd3)
The earlier design used a **Provider Factory Pattern** with Resource Abstractions:

```
Provider (Interface)
├── AWSProvider
├── AzureProvider  
├── GCPProvider
└── LocalProvider

Provider.bucket() → Bucket (Generic Resource)
Provider.serverless() → Serverless (Generic Resource)

Bucket/Serverless → Provider-specific Adapter
├── S3BucketAdapter
├── AzureBlobAdapter
├── GCSBucketAdapter
└── LocalBucketAdapter

Serverless →
├── LambdaAdapter
├── AzureFunctionAdapter
├── CloudFunctionAdapter
└── LocalFunctionAdapter
```

### Key Components

#### Provider Base Class
```python
class Provider(ABC):
    def bucket(
        self,
        bucket: str,
        path: str,
        format: str = "parquet",
        config: Any | None = None
    ) -> Bucket:
        """Create cloud-agnostic Bucket resource"""
    
    def serverless(
        self,
        function_name: str,
        handler: Any | None = None,
        config: Any | None = None
    ) -> Serverless:
        """Create cloud-agnostic Serverless resource"""
```

#### Generic Resource Abstractions

**Bucket** - Storage abstraction:
```python
class Bucket(Source):
    def __init__(
        self,
        bucket_name: str,
        path: str,
        format: str = "parquet",
        provider: Provider | None = None,
        config: BucketConfig | None = None,
        options: dict[str, Any] | None = None
    ):
        self._adapter = None  # Lazy-initialized
    
    def scan(self) -> pl.LazyFrame:
        """Delegate to provider-specific adapter"""
        adapter = self._get_adapter()
        return adapter.scan()
    
    def get_uri(self) -> str:
        """Get cloud-specific URI"""
    
    def exists(self) -> bool:
        """Check if bucket/path exists"""
```

**Serverless** - Compute abstraction:
```python
class Serverless:
    def __init__(
        self,
        function_name: str,
        handler: Callable | str | None = None,
        runtime: str | None = None,
        provider: Provider | None = None,
        config: ServerlessConfig | None = None
    ):
        self._adapter = None  # Lazy-initialized
    
    def invoke(self, payload: dict[str, Any] | None = None) -> Any:
        """Delegate to provider-specific adapter"""
    
    def get_metadata(self) -> ServerlessMetadata:
        """For infrastructure generation"""
    
    def get_arn_or_id(self) -> str:
        """Cloud-specific identifier"""
```

#### Adapter Pattern

**BucketAdapter** (Base):
```python
class BucketAdapter(ABC):
    @abstractmethod
    def scan(self) -> pl.LazyFrame: pass
    
    @abstractmethod
    def get_uri(self) -> str: pass
    
    @abstractmethod
    def get_metadata(self) -> SourceMetadata: pass
    
    @abstractmethod
    def exists(self) -> bool: pass

# S3 Implementation
class S3BucketAdapter(BucketAdapter):
    def scan(self) -> pl.LazyFrame:
        uri = f"s3://{bucket}/{path}"
        return pl.scan_parquet(uri)
    
    def get_uri(self) -> str:
        return f"s3://{self.bucket.bucket_name}/{self.bucket.path}"
```

**ServerlessAdapter** (Base):
```python
class ServerlessAdapter(ABC):
    @abstractmethod
    def invoke(self, payload: dict | None = None) -> Any: pass
    
    @abstractmethod
    def get_metadata(self) -> ServerlessMetadata: pass
    
    @abstractmethod
    def get_arn_or_id(self) -> str: pass

# Lambda Implementation
class LambdaAdapter(ServerlessAdapter):
    def invoke(self, payload: dict | None = None) -> Any:
        # Use boto3 to invoke Lambda
        pass
    
    def get_metadata(self) -> ServerlessMetadata:
        return ServerlessMetadata(
            resource_type="lambda",
            cloud_provider="aws",
            region=self.region,
            runtime=self.serverless.runtime
        )
```

#### Provider Implementations

**AWSProvider**:
```python
class AWSProvider(Provider):
    def __init__(
        self,
        region: str = "us-east-1",
        profile: str | None = None,
        account_id: str | None = None
    ):
        self.region = region
        self.profile = profile
        self.account_id = account_id
    
    def _create_bucket_adapter(self, bucket) -> BucketAdapter:
        return S3BucketAdapter(bucket)
    
    def _create_serverless_adapter(self, serverless) -> ServerlessAdapter:
        return LambdaAdapter(serverless)
    
    def get_provider_type(self) -> str:
        return "aws"
```

Similar implementations existed for:
- AzureProvider → AzureBlobAdapter, AzureFunctionAdapter
- GCPProvider → GCSBucketAdapter, CloudFunctionAdapter
- LocalProvider → LocalBucketAdapter, LocalFunctionAdapter

#### Configuration Classes
Provider-specific optional configs:
```python
class S3Config:
    versioning: bool = False
    encryption: str | None = None
    # AWS-specific options

class AzureBlobConfig:
    tier: str = "Hot"
    # Azure-specific options
```

### Usage Pattern (Old Design)
```python
from glacier.providers import AWSProvider
from glacier.config import S3Config

# Create provider
provider = AWSProvider(region="us-east-1")

# Create cloud-agnostic storage resources
raw_bucket = provider.bucket(
    "my-data",
    path="raw/file.parquet",
    config=S3Config(versioning=True)
)

# Create cloud-agnostic compute resources
compute = provider.serverless(
    "process-function",
    handler=process_handler,
    runtime="python3.11"
)

# Use in pipeline (cloud-agnostic!)
@task
def load_and_process(source: Bucket) -> pl.LazyFrame:
    data = source.scan()  # Works with any cloud provider!
    return data.filter(...)
```

### Key Design Decisions (Old Pattern)
1. **Separation of Resources from Providers**: Create resources through provider factory methods
2. **Adapter Pattern for Implementation**: Cloud-specific logic isolated in adapters
3. **Optional Configuration**: Provider-specific configs applied selectively
4. **Runtime Abstraction**: Same code works with different providers via runtime dispatch

---

## Design Evolution & Strategic Shifts

### Why the Redesign?

The transition from Provider Factory Pattern → Dataset-Centric Pattern represents a strategic shift:

#### Problem with Provider Factory (Old Design)
1. **Provider centrality** - Required explicit provider instantiation before defining pipelines
2. **Tight coupling to provider lifecycle** - Resources tied to provider instance
3. **Execution-focused** - Design emphasized execution (scan, invoke) over declaration
4. **DAG was implicit** - No explicit data flow representation
5. **Data lineage unclear** - Hard to track what data flows where

#### Benefits of Dataset-Centric (New Design)
1. **Provider-agnostic core** - No provider imports needed in pipeline code
2. **Type-safe declarations** - IDE autocompletion for dataset references
3. **Declarative over imperative** - Declare what happens, not how to implement it
4. **Explicit data flow** - DAG automatically inferred from dataset types
5. **Infrastructure from code** - Configuration carries through datasets and tasks
6. **Easier testing** - Can test logic without cloud provider setup
7. **Language natural** - Reads like normal Python with type hints

#### Comparison Table
| Aspect | Old Pattern | New Pattern |
|--------|-----------|-----------|
| Provider requirement | Must instantiate | Optional at compile time |
| Data flow declaration | Implicit | Explicit (type annotations) |
| DAG representation | Built separately | Inferred from signatures |
| Configuration location | Provider + Config classes | Dataset + Task decorators |
| Cloud dependency | In runtime usage | Only at compile/execution |
| Code example | `provider.bucket()` | `Dataset(..., storage=...)` |

---

## Storage Provider Abstraction Strategy

### Current Design (Post-Redesign)

#### Storage Interface (Not Yet Implemented)
```python
# Forward reference in Dataset
storage: Optional['StorageResource'] = None

# Expected interface (from NEW_DESIGN.md, README examples):
class StorageResource(ABC):
    @abstractmethod
    def read(self) -> Any:
        """Read data from storage"""
        
    @abstractmethod
    def write(self, data: Any) -> None:
        """Write data to storage"""
        
    @abstractmethod
    def get_uri(self) -> str:
        """Get cloud-specific URI"""
```

#### Planned Storage Implementations
1. **S3** (AWS)
   - From README: `S3(bucket="my-bucket", prefix="raw/")`
   - Configuration: bucket, prefix, region, credentials
   
2. **GCS** (Google Cloud)
   - Similar interface
   - Configuration: bucket, path, project_id
   
3. **Azure Blob Storage**
   - Configuration: container, blob_path, storage_account
   
4. **Local Filesystem**
   - For development/testing
   - Configuration: base_path

#### Design Principles
- **Datasets carry storage info** - Not tasks or pipelines
- **Storage optional** - Can have datasets without attached storage
- **Late binding** - Actual storage location determined at execution/compilation time
- **Provider-agnostic path** - Same dataset definition works with different storage backends

#### Example (From Documentation)
```python
from glacier import Dataset
from glacier.storage import S3  # Not yet implemented

# Declare dataset with storage
raw_data = Dataset(
    name="raw_data",
    storage=S3(bucket="my-bucket", prefix="raw/"),
    schema=RawSchema
)

# Same dataset used in pipeline
@task(compute=compute.local())
def extract() -> raw_data:
    # Storage config attached to dataset
    # Can be used for infrastructure generation
    return fetch_from_api()
```

### Storage Abstraction Mechanism
1. **For Development**: Datasets can work without storage specification
2. **For Cloud Compilation**: Datasets with storage→Infrastructure templates
3. **Provider Selection**: At compile time, e.g., `pipeline.compile(target=AWSTarget())`
4. **Format Support**: Via dataset metadata/schema
5. **Serialization**: Storage resource converts to dict for infrastructure generation

---

## Compute Provider Abstraction Strategy

### Current Design (Fully Implemented)

#### Compute Resource Hierarchy
```
ComputeResource (ABC)
├── Local(workers: int = 1)
├── Container(image, cpu, memory, gpu, env)
└── Serverless(memory, timeout, runtime, env)
```

#### Provider Mapping
- **Local**: Immediate local process execution
- **Container**: 
  - Docker (local)
  - Kubernetes (cloud-native)
  - ECS (AWS)
  - Cloud Run (GCP)
  - Container Instances (Azure)
- **Serverless**:
  - Lambda (AWS)
  - Cloud Functions (GCP)
  - Azure Functions (Azure)
  - Local function execution (development)

#### Design Features
1. **Capability-based abstraction** - Describe needs (memory, CPU), not specific services
2. **Provider independence** - Same code declaration works everywhere
3. **Infrastructure generation** - to_dict() provides data for Terraform/K8s generation
4. **Environment variable support** - For injecting secrets, configs
5. **Type identification** - get_type() enables compile-time routing

#### Compilation Strategy (Not Yet Implemented)
```python
# Execute locally
pipeline.run(executor=LocalExecutor())

# Generate AWS infrastructure
compiled = pipeline.compile(target=AWSTarget())
compiled.to_terraform("./infra")

# Generate Kubernetes manifests
compiled = pipeline.compile(target=KubernetesTarget())
compiled.to_yaml("./k8s")
```

---

## Configuration Mechanisms

### User Configuration Entry Points

#### 1. Dataset Configuration
```python
raw_data = Dataset(
    name="raw_data",
    storage=S3(bucket="my-bucket", prefix="raw/"),  # Storage config
    schema=RawSchema,                                 # Schema validation
    metadata={                                        # Custom metadata
        "partitioning": "by_date",
        "format": "parquet"
    }
)
```

#### 2. Task Configuration
```python
@task(
    compute=compute.serverless(memory=1024, timeout=300),  # Compute config
    # Future: retries, timeout, alerts, etc.
)
def my_task(data: input_data) -> output_data:
    pass
```

#### 3. Pipeline Configuration
```python
pipeline = Pipeline(
    tasks=[...],
    name="my-pipeline"
    # Future: global config, defaults, etc.
)
```

#### 4. Execution Configuration (Planned)
```python
# At execution time, select provider/executor
executor = AWSExecutor(
    region="us-east-1",
    role_arn="arn:aws:iam::..."
)
result = pipeline.run(executor=executor)

# Or compile to infrastructure
target = AWSTarget(region="us-east-1")
compiled = pipeline.compile(target=target)
compiled.to_terraform("./infra")
```

### Environment Variables
Compute resources support environment variable injection:
```python
@task(
    compute=compute.container(
        image="processor:latest",
        env={
            "DATABASE_URL": "${DB_URL}",  # Injected at runtime
            "LOG_LEVEL": "DEBUG"
        }
    )
)
def process() -> results:
    import os
    db_url = os.getenv("DATABASE_URL")
```

---

## Infrastructure Generation (Planned)

### Design Intent
While not yet implemented, the architecture supports:

#### 1. Terraform Generation
```python
pipeline = Pipeline([extract, transform, load])
compiled = pipeline.compile(target=AWSTarget())
compiled.to_terraform("./infra")

# Generates:
# - main.tf (Lambda functions, S3 buckets)
# - variables.tf (configuration inputs)
# - outputs.tf (pipeline outputs)
# - terraform.tfvars (default values)
```

#### 2. Kubernetes Generation
```python
compiled = pipeline.compile(target=KubernetesTarget())
compiled.to_yaml("./k8s")

# Generates:
# - deployment.yaml (pod definitions)
# - service.yaml (networking)
# - configmap.yaml (configuration)
# - persistentvolumeclaim.yaml (storage)
```

#### 3. Infrastructure Metadata Collection
```python
# During compilation, pipeline gathers:
compute_tasks = [
    {"name": "extract", "type": "serverless", "memory": 512, ...},
    {"name": "transform", "type": "local", "workers": 4, ...},
    {"name": "load", "type": "container", "image": "...", ...}
]

storage_resources = [
    {"name": "raw_data", "bucket": "...", "prefix": "raw/"},
    {"name": "processed_data", "bucket": "...", "prefix": "processed/"}
]
```

---

## Current Implementation Status

### Fully Implemented (✅)
- Dataset class with storage/schema/metadata slots
- Task decorator with type hint inspection
- Pipeline with automatic DAG inference
- ComputeResource abstract base class
- Local, Container, Serverless compute resources
- Factory functions (local(), container(), serverless())
- DAG validation (cycle detection)
- Topological sorting
- Pipeline visualization
- Complex DAG support (fan-in, fan-out, diamonds)

### Planned (🚧)
- StorageResource interface and implementations (S3, GCS, Azure, Local)
- Execution engines (local, distributed)
- Infrastructure compilation:
  - Terraform generation
  - Kubernetes manifest generation
  - CloudFormation generation
- Provider adapters for actual execution
- Schema validation framework
- Data lineage tracking
- Execution monitoring
- Error handling and retries

### Not Yet Designed (⚠️)
- Multi-tenant considerations
- Cost optimization
- Security/IAM generation
- Monitoring/observability
- Orchestration integration (Airflow, Prefect, etc.)
- State management for incremental runs

---

## Architectural Comparison

### Old vs. New Design

#### Old Design (Provider Factory Pattern)
**Strengths**:
- Explicit provider instantiation (clear where cloud calls happen)
- Separation of concerns (adapters isolated)
- Familiar pattern (similar to cloud SDKs)
- Easy to implement provider-specific features

**Weaknesses**:
- Requires provider knowledge in pipeline code
- Provider lifecycle management needed
- DAG implicit in pipeline builder
- Data flow not explicit
- Tight coupling to execution

#### New Design (Dataset-Centric Type-Driven)
**Strengths**:
- Zero provider imports in pipeline code
- Type-safe dataset references
- Explicit data flow (DAG from types)
- Separation of declaration from execution
- Testability (can test logic without cloud)
- Natural Python idioms

**Weaknesses**:
- Storage/compute not yet implemented
- Infrastructure generation not yet designed
- May require custom compilation targets
- Execution engines not yet built

---

## Strategic Insights

### Why Glacier Chose Provider Abstraction
1. **No Vendor Lock-in** - Users can switch clouds without rewriting pipelines
2. **Flexible Deployment** - Same code for dev (local) → test (cloud) → prod
3. **Future-Proof** - Can add providers without breaking existing code
4. **Tool Interoperability** - Better positioning against cloud vendor tools
5. **User Choice** - Empowers users to make infrastructure decisions

### Key Design Decisions
1. **Type-Driven over API-Driven** - Python type hints as contract language
2. **Declaration over Configuration** - Declare what, not how
3. **Late Binding** - Defer provider/target selection to compile/execution time
4. **Minimal Core** - Only essentials in core (Dataset, Task, Pipeline)
5. **Provider-Agnostic Core** - Zero cloud dependencies in base library

### Future Roadmap Implications
- Storage implementations follow compute pattern
- Infrastructure generation via compile targets
- Multiple execution engines (local, Lambda, Kubernetes, etc.)
- Provider ecosystem (community extensions)
- Managed service potential (Glacier-as-a-service)

---

## Conclusion

Glacier's provider abstraction strategy represents a thoughtful evolution from Provider-Factory Pattern to Dataset-Centric Type-Driven Design. The new approach:

1. **Eliminates provider coupling** from pipeline definitions
2. **Leverages Python type system** for data flow declaration
3. **Defers provider selection** to compile/execution time
4. **Supports infrastructure-from-code** generation
5. **Enables true cloud-agnosticism** in user code

The implementation is partially complete (compute abstraction done, storage not yet implemented) but the architectural foundation is solid and extensible. The design prioritizes developer experience and flexibility while maintaining clean separation between declaration, compilation, and execution phases.

