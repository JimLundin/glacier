"""
Test file to verify type checkers accept Dataset instances as type annotations.

This file should pass mypy and pyright type checking.
"""

from glacier import Pipeline, Dataset
from typing import Tuple

# Create pipeline
pipeline = Pipeline(name="type_check_test")

# Create dataset instances
raw = Dataset(name="raw")
processed = Dataset(name="processed")
final = Dataset(name="final")
users = Dataset(name="users")
events = Dataset(name="events")

# Test 1: Simple input/output
@pipeline.task()
def extract() -> raw:
    """Task with no inputs, one output"""
    return {"data": [1, 2, 3]}

# Test 2: Single input, single output
@pipeline.task()
def transform(input_data: raw) -> processed:
    """Task with one input, one output"""
    return {"data": [x * 2 for x in input_data["data"]]}

# Test 3: Single input, single output (different name)
@pipeline.task()
def load(data: processed) -> final:
    """Task with one input, one output"""
    return {"result": sum(data["data"])}

# Test 4: Multiple outputs with Tuple
@pipeline.task()
def split(data: raw) -> Tuple[users, events]:
    """Task with one input, multiple outputs"""
    return {"users": [1, 2]}, {"events": [10, 20]}

# Test 5: Multiple inputs
@pipeline.task()
def merge(u: users, e: events) -> final:
    """Task with multiple inputs"""
    return {"users": len(u["users"]), "events": len(e["events"])}

# Test 6: Mixed parameters (Dataset + regular types)
@pipeline.task()
def process_with_config(data: raw, config: dict) -> processed:
    """Task with mixed parameter types"""
    multiplier = config.get("multiplier", 1)
    return {"data": [x * multiplier for x in data["data"]]}

# Test 7: Optional parameters
@pipeline.task()
def optional_input(data: raw, threshold: int = 10) -> processed:
    """Task with optional regular parameter"""
    return {"data": [x for x in data["data"] if x > threshold]}

print("Type checking test file created.")
print("Run: mypy test_type_checking.py")
