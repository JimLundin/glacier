"""
AWS Environment: Convenience wrapper around Pulumi for common AWS patterns.

This is NOT a new abstraction - it's just a thin wrapper that makes Pulumi
easier to use for common cases. You can always drop down to raw Pulumi.
"""

from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class Environment:
    """
    AWS environment configuration for multi-account/multi-region deployments.

    This is a convenience wrapper that helps organize resources by environment.
    It creates Pulumi resources with sensible defaults.

    Example:
        # Define environments
        aws_prod = Environment(account="123", region="us-east-1", name="prod")
        aws_dev = Environment(account="456", region="us-west-2", name="dev")

        # Create resources in specific environments
        prod_bucket = aws_prod.s3(bucket="prod-data")
        dev_bucket = aws_dev.s3(bucket="dev-data")
    """

    account: str
    """AWS account ID"""

    region: str = "us-east-1"
    """AWS region"""

    name: str = "default"
    """Environment name (dev, staging, prod, etc.)"""

    tags: Optional[Dict[str, str]] = None
    """Default tags for all resources"""

    def __post_init__(self):
        """Initialize default tags"""
        if self.tags is None:
            self.tags = {}
        if "Environment" not in self.tags:
            self.tags["Environment"] = self.name

    def s3(self, bucket: str, **kwargs) -> Any:
        """
        Create an S3 bucket with sensible defaults.

        This wraps pulumi_aws.s3.BucketV2 with common defaults.
        For advanced features, use pulumi_aws directly (escape hatch).

        Args:
            bucket: Bucket name
            **kwargs: Additional arguments passed to pulumi_aws.s3.BucketV2

        Returns:
            Pulumi S3 bucket resource
        """
        try:
            import pulumi_aws as aws
        except ImportError:
            raise ImportError(
                "pulumi_aws not installed. Run: pip install glacier-pipeline[aws]"
            )

        # Merge environment tags with any provided tags
        resource_tags = {**self.tags, **kwargs.pop("tags", {})}

        return aws.s3.BucketV2(
            bucket,
            bucket=bucket,
            tags=resource_tags,
            **kwargs
        )

    def lambda_(
        self,
        name: str,
        handler: str,
        code: Any,
        runtime: str = "python3.11",
        **kwargs
    ) -> Any:
        """
        Create a Lambda function with sensible defaults.

        This wraps pulumi_aws.lambda_.Function with common defaults.

        Args:
            name: Function name
            handler: Function handler (e.g., "index.handler")
            code: Function code (Pulumi Archive or path)
            runtime: Lambda runtime
            **kwargs: Additional arguments passed to pulumi_aws.lambda_.Function

        Returns:
            Pulumi Lambda function resource
        """
        try:
            import pulumi_aws as aws
        except ImportError:
            raise ImportError(
                "pulumi_aws not installed. Run: pip install glacier-pipeline[aws]"
            )

        # Merge environment tags
        resource_tags = {**self.tags, **kwargs.pop("tags", {})}

        # Create IAM role if not provided
        if "role" not in kwargs:
            role = aws.iam.Role(
                f"{name}-role",
                assume_role_policy="""{
                    "Version": "2012-10-17",
                    "Statement": [{
                        "Effect": "Allow",
                        "Principal": {"Service": "lambda.amazonaws.com"},
                        "Action": "sts:AssumeRole"
                    }]
                }""",
                tags=resource_tags
            )
            kwargs["role"] = role.arn

        return aws.lambda_.Function(
            name,
            name=name,
            handler=handler,
            code=code,
            runtime=runtime,
            tags=resource_tags,
            **kwargs
        )

    def rds(
        self,
        name: str,
        engine: str = "postgres",
        instance_class: str = "db.t3.micro",
        **kwargs
    ) -> Any:
        """
        Create an RDS instance with sensible defaults.

        Args:
            name: Instance identifier
            engine: Database engine
            instance_class: Instance class
            **kwargs: Additional arguments passed to pulumi_aws.rds.Instance

        Returns:
            Pulumi RDS instance resource
        """
        try:
            import pulumi_aws as aws
        except ImportError:
            raise ImportError(
                "pulumi_aws not installed. Run: pip install glacier-pipeline[aws]"
            )

        resource_tags = {**self.tags, **kwargs.pop("tags", {})}

        return aws.rds.Instance(
            name,
            identifier=name,
            engine=engine,
            instance_class=instance_class,
            tags=resource_tags,
            **kwargs
        )

    def __repr__(self):
        return f"Environment(name={self.name}, account={self.account}, region={self.region})"
