"""
Exploring solutions to make Dataset instances work with static type checkers.
"""

from typing import Any, TYPE_CHECKING, Generic, TypeVar, Annotated, get_type_hints
import sys

print("=" * 70)
print("EXPLORING TYPE CHECKER SOLUTIONS")
print("=" * 70)
print()

# ==============================================================================
# Solution 1: Using __mro_entries__ (PEP 560)
# ==============================================================================
print("Solution 1: Using __mro_entries__ (PEP 560)")
print("-" * 70)

class DatasetV1:
    """Dataset that uses __mro_entries__ to appear as a base class in type annotations."""

    def __init__(self, name: str):
        self.name = name
        self._value = None

    def __mro_entries__(self, bases):
        """Called when this instance is used in a base class list.

        This is what allows instances to appear in type annotations.
        It doesn't fully solve type checking, but it prevents runtime errors.
        """
        # Return the class itself
        return (DatasetV1,)

    def __repr__(self):
        return f"Dataset({self.name})"

# Test it
raw_v1 = DatasetV1("raw")
clean_v1 = DatasetV1("clean")

# This should work at runtime
def test_v1(data: raw_v1) -> clean_v1:  # type: ignore[valid-type]
    return data

print(f"Created datasets: {raw_v1}, {clean_v1}")
print(f"Function signature: {test_v1.__annotations__}")
print(f"✓ __mro_entries__ prevents runtime errors but doesn't satisfy type checkers")
print()

# ==============================================================================
# Solution 2: Dual Type/Instance Pattern
# ==============================================================================
print("Solution 2: Dual Type/Instance Pattern")
print("-" * 70)

class DatasetType:
    """The actual type that type checkers see."""
    def __init__(self, name: str):
        self.name = name

class DatasetV2:
    """Factory that returns both a type and instance."""
    _registry = {}

    def __new__(cls, name: str):
        if name not in cls._registry:
            # Create a new class for this dataset name
            dataset_class = type(
                f"Dataset_{name}",
                (DatasetType,),
                {
                    "__module__": cls.__module__,
                    "name": name,
                    "_instance": None,
                }
            )
            # Store the class
            cls._registry[name] = dataset_class

        return cls._registry[name]

# Test it
Raw = DatasetV2("raw")
Clean = DatasetV2("clean")

print(f"Raw type: {Raw}")
print(f"Clean type: {Clean}")
print(f"✓ Creates distinct types for each dataset")
print()

# ==============================================================================
# Solution 3: Using typing.Annotated (PEP 593)
# ==============================================================================
print("Solution 3: Using typing.Annotated")
print("-" * 70)

class DatasetV3:
    """Simple dataset class."""
    def __init__(self, name: str):
        self.name = name

    def __repr__(self):
        return f"Dataset({self.name})"

# The instance stores metadata
raw_v3 = DatasetV3("raw")
clean_v3 = DatasetV3("clean")

# For type hints, we'd use Annotated
# def transform(data: Annotated[Any, raw_v3]) -> Annotated[Any, clean_v3]:
#     return data

print(f"Created datasets: {raw_v3}, {clean_v3}")
print(f"Type hints would use: Annotated[Any, instance]")
print(f"✓ Type-checker friendly but changes API")
print()

# ==============================================================================
# Solution 4: Make Dataset itself a Generic type
# ==============================================================================
print("Solution 4: Generic Dataset with TypeVar")
print("-" * 70)

T = TypeVar('T')

class DatasetV4(Generic[T]):
    """Generic dataset that can be parameterized."""

    def __init__(self, name: str):
        self.name = name
        self._type_param = None

    def __class_getitem__(cls, name: str):
        """Allow Dataset[name] syntax."""
        instance = cls(name)
        return instance

    def __repr__(self):
        return f"Dataset({self.name})"

# This allows: Dataset["raw"]
raw_v4 = DatasetV4["raw"]
clean_v4 = DatasetV4["clean"]

print(f"Created datasets: {raw_v4}, {clean_v4}")
print(f"Syntax: Dataset['name']")
print(f"✓ Type-checker might accept this with proper stubs")
print()

# ==============================================================================
# Solution 5: Type stub files (.pyi)
# ==============================================================================
print("Solution 5: Type Stub Files (.pyi)")
print("-" * 70)
print("Create .pyi stub files with different signatures than runtime:")
print()
print("# dataset.py (runtime)")
print("class Dataset:")
print("    def __init__(self, name: str): ...")
print()
print("# dataset.pyi (type stubs)")
print("class Dataset:")
print("    def __init__(self, name: str): ...")
print("    def __class_getitem__(cls, name: str) -> type[Dataset]: ...")
print()
print("✓ Allows different type-time vs runtime behavior")
print()

# ==============================================================================
# Solution 6: Protocol-based approach
# ==============================================================================
print("Solution 6: Protocol-based approach")
print("-" * 70)
from typing import Protocol

class DatasetProtocol(Protocol):
    """Protocol that datasets conform to."""
    name: str
    _value: Any

class DatasetV6:
    def __init__(self, name: str):
        self.name = name
        self._value = None

raw_v6 = DatasetV6("raw")

# Type hints use the Protocol
def transform_v6(data: DatasetProtocol) -> DatasetProtocol:
    return data

print(f"Created dataset: {raw_v6}")
print(f"Type hints use DatasetProtocol")
print(f"✗ Loses per-dataset type safety")
print()

print("=" * 70)
print("RECOMMENDATIONS")
print("=" * 70)
print()
print("Best approach: Combination of:")
print("  1. Keep current runtime behavior (instances as annotations)")
print("  2. Add __mro_entries__ to prevent runtime errors")
print("  3. Provide .pyi stub files for type checkers")
print("  4. Optional: Create mypy plugin for full support")
print()
print("This maintains the elegant API while satisfying type checkers.")
