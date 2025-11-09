"""
Environment: Provider-agnostic environment for organizing resources.

The Environment provides generic methods (object_storage, serverless, etc.)
and delegates to provider-specific implementations via dependency injection.
"""

from typing import Any, Optional, Dict
from dataclasses import dataclass


class Provider:
    """
    Base class for provider implementations.

    Providers implement how to create cloud resources (S3, Lambda, etc.)
    using their specific cloud SDK (pulumi_aws, pulumi_azure, etc.).
    """

    def object_storage(self, name: str, **kwargs) -> Any:
        """Create object storage (S3, Blob Storage, GCS, etc.)"""
        raise NotImplementedError

    def serverless(self, name: str, handler: str, code: Any, **kwargs) -> Any:
        """Create serverless function (Lambda, Azure Function, Cloud Run, etc.)"""
        raise NotImplementedError

    def database(self, name: str, engine: str = "postgres", **kwargs) -> Any:
        """Create managed database (RDS, Azure SQL, Cloud SQL, etc.)"""
        raise NotImplementedError

    def get_provider_name(self) -> str:
        """Return provider name (aws, azure, gcp)"""
        raise NotImplementedError


@dataclass
class Environment:
    """
    Provider-agnostic environment for organizing resources by account/region.

    The Environment provides generic resource methods and delegates to the
    provider implementation. This allows switching providers by just changing
    the provider config.

    Example - AWS:
        from glacier import Environment
        from glacier_aws import AWSProvider

        env = Environment(
            provider=AWSProvider(account="123", region="us-east-1"),
            name="prod"
        )

        storage = env.object_storage(name="data")  # Creates S3 bucket
        compute = env.serverless(name="func", handler="index.handler", code=...)

    Example - Azure (same code, different provider):
        from glacier_azure import AzureProvider

        env = Environment(
            provider=AzureProvider(subscription="xyz", region="eastus"),
            name="prod"
        )

        storage = env.object_storage(name="data")  # Creates Blob Storage
        compute = env.serverless(name="func", handler="index.handler", code=...)
    """

    provider: Provider
    """Provider implementation (AWSProvider, AzureProvider, etc.)"""

    name: str = "default"
    """Environment name (dev, staging, prod, etc.)"""

    tags: Optional[Dict[str, str]] = None
    """Tags/labels to apply to all resources"""

    def __post_init__(self):
        """Initialize default tags"""
        if self.tags is None:
            self.tags = {}
        if "Environment" not in self.tags:
            self.tags["Environment"] = self.name

    def object_storage(self, name: str, **kwargs) -> Any:
        """
        Create object storage (provider-agnostic).

        Maps to:
        - S3 on AWS
        - Blob Storage on Azure
        - Cloud Storage on GCP

        Args:
            name: Storage name
            **kwargs: Provider-specific options

        Returns:
            Pulumi resource for the object storage
        """
        return self.provider.object_storage(name=name, env_tags=self.tags, **kwargs)

    def serverless(self, name: str, handler: str, code: Any, **kwargs) -> Any:
        """
        Create serverless function (provider-agnostic).

        Maps to:
        - Lambda on AWS
        - Azure Functions on Azure
        - Cloud Functions/Cloud Run on GCP

        Args:
            name: Function name
            handler: Function handler
            code: Function code
            **kwargs: Provider-specific options

        Returns:
            Pulumi resource for the serverless function
        """
        return self.provider.serverless(
            name=name, handler=handler, code=code, env_tags=self.tags, **kwargs
        )

    def database(self, name: str, engine: str = "postgres", **kwargs) -> Any:
        """
        Create managed database (provider-agnostic).

        Maps to:
        - RDS on AWS
        - Azure Database for PostgreSQL/MySQL on Azure
        - Cloud SQL on GCP

        Args:
            name: Database identifier
            engine: Database engine (postgres, mysql, etc.)
            **kwargs: Provider-specific options

        Returns:
            Pulumi resource for the database
        """
        return self.provider.database(
            name=name, engine=engine, env_tags=self.tags, **kwargs
        )

    def __repr__(self):
        provider_name = self.provider.get_provider_name()
        return f"Environment(name={self.name}, provider={provider_name})"
