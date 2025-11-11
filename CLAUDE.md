# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Glacier is a code-centric data pipeline framework with **progressive disclosure** through three layers:
- **Layer 1 (Implicit)**: Simple pipelines with no cloud config - just Python functions and type hints
- **Layer 2 (Environment)**: Provider-agnostic cloud resources via dependency injection (switch AWS/Azure/GCP by changing config)
- **Layer 3 (Raw Pulumi)**: Full control using Pulumi directly when needed

Key innovation: **Type-driven DAG inference** - pipeline dependencies are automatically extracted from function type annotations using a novel `Annotated[Dataset, instance]` pattern.

## Pre-Release Development Principles

**⚠️ CRITICAL: This project is in pre-release (alpha). Read this carefully.**

### API Design Philosophy

We are **actively experimenting** with API design. This means:

1. **NO backwards compatibility required** - The API is not fixed and will change
2. **NO obligation to maintain failed experiments** - If an approach doesn't work, remove it entirely
3. **NO users depend on this API yet** - We have complete freedom to redesign
4. **Feel free to break things** - Boldly refactor, rename, restructure as needed
5. **Delete liberally** - Remove code that doesn't serve the current vision

When making changes:
- Do NOT try to maintain backwards compatibility
- Do NOT deprecate - just change or delete
- Do NOT add compatibility layers or migration paths
- DO feel free to completely redesign APIs that aren't working
- DO remove entire modules/patterns if they're not pulling their weight

### Modern Python (3.14) Standards

We use **Python 3.14** as the target version. This means:

1. **NEVER use `from __future__ import annotations`** - Not needed in Python 3.14
2. **ALWAYS use builtin types for type hints**:
   - ✅ `dict[str, int]` NOT ❌ `Dict[str, int]`
   - ✅ `list[str]` NOT ❌ `List[str]`
   - ✅ `set[int]` NOT ❌ `Set[int]`
   - ✅ `tuple[str, ...]` NOT ❌ `Tuple[str, ...]`
3. **Use modern type syntax** - Take advantage of Python 3.14 features

Example of correct modern typing:

```python
# ✅ CORRECT - Modern Python 3.14
def process_data(
    items: list[str],
    mapping: dict[str, int],
    options: set[str] | None = None
) -> tuple[dict[str, Any], list[str]]:
    ...

# ❌ WRONG - Old style
from typing import List, Dict, Set, Tuple, Optional

def process_data(
    items: List[str],
    mapping: Dict[str, int],
    options: Optional[Set[str]] = None
) -> Tuple[Dict[str, Any], List[str]]:
    ...
```

## Development Commands

```bash
# Run examples (may need dependencies like pandas)
python3 examples/three_layers.py
python3 examples/provider_switching.py

# Format code
uv run black glacier/ providers/

# Lint code
uv run ruff check glacier/ providers/

# Type check
uv run mypy glacier/
```

**Note**: Project is configured for Python 3.14 in pyproject.toml but works fine on Python 3.11+. The uv commands may fail until 3.14 is available - use `python3` directly for now.

## Core Architecture

### The Annotated Pattern (Critical!)

Glacier uses `typing.Annotated` to enable clean syntax while maintaining type-checker compatibility:

```python
# Dataset.__new__ returns Annotated[Dataset, instance]
raw = Dataset("raw")  # Returns: Annotated[Dataset, instance]

# This allows clean usage in function signatures:
@task
def process(x: raw) -> clean:
    return transform(x)
```

**How it works:**
1. `Dataset("raw")` returns `Annotated[Dataset, <instance>]` instead of the instance directly
2. Type checkers see `Dataset` type (first arg of Annotated)
3. Runtime code extracts the actual instance from metadata (second arg of Annotated)
4. Task decorator uses `get_origin()` and `get_args()` to extract Dataset instances from type hints

**Implementation locations:**
- `glacier/core/dataset.py:33-71` - Dataset.__new__ returns Annotated
- `glacier/core/task.py:45-70` - Task._extract_dataset_from_annotation() extracts instances
- `glacier/core/task.py:71-121` - Task._extract_datasets() builds inputs/outputs

### Progressive Disclosure API

Glacier's API provides three levels of explicitness, allowing users to start simple and progressively add control:

**Level 1: Implicit defaults** - Everything uses hidden module-level defaults:
```python
from glacier import Dataset, object_storage, pipeline

raw = Dataset("raw")
storage = object_storage("data")  # Uses default environment
etl = pipeline("etl")  # Uses default stack

@etl.task()  # Uses default environment
def extract() -> raw:
    return data
```

**Level 2: Explicit environment** - Specify cloud provider, stack is still implicit:
```python
from glacier import Environment
from glacier_aws import AWSProvider

aws = Environment(AWSProvider(...), "prod")
storage = aws.object_storage("data")  # Explicit environment

@etl.task(environment=aws)  # Explicit environment
def extract() -> raw:
    return data
```

**Level 3: Fully explicit** - Full control over Stack and Environment:
```python
from glacier import Stack
from glacier_aws import AWSProvider

stack = Stack("my-stack")
aws = stack.environment(AWSProvider(...), "aws")
storage = aws.object_storage("data")

pipeline = stack.pipeline("etl")

@pipeline.task(environment=aws)
def extract() -> raw:
    return data

compiled = stack.compile()
```

**Implementation details:**
- `glacier/defaults.py` - Default stack and environment (lazy-created)
- `glacier/__init__.py` - Exports factory functions (`object_storage`, `pipeline`, etc.)
- Factory functions internally use `get_default_stack()` and `get_default_environment()`
- Default environment uses `LocalProvider` from `glacier-local` if installed
- Compilers fall back to default environment if task doesn't specify one
- Users never explicitly set defaults - they're hidden implementation details

### DAG Inference

The Pipeline automatically builds a DAG by analyzing task signatures:

1. **Extract phase** (`task.py`): Each Task extracts Dataset instances from its function signature
   - Input datasets from parameter annotations
   - Output datasets from return annotation

2. **Build phase** (`pipeline.py:141-183`): Pipeline connects tasks:
   - Maps each Dataset to its producer Task
   - For each Task input, finds the producer Task
   - Creates edges: producer → consumer

3. **Execution phase** (`pipeline.py:283-324`): Topological sort determines execution order

### Provider Pattern (Layer 2)

Environment is **truly provider-agnostic** via dependency injection:

```python
# Environment provides generic methods
class Environment:
    def object_storage(self, name, **kwargs):
        return self.provider.object_storage(name=name, env_tags=self.tags, **kwargs)

# Provider implementations handle cloud-specific details
class AWSProvider(Provider):
    def object_storage(self, name, **kwargs):
        return pulumi_aws.s3.BucketV2(...)

# Switch clouds by changing provider config, not code
aws_env = Environment(provider=AWSProvider(...), name="prod")
azure_env = Environment(provider=AzureProvider(...), name="prod")
```

**Key files:**
- `glacier/core/environment.py` - Provider interface and Environment
- `providers/glacier-aws/glacier_aws/provider.py` - AWS implementation
- `providers/glacier-local/glacier_local/executor.py` - Local execution (no cloud)

### Package Structure

```
glacier/                      # Core library (no cloud dependencies)
├── core/
│   ├── pipeline.py          # DAG building and validation
│   ├── task.py              # Task decorator, dataset extraction
│   ├── dataset.py           # Annotated pattern implementation
│   └── environment.py       # Provider interface
├── storage/                 # Generic storage configs (Layer 1)
└── compute/                 # Generic compute configs (Layer 1)

providers/                   # Optional provider packages
├── glacier-aws/             # AWS via pulumi_aws
├── glacier-gcp/             # GCP (placeholder)
└── glacier-local/           # Local executor (in-memory)
```

Each provider package is independently installable and adds zero dependencies to core.

## Key Implementation Details

### Task Registration

Two patterns supported (new pattern recommended):

```python
# NEW: Decorator registers with pipeline
pipeline = Pipeline(name="etl")

@pipeline.task(compute=...)
def extract() -> raw:
    return data

# OLD: Manual registration (still works)
@task
def extract() -> raw:
    return data

pipeline = Pipeline([extract, transform])
```

### Multiple Outputs

Tasks can return tuples for multiple outputs:

```python
@task
def split(data: input) -> Tuple[left, right]:
    return left_data, right_data
```

The Task class checks if return annotation has `get_origin()` of `tuple` and extracts each Dataset.

### Validation

Pipeline validates:
- No cycles (DFS check in `pipeline.py:219-249`)
- Single producer per dataset (enforced in `pipeline.py:155-162`)
- Topological ordering exists

### Local Execution

LocalExecutor runs tasks sequentially:
1. Get topological order from pipeline
2. For each task, gather input dataset values
3. Execute task.fn(**inputs)
4. Store results in dataset_values dict
5. Make results available to downstream tasks

## Common Patterns

### Creating a Simple Pipeline

```python
from glacier import Pipeline, Dataset

pipeline = Pipeline(name="etl")
raw = Dataset(name="raw")
clean = Dataset(name="clean")

@pipeline.task()
def extract() -> raw:
    return fetch_data()

@pipeline.task()
def transform(data: raw) -> clean:
    return process(data)

# Run locally
from glacier_local import LocalExecutor
results = LocalExecutor().execute(pipeline)
```

### Adding Cloud Storage

```python
from glacier import Environment
from glacier_aws import AWSProvider

env = Environment(
    provider=AWSProvider(account="123456", region="us-east-1"),
    name="prod"
)

# Provider-agnostic - works with any provider
storage = env.object_storage(name="data")
data = Dataset(name="data", storage=storage)
```

### Mixing Layers

You can freely mix all three layers:

```python
# Layer 1: Simple datasets
temp = Dataset("temp")

# Layer 2: Provider-agnostic
storage = env.object_storage("data")
persisted = Dataset("persisted", storage=storage)

# Layer 3: Raw Pulumi
import pulumi_aws as aws
bucket = aws.s3.BucketV2("custom", versioning=...)
advanced = Dataset("advanced", storage=bucket)
```

## Testing Strategy

The project currently uses direct script execution for testing rather than pytest. Key example files:

- `examples/three_layers.py` - Demonstrates all three layers
- `examples/provider_switching.py` - Shows provider switching

## Important Notes

1. **Python Version**: Configured for 3.14 but works on 3.11+. May need to adjust pyproject.toml for development.

2. **Type Checking**: The Annotated pattern is specifically designed for mypy compatibility. Don't remove `include_extras=True` from `get_type_hints()` calls.

3. **Provider Independence**: The core `glacier` package has ZERO cloud dependencies. Keep it that way - all cloud SDKs belong in provider packages.

4. **DAG Invalidation**: When tasks are added via `@pipeline.task()`, set `_dag_built = False` to trigger rebuild on next access.

5. **Dataset Identity**: Datasets are compared by name (see `__hash__` and `__eq__` in dataset.py). Two Dataset instances with the same name are considered equal.

6. **Workspace Setup**: This is a uv workspace with multiple packages. Changes to provider packages require awareness of the workspace structure.
