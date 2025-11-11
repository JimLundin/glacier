"""
Glacier Local Provider.

This package provides local execution for Glacier pipelines.
"""

from glacier_local.executor import LocalExecutor
from glacier_local.provider import LocalProvider

__all__ = [
    "LocalExecutor",
    "LocalProvider",
]

__version__ = "0.1.0"
