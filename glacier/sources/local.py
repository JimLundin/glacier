"""
Local filesystem source implementation.
"""

from typing import Any, TYPE_CHECKING
from pathlib import Path
import polars as pl
from glacier.sources.bucket import BucketSource
from glacier.sources.base import SourceMetadata

if TYPE_CHECKING:
    from glacier.providers.base import Provider


class LocalSource(BucketSource):
    """
    Source for reading data from local filesystem.

    This is primarily used for:
    1. Local development and testing
    2. Small-scale deployments
    3. Data that doesn't need cloud storage

    The "bucket" parameter is treated as a base directory path.

    Note: Typically created via LocalProvider.bucket_source() for consistency.
    """

    def __init__(
        self,
        bucket: str,
        path: str = "",
        format: str = "parquet",
        name: str | None = None,
        options: dict[str, Any] | None = None,
        provider: "Provider | None" = None,
    ):
        """
        Initialize a local source.

        Args:
            bucket: Base directory path (analogous to bucket name)
            path: Relative path within the base directory
            format: Data format (parquet, csv, json, etc.)
            name: Optional name for this source
            options: Additional options for Polars scan functions
            provider: Provider that created this source
        """
        super().__init__(bucket, path, format, region=None, name=name, options=options, provider=provider)
        self.base_dir = Path(bucket)

    def scan(self) -> pl.LazyFrame:
        """
        Scan data from local filesystem using Polars LazyFrame.
        """
        file_path = self.get_file_path()

        # Map format to appropriate Polars scan function
        if self.format == "parquet":
            return pl.scan_parquet(str(file_path), **self.options)
        elif self.format == "csv":
            return pl.scan_csv(str(file_path), **self.options)
        elif self.format == "ndjson" or self.format == "jsonl":
            return pl.scan_ndjson(str(file_path), **self.options)
        elif self.format == "ipc" or self.format == "arrow":
            return pl.scan_ipc(str(file_path), **self.options)
        else:
            raise ValueError(
                f"Unsupported format '{self.format}' for LocalSource. "
                f"Supported formats: parquet, csv, ndjson, ipc"
            )

    def get_file_path(self) -> Path:
        """Get the full file path."""
        if self.path:
            return self.base_dir / self.path
        return self.base_dir

    def get_uri(self) -> str:
        """Return the file:// URI for this source."""
        return f"file://{self.get_file_path().absolute()}"

    def get_metadata(self) -> SourceMetadata:
        """Return metadata for infrastructure generation."""
        return SourceMetadata(
            source_type="local",
            cloud_provider=None,
            region=None,
            resource_name=str(self.base_dir),
            additional_config={
                "path": self.path,
                "format": self.format,
                "full_path": str(self.get_file_path()),
            },
        )

    def get_adapter(self):
        """Get the local filesystem adapter (for future extensibility)."""
        # TODO: Implement adapter pattern for custom filesystem clients
        return None

    def ensure_exists(self) -> None:
        """Ensure the base directory exists (useful for sinks)."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
