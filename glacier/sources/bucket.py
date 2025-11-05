"""
Bucket source abstraction for cloud-agnostic storage.
"""

from abc import abstractmethod
from typing import Any, TYPE_CHECKING
from glacier.sources.base import Source, SourceMetadata

if TYPE_CHECKING:
    from glacier.providers.base import Provider


class BucketSource(Source):
    """
    Abstract base class for bucket-based storage sources.

    This provides a unified interface for S3, GCS, Azure Blob, and local directories.
    Specific implementations handle the adapter logic for each backend.
    """

    def __init__(
        self,
        bucket: str,
        path: str,
        format: str = "parquet",
        region: str | None = None,
        name: str | None = None,
        options: dict[str, Any] | None = None,
        provider: "Provider | None" = None,
    ):
        """
        Initialize a bucket source.

        Args:
            bucket: Name of the bucket (or local directory for LocalSource)
            path: Path within the bucket to the data file/directory
            format: Data format (parquet, csv, json, etc.)
            region: Cloud region (if applicable)
            name: Optional name for this source
            options: Additional options passed to Polars scan functions
            provider: Provider that created this source
        """
        super().__init__(name, provider)
        self.bucket = bucket
        self.path = path.lstrip("/")  # Normalize path
        self.format = format.lower()
        self.region = region
        self.options = options or {}

    @abstractmethod
    def get_adapter(self):
        """
        Return the storage adapter for this bucket source.

        Adapters handle the actual I/O operations for different backends.
        """
        pass

    def get_full_path(self) -> str:
        """Get the full path within the bucket."""
        return f"{self.bucket}/{self.path}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(bucket='{self.bucket}', path='{self.path}', format='{self.format}')"
