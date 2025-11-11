"""
Glacier: Infrastructure-from-code data pipeline library.

Glacier provides a declarative, type-safe way to define data pipelines
where infrastructure and logic are defined together.

Core concepts:
- Dataset: Named data artifacts that flow through the pipeline
- Task: Functions decorated with @task that consume/produce datasets
- Pipeline: Automatically infers DAG from task signatures
- Compute: Provider-agnostic execution resources

Example:
    from glacier import Dataset, task, Pipeline, compute

    # Declare datasets
    raw_data = Dataset("raw_data")
    clean_data = Dataset("clean_data")

    # Define tasks with type hints
    @task(compute=compute.local())
    def extract() -> raw_data:
        return fetch_from_api()

    @task(compute=compute.serverless(memory=1024))
    def transform(data: raw_data) -> clean_data:
        return process(data)

    # Pipeline automatically infers DAG from signatures
    pipeline = Pipeline([extract, transform], name="etl")

    # Run locally
    pipeline.run()

    # Or generate infrastructure
    pipeline.to_terraform("./infra")
"""

from glacier.core.dataset import Dataset
from glacier.core.task import task, Task
from glacier.core.pipeline import Pipeline
from glacier.core.environment import Environment, Provider
from glacier.core.stack import Stack
import glacier.compute as compute
import glacier.storage as storage
import glacier.secrets as secrets
import glacier.scheduling as scheduling
import glacier.monitoring as monitoring

# Import factory functions that use defaults
from glacier.defaults import (
    object_storage,
    database,
    secret,
    pipeline,
)

__version__ = "0.2.0-alpha"
__all__ = [
    "Dataset",
    "task",
    "Task",
    "Pipeline",
    "Environment",
    "Provider",
    "Stack",
    "compute",
    "storage",
    "secrets",
    "scheduling",
    "monitoring",
    # Factory functions
    "object_storage",
    "database",
    "secret",
    "pipeline",
]
