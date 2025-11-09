"""
AWS-specific storage resources.

These are explicit AWS resources for when you need AWS-specific features
or want to deploy to AWS specifically.
"""

from typing import Optional, Dict, Any, List
from glacier.storage.resources import StorageResource


class S3(StorageResource):
    """
    AWS S3 bucket (provider-specific).

    Use this when:
    - You specifically want AWS S3
    - You need AWS-specific features (object lock, intelligent tiering, etc.)
    - You're building a multi-cloud pipeline with AWS storage

    For provider-agnostic storage, use ObjectStorage from glacier.storage
    """

    def __init__(
        self,
        bucket: str,
        region: str = "us-east-1",
        prefix: str = "",
        storage_class: str = "STANDARD",
        versioning: bool = False,
        encryption: Optional[str] = None,
        kms_key_id: Optional[str] = None,
        object_lock_enabled: bool = False,
        lifecycle_rules: Optional[List[Dict]] = None,
    ):
        """
        Create an S3 bucket resource.

        Args:
            bucket: S3 bucket name
            region: AWS region
            prefix: Key prefix for objects
            storage_class: S3 storage class
            versioning: Enable versioning
            encryption: Encryption type (None, "AES256", "aws:kms")
            kms_key_id: KMS key ARN (if using KMS encryption)
            object_lock_enabled: Enable object lock (compliance/governance)
            lifecycle_rules: Lifecycle configuration rules
        """
        self.bucket = bucket
        self.region = region
        self.prefix = prefix
        self.storage_class = storage_class
        self.versioning = versioning
        self.encryption = encryption
        self.kms_key_id = kms_key_id
        self.object_lock_enabled = object_lock_enabled
        self.lifecycle_rules = lifecycle_rules or []

    def get_type(self) -> str:
        return "object_storage"

    def get_provider(self) -> Optional[str]:
        return "aws"  # Provider-specific!

    def supports_provider(self, provider: str) -> bool:
        return provider == "aws"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "object_storage",
            "provider": "aws",
            "service": "s3",
            "config": {
                "bucket": self.bucket,
                "region": self.region,
                "prefix": self.prefix,
                "storage_class": self.storage_class,
                "versioning": self.versioning,
                "encryption": self.encryption,
                "kms_key_id": self.kms_key_id,
                "object_lock_enabled": self.object_lock_enabled,
                "lifecycle_rules": self.lifecycle_rules,
            }
        }

    def __repr__(self):
        return f"S3(bucket={self.bucket}, region={self.region})"


class RDS(StorageResource):
    """AWS RDS database (provider-specific)."""

    def __init__(
        self,
        instance_identifier: str,
        engine: str = "postgres",
        instance_class: str = "db.t3.micro",
        allocated_storage: int = 20,
        multi_az: bool = False,
        backup_retention_period: int = 7,
    ):
        self.instance_identifier = instance_identifier
        self.engine = engine
        self.instance_class = instance_class
        self.allocated_storage = allocated_storage
        self.multi_az = multi_az
        self.backup_retention_period = backup_retention_period

    def get_type(self) -> str:
        return "database"

    def get_provider(self) -> Optional[str]:
        return "aws"

    def supports_provider(self, provider: str) -> bool:
        return provider == "aws"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "database",
            "provider": "aws",
            "service": "rds",
            "config": {
                "instance_identifier": self.instance_identifier,
                "engine": self.engine,
                "instance_class": self.instance_class,
                "allocated_storage": self.allocated_storage,
                "multi_az": self.multi_az,
                "backup_retention_period": self.backup_retention_period,
            }
        }

    def __repr__(self):
        return f"RDS(instance={self.instance_identifier}, engine={self.engine})"
