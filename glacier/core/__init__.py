"""
Core Glacier functionality.

The global @pipeline decorator is available for creating pipelines from functions.
Tasks are created using @executor.task() decorators on execution resources.
"""

from glacier.core.task import Task, TaskInstance
from glacier.core.pipeline import (
    Pipeline,
    TransformStep,
    PendingStep,
    pipeline,
)
from glacier.core.context import GlacierContext
from glacier.core.env import GlacierEnv

__all__ = [
    "Task",
    "TaskInstance",
    "Pipeline",
    "TransformStep",
    "PendingStep",
    "pipeline",
    "GlacierContext",
    "GlacierEnv",
]
