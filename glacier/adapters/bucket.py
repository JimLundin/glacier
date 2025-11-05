"""
Bucket adapter base class and implementations.

These adapters handle the cloud-specific logic for bucket storage,
allowing the generic Bucket class to work across all providers.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING
import polars as pl
from glacier.sources.base import SourceMetadata

if TYPE_CHECKING:
    from glacier.resources.bucket import Bucket


class BucketAdapter(ABC):
    """
    Base class for cloud-specific bucket adapters.

    Each cloud provider implements this to provide the actual
    storage access logic.
    """

    def __init__(self, bucket: "Bucket"):
        """
        Initialize the adapter.

        Args:
            bucket: The generic Bucket instance this adapter serves
        """
        self.bucket = bucket

    @abstractmethod
    def scan(self) -> pl.LazyFrame:
        """
        Scan data from the bucket.

        Returns:
            LazyFrame for reading the bucket data
        """
        pass

    @abstractmethod
    def get_uri(self) -> str:
        """
        Get the cloud-specific URI for this bucket.

        Returns:
            URI string (s3://, gs://, abfs://, file://, etc.)
        """
        pass

    @abstractmethod
    def get_metadata(self) -> SourceMetadata:
        """
        Get metadata for infrastructure generation.

        Returns:
            SourceMetadata describing this bucket
        """
        pass

    @abstractmethod
    def exists(self) -> bool:
        """
        Check if the bucket and path exist.

        Returns:
            True if exists, False otherwise
        """
        pass


class S3BucketAdapter(BucketAdapter):
    """AWS S3 adapter for Bucket."""

    def __init__(self, bucket: "Bucket"):
        super().__init__(bucket)
        self.region = bucket.provider.config.region if bucket.provider else "us-east-1"

    def scan(self) -> pl.LazyFrame:
        """Scan data from S3."""
        uri = self.get_uri()
        options = self.bucket.options

        # Map format to appropriate Polars scan function
        if self.bucket.format == "parquet":
            return pl.scan_parquet(uri, **options)
        elif self.bucket.format == "csv":
            return pl.scan_csv(uri, **options)
        elif self.bucket.format in ("ndjson", "jsonl"):
            return pl.scan_ndjson(uri, **options)
        elif self.bucket.format in ("ipc", "arrow"):
            return pl.scan_ipc(uri, **options)
        else:
            raise ValueError(
                f"Unsupported format '{self.bucket.format}' for S3. "
                f"Supported formats: parquet, csv, ndjson, ipc"
            )

    def get_uri(self) -> str:
        """Get S3 URI."""
        return f"s3://{self.bucket.bucket_name}/{self.bucket.path}"

    def get_metadata(self) -> SourceMetadata:
        """Get S3 metadata."""
        additional_config = {
            "path": self.bucket.path,
            "format": self.bucket.format,
            "requires_read_access": True,
        }

        # Add S3-specific config if provided
        if self.bucket.config:
            additional_config["s3_config"] = self.bucket.config.model_dump(exclude_none=True)

        return SourceMetadata(
            source_type="s3",
            cloud_provider="aws",
            region=self.region,
            resource_name=self.bucket.bucket_name,
            additional_config=additional_config,
        )

    def exists(self) -> bool:
        """Check if S3 bucket/path exists."""
        # TODO: Implement actual S3 existence check
        # This would require boto3 and proper error handling
        return True


class AzureBlobAdapter(BucketAdapter):
    """Azure Blob Storage adapter for Bucket."""

    def __init__(self, bucket: "Bucket"):
        super().__init__(bucket)
        self.storage_account = (
            bucket.provider.storage_account if bucket.provider else None
        )
        self.resource_group = (
            bucket.provider.resource_group if bucket.provider else None
        )

    def scan(self) -> pl.LazyFrame:
        """Scan data from Azure Blob Storage."""
        uri = self.get_uri()
        options = self.bucket.options

        # Map format to appropriate Polars scan function
        if self.bucket.format == "parquet":
            return pl.scan_parquet(uri, **options)
        elif self.bucket.format == "csv":
            return pl.scan_csv(uri, **options)
        elif self.bucket.format in ("ndjson", "jsonl"):
            return pl.scan_ndjson(uri, **options)
        elif self.bucket.format in ("ipc", "arrow"):
            return pl.scan_ipc(uri, **options)
        else:
            raise ValueError(
                f"Unsupported format '{self.bucket.format}' for Azure Blob. "
                f"Supported formats: parquet, csv, ndjson, ipc"
            )

    def get_uri(self) -> str:
        """Get Azure Blob URI."""
        if self.storage_account:
            # ABFS URI format
            return (
                f"abfs://{self.bucket.bucket_name}@{self.storage_account}"
                f".dfs.core.windows.net/{self.bucket.path}"
            )
        else:
            # Fallback to az:// format
            return f"az://{self.bucket.bucket_name}/{self.bucket.path}"

    def get_metadata(self) -> SourceMetadata:
        """Get Azure Blob metadata."""
        additional_config = {
            "path": self.bucket.path,
            "format": self.bucket.format,
            "storage_account": self.storage_account,
            "resource_group": self.resource_group,
            "requires_read_access": True,
        }

        # Add Azure-specific config if provided
        if self.bucket.config:
            additional_config["azure_config"] = self.bucket.config.model_dump(exclude_none=True)

        return SourceMetadata(
            source_type="azure_blob",
            cloud_provider="azure",
            region=self.bucket.provider.config.region if self.bucket.provider else None,
            resource_name=self.bucket.bucket_name,
            additional_config=additional_config,
        )

    def exists(self) -> bool:
        """Check if Azure blob exists."""
        # TODO: Implement actual Azure existence check
        return True


class GCSBucketAdapter(BucketAdapter):
    """Google Cloud Storage adapter for Bucket."""

    def __init__(self, bucket: "Bucket"):
        super().__init__(bucket)
        self.project_id = bucket.provider.project_id if bucket.provider else None
        self.region = bucket.provider.config.region if bucket.provider else "us-central1"

    def scan(self) -> pl.LazyFrame:
        """Scan data from GCS."""
        uri = self.get_uri()
        options = self.bucket.options

        # Map format to appropriate Polars scan function
        if self.bucket.format == "parquet":
            return pl.scan_parquet(uri, **options)
        elif self.bucket.format == "csv":
            return pl.scan_csv(uri, **options)
        elif self.bucket.format in ("ndjson", "jsonl"):
            return pl.scan_ndjson(uri, **options)
        elif self.bucket.format in ("ipc", "arrow"):
            return pl.scan_ipc(uri, **options)
        else:
            raise ValueError(
                f"Unsupported format '{self.bucket.format}' for GCS. "
                f"Supported formats: parquet, csv, ndjson, ipc"
            )

    def get_uri(self) -> str:
        """Get GCS URI."""
        return f"gs://{self.bucket.bucket_name}/{self.bucket.path}"

    def get_metadata(self) -> SourceMetadata:
        """Get GCS metadata."""
        additional_config = {
            "path": self.bucket.path,
            "format": self.bucket.format,
            "project_id": self.project_id,
            "requires_read_access": True,
        }

        # Add GCS-specific config if provided
        if self.bucket.config:
            additional_config["gcs_config"] = self.bucket.config.model_dump(exclude_none=True)

        return SourceMetadata(
            source_type="gcs",
            cloud_provider="gcp",
            region=self.region,
            resource_name=self.bucket.bucket_name,
            additional_config=additional_config,
        )

    def exists(self) -> bool:
        """Check if GCS bucket/path exists."""
        # TODO: Implement actual GCS existence check
        return True


class LocalBucketAdapter(BucketAdapter):
    """Local filesystem adapter for Bucket."""

    def scan(self) -> pl.LazyFrame:
        """Scan data from local filesystem."""
        uri = self.get_uri()
        options = self.bucket.options

        # Map format to appropriate Polars scan function
        if self.bucket.format == "parquet":
            return pl.scan_parquet(uri, **options)
        elif self.bucket.format == "csv":
            return pl.scan_csv(uri, **options)
        elif self.bucket.format in ("ndjson", "jsonl"):
            return pl.scan_ndjson(uri, **options)
        elif self.bucket.format in ("ipc", "arrow"):
            return pl.scan_ipc(uri, **options)
        else:
            raise ValueError(
                f"Unsupported format '{self.bucket.format}' for local filesystem. "
                f"Supported formats: parquet, csv, ndjson, ipc"
            )

    def get_uri(self) -> str:
        """Get local filesystem path."""
        # Treat bucket_name as base directory
        from pathlib import Path

        base_path = Path(self.bucket.bucket_name)
        full_path = base_path / self.bucket.path
        return str(full_path)

    def get_metadata(self) -> SourceMetadata:
        """Get local filesystem metadata."""
        return SourceMetadata(
            source_type="local",
            cloud_provider=None,
            region=None,
            resource_name=self.bucket.bucket_name,
            additional_config={
                "path": self.bucket.path,
                "format": self.bucket.format,
            },
        )

    def exists(self) -> bool:
        """Check if local path exists."""
        from pathlib import Path

        path = Path(self.get_uri())
        return path.exists()
