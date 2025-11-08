"""
Core Glacier functionality.

New design:
- Datasets: Data artifacts declared with type hints
- Tasks: Functions decorated with @task
- Pipeline: Automatically infers DAG from task signatures
"""

from glacier.core.dataset import Dataset
from glacier.core.task import Task, task
from glacier.core.pipeline import Pipeline

__all__ = [
    "Dataset",
    "Task",
    "task",
    "Pipeline",
]
