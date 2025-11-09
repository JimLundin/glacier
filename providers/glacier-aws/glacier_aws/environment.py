"""
AWS Environment: Represents an AWS account/region context.

An environment encapsulates:
- AWS account ID and region
- Credentials/authentication
- Naming conventions and tags
- Resource factory methods

Resources are created FROM environments, ensuring they belong
to the correct account/region context.
"""

from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class AWSEnvironment:
    """
    AWS environment context for resource creation.

    This represents a specific AWS account + region + credential context.
    Resources created from this environment belong to this context.

    Example:
        # Production environment
        aws_prod = AWSEnvironment(
            account_id="123456789012",
            region="us-east-1",
            profile="production",
            environment="prod",
            tags={"Environment": "production", "Team": "data"}
        )

        # Development environment (different account!)
        aws_dev = AWSEnvironment(
            account_id="987654321098",
            region="us-west-2",
            profile="development",
            environment="dev",
            tags={"Environment": "development"}
        )

        # Resources belong to specific environment
        prod_bucket = aws_prod.storage.s3(bucket="prod-data")
        dev_bucket = aws_dev.storage.s3(bucket="dev-data")

        @pipeline.task(compute=aws_prod.compute.lambda_(memory=1024))
        def process(data: prod_bucket) -> output:
            return transform(data)
    """

    account_id: str
    """AWS account ID"""

    region: str = "us-east-1"
    """AWS region"""

    profile: Optional[str] = None
    """AWS profile name for credentials"""

    environment: str = "default"
    """Environment name (dev, staging, prod, etc.)"""

    naming_prefix: str = ""
    """Prefix for generated resource names"""

    tags: Optional[Dict[str, str]] = None
    """Default tags for all resources in this environment"""

    vpc_id: Optional[str] = None
    """VPC ID for resources requiring VPC"""

    subnet_ids: Optional[list] = None
    """Subnet IDs for VPC resources"""

    security_group_ids: Optional[list] = None
    """Security group IDs for VPC resources"""

    def __post_init__(self):
        """Initialize resource factories"""
        self.tags = self.tags or {}
        self.storage = AWSStorageFactory(self)
        self.compute = AWSComputeFactory(self)
        self.database = AWSDatabaseFactory(self)

    def __repr__(self):
        return (
            f"AWSEnvironment(account={self.account_id}, "
            f"region={self.region}, env={self.environment})"
        )


class AWSStorageFactory:
    """Factory for creating AWS storage resources in this environment"""

    def __init__(self, environment: AWSEnvironment):
        self.environment = environment

    def s3(
        self,
        bucket: str,
        prefix: str = "",
        storage_class: str = "STANDARD",
        versioning: bool = False,
        encryption: Optional[str] = None,
        kms_key_id: Optional[str] = None,
        lifecycle_rules: Optional[list] = None,
        **kwargs
    ):
        """
        Create an S3 bucket in this environment.

        Args:
            bucket: Bucket name
            prefix: Key prefix
            storage_class: S3 storage class
            versioning: Enable versioning
            encryption: Encryption type
            kms_key_id: KMS key ARN
            lifecycle_rules: Lifecycle rules
            **kwargs: Additional S3-specific configuration

        Returns:
            S3Resource bound to this environment
        """
        from glacier_aws.resources.storage import S3Resource

        return S3Resource(
            environment=self.environment,
            bucket=bucket,
            prefix=prefix,
            storage_class=storage_class,
            versioning=versioning,
            encryption=encryption,
            kms_key_id=kms_key_id,
            lifecycle_rules=lifecycle_rules or [],
            **kwargs
        )

    def efs(self, file_system_name: str, **kwargs):
        """Create an EFS file system in this environment"""
        from glacier_aws.resources.storage import EFSResource

        return EFSResource(
            environment=self.environment,
            file_system_name=file_system_name,
            **kwargs
        )


class AWSComputeFactory:
    """Factory for creating AWS compute resources in this environment"""

    def __init__(self, environment: AWSEnvironment):
        self.environment = environment

    def lambda_(
        self,
        memory: int = 512,
        timeout: int = 300,
        runtime: str = "python3.11",
        layers: Optional[list] = None,
        reserved_concurrency: Optional[int] = None,
        environment_vars: Optional[Dict[str, str]] = None,
        **kwargs
    ):
        """
        Create a Lambda function in this environment.

        Args:
            memory: Memory in MB (128-10240)
            timeout: Timeout in seconds (1-900)
            runtime: Lambda runtime
            layers: Lambda layer ARNs
            reserved_concurrency: Reserved concurrent executions
            environment_vars: Environment variables
            **kwargs: Additional Lambda configuration

        Returns:
            LambdaResource bound to this environment
        """
        from glacier_aws.resources.compute import LambdaResource

        return LambdaResource(
            environment=self.environment,
            memory=memory,
            timeout=timeout,
            runtime=runtime,
            layers=layers or [],
            reserved_concurrency=reserved_concurrency,
            environment_vars=environment_vars or {},
            **kwargs
        )

    def ecs(
        self,
        image: str,
        cpu: int = 256,
        memory: int = 512,
        **kwargs
    ):
        """Create an ECS task in this environment"""
        from glacier_aws.resources.compute import ECSResource

        return ECSResource(
            environment=self.environment,
            image=image,
            cpu=cpu,
            memory=memory,
            **kwargs
        )


class AWSDatabaseFactory:
    """Factory for creating AWS database resources in this environment"""

    def __init__(self, environment: AWSEnvironment):
        self.environment = environment

    def rds(
        self,
        instance_identifier: str,
        engine: str = "postgres",
        instance_class: str = "db.t3.micro",
        allocated_storage: int = 20,
        **kwargs
    ):
        """Create an RDS instance in this environment"""
        from glacier_aws.resources.storage import RDSResource

        return RDSResource(
            environment=self.environment,
            instance_identifier=instance_identifier,
            engine=engine,
            instance_class=instance_class,
            allocated_storage=allocated_storage,
            **kwargs
        )

    def dynamodb(self, table_name: str, **kwargs):
        """Create a DynamoDB table in this environment"""
        from glacier_aws.resources.storage import DynamoDBResource

        return DynamoDBResource(
            environment=self.environment,
            table_name=table_name,
            **kwargs
        )
