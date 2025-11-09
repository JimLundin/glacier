"""
AWS Resources: Environment-scoped resources.

All resources are created from an AWSEnvironment and carry
their environment context with them.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from glacier.storage.resources import StorageResource
from glacier.compute.resources import ComputeResource


@dataclass
class S3Resource(StorageResource):
    """
    S3 bucket resource bound to an AWS environment.

    This resource knows which AWS account and region it belongs to.
    """

    environment: 'AWSEnvironment'
    """AWS environment this resource belongs to"""

    bucket: str
    """S3 bucket name"""

    prefix: str = ""
    """Key prefix"""

    storage_class: str = "STANDARD"
    """S3 storage class"""

    versioning: bool = False
    """Enable versioning"""

    encryption: Optional[str] = None
    """Encryption type (None, "AES256", "aws:kms")"""

    kms_key_id: Optional[str] = None
    """KMS key ARN"""

    lifecycle_rules: List[Dict] = field(default_factory=list)
    """Lifecycle rules"""

    def get_type(self) -> str:
        return "object_storage"

    def get_provider(self) -> Optional[str]:
        return "aws"

    def supports_provider(self, provider: str) -> bool:
        return provider == "aws"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "object_storage",
            "provider": "aws",
            "service": "s3",
            "environment": {
                "account_id": self.environment.account_id,
                "region": self.environment.region,
                "environment": self.environment.environment,
            },
            "config": {
                "bucket": self.bucket,
                "prefix": self.prefix,
                "storage_class": self.storage_class,
                "versioning": self.versioning,
                "encryption": self.encryption,
                "kms_key_id": self.kms_key_id,
                "lifecycle_rules": self.lifecycle_rules,
            }
        }

    def __repr__(self):
        return (
            f"S3(bucket={self.bucket}, "
            f"account={self.environment.account_id}, "
            f"region={self.environment.region})"
        )


@dataclass
class RDSResource(StorageResource):
    """RDS database instance bound to an AWS environment"""

    environment: 'AWSEnvironment'
    instance_identifier: str
    engine: str = "postgres"
    instance_class: str = "db.t3.micro"
    allocated_storage: int = 20
    multi_az: bool = False

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
            "environment": {
                "account_id": self.environment.account_id,
                "region": self.environment.region,
            },
            "config": {
                "instance_identifier": self.instance_identifier,
                "engine": self.engine,
                "instance_class": self.instance_class,
                "allocated_storage": self.allocated_storage,
                "multi_az": self.multi_az,
            }
        }


@dataclass
class EFSResource(StorageResource):
    """EFS file system bound to an AWS environment"""

    environment: 'AWSEnvironment'
    file_system_name: str
    performance_mode: str = "generalPurpose"

    def get_type(self) -> str:
        return "filesystem"

    def get_provider(self) -> Optional[str]:
        return "aws"

    def supports_provider(self, provider: str) -> bool:
        return provider == "aws"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "filesystem",
            "provider": "aws",
            "service": "efs",
            "environment": {
                "account_id": self.environment.account_id,
                "region": self.environment.region,
            },
            "config": {
                "file_system_name": self.file_system_name,
                "performance_mode": self.performance_mode,
            }
        }


@dataclass
class DynamoDBResource(StorageResource):
    """DynamoDB table bound to an AWS environment"""

    environment: 'AWSEnvironment'
    table_name: str
    hash_key: str = "id"
    billing_mode: str = "PAY_PER_REQUEST"

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
            "service": "dynamodb",
            "environment": {
                "account_id": self.environment.account_id,
                "region": self.environment.region,
            },
            "config": {
                "table_name": self.table_name,
                "hash_key": self.hash_key,
                "billing_mode": self.billing_mode,
            }
        }
