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
from glacier.config.provider import (
    AwsConfig,
    GcpConfig,
    AzureConfig,
    LocalConfig,
)

__all__ = [
    # Bucket configs
    "BucketConfig",
    "S3Config",
    "AzureBlobConfig",
    "GCSConfig",
    # Serverless configs
    "ServerlessConfig",
    "LambdaConfig",
    "AzureFunctionConfig",
    "CloudFunctionConfig",
    # Provider configs
    "AwsConfig",
    "GcpConfig",
    "AzureConfig",
    "LocalConfig",
]
