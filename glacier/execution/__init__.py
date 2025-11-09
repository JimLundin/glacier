"""
Execution interfaces for Glacier pipelines.

This module provides abstract interfaces for executing pipelines.
Provider-specific executors are injected as dependencies.
"""

from glacier.execution.executor import Executor

__all__ = [
    "Executor",
]
