"""
Storage resources for Glacier pipelines.

This module provides provider-agnostic storage abstractions.
Specific provider implementations are injected via compilers.
"""

from glacier.storage.resources import (
    StorageResource,
    ObjectStorage,
    Database,
    Cache,
    Queue,
)

__all__ = [
    "StorageResource",
    "ObjectStorage",
    "Database",
    "Cache",
    "Queue",
]
