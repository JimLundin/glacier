"""
Azure provider implementation.
"""

import os
from typing import Any
from glacier.providers.base import Provider, ProviderConfig


class AzureProvider(Provider):
    """
    Azure cloud provider.

    Creates Azure-specific resources (Blob Storage, etc.) and generates
    Terraform for Azure infrastructure.

    Example:
        provider = AzureProvider(
            resource_group="my-rg",
            location="eastus"
        )

        source = provider.bucket_source(
            bucket="mycontainer",
            path="data/file.parquet"
        )
    """

    def __init__(
        self,
        resource_group: str,
        location: str = "eastus",
        subscription_id: str | None = None,
        storage_account: str | None = None,
        config: ProviderConfig | None = None,
        **kwargs,
    ):
        """
        Initialize Azure provider.

        Args:
            resource_group: Azure resource group name
            location: Azure location/region
            subscription_id: Azure subscription ID (optional)
            storage_account: Default storage account (optional)
            config: Provider configuration (optional)
            **kwargs: Additional configuration
        """
        self.resource_group = resource_group
        self.location = location
        self.subscription_id = subscription_id
        self.storage_account = storage_account

        if config is None:
            config = ProviderConfig(
                provider_type="azure",
                region=location,
                credentials={
                    "subscription_id": subscription_id,
                    "resource_group": resource_group,
                    "storage_account": storage_account,
                },
                tags=kwargs.get("tags"),
            )

        super().__init__(config, **kwargs)

    def _load_config_from_env(self, **kwargs) -> ProviderConfig:
        """Load Azure configuration from environment variables."""
        resource_group = kwargs.get("resource_group") or os.getenv("AZURE_RESOURCE_GROUP")
        location = kwargs.get("location") or os.getenv("AZURE_LOCATION", "eastus")
        subscription_id = kwargs.get("subscription_id") or os.getenv("AZURE_SUBSCRIPTION_ID")
        storage_account = kwargs.get("storage_account") or os.getenv("AZURE_STORAGE_ACCOUNT")

        if not resource_group:
            raise ValueError(
                "Azure resource group must be specified via resource_group parameter "
                "or AZURE_RESOURCE_GROUP environment variable"
            )

        return ProviderConfig(
            provider_type="azure",
            region=location,
            credentials={
                "subscription_id": subscription_id,
                "resource_group": resource_group,
                "storage_account": storage_account,
            },
            tags=kwargs.get("tags"),
        )

    def _validate_config(self) -> None:
        """Validate Azure configuration."""
        if not self.resource_group:
            raise ValueError("Azure resource group must be specified")

    def bucket_source(
        self,
        bucket: str,
        path: str,
        format: str = "parquet",
        name: str | None = None,
        options: dict[str, Any] | None = None,
    ):
        """
        Create an Azure Blob Storage source.

        Args:
            bucket: Azure container name
            path: Path within container
            format: Data format
            name: Optional name
            options: Additional options

        Returns:
            AzureBlobSource instance
        """
        from glacier.sources.azure import AzureBlobSource

        return AzureBlobSource(
            container=bucket,
            path=path,
            format=format,
            storage_account=self.storage_account,
            resource_group=self.resource_group,
            name=name,
            options=options,
            provider=self,
        )

    def get_infrastructure_metadata(self) -> dict[str, Any]:
        """Get Azure infrastructure metadata."""
        return {
            "provider": "azure",
            "location": self.location,
            "resource_group": self.resource_group,
            "subscription_id": self.subscription_id,
            "storage_account": self.storage_account,
            "requires_terraform_backend": True,
            "supported_resources": [
                "storage_account",
                "storage_container",
                "databricks_workspace",
                "data_factory",
            ],
        }

    def get_provider_type(self) -> str:
        """Return provider type."""
        return "azure"
