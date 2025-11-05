# Glacier Architecture V2 - Key Improvements

This document outlines the major architectural improvements made to Glacier to address cloud-agnostic deployment, explicit dependencies, and modern Python conventions.

## Major Changes

### 1. Provider Abstraction Layer ⭐

**Problem**: Original design had explicit `S3Source`, making it impossible to deploy the same pipeline code to Azure or GCP without rewriting.

**Solution**: Introduced `Provider` abstraction that creates sources in a cloud-agnostic way.

```python
# OLD WAY - Cloud provider is hard-coded
from glacier.sources import S3Source

data_source = S3Source(
    bucket="my-data",
    path="file.parquet",
    region="us-east-1"
)
```

```python
# NEW WAY - Cloud provider is configurable
from glacier.providers import AWSProvider

provider = AWSProvider(region="us-east-1")
data_source = provider.bucket_source(
    bucket="my-data",
    path="file.parquet"
)

# Same pipeline code, different provider!
from glacier.providers import AzureProvider

provider = AzureProvider(resource_group="my-rg", location="eastus")
data_source = provider.bucket_source(
    bucket="my-data",
    path="file.parquet"
)
# Creates AzureBlobSource instead, but pipeline code unchanged!
```

**Benefits**:
- ✅ **Cloud-agnostic pipelines**: Write once, deploy anywhere
- ✅ **Environment-based configuration**: Load provider from env vars
- ✅ **No code changes** needed to switch clouds
- ✅ **Testable**: Use `LocalProvider` for testing, cloud provider for production

**Supported Providers**:
- `AWSProvider` → Creates `S3Source`
- `AzureProvider` → Creates `AzureBlobSource`
- `GCPProvider` → Creates `GCSSource`
- `LocalProvider` → Creates `LocalSource`

**Provider Configuration**:
```python
# Explicit configuration
provider = AWSProvider(region="us-east-1", profile="prod")

# From environment variables (12-factor app)
provider = AWSProvider.from_env()  # Reads AWS_REGION, AWS_PROFILE, etc.
```

### 2. Explicit Dependencies (No Magic Strings) ⭐

**Problem**: Original design used string-based dependencies which are error-prone and not type-safe.

```python
# OLD WAY - Magic strings, easy to make typos
@task
def load_data():
    pass

@task(depends_on=["load_data"])  # String! Typo-prone, no IDE support
def process():
    pass
```

**Solution**: Pass actual `Task` objects as dependencies.

```python
# NEW WAY - Explicit, type-safe dependencies
@task
def load_data():
    pass

@task(depends_on=[load_data])  # Pass the actual task object!
def process():
    pass

# Multiple dependencies
@task(depends_on=[task1, task2, task3])
def final_step():
    pass
```

**Benefits**:
- ✅ **Type-safe**: IDE can check if task exists
- ✅ **Refactoring-friendly**: Rename works automatically
- ✅ **No typos**: Can't reference non-existent tasks
- ✅ **Better errors**: Immediate error if dependency not decorated with `@task`

### 3. Heterogeneous Execution (Executor Specification) ⭐

**Problem**: Original design assumed all tasks run in the same environment. What if you want different tasks on different platforms (DBT, Databricks, Spark, etc.)?

**Solution**: Added `executor` parameter to specify execution backend per task.

```python
@task
def load_data():
    """Runs locally"""
    pass

@task(depends_on=[load_data], executor="dbt")
def run_dbt_models():
    """Runs on DBT"""
    pass

@task(depends_on=[run_dbt_models], executor="databricks")
def transform_on_databricks():
    """Runs on Databricks"""
    pass

@task(depends_on=[transform_on_databricks], executor="spark")
def aggregate_on_spark():
    """Runs on Spark cluster"""
    pass
```

**Benefits**:
- ✅ **Heterogeneous pipelines**: Mix local, DBT, Databricks, Spark, etc.
- ✅ **Right tool for the job**: Use the best platform for each task
- ✅ **Infrastructure generation**: Generate different resources per executor
- ✅ **Future-proof**: Easy to add new executors

**Supported Executors** (extensible):
- `local` (default) - Local Python process
- `dbt` - DBT models
- `databricks` - Databricks jobs
- `spark` - Spark jobs
- `airflow` - Airflow operators
- Custom executors can be added

### 4. Modern Python Typing ⭐

**Problem**: Code used deprecated typing conventions (`Optional`, `Dict`, `List` from `typing` module).

**Solution**: Migrated to modern Python 3.10+ union syntax.

```python
# OLD WAY - Deprecated
from typing import Optional, Dict, List

def my_func(x: Optional[str], config: Dict[str, Any]) -> List[int]:
    pass
```

```python
# NEW WAY - Modern Python
def my_func(x: str | None, config: dict[str, Any]) -> list[int]:
    pass
```

**Changes**:
- ❌ `Optional[X]` → ✅ `X | None`
- ❌ `Dict[K, V]` → ✅ `dict[K, V]`
- ❌ `List[X]` → ✅ `list[X]`
- ❌ `Tuple[X, Y]` → ✅ `tuple[X, Y]`

**Benefits**:
- ✅ **Modern codebase**: Uses current Python best practices
- ✅ **Cleaner syntax**: Easier to read
- ✅ **Better performance**: Built-in types are faster
- ✅ **Future-proof**: This is the direction Python is going

### 5. Multi-Cloud Source Implementations

Added support for Azure Blob Storage and Google Cloud Storage:

**Azure**:
```python
from glacier.providers import AzureProvider

provider = AzureProvider(
    resource_group="my-rg",
    location="eastus",
    storage_account="mystorageacct"
)

source = provider.bucket_source(
    bucket="mycontainer",
    path="data.parquet"
)
# Creates AzureBlobSource with Azure-specific metadata
```

**GCP**:
```python
from glacier.providers import GCPProvider

provider = GCPProvider(
    project_id="my-project",
    region="us-central1"
)

source = provider.bucket_source(
    bucket="my-gcs-bucket",
    path="data.parquet"
)
# Creates GCSSource with GCP-specific metadata
```

## Migration Guide

### Updating Existing Pipelines

#### 1. Update Imports

```python
# OLD
from glacier.sources import S3Source

# NEW
from glacier.providers import AWSProvider
```

#### 2. Use Provider to Create Sources

```python
# OLD
data_source = S3Source(
    bucket="my-bucket",
    path="data.parquet",
    region="us-east-1"
)

# NEW
provider = AWSProvider(region="us-east-1")
data_source = provider.bucket_source(
    bucket="my-bucket",
    path="data.parquet"
)
```

#### 3. Update Task Dependencies

```python
# OLD
@task
def load_data():
    pass

@task(depends_on=["load_data"])  # String
def process():
    pass

# NEW
@task
def load_data():
    pass

@task(depends_on=[load_data])  # Task object
def process():
    pass
```

#### 4. Optionally Specify Executors

```python
# Add executor specification where needed
@task(depends_on=[load_data], executor="databricks")
def heavy_transform():
    pass
```

## Architectural Benefits

### Before (V1)

```
Pipeline Code
    ↓
Hardcoded S3Source
    ↓
Can only deploy to AWS
```

### After (V2)

```
Pipeline Code
    ↓
Provider Abstraction (AWS/Azure/GCP/Local)
    ↓
Creates appropriate source
    ↓
Can deploy to any cloud!
```

## Design Patterns Used

### 1. Abstract Factory Pattern (Provider)
Providers are factories that create cloud-specific sources without exposing the implementation details to pipeline code.

### 2. Adapter Pattern (Sources)
Each cloud provider's source adapts the cloud-specific API to Glacier's unified interface.

### 3. Strategy Pattern (Executors)
Different execution strategies (local, databricks, dbt) can be swapped without changing task logic.

## Infrastructure Generation Impact

With providers, infrastructure generation can now:

1. **Detect provider type** from pipeline analysis
2. **Generate appropriate IaC**:
   - AWS → Terraform with AWS resources
   - Azure → Terraform with Azure resources
   - GCP → Terraform with GCP resources
   - Local → No cloud resources needed

3. **Multi-cloud deployments**: Same pipeline, different providers per environment
   ```python
   # Dev environment
   dev_provider = LocalProvider()

   # Staging environment
   staging_provider = AWSProvider(region="us-west-2")

   # Production (multi-cloud)
   prod_provider_primary = AWSProvider(region="us-east-1")
   prod_provider_dr = AzureProvider(resource_group="dr-rg")
   ```

## Backward Compatibility

The changes are **mostly backward compatible**:

✅ **Still works**: Direct source instantiation (`S3Source(...)`)
✅ **Still works**: Simple pipelines without dependencies
✅ **Still works**: All existing examples (with deprecation warnings)

❌ **Breaking change**: String-based dependencies in `depends_on` now require Task objects
- **Why**: Prevents bugs and improves type safety
- **Fix**: Easy automated migration possible

## Future Enhancements

### Phase 1 (Current)
- ✅ Provider abstraction
- ✅ Explicit dependencies
- ✅ Executor specification
- ✅ Modern typing

### Phase 2 (Next)
- [ ] Executor implementations (databricks, dbt, spark)
- [ ] Multi-cloud infrastructure generation
- [ ] Provider credential management
- [ ] Cross-cloud data transfer

### Phase 3 (Future)
- [ ] Data locality optimization
- [ ] Cost optimization across clouds
- [ ] Automatic failover between providers
- [ ] Hybrid cloud orchestration

## Summary

These architectural improvements make Glacier:

1. **Cloud-agnostic**: Deploy to AWS, Azure, GCP, or local
2. **Type-safe**: No more magic strings
3. **Flexible**: Mix different execution backends
4. **Modern**: Uses current Python best practices
5. **Scalable**: Easy to add new providers and executors

The changes maintain Glacier's core philosophy of **Infrastructure from Code** while making the codebase more robust, flexible, and maintainable.
