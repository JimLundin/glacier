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

    def bucket(
        self,
        bucket: str,
        path: str,
        format: str = "parquet",
        name: str | None = None,
        config: Any | None = None,
        options: dict[str, Any] | None = None,
    ):
        """
        Create a cloud-agnostic Bucket resource.

        This is the primary way users interact with bucket storage.
        Returns a generic Bucket instance that works across all providers.

        Args:
            bucket: Bucket/container name
            path: Path within bucket
            format: Data format (parquet, csv, json, etc.)
            name: Optional name for this resource
            config: Optional provider-specific configuration (S3Config, AzureBlobConfig, etc.)
            options: Additional options passed to scan functions

        Returns:
            Generic Bucket instance

        Example:
            # Cloud-agnostic code
            provider = AWSProvider()  # or any provider
            bucket = provider.bucket("my-data", path="file.parquet")

            # With provider-specific config
            from glacier.config import S3Config
            bucket = provider.bucket(
                "my-data",
                path="file.parquet",
                config=S3Config(versioning=True)
            )
        """
        from glacier.resources.bucket import Bucket

        return Bucket(
            bucket_name=bucket,
            path=path,
            format=format,
            provider=self,
            config=config,
            name=name,
            options=options,
        )

    def serverless(
        self,
        function_name: str,
        handler: Any | None = None,
        runtime: str | None = None,
        config: Any | None = None,
        **kwargs,
    ):
        """
        Create a cloud-agnostic Serverless execution environment.

        Returns a generic Serverless instance that works across all providers.

        Args:
            function_name: Name of the serverless function
            handler: Handler function or handler path
            runtime: Runtime environment (python3.11, nodejs18, etc.)
            config: Optional provider-specific configuration (LambdaConfig, etc.)
            **kwargs: Additional configuration options

        Returns:
            Generic Serverless instance

        Example:
            provider = AWSProvider()
            func = provider.serverless(
                "my-function",
                runtime="python3.11"
            )

            # With provider-specific config
            from glacier.config import LambdaConfig
            func = provider.serverless(
                "my-function",
                config=LambdaConfig(memory=1024, timeout=300)
            )
        """
        from glacier.resources.serverless import Serverless

        return Serverless(
            function_name=function_name,
            handler=handler,
            runtime=runtime,
            provider=self,
            config=config,
            **kwargs,
        )

    @abstractmethod
    def _create_bucket_adapter(self, bucket):
        """
        Create a cloud-specific bucket adapter.

        This is called internally by Bucket to get the appropriate adapter.
        Subclasses must implement this to return the correct adapter type.

        Args:
            bucket: The Bucket instance needing an adapter

        Returns:
            BucketAdapter subclass instance
        """
        pass

    @abstractmethod
    def _create_serverless_adapter(self, serverless):
        """
        Create a cloud-specific serverless adapter.

        This is called internally by Serverless to get the appropriate adapter.
        Subclasses must implement this to return the correct adapter type.

        Args:
            serverless: The Serverless instance needing an adapter

        Returns:
            ServerlessAdapter subclass instance
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

    def env(self, name: str = "default", **kwargs):
        """
        Create a GlacierEnv environment bound to this provider.

        This is a convenience factory method for creating environments
        from an existing provider instance.

        Args:
            name: Environment name (e.g., "development", "production")
            **kwargs: Additional arguments for GlacierEnv

        Returns:
            GlacierEnv instance with this provider

        Example:
            provider = AWSProvider(region="us-east-1")
            env = provider.env(name="production")

            @env.task()
            def my_task(source):
                return source.scan()
        """
        from glacier.core.env import GlacierEnv

        return GlacierEnv(provider=self, name=name, **kwargs)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(type='{self.get_provider_type()}', region='{self.config.region}')"
