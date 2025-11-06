"""
Core Glacier functionality.

Pipelines are created using the builder pattern: Pipeline(name="...").source().transform().to()
Tasks are created using @executor.task() decorators on execution resources.
"""

from glacier.core.task import Task, TaskInstance
from glacier.core.pipeline import (
    Pipeline,
    TransformStep,
    PendingStep,
)
from glacier.core.context import GlacierContext
from glacier.core.env import GlacierEnv

__all__ = [
    "Task",
    "TaskInstance",
    "Pipeline",
    "TransformStep",
    "PendingStep",
    "GlacierContext",
    "GlacierEnv",
]
