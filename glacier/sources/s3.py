"""
S3 source implementation for AWS.
"""

from typing import Optional, Dict, Any
import polars as pl
from glacier.sources.bucket import BucketSource
from glacier.sources.base import SourceMetadata


class S3Source(BucketSource):
    """
    Source for reading data from AWS S3 buckets.

    This source can be introspected at "compile time" to generate:
    - S3 bucket resources
    - IAM policies for bucket access
    - VPC endpoints (if needed)

    At runtime, it uses Polars' native S3 support to read data efficiently.
    """

    def __init__(
        self,
        bucket: str,
        path: str,
        format: str = "parquet",
        region: str = "us-east-1",
        name: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize an S3 source.

        Args:
            bucket: S3 bucket name
            path: Path within the bucket
            format: Data format (parquet, csv, json, etc.)
            region: AWS region
            name: Optional name for this source
            options: Additional options for Polars scan functions
        """
        super().__init__(bucket, path, format, region, name, options)

    def scan(self) -> pl.LazyFrame:
        """
        Scan data from S3 using Polars LazyFrame.

        Returns a lazy evaluation that can be optimized by Polars.
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
                f"Unsupported format '{self.format}' for S3Source. "
                f"Supported formats: parquet, csv, ndjson, ipc"
            )

    def get_uri(self) -> str:
        """Return the S3 URI for this source."""
        return f"s3://{self.bucket}/{self.path}"

    def get_metadata(self) -> SourceMetadata:
        """Return metadata for infrastructure generation."""
        return SourceMetadata(
            source_type="s3",
            cloud_provider="aws",
            region=self.region,
            resource_name=self.bucket,
            additional_config={
                "path": self.path,
                "format": self.format,
                "requires_read_access": True,
            },
        )

    def get_adapter(self):
        """Get the S3 storage adapter (for future extensibility)."""
        # TODO: Implement adapter pattern for custom S3 clients
        return None
