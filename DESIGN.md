# Glacier Design Document

## Overview

Glacier is a code-centric data pipeline library that enables **Infrastructure from Code** - the ability to generate cloud infrastructure directly from pipeline definitions.

## Core Philosophy

### Infrastructure from Code

Unlike traditional Infrastructure as Code (IaC) where you write separate configuration files, Glacier analyzes your Python pipeline code to automatically generate the required infrastructure. This means:

1. **Single Source of Truth**: Your pipeline code defines both the logic AND the infrastructure
2. **No Drift**: Infrastructure always matches your code since it's generated from it
3. **Better DX**: Write Python, not YAML or HCL
4. **Type Safety**: Full IDE support and type checking

### Code-Centric Design

Everything in Glacier is defined in Python:
- Pipelines are Python functions with `@pipeline` decorators
- Tasks are Python functions with `@task` decorators
- Sources are explicit Python objects (S3Source, LocalSource, etc.)
- Configuration is Python dictionaries

This enables:
- Rich IDE support (autocomplete, type checking, refactoring)
- Easy testing and debugging
- Programmatic generation of pipelines
- Version control of everything

## Architecture

### Layer 1: Core Abstractions

#### Sources (`glacier.sources`)

Sources represent where data comes from. They serve dual purposes:

1. **Runtime**: Provide access to data via Polars LazyFrames
2. **Compile-time**: Expose metadata for infrastructure generation

```python
class Source(ABC):
    def scan(self) -> pl.LazyFrame:
        """Runtime: Return lazy dataframe"""

    def get_metadata(self) -> SourceMetadata:
        """Compile-time: Return infrastructure metadata"""
```

**Key Design Decisions**:
- Sources are explicit objects, not strings or URIs
- This allows static analysis to discover them
- Adapter pattern enables swapping backends (S3 → GCS → Local)
- Metadata is separate from runtime logic

#### Tasks (`glacier.core.task`)

Tasks are the computational nodes in the pipeline DAG. The `@task` decorator transforms functions into Task objects that can be:

1. **Executed**: Run the actual computation
2. **Analyzed**: Extract dependencies and sources
3. **Orchestrated**: Placed in a DAG for execution

```python
@task
def my_task(source: S3Source) -> pl.LazyFrame:
    return source.scan().filter(...)
```

**Key Design Decisions**:
- Tasks are pure functions (ideally)
- Dependencies can be explicit (`depends_on=["task1"]`)
- Type hints enable inference of data flow
- Task metadata is extracted from function signatures

#### Pipelines (`glacier.core.pipeline`)

Pipelines orchestrate tasks. The `@pipeline` decorator creates a Pipeline object that can:

1. **Execute locally**: For testing and small data
2. **Generate DAG**: For visualization and validation
3. **Generate infrastructure**: For deployment

```python
@pipeline(name="my_pipeline")
def my_pipeline():
    data = load_data(source)
    result = process(data)
    return result
```

**Key Design Decisions**:
- Pipelines are entry points, not execution engines
- Same code can run locally or generate infra
- Pipeline functions define the data flow
- Multiple execution modes without code changes

### Layer 2: Execution & Analysis

#### DAG Builder (`glacier.core.dag`)

The DAG (Directed Acyclic Graph) represents task dependencies. It provides:

- **Topological sorting**: Execution order
- **Cycle detection**: Validation
- **Parallel execution levels**: Optimization opportunities

**Key Design Decisions**:
- DAG is built from task dependencies, not execution traces
- Supports both explicit and inferred dependencies
- Can detect circular dependencies before execution
- Enables parallel execution planning

#### Analyzer (`glacier.codegen.analyzer`)

The analyzer introspects pipeline code to extract:
- All tasks and their dependencies
- All sources and their metadata
- Infrastructure requirements

**Two Analysis Strategies**:

1. **Static Analysis**: Parse AST to find tasks/sources
   - Pros: Fast, no execution needed
   - Cons: Limited to simple patterns

2. **Execution Tracing**: Run code and capture calls
   - Pros: Works with dynamic code
   - Cons: Requires execution environment

**Current Implementation**: Hybrid approach, prioritizing static analysis

#### Local Executor (`glacier.runtime.local`)

Executes pipelines in the current Python process. Features:

- Direct function execution (simple)
- DAG-based execution (advanced)
- Validation without execution

**Key Design Decisions**:
- Polars handles optimization (lazy evaluation)
- Executor just orchestrates task execution
- Future: Could support parallel task execution

### Layer 3: Code Generation

#### Terraform Generator (`glacier.codegen.terraform`)

Generates Terraform configuration from pipeline analysis. Creates:

- Storage resources (S3 buckets, etc.)
- IAM policies and roles
- Networking configuration (future)
- Compute resources (future)

**Key Design Decisions**:
- Generate complete, production-ready Terraform
- Include best practices (versioning, encryption, etc.)
- Parameterize with variables for multi-env
- Include documentation in generated code

#### Future Generators

The architecture supports multiple backends:
- Pulumi (Python IaC)
- CloudFormation (AWS native)
- Kubernetes manifests (for orchestration)

### Layer 4: CLI & UX

#### CLI (`glacier.cli`)

Command-line interface with three core commands:

```bash
glacier run       # Execute locally
glacier generate  # Generate infrastructure
glacier analyze   # Show DAG and metadata
glacier validate  # Check for errors
```

**Key Design Decisions**:
- Simple, intuitive commands
- Progressive disclosure (start simple, add flags as needed)
- Rich output with colors and formatting
- Support for both interactive and CI/CD use

## Data Flow

### Runtime Execution Flow

```
1. User defines pipeline with @pipeline decorator
2. User calls pipeline.run(mode="local")
3. LocalExecutor executes the pipeline function
4. Tasks are called and return LazyFrames
5. Final result is returned (still lazy)
6. User calls .collect() to materialize
```

### Infrastructure Generation Flow

```
1. User calls pipeline.run(mode="generate")
2. Analyzer introspects the pipeline code
3. Extracts all tasks and sources
4. Builds DAG from dependencies
5. Collects infrastructure requirements from sources
6. TerraformGenerator creates .tf files
7. Files written to output directory
```

## Key Design Patterns

### Adapter Pattern

Sources use adapters to support multiple backends:

```python
class BucketSource(Source):
    """Abstract bucket interface"""

class S3Source(BucketSource):
    """AWS S3 implementation"""

class GCSSource(BucketSource):
    """Google Cloud Storage implementation"""
```

This allows users to swap backends without changing pipeline code.

### Decorator Pattern

Tasks and pipelines use decorators for clean syntax:

```python
@task
def my_task():
    pass

@pipeline
def my_pipeline():
    pass
```

Decorators wrap functions and attach metadata while preserving callable behavior.

### Strategy Pattern

Multiple execution strategies for different environments:

```python
pipeline.run(mode="local")    # LocalExecutor
pipeline.run(mode="generate") # TerraformGenerator
pipeline.run(mode="deploy")   # DeploymentEngine (future)
```

Same pipeline code, different execution strategies.

## Extension Points

### Custom Sources

Users can create custom sources:

```python
class MyCustomSource(Source):
    def scan(self) -> pl.LazyFrame:
        # Custom logic

    def get_metadata(self) -> SourceMetadata:
        # Custom metadata
```

### Custom Executors

Future: Support for custom execution engines:

```python
class AirflowExecutor(Executor):
    def execute(self):
        # Generate Airflow DAG
```

### Custom Code Generators

Future: Support for custom IaC generators:

```python
class PulumiGenerator(CodeGenerator):
    def generate(self):
        # Generate Pulumi code
```

## Future Roadmap

### Phase 1: MVP (Current)
- ✅ Core abstractions (Source, Task, Pipeline)
- ✅ Local execution
- ✅ Basic DAG analysis
- ✅ Terraform generation for S3
- ✅ CLI

### Phase 2: Cloud Integration
- [ ] GCS and Azure Blob support
- [ ] Deploy command (apply Terraform)
- [ ] Cloud executor (submit to cloud service)
- [ ] Secrets management
- [ ] Cost estimation

### Phase 3: Advanced Features
- [ ] Streaming pipelines
- [ ] Data quality checks
- [ ] Automatic retry/recovery
- [ ] Pipeline versioning
- [ ] Observability (metrics, logging)

### Phase 4: Orchestration
- [ ] Airflow integration
- [ ] Prefect integration
- [ ] Dagster integration
- [ ] Kubernetes operator

## Performance Considerations

### Lazy Evaluation

Glacier prioritizes Polars' lazy evaluation:

```python
@task
def my_task(source: S3Source) -> pl.LazyFrame:
    return source.scan()  # Returns LazyFrame, not DataFrame
```

This allows Polars to:
- Build an optimized query plan
- Push down predicates
- Minimize memory usage
- Parallelize execution

### Parallel Execution

The DAG's execution levels enable parallelization:

```python
levels = dag.get_execution_levels()
# [[task1], [task2, task3], [task4]]
# task2 and task3 can run in parallel
```

Future executors can leverage this for:
- Multi-threading
- Multi-processing
- Distributed execution

## Testing Strategy

### Unit Tests

Test individual components:
- Sources (test_sources.py)
- Tasks and Pipelines (test_decorators.py)
- DAG (test_dag.py)

### Integration Tests

Test end-to-end flows:
- Pipeline execution
- Infrastructure generation
- CLI commands

### Example Pipelines

Serve as both documentation and smoke tests:
- simple_pipeline.py
- s3_pipeline.py

## Security Considerations

### Credential Management

- Never embed credentials in code
- Use environment variables or credential files
- Support IAM roles and service accounts

### Generated Infrastructure

- Enable encryption by default
- Block public access to buckets
- Apply least-privilege IAM policies
- Enable versioning and logging

### Code Execution

- Validate pipeline code before execution
- Sandbox analysis when possible
- Warn on potentially dangerous operations

## Conclusion

Glacier's design prioritizes:

1. **Developer Experience**: Clean, intuitive Python API
2. **Infrastructure from Code**: Automatic infra generation
3. **Flexibility**: Adapter pattern for extensibility
4. **Performance**: Leverage Polars' lazy evaluation
5. **Safety**: Validation, type checking, secure defaults

The architecture is designed to be extensible, allowing for future enhancements without breaking changes.
