"""
Cloud-agnostic resource abstractions for Glacier.

These resources provide generic interfaces that work across all cloud providers.
Users interact with these abstractions, never with cloud-specific implementations.
"""

from glacier.resources.bucket import Bucket
from glacier.resources.serverless import Serverless
from glacier.resources.execution import (
    ExecutionResource,
    LocalExecutor,
    ServerlessExecutor,
    ClusterExecutor,
    VMExecutor,
)

__all__ = [
    "Bucket",
    "Serverless",
    "ExecutionResource",
    "LocalExecutor",
    "ServerlessExecutor",
    "ClusterExecutor",
    "VMExecutor",
]
