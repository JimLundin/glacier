"""
Cloud-agnostic configuration classes for Glacier.

These config classes allow users to specify provider-specific options
while keeping their pipeline code cloud-agnostic.
"""

from glacier.config.bucket import (
    BucketConfig,
    S3Config,
    AzureBlobConfig,
    GCSConfig,
)
from glacier.config.serverless import (
    ServerlessConfig,
    LambdaConfig,
    AzureFunctionConfig,
    CloudFunctionConfig,
)

__all__ = [
    "BucketConfig",
    "S3Config",
    "AzureBlobConfig",
    "GCSConfig",
    "ServerlessConfig",
    "LambdaConfig",
    "AzureFunctionConfig",
    "CloudFunctionConfig",
]
