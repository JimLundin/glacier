"""
Dataset: Represents a data artifact in the pipeline.

A Dataset is a named data artifact that flows through the pipeline.
It can be used in function signatures to declare inputs and outputs.
"""

from __future__ import annotations

from typing import Any
from dataclasses import dataclass


class Dataset:
    """
    A Dataset represents a data artifact in the pipeline.

    Datasets are used in function type annotations to declare:
    - What data a task consumes (input parameters)
    - What data a task produces (return type)

    The pipeline DAG is automatically inferred from these declarations.

    Example:
        raw_data = Dataset("raw_data")
        clean_data = Dataset("clean_data")

        @task
        def clean(input: raw_data) -> clean_data:
            return process(input)
    """

    def __init__(
        self,
        name: str,
        storage: Any | None = None,
        schema: Any | None = None,
        metadata: dict[str, Any] | None = None
    ):
        """
        Create a new Dataset.

        Args:
            name: Unique identifier for this dataset
            storage: Where this dataset is stored - can be our StorageResource OR a Pulumi resource
            schema: Schema definition for validation
            metadata: Additional metadata (partitioning, format, etc.)

        Example - Option 1 (our config):
            from glacier import Dataset
            from glacier.storage import ObjectStorage

            raw_data = Dataset(
                "raw_data",
                storage=ObjectStorage(
                    access_pattern="frequent",
                    versioning=True
                )
            )

        Example - Option 2 (Pulumi resource):
            import pulumi_aws as aws

            raw_data = Dataset(
                "raw_data",
                storage=aws.s3.Bucket(
                    "my-bucket",
                    versioning=aws.s3.BucketVersioningArgs(enabled=True)
                )
            )
        """
        self.name = name
        self.storage = storage  # Can be our StorageResource or a Pulumi resource
        self.schema = schema
        self.metadata = metadata or {}

        # Runtime state (populated during execution)
        self._value = None
        self._materialized = False

    def __repr__(self):
        storage_info = f", storage={self.storage}" if self.storage else ""
        return f"Dataset({self.name}{storage_info})"

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        if not isinstance(other, Dataset):
            return False
        return self.name == other.name

    def set_value(self, value: Any):
        """Set the materialized value of this dataset"""
        self._value = value
        self._materialized = True

    def get_value(self) -> Any:
        """Get the materialized value of this dataset"""
        if not self._materialized:
            raise ValueError(f"Dataset '{self.name}' has not been materialized yet")
        return self._value

    @property
    def is_materialized(self) -> bool:
        """Check if this dataset has been computed"""
        return self._materialized

    def validate(self, value: Any) -> bool:
        """
        Validate that a value conforms to this dataset's schema.

        Args:
            value: The value to validate

        Returns:
            True if valid

        Raises:
            ValueError if validation fails
        """
        if self.schema is None:
            return True

        # Schema validation logic will be implemented based on schema type
        # For now, just return True
        return True


@dataclass
class DatasetReference:
    """
    A reference to a dataset instance.
    Used internally to track dataset flow through the pipeline.
    """
    dataset: Dataset
    producer_task: Task | None = None

    def __repr__(self):
        return f"DatasetRef({self.dataset.name})"
