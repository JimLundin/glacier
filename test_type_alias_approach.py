"""
Test using TypeAlias to make mypy accept Dataset instances.
"""

from typing import TypeAlias
from glacier import Pipeline, Dataset

# Approach 1: Explicit TypeAlias annotation
raw: TypeAlias = Dataset(name="raw")  # type: ignore[misc]
processed: TypeAlias = Dataset(name="processed")  # type: ignore[misc]

pipeline = Pipeline(name="test")

@pipeline.task()
def extract() -> raw:  # type: ignore[valid-type]
    return {"data": [1, 2, 3]}

@pipeline.task()
def transform(input_data: raw) -> processed:  # type: ignore[valid-type]
    return {"data": [x * 2 for x in input_data["data"]]}  # type: ignore[index]

print("Testing TypeAlias approach")
