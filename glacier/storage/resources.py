"""
Storage Resources: Provider-agnostic storage abstractions.

These resources define WHAT data to store and WHERE, but not the
specific cloud provider implementation. The provider is chosen
at compile/execution time.
"""

from abc import ABC
from typing import Any, Literal


class StorageResource(ABC):
    """
    Abstract base class for storage resources.

    Storage resources define data storage requirements without
    being tied to a specific provider (AWS, GCP, Azure, local, etc.).
    """
    pass


class ObjectStorage(StorageResource):
    """
    Generic object storage (blob storage).

    Maps to:
    - S3 on AWS
    - Cloud Storage (GCS) on GCP
    - Blob Storage on Azure
    - MinIO or filesystem locally

    This is the recommended storage type for most data pipeline use cases.
    """

    def __init__(
        self,
        resource_name: str | None = None,
        access_pattern: Literal["frequent", "infrequent", "archive"] = "frequent",
        versioning: bool = False,
        encryption: bool = True,
        lifecycle_days: int | None = None,
        **provider_hints
    ):
        """
        Create an object storage resource.

        Args:
            resource_name: Optional name for the storage resource (e.g., bucket name)
            access_pattern: Data access frequency (affects storage class)
            versioning: Enable versioning for objects
            encryption: Enable encryption at rest
            lifecycle_days: Optional lifecycle policy (days until archival)
            **provider_hints: Provider-specific hints (e.g., aws_storage_class="INTELLIGENT_TIERING")
        """
        self.resource_name = resource_name
        self.access_pattern = access_pattern
        self.versioning = versioning
        self.encryption = encryption
        self.lifecycle_days = lifecycle_days
        self.provider_hints = provider_hints

    def __repr__(self):
        name = f"name={self.resource_name}" if self.resource_name else "auto"
        return f"ObjectStorage({name}, access={self.access_pattern})"


class Database(StorageResource):
    """
    Generic relational database.

    Maps to:
    - RDS on AWS
    - Cloud SQL on GCP
    - Azure SQL Database on Azure
    - PostgreSQL/MySQL locally
    """

    def __init__(
        self,
        schema: Any,
        engine: Literal["postgres", "mysql", "sqlserver"] = "postgres",
        size: Literal["small", "medium", "large"] = "small",
        resource_name: str | None = None,
        high_availability: bool = False,
        backup_retention_days: int = 7,
        **provider_hints
    ):
        """
        Create a database resource.

        Args:
            schema: Schema definition for the database
            engine: Database engine type
            size: Database instance size (rough sizing)
            resource_name: Optional name for the database instance
            high_availability: Enable HA/replication
            backup_retention_days: Number of days to retain backups
            **provider_hints: Provider-specific hints
        """
        self.schema = schema
        self.engine = engine
        self.size = size
        self.resource_name = resource_name
        self.high_availability = high_availability
        self.backup_retention_days = backup_retention_days
        self.provider_hints = provider_hints

    def __repr__(self):
        name = f"name={self.resource_name}" if self.resource_name else "auto"
        return f"Database({name}, engine={self.engine}, size={self.size})"


class Cache(StorageResource):
    """
    Generic in-memory cache/key-value store.

    Maps to:
    - ElastiCache (Redis/Memcached) on AWS
    - Memorystore on GCP
    - Azure Cache for Redis on Azure
    - Redis/Memcached locally
    """

    def __init__(
        self,
        size_mb: int = 512,
        ttl_seconds: int | None = None,
        engine: Literal["redis", "memcached"] = "redis",
        resource_name: str | None = None,
        **provider_hints
    ):
        """
        Create a cache resource.

        Args:
            size_mb: Cache size in megabytes
            ttl_seconds: Default time-to-live for cache entries
            engine: Cache engine type
            resource_name: Optional name for the cache instance
            **provider_hints: Provider-specific hints
        """
        self.size_mb = size_mb
        self.ttl_seconds = ttl_seconds
        self.engine = engine
        self.resource_name = resource_name
        self.provider_hints = provider_hints

    def __repr__(self):
        name = f"name={self.resource_name}" if self.resource_name else "auto"
        return f"Cache({name}, engine={self.engine}, size={self.size_mb}MB)"


class Queue(StorageResource):
    """
    Generic message queue.

    Maps to:
    - SQS on AWS
    - Pub/Sub on GCP
    - Service Bus on Azure
    - RabbitMQ/local queue locally
    """

    def __init__(
        self,
        resource_name: str | None = None,
        fifo: bool = False,
        retention_seconds: int = 345600,  # 4 days default
        visibility_timeout: int = 30,
        **provider_hints
    ):
        """
        Create a queue resource.

        Args:
            resource_name: Optional name for the queue
            fifo: Enable FIFO (first-in-first-out) ordering
            retention_seconds: Message retention period
            visibility_timeout: Message visibility timeout
            **provider_hints: Provider-specific hints
        """
        self.resource_name = resource_name
        self.fifo = fifo
        self.retention_seconds = retention_seconds
        self.visibility_timeout = visibility_timeout
        self.provider_hints = provider_hints

    def __repr__(self):
        name = f"name={self.resource_name}" if self.resource_name else "auto"
        fifo_str = ", FIFO" if self.fifo else ""
        return f"Queue({name}{fifo_str})"
