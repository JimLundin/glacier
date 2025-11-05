"""
Configuration classes for bucket-based storage.

These allow provider-specific options to be passed to generic Bucket instances.
"""

from typing import Any
from pydantic import BaseModel, Field


class BucketConfig(BaseModel):
    """
    Base configuration for bucket storage.

    This is the cloud-agnostic base class. Provider-specific configs
    inherit from this to add cloud-specific options.
    """

    class Config:
        arbitrary_types_allowed = True
        extra = "allow"  # Allow additional fields for extensibility


class S3Config(BucketConfig):
    """
    AWS S3-specific bucket configuration.

    Example:
        provider = AWSProvider()
        bucket = provider.bucket(
            "my-bucket",
            path="data.parquet",
            config=S3Config(
                versioning=True,
                encryption="AES256",
                storage_class="INTELLIGENT_TIERING"
            )
        )
    """

    versioning: bool | None = Field(
        None,
        description="Enable S3 bucket versioning"
    )
    encryption: str | None = Field(
        None,
        description="Server-side encryption (AES256, aws:kms)"
    )
    kms_key_id: str | None = Field(
        None,
        description="KMS key ID for encryption"
    )
    storage_class: str | None = Field(
        None,
        description="S3 storage class (STANDARD, INTELLIGENT_TIERING, GLACIER, etc.)"
    )
    lifecycle_rules: list[dict[str, Any]] | None = Field(
        None,
        description="S3 lifecycle rules"
    )
    replication: dict[str, Any] | None = Field(
        None,
        description="S3 replication configuration"
    )
    acceleration: bool | None = Field(
        None,
        description="Enable S3 transfer acceleration"
    )
    requester_pays: bool | None = Field(
        None,
        description="Enable requester pays"
    )


class AzureBlobConfig(BucketConfig):
    """
    Azure Blob Storage-specific configuration.

    Example:
        provider = AzureProvider()
        bucket = provider.bucket(
            "my-container",
            path="data.parquet",
            config=AzureBlobConfig(
                tier="Hot",
                replication_type="LRS"
            )
        )
    """

    tier: str | None = Field(
        None,
        description="Access tier (Hot, Cool, Archive)"
    )
    replication_type: str | None = Field(
        None,
        description="Replication type (LRS, GRS, RAGRS, ZRS, GZRS, RAGZRS)"
    )
    encryption: bool | None = Field(
        None,
        description="Enable encryption at rest"
    )
    soft_delete_retention: int | None = Field(
        None,
        description="Soft delete retention period in days"
    )
    versioning: bool | None = Field(
        None,
        description="Enable blob versioning"
    )
    lifecycle_policy: dict[str, Any] | None = Field(
        None,
        description="Lifecycle management policy"
    )
    public_access: str | None = Field(
        None,
        description="Public access level (None, Blob, Container)"
    )


class GCSConfig(BucketConfig):
    """
    Google Cloud Storage-specific configuration.

    Example:
        provider = GCPProvider()
        bucket = provider.bucket(
            "my-bucket",
            path="data.parquet",
            config=GCSConfig(
                storage_class="NEARLINE",
                versioning=True
            )
        )
    """

    storage_class: str | None = Field(
        None,
        description="Storage class (STANDARD, NEARLINE, COLDLINE, ARCHIVE)"
    )
    versioning: bool | None = Field(
        None,
        description="Enable object versioning"
    )
    lifecycle_rules: list[dict[str, Any]] | None = Field(
        None,
        description="Lifecycle rules"
    )
    uniform_bucket_level_access: bool | None = Field(
        None,
        description="Enable uniform bucket-level access"
    )
    retention_policy: dict[str, Any] | None = Field(
        None,
        description="Retention policy configuration"
    )
    encryption: dict[str, Any] | None = Field(
        None,
        description="Encryption configuration (KMS key)"
    )
    labels: dict[str, str] | None = Field(
        None,
        description="Bucket labels"
    )
