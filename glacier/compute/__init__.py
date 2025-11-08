"""
Compute: Provider-agnostic compute resources for task execution.

Compute resources define where and how tasks run, without being
tied to specific cloud providers.
"""

from glacier.compute.resources import (
    ComputeResource,
    Local,
    Container,
    Serverless,
    local,
    container,
    serverless,
)

__all__ = [
    "ComputeResource",
    "Local",
    "Container",
    "Serverless",
    "local",
    "container",
    "serverless",
]
