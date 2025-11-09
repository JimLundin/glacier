# Type Checker Compatibility Solution

## Problem Solved

Your original API used Dataset instances directly as type annotations, which worked perfectly at runtime but caused mypy errors:

```python
raw = Dataset(name="raw")

def extract() -> raw:  # ❌ mypy: "Variable 'raw' is not valid as a type"
    return data
```

## Solution: `typing.Annotated`

We now support the **`typing.Annotated`** pattern from PEP 593, which is the standard Python way to attach metadata to type hints. This is the same approach used by modern libraries like Typer, FastAPI, and Pydantic.

### New Pattern (Type-Checker Friendly)

```python
from typing import Annotated, Any
from glacier import Pipeline, Dataset

pipeline = Pipeline(name="etl")

# Create dataset instances as before
raw = Dataset(name="raw")
clean = Dataset(name="clean")

# Use Annotated[Type, dataset] for type hints
@pipeline.task()
def extract() -> Annotated[Any, raw]:  # ✅ mypy accepts this!
    return fetch_data()

@pipeline.task()
def transform(data: Annotated[Any, raw]) -> Annotated[Any, clean]:  # ✅ mypy accepts this!
    return process(data)
```

**How it works:**
- Type checkers see `Any` (or any other type you specify)
- At runtime, Glacier extracts the Dataset instance from the metadata
- Full backward compatibility maintained with old pattern

## Implementation Details

### Updated `Task._extract_datasets()` Method

The task extraction now handles both patterns:

```python
from typing import get_type_hints, get_origin, get_args, Annotated

# Get type hints with include_extras=True to preserve Annotated
hints = get_type_hints(self.fn, include_extras=True)

# Extract Dataset from annotation
def _extract_dataset_from_annotation(self, annotation):
    # Pattern 1: Direct instance (legacy)
    if isinstance(annotation, Dataset):
        return annotation

    # Pattern 2: Annotated[Type, dataset, ...]
    if get_origin(annotation) is Annotated:
        args = get_args(annotation)
        # args[0] is the type, args[1:] is metadata
        for metadata_item in args[1:]:
            if isinstance(metadata_item, Dataset):
                return metadata_item

    return None
```

### Key Changes

1. **Import Annotated**: `from typing import Annotated`
2. **Use `include_extras=True`**: `get_type_hints(func, include_extras=True)`
3. **Check for Annotated**: `get_origin(annotation) is Annotated`
4. **Extract metadata**: `get_args(annotation)[1:]`

## Usage Examples

### Simple Pipeline

```python
from typing import Annotated, Any
from glacier import Pipeline, Dataset

pipeline = Pipeline(name="simple")

raw = Dataset(name="raw")
processed = Dataset(name="processed")

@pipeline.task()
def extract() -> Annotated[Any, raw]:
    return {"data": [1, 2, 3]}

@pipeline.task()
def transform(data: Annotated[Any, raw]) -> Annotated[Any, processed]:
    return {"data": [x * 2 for x in data["data"]]}
```

### Multiple Outputs

```python
from typing import Annotated, Any, Tuple

users = Dataset(name="users")
events = Dataset(name="events")

@pipeline.task()
def split(data: Annotated[Any, raw]) -> Tuple[
    Annotated[Any, users],
    Annotated[Any, events]
]:
    user_data = data[data['type'] == 'user']
    event_data = data[data['type'] == 'event']
    return user_data, event_data
```

### Multiple Inputs

```python
summary = Dataset(name="summary")

@pipeline.task()
def merge(
    u: Annotated[Any, users],
    e: Annotated[Any, events]
) -> Annotated[Any, summary]:
    return {
        "user_count": len(u),
        "event_count": len(e)
    }
```

### Mixed Parameters

```python
@pipeline.task()
def process_with_config(
    data: Annotated[Any, raw],
    config: dict  # Regular parameter
) -> Annotated[Any, processed]:
    multiplier = config.get("multiplier", 1)
    return {"data": [x * multiplier for x in data["data"]]}
```

### Using More Specific Types

Instead of `Any`, you can use more specific types for better type checking:

```python
from typing import Annotated
import pandas as pd

raw_df = Dataset(name="raw_df")
clean_df = Dataset(name="clean_df")

@pipeline.task()
def extract() -> Annotated[pd.DataFrame, raw_df]:  # Type checker knows it's a DataFrame!
    return pd.DataFrame({"id": [1, 2, 3]})

@pipeline.task()
def transform(data: Annotated[pd.DataFrame, raw_df]) -> Annotated[pd.DataFrame, clean_df]:
    return data.dropna()  # ✅ Type checker knows .dropna() exists!
```

## Backward Compatibility

The old pattern still works perfectly for those who don't care about type checking:

```python
raw = Dataset(name="raw")
clean = Dataset(name="clean")

@pipeline.task()
def extract() -> raw:  # Still works at runtime!
    return data

@pipeline.task()
def transform(data: raw) -> clean:  # Still works at runtime!
    return process(data)
```

**Note:** You can mix both patterns in the same codebase. Glacier detects which pattern you're using automatically.

## Verification

### Runtime Testing

Both patterns work identically at runtime:

```bash
$ python test_annotated_pattern.py
✓ Annotated[Any, dataset] works as type annotation
✓ Type hints are extracted correctly from metadata
✓ DAG is automatically inferred
✓ Data flows correctly between tasks
✓ Backward compatible with old pattern
```

### Type Checking

The Annotated pattern passes mypy without errors:

```bash
$ mypy test_annotated_pattern.py
# No errors about invalid type annotations!
```

The old pattern requires `# type: ignore` comments:

```python
def extract() -> raw:  # type: ignore[valid-type]
    return data
```

## Comparison to Other Libraries

### Typer

```python
from typing import Annotated
import typer

def main(name: Annotated[str, typer.Option("--name")]):
    # Type checker sees: str
    # Runtime extracts: typer.Option("--name")
    print(f"Hello {name}")
```

### FastAPI

```python
from typing import Annotated
from fastapi import Query

async def read_items(q: Annotated[str | None, Query(max_length=50)]):
    # Type checker sees: str | None
    # Runtime extracts: Query(max_length=50)
    return {"q": q}
```

### Glacier

```python
from typing import Annotated, Any
from glacier import Dataset

raw = Dataset(name="raw")

def extract() -> Annotated[Any, raw]:
    # Type checker sees: Any
    # Runtime extracts: raw (Dataset instance)
    return data
```

Same pattern, different use case!

## Benefits

1. ✅ **Standards-Compliant**: Uses PEP 593 (`typing.Annotated`)
2. ✅ **Type-Checker Friendly**: Works with mypy, pyright, pytype
3. ✅ **Zero Runtime Cost**: Metadata extraction happens once at decoration
4. ✅ **Backward Compatible**: Old pattern still works
5. ✅ **Flexible**: Use `Any` or specific types
6. ✅ **Industry Standard**: Same pattern as Typer, FastAPI, Pydantic
7. ✅ **No Special Configuration**: No mypy plugins or config needed

## Migration Guide

### For Existing Code

You have two options:

**Option 1:** Add `# type: ignore[valid-type]` comments (quick fix)

```python
def extract() -> raw:  # type: ignore[valid-type]
    return data
```

**Option 2:** Migrate to Annotated pattern (recommended)

```python
# Before
def extract() -> raw:
    return data

# After
from typing import Annotated, Any

def extract() -> Annotated[Any, raw]:
    return data
```

Both work identically at runtime!

### For New Code

Use the Annotated pattern from the start:

```python
from typing import Annotated, Any
from glacier import Pipeline, Dataset

pipeline = Pipeline(name="my_pipeline")

input_data = Dataset(name="input")
output_data = Dataset(name="output")

@pipeline.task()
def process(data: Annotated[Any, input_data]) -> Annotated[Any, output_data]:
    return transform(data)
```

## Summary

We solved type checker compatibility by adopting the standard `typing.Annotated` pattern:

- **No custom mypy plugins needed**
- **No configuration files needed**
- **No version constraints**
- **Works with all type checkers**
- **Full backward compatibility**
- **Industry-standard approach**

This is the Python way to attach metadata to types!
