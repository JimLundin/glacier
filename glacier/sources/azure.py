"""
Azure Blob Storage source implementation.
"""

from typing import Any, TYPE_CHECKING
import polars as pl
from glacier.sources.bucket import BucketSource
from glacier.sources.base import SourceMetadata

if TYPE_CHECKING:
    from glacier.providers.base import Provider


class AzureBlobSource(BucketSource):
    """
    Source for reading data from Azure Blob Storage.

    This source can be introspected at "compile time" to generate:
    - Azure Storage Account resources
    - Blob containers
    - Role assignments for access

    At runtime, it uses Polars' Azure support to read data efficiently.

    Note: Typically created via AzureProvider.bucket_source() for cloud-agnostic pipelines.
    """

    def __init__(
        self,
        container: str,
        path: str,
        format: str = "parquet",
        storage_account: str | None = None,
        resource_group: str | None = None,
        name: str | None = None,
        options: dict[str, Any] | None = None,
        provider: "Provider | None" = None,
    ):
        """
        Initialize an Azure Blob source.

        Args:
            container: Azure Blob container name
            path: Path within the container
            format: Data format (parquet, csv, json, etc.)
            storage_account: Azure storage account name
            resource_group: Azure resource group
            name: Optional name for this source
            options: Additional options for Polars scan functions
            provider: Provider that created this source
        """
        self.storage_account = storage_account
        self.resource_group = resource_group
        super().__init__(container, path, format, region=None, name=name, options=options, provider=provider)

    def scan(self) -> pl.LazyFrame:
        """
        Scan data from Azure Blob Storage using Polars LazyFrame.
        """
        uri = self.get_uri()

        # Map format to appropriate Polars scan function
        if self.format == "parquet":
            return pl.scan_parquet(uri, **self.options)
        elif self.format == "csv":
            return pl.scan_csv(uri, **self.options)
        elif self.format == "ndjson" or self.format == "jsonl":
            return pl.scan_ndjson(uri, **self.options)
        elif self.format == "ipc" or self.format == "arrow":
            return pl.scan_ipc(uri, **self.options)
        else:
            raise ValueError(
                f"Unsupported format '{self.format}' for AzureBlobSource. "
                f"Supported formats: parquet, csv, ndjson, ipc"
            )

    def get_uri(self) -> str:
        """Return the Azure Blob URI for this source."""
        if self.storage_account:
            return f"az://{self.bucket}/{self.path}?storage_account={self.storage_account}"
        return f"az://{self.bucket}/{self.path}"

    def get_metadata(self) -> SourceMetadata:
        """Return metadata for infrastructure generation."""
        return SourceMetadata(
            source_type="azure_blob",
            cloud_provider="azure",
            region=self.resource_group,
            resource_name=self.bucket,
            additional_config={
                "path": self.path,
                "format": self.format,
                "storage_account": self.storage_account,
                "resource_group": self.resource_group,
                "requires_read_access": True,
            },
        )

    def get_adapter(self):
        """Get the Azure storage adapter (for future extensibility)."""
        # TODO: Implement adapter pattern for custom Azure clients
        return None
