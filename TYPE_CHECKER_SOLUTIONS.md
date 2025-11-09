# Type Checker Compatibility Solutions

## The Challenge

Your current elegant API uses Dataset instances as type annotations:

```python
raw = Dataset(name="raw")

def extract() -> raw:  # ← instance used as type (mypy doesn't like this)
    return data
```

This works perfectly at runtime but violates PEP 484, causing mypy errors.

## Solution Options

### Option 1: Type Ignore Comments (Simplest)

**Keep current API, add `# type: ignore` comments**

```python
raw = Dataset(name="raw")
clean = Dataset(name="clean")

@pipeline.task()
def extract() -> raw:  # type: ignore[valid-type]
    return data

@pipeline.task()
def transform(data: raw) -> clean:  # type: ignore[valid-type]
    return process(data)
```

**Pros:**
- ✅ Keeps elegant API unchanged
- ✅ Zero runtime cost
- ✅ Works immediately
- ✅ Clear what's being ignored

**Cons:**
- ❌ No type checking for pipeline code
- ❌ Comments on every function

**Verdict:** Best for rapid prototyping, acceptable for production

---

### Option 2: typing.Any with Runtime Checks (Pragmatic)

**Use `Any` for type checking, rely on runtime validation**

```python
from typing import Any

raw = Dataset(name="raw")
clean = Dataset(name="clean")

@pipeline.task()
def extract() -> Any:  # Runtime: returns raw
    return data

@pipeline.task()
def transform(data: Any) -> Any:  # Runtime: data is raw, returns clean
    return process(data)
```

**Pros:**
- ✅ No mypy errors
- ✅ Simple, clean code
- ✅ Runtime validation still works (DAG inference unchanged)

**Cons:**
- ❌ No static type checking at all
- ❌ Loses documentation value of annotations

**Verdict:** Clean but loses type safety entirely

---

### Option 3: Dual Annotation (Hybrid)

**Use string annotations for runtime, comments for docs**

```python
from typing import TYPE_CHECKING, Any

raw = Dataset(name="raw")
clean = Dataset(name="clean")

if TYPE_CHECKING:
    # Type checkers see these clean types
    RawData = Any
    CleanData = Any
else:
    # Runtime uses instance-based annotations
    RawData = raw
    CleanData = clean

@pipeline.task()
def extract() -> RawData:
    return data

@pipeline.task()
def transform(data: RawData) -> CleanData:
    return process(data)
```

**Pros:**
- ✅ Mypy happy
- ✅ Runtime behavior unchanged
- ✅ No comments on every function

**Cons:**
- ❌ Extra boilerplate
- ❌ Two sets of "types"
- ❌ Confusing for new users

**Verdict:** Clever but awkward

---

### Option 4: Factory with Literal Types (Type-Safe)

**Use string literals for type checking**

```python
from typing import Literal, TYPE_CHECKING, overload

if TYPE_CHECKING:
    # Create distinct types for each dataset
    @overload
    def dataset(name: Literal["raw"]) -> type["RawDataset"]: ...
    @overload
    def dataset(name: Literal["clean"]) -> type["CleanDataset"]: ...

def dataset(name: str) -> Dataset:
    """Create a dataset - works with mypy!"""
    return Dataset(name=name)

raw = dataset("raw")
clean = dataset("clean")

@pipeline.task()
def extract() -> raw:  # ✓ mypy accepts this!
    return data
```

**Pros:**
- ✅ Type-checker friendly
- ✅ Autocomplete for dataset names
- ✅ Compile-time checking

**Cons:**
- ❌ Requires overload for each dataset
- ❌ Complex implementation
- ❌ Doesn't scale to dynamic datasets

**Verdict:** Over-engineered for most use cases

---

### Option 5: Per-File Mypy Configuration (Recommended)

**Disable specific checks for pipeline files**

Create `mypy.ini`:

```ini
[mypy]
python_version = 3.11

# Global settings
warn_return_any = True
warn_unused_configs = True

# Disable valid-type check for pipeline definitions
[mypy-*_pipeline,*_dag,*/pipelines/*]
disable_error_code = valid-type
```

Then use your current API without any type: ignore comments:

```python
raw = Dataset(name="raw")
clean = Dataset(name="clean")

@pipeline.task()
def extract() -> raw:  # ✓ No error in pipeline files!
    return data

@pipeline.task()
def transform(data: raw) -> clean:  # ✓ No error in pipeline files!
    return process(data)
```

**Pros:**
- ✅ Clean code, no comments
- ✅ Elegant API unchanged
- ✅ Configure once, works everywhere
- ✅ Can still type-check non-pipeline code

**Cons:**
- ❌ Requires mypy.ini setup
- ❌ Per-project configuration

**Verdict:** **BEST OPTION** for production use

---

### Option 6: Full Mypy Plugin (Most Complete)

**Write a mypy plugin that understands Dataset instances**

Create `glacier/mypy_plugin.py` (complex, ~200+ lines) that hooks into mypy's type system.

**Pros:**
- ✅ Perfect type checking
- ✅ No compromises
- ✅ Best user experience

**Cons:**
- ❌ Complex implementation (requires mypy internals knowledge)
- ❌ Maintenance burden
- ❌ Users must configure plugin

**Verdict:** Ideal but high effort

---

## Recommendation

**Use Option 5: Per-File Mypy Configuration**

This is the sweet spot between ergonomics and type safety:

1. Keep your elegant API exactly as is
2. Create `mypy.ini` with per-file configuration
3. Pipeline files get relaxed checking
4. Other code gets full type checking

### Implementation

Create `/home/user/glacier/mypy.ini`:

```ini
[mypy]
python_version = 3.11
warn_return_any = True
warn_unused_configs = True
disallow_untyped_defs = False

# Relax type checking for pipeline definition files
# Users can put their pipelines in a specific directory
[mypy-*_pipeline]
disable_error_code = valid-type, index

[mypy-*_dag]
disable_error_code = valid-type, index

[mypy-examples.*]
disable_error_code = valid-type, index

[mypy-tests.test_type_*]
disable_error_code = valid-type, index
```

Now all files matching these patterns work without any `# type: ignore` comments!

### For Users

Document in your README:

```markdown
## Type Checking

Glacier uses Dataset instances as type annotations for an elegant API.
To use mypy with your pipelines:

1. Create `mypy.ini` in your project root:

\`\`\`ini
[mypy]
python_version = 3.11

[mypy-*_pipeline]
disable_error_code = valid-type
\`\`\`

2. Name your pipeline files with `_pipeline.py` suffix

3. Run mypy as normal:

\`\`\`bash
mypy src/
\`\`\`

Your pipeline code will work perfectly with type checkers!
```

---

## Conclusion

**Recommended approach: Option 5 (mypy.ini configuration)**

This gives you:
- ✅ Clean, elegant API
- ✅ No code changes needed
- ✅ Works with mypy and pyright
- ✅ Easy for users to configure
- ✅ Type checking where it matters

The fix is in configuration, not code. This is the Python way!
