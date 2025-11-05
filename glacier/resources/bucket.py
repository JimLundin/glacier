"""
Generic Bucket abstraction for cloud-agnostic storage.

The Bucket class provides a unified interface for bucket-based storage
across AWS S3, Azure Blob Storage, GCS, and local filesystems.
"""

from typing import Any, TYPE_CHECKING
import polars as pl
from glacier.sources.base import Source, SourceMetadata

if TYPE_CHECKING:
    from glacier.providers.base import Provider
    from glacier.config.bucket import BucketConfig


class Bucket(Source):
    """
    Cloud-agnostic bucket abstraction.

    This class provides a generic interface for bucket storage that works
    across all cloud providers. The actual implementation is delegated to
    provider-specific adapters.

    Users should never instantiate this directly - instead, use:
        provider.bucket(name, path, ...)

    Example:
        # Works with any provider!
        provider = AWSProvider()  # or AzureProvider, GCPProvider, etc.
        bucket = provider.bucket(
            "my-data",
            path="sales/2024/data.parquet",
            format="parquet"
        )

        # Can optionally pass provider-specific config
        bucket = provider.bucket(
            "my-data",
            path="data.parquet",
            config=S3Config(versioning=True)  # Only used with AWS
        )

        # Use in pipeline (completely cloud-agnostic!)
        @task
        def load_data(source: Bucket) -> pl.LazyFrame:
            return source.scan()
    """

    def __init__(
        self,
        bucket_name: str,
        path: str,
        format: str = "parquet",
        provider: "Provider | None" = None,
        config: "BucketConfig | None" = None,
        name: str | None = None,
        options: dict[str, Any] | None = None,
    ):
        """
        Initialize a generic Bucket.

        Note: Users should not call this directly. Use provider.bucket() instead.

        Args:
            bucket_name: Name of the bucket/container
            path: Path within the bucket
            format: Data format (parquet, csv, json, etc.)
            provider: Provider that created this bucket
            config: Optional provider-specific configuration
            name: Optional name for this resource
            options: Additional options passed to scan functions
        """
        super().__init__(name, provider)
        self.bucket_name = bucket_name
        self.path = path.lstrip("/")  # Normalize path
        self.format = format.lower()
        self.config = config
        self.options = options or {}

        # Lazy-initialize the adapter
        self._adapter = None

    def _get_adapter(self):
        """
        Get the cloud-specific adapter for this bucket.

        This delegates to the provider to create the appropriate adapter
        (S3, Azure Blob, GCS, etc.) based on the provider type.
        """
        if self._adapter is None:
            if self.provider is None:
                raise ValueError(
                    "Bucket must be created through a Provider instance. "
                    "Use provider.bucket(...) instead of Bucket(...)"
                )
            self._adapter = self.provider._create_bucket_adapter(self)
        return self._adapter

    def scan(self) -> pl.LazyFrame:
        """
        Scan data from the bucket using Polars LazyFrame.

        This returns a lazy evaluation that can be optimized by Polars.
        The actual cloud-specific implementation is handled by the adapter.

        Returns:
            LazyFrame for reading the bucket data
        """
        adapter = self._get_adapter()
        return adapter.scan()

    def get_uri(self) -> str:
        """
        Return the URI for this bucket.

        The URI format depends on the provider:
        - AWS: s3://bucket/path
        - Azure: abfs://container@account.dfs.core.windows.net/path
        - GCS: gs://bucket/path
        - Local: file:///path/to/bucket
        """
        adapter = self._get_adapter()
        return adapter.get_uri()

    def get_metadata(self) -> SourceMetadata:
        """
        Return metadata for infrastructure generation.

        This is used during the "compile" phase to understand what
        infrastructure is needed (buckets, IAM roles, etc.).
        """
        adapter = self._get_adapter()
        return adapter.get_metadata()

    def exists(self) -> bool:
        """
        Check if the bucket/path exists.

        Returns:
            True if the bucket and path exist, False otherwise
        """
        adapter = self._get_adapter()
        return adapter.exists()

    def __repr__(self) -> str:
        provider_type = self.provider.get_provider_type() if self.provider else "unknown"
        return (
            f"Bucket(name='{self.bucket_name}', path='{self.path}', "
            f"format='{self.format}', provider='{provider_type}')"
        )
