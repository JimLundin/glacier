# Glacier Architecture - Quick Reference

## One-Sentence Summary
Glacier is an ALPHA Python data pipeline library transitioning from environment-based task binding to first-class execution resources as task decorators, enabling cloud-agnostic pipeline composition.

## The Design Vision (CORRECT - in DESIGN_UX.md, README.md, examples/)

**Three Objects Users Work With:**
1. **Provider** - Creates resources based on config
   ```python
   provider = Provider(config=AwsConfig(region="us-east-1"))
   ```

2. **Execution Resources** - Where code runs (FIRST-CLASS OBJECTS)
   ```python
   local_exec = provider.local()
   lambda_exec = provider.serverless(config=LambdaConfig(memory=1024))
   databricks_exec = provider.cluster(config=DatabricksConfig(...))
   ```

3. **Storage Resources** - Where data lives
   ```python
   bucket = provider.bucket(bucket="data", path="file.parquet")
   ```

**How They Compose:**
```python
@local_exec.task()
def extract(source) -> pl.LazyFrame:
    return source.scan()

@lambda_exec.task()  
def transform(df: pl.LazyFrame) -> pl.LazyFrame:
    return df.filter(pl.col("value") > 0)

@pipeline(name="etl")
def my_pipeline():
    data = extract(bucket)
    result = transform(data)
    return result
```

## Current Implementation Status

### ✓ CORRECT (Matches Design)
- Single `Provider` class with config injection (provider.py)
- `Bucket` resource abstraction (resources/bucket.py)
- Adapter pattern for cloud implementations (adapters/)
- Config classes for all providers (config/)
- DAG builder for dependency resolution (core/dag.py)
- Pipeline and Task core classes (core/pipeline.py, core/task.py)
- Examples showing desired pattern (examples/*.py)
- Design documentation (DESIGN_UX.md, README.md)

### ✗ INCOMPLETE (Doesn't Match Design)
- **No local()/vm()/cluster() methods on Provider** → Can't create execution resources
- **Execution resources missing task() method** → Can't bind tasks to executors
- **Provider-specific classes still exist** (AWSProvider, GCPProvider, etc.) → Contradicts single Provider design
- **GlacierEnv exposed in public API** → Should be internal-only
- **Global @pipeline decorator missing** → Not exported
- **PipelineAnalyzer uses old GlacierEnv pattern** → Won't work with new design

## The Gap Explained in Code

### What Examples Show (DESIRED)
```python
local_exec = provider.local()  # This method doesn't exist yet!
@local_exec.task()             # This method doesn't exist yet!
def my_task():
    pass
```

### What's Currently Possible (OLD PATTERN)
```python
env = GlacierEnv(provider=provider)  # Not in user API per design
@env.task()                          # Old pattern, not type-safe
def my_task():
    pass
```

## Key Insights

### Why the Discrepancy?
The last commit (7e9420a) "Updated all documentation to match correct architecture" - this means:
1. Design was finalized for a breaking redesign
2. Examples and docs were updated to show the goal
3. But implementation is still mid-transition and incomplete

### What Needs to Happen
Finish implementing the new design:
1. Add `local()`, `vm()`, `cluster()` methods to Provider
2. Return execution resource objects that have `.task()` methods
3. Add `@task()` decorators to execution resource classes
4. Add global `@pipeline()` decorator and export it
5. Update PipelineAnalyzer to work with new pattern
6. Remove old provider-specific classes
7. Hide GlacierEnv from public API

### The Why (Design Rationale)
- **Type Safety**: `@executor.task()` vs `@env.task(executor="string")`
- **Cloud Agnostic**: Same code works with any provider via config
- **Explicit Composition**: Tasks clearly bound to specific resources
- **No Registry**: Pass resources directly, don't retrieve by name

## File Quick Lookup

| Need | File | Status |
|------|------|--------|
| Desired Architecture | DESIGN_UX.md | ✓ Complete |
| Design Examples | examples/*.py | ✓ Complete |
| Provider Implementation | providers/provider.py | ✓ Good (but needs methods) |
| Execution Resources | resources/serverless.py | ✗ Missing .task() |
| Task Class | core/task.py | ✓ Good |
| Pipeline Class | core/pipeline.py | ✓ Good |
| Outdated Pattern | core/env.py | ✗ Should be internal |
| DAG Builder | core/dag.py | ✓ Good |
| Old Classes | providers/aws.py, gcp.py, azure.py, local.py | ✗ Should not exist |

## How to Navigate the Code

### To Understand the Vision
1. Read: `/home/user/glacier/DESIGN_UX.md` (entire file)
2. Read: `/home/user/glacier/examples/simple_pipeline.py` (lines 1-84)
3. Read: `/home/user/glacier/examples/heterogeneous_pipeline.py` (lines 1-100)

### To See Implementation Status
1. Check: `/home/user/glacier/glacier/providers/provider.py` (lines 38-220)
2. Check: `/home/user/glacier/glacier/resources/serverless.py` (lines 33-158)
3. Check: `/home/user/glacier/glacier/core/env.py` (lines 13-147)

### To Understand Pipeline Composition
1. Study: `/home/user/glacier/glacier/core/pipeline.py` (lines 23-107)
2. Study: `/home/user/glacier/glacier/core/task.py` (lines 25-120)
3. Study: `/home/user/glacier/glacier/core/dag.py` (lines 21-170)

### To See The Gap
Compare these two files side-by-side:
- `/home/user/glacier/examples/heterogeneous_pipeline.py` (what user code should look like)
- `/home/user/glacier/glacier/core/env.py` (what currently exists)

## Critical Design Decisions

1. **No Deployment Environment** 
   - Glacier handles EXECUTION env only (where code runs, where data lives)
   - Dev/staging/prod is handled by infrastructure tools (Terraform, cloud accounts, CI/CD)

2. **Configuration Determines Everything**
   - Single Provider class
   - Config class determines cloud backend
   - Same code, different configs = works everywhere

3. **Explicit Over Implicit**
   - Resources are objects, not strings
   - Dependencies are Task objects, not strings
   - Executors are resource objects, not string names

4. **Infrastructure from Code**
   - Analyzer examines pipeline code
   - Generates Terraform for required resources
   - Auto-generates IAM policies, etc.

## Pending Work (For Implementation)

- [ ] Add `local()` method to Provider → returns LocalExecutor
- [ ] Add `serverless(config)` method signature (signature changes needed)
- [ ] Add `vm(config)` method to Provider
- [ ] Add `cluster(config)` method to Provider
- [ ] Create execution resource base class with `task()` method
- [ ] Implement `task()` on LocalExecutor, Serverless, VM, Cluster classes
- [ ] Create global `@pipeline()` decorator and export
- [ ] Update PipelineAnalyzer to discover tasks from executor decorators
- [ ] Hide GlacierEnv from public API (__init__.py)
- [ ] Remove AWSProvider, GCPProvider, AzureProvider, LocalProvider classes
- [ ] Remove base.py Provider ABC (no longer needed)

---

See **ARCHITECTURE_ANALYSIS.md** for complete 467-line detailed analysis.
