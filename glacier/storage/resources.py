"""
Storage Resources: Provider-agnostic storage abstractions.

These resources define WHAT data to store and WHERE, but not the
specific cloud provider implementation. The provider is chosen
at compile/execution time.
"""

from abc import ABC, abstractmethod
from typing import Any, Literal


class StorageResource(ABC):
    """
    Abstract base class for storage resources.

    Storage resources define data storage requirements without
    being tied to a specific provider (AWS, GCP, Azure, local, etc.).
    """

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """
        Convert to dictionary representation for infrastructure generation.

        Returns:
            Dictionary with resource configuration
        """
        pass

    @abstractmethod
    def get_type(self) -> str:
        """
        Get the resource type identifier.

        Returns:
            Resource type string ('object_storage', 'database', 'cache', etc.)
        """
        pass

    @abstractmethod
    def get_provider(self) -> str | None:
        """
        Get the specific provider if this is a provider-specific resource.

        Returns:
            Provider name ('aws', 'gcp', 'azure') or None if generic
        """
        pass

    @abstractmethod
    def supports_provider(self, provider: str) -> bool:
        """
        Check if this resource can be compiled to the given provider.

        Args:
            provider: Provider name ('aws', 'gcp', 'azure', 'local')

        Returns:
            True if this resource supports the provider
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

    def get_type(self) -> str:
        return "object_storage"

    def get_provider(self) -> str | None:
        return None  # Generic resource

    def supports_provider(self, provider: str) -> bool:
        """Object storage is supported by all providers"""
        return provider in ["aws", "gcp", "azure", "local"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "object_storage",
            "provider": None,
            "resource_name": self.resource_name,
            "access_pattern": self.access_pattern,
            "versioning": self.versioning,
            "encryption": self.encryption,
            "lifecycle_days": self.lifecycle_days,
            "provider_hints": self.provider_hints,
        }

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

    def get_type(self) -> str:
        return "database"

    def get_provider(self) -> str | None:
        return None  # Generic resource

    def supports_provider(self, provider: str) -> bool:
        """Database is supported by all providers"""
        return provider in ["aws", "gcp", "azure", "local"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "database",
            "provider": None,
            "engine": self.engine,
            "size": self.size,
            "resource_name": self.resource_name,
            "high_availability": self.high_availability,
            "backup_retention_days": self.backup_retention_days,
            "provider_hints": self.provider_hints,
        }

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

    def get_type(self) -> str:
        return "cache"

    def get_provider(self) -> str | None:
        return None  # Generic resource

    def supports_provider(self, provider: str) -> bool:
        """Cache is supported by all providers"""
        return provider in ["aws", "gcp", "azure", "local"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "cache",
            "provider": None,
            "size_mb": self.size_mb,
            "ttl_seconds": self.ttl_seconds,
            "engine": self.engine,
            "resource_name": self.resource_name,
            "provider_hints": self.provider_hints,
        }

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

    def get_type(self) -> str:
        return "queue"

    def get_provider(self) -> str | None:
        return None  # Generic resource

    def supports_provider(self, provider: str) -> bool:
        """Queue is supported by all providers"""
        return provider in ["aws", "gcp", "azure", "local"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "queue",
            "provider": None,
            "resource_name": self.resource_name,
            "fifo": self.fifo,
            "retention_seconds": self.retention_seconds,
            "visibility_timeout": self.visibility_timeout,
            "provider_hints": self.provider_hints,
        }

    def __repr__(self):
        name = f"name={self.resource_name}" if self.resource_name else "auto"
        fifo_str = ", FIFO" if self.fifo else ""
        return f"Queue({name}{fifo_str})"
