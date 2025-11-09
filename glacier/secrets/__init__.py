"""
Secrets management for secure credential handling.

Provides provider-agnostic secret storage and retrieval.
"""

from glacier.secrets.resources import (
    SecretResource,
    Secret,
    secret,
)

__all__ = [
    "SecretResource",
    "Secret",
    "secret",
]
