"""
Provider abstraction for cloud-agnostic resource management.

IMPORTANT: Glacier uses a SINGLE Provider class that adapts its behavior
based on the configuration object injected into it. There are NO provider-
specific classes (AWSProvider, GCPProvider, etc.).

Example:
    from glacier.providers import Provider
    from glacier.config import AwsConfig, GcpConfig

    # AWS provider via config injection
    aws_provider = Provider(config=AwsConfig(region="us-east-1"))

    # GCP provider via config injection
    gcp_provider = Provider(config=GcpConfig(project_id="my-project"))

The configuration classes (AwsConfig, GcpConfig, AzureConfig, LocalConfig)
determine the provider's behavior - NOT subclasses.
"""

from glacier.providers.provider import Provider

__all__ = ["Provider"]
