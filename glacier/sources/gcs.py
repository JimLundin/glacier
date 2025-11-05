"""
Google Cloud Storage source implementation.
"""

from typing import Any, TYPE_CHECKING
import polars as pl
from glacier.sources.bucket import BucketSource
from glacier.sources.base import SourceMetadata

if TYPE_CHECKING:
    from glacier.providers.base import Provider


class GCSSource(BucketSource):
    """
    Source for reading data from Google Cloud Storage.

    This source can be introspected at "compile time" to generate:
    - GCS bucket resources
    - IAM bindings for bucket access
    - Service accounts (if needed)

    At runtime, it uses Polars' GCS support to read data efficiently.

    Note: Typically created via GCPProvider.bucket_source() for cloud-agnostic pipelines.
    """

    def __init__(
        self,
        bucket: str,
        path: str,
        format: str = "parquet",
        project_id: str | None = None,
        region: str = "us-central1",
        name: str | None = None,
        options: dict[str, Any] | None = None,
        provider: "Provider | None" = None,
    ):
        """
        Initialize a GCS source.

        Args:
            bucket: GCS bucket name
            path: Path within the bucket
            format: Data format (parquet, csv, json, etc.)
            project_id: GCP project ID
            region: GCP region
            name: Optional name for this source
            options: Additional options for Polars scan functions
            provider: Provider that created this source
        """
        self.project_id = project_id
        super().__init__(bucket, path, format, region, name, options, provider)

    def scan(self) -> pl.LazyFrame:
        """
        Scan data from GCS using Polars LazyFrame.
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
                f"Unsupported format '{self.format}' for GCSSource. "
                f"Supported formats: parquet, csv, ndjson, ipc"
            )

    def get_uri(self) -> str:
        """Return the GCS URI for this source."""
        return f"gs://{self.bucket}/{self.path}"

    def get_metadata(self) -> SourceMetadata:
        """Return metadata for infrastructure generation."""
        return SourceMetadata(
            source_type="gcs",
            cloud_provider="gcp",
            region=self.region,
            resource_name=self.bucket,
            additional_config={
                "path": self.path,
                "format": self.format,
                "project_id": self.project_id,
                "requires_read_access": True,
            },
        )

    def get_adapter(self):
        """Get the GCS storage adapter (for future extensibility)."""
        # TODO: Implement adapter pattern for custom GCS clients
        return None
