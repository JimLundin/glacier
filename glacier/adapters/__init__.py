"""
Cloud-specific adapters for Glacier resources.

Adapters handle the actual cloud-specific implementation details,
allowing generic resources (Bucket, Serverless) to work across providers.
"""

from glacier.adapters.bucket import BucketAdapter
from glacier.adapters.serverless import ServerlessAdapter

__all__ = ["BucketAdapter", "ServerlessAdapter"]
