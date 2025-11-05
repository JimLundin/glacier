"""
Base provider abstraction for cloud-agnostic infrastructure.
"""

from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel
from pathlib import Path


class ProviderConfig(BaseModel):
    """
    Configuration for a provider.

    This can be loaded from:
    - Environment variables
    - Configuration files
    - Secret stores (AWS Secrets Manager, Azure Key Vault, etc.)
    """

    provider_type: str
    region: str | None = None
    credentials: dict[str, Any] | None = None
    tags: dict[str, str] | None = None

    class Config:
        arbitrary_types_allowed = True


class Provider(ABC):
    """
    Base class for cloud providers.

    Providers abstract over different cloud platforms (AWS, Azure, GCP)
    and local development environments. They:

    1. Create sources in a platform-agnostic way
    2. Provide configuration for infrastructure generation
    3. Handle authentication and credentials
    4. Enable pipeline code to be cloud-agnostic

    Example:
        # Pipeline code doesn't know about S3 vs Azure Blob
        provider = AWSProvider(region="us-east-1")
        source = provider.bucket_source(bucket="my-data", path="file.parquet")

        # Same pipeline code, different provider
        provider = AzureProvider(resource_group="my-rg")
        source = provider.bucket_source(bucket="my-data", path="file.parquet")
    """

    def __init__(self, config: ProviderConfig | None = None, **kwargs):
        """
        Initialize the provider.

        Args:
            config: Provider configuration (optional, can load from env)
            **kwargs: Additional provider-specific configuration
        """
        self.config = config or self._load_config_from_env(**kwargs)
        self._validate_config()

    @abstractmethod
    def _load_config_from_env(self, **kwargs) -> ProviderConfig:
        """
        Load provider configuration from environment variables.

        This allows pipelines to work without hard-coded credentials.
        """
        pass

    @abstractmethod
    def _validate_config(self) -> None:
        """Validate that the provider is properly configured."""
        pass

    @abstractmethod
    def bucket_source(
        self,
        bucket: str,
        path: str,
        format: str = "parquet",
        name: str | None = None,
        options: dict[str, Any] | None = None,
    ):
        """
        Create a bucket source for this provider.

        This abstracts over S3, Azure Blob, GCS, etc.

        Args:
            bucket: Bucket/container name
            path: Path within bucket
            format: Data format (parquet, csv, etc.)
            name: Optional name for this source
            options: Additional options

        Returns:
            A source appropriate for this provider
        """
        pass

    @abstractmethod
    def get_infrastructure_metadata(self) -> dict[str, Any]:
        """
        Get metadata about infrastructure requirements.

        Used by code generators to create IaC.
        """
        pass

    @abstractmethod
    def get_provider_type(self) -> str:
        """Return the provider type (aws, azure, gcp, local)."""
        pass

    def get_tags(self) -> dict[str, str]:
        """Get default tags to apply to resources."""
        return self.config.tags or {}

    @classmethod
    def from_env(cls, **kwargs):
        """
        Create a provider instance from environment variables.

        Example:
            # Reads from AWS_REGION, AWS_ACCESS_KEY_ID, etc.
            provider = AWSProvider.from_env()
        """
        return cls(config=None, **kwargs)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(type='{self.get_provider_type()}', region='{self.config.region}')"
