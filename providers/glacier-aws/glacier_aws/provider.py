"""
AWS Provider: Implements Glacier Provider interface for AWS.

This creates actual Pulumi resources (pulumi_aws) with sensible defaults.
"""

from typing import Any
from glacier.core.environment import Provider


class AWSProvider(Provider):
    """
    AWS provider implementation.

    Creates Pulumi AWS resources with sensible defaults.
    """

    def __init__(
        self,
        account: str,
        region: str = "us-east-1",
        profile: str | None = None,
    ):
        """
        Create AWS provider.

        Args:
            account: AWS account ID
            region: AWS region
            profile: AWS profile name (optional)
        """
        self.account = account
        self.region = region
        self.profile = profile

    def get_provider_name(self) -> str:
        return "aws"

    def object_storage(self, name: str, env_tags: dict | None = None, **kwargs) -> Any:
        """
        Create S3 bucket.

        This is a thin wrapper around pulumi_aws.s3.BucketV2.
        For advanced features, use pulumi_aws directly (Layer 3).

        Args:
            name: Bucket name
            env_tags: Tags from environment
            **kwargs: Additional args passed to pulumi_aws.s3.BucketV2

        Returns:
            Pulumi S3 bucket resource
        """
        try:
            import pulumi_aws as aws
        except ImportError:
            raise ImportError(
                "pulumi_aws not installed. Run: pip install glacier-pipeline[aws]"
            )

        # Merge tags
        tags = {**(env_tags or {}), **kwargs.pop("tags", {})}

        return aws.s3.BucketV2(
            name,
            bucket=name,
            tags=tags,
            **kwargs
        )

    def serverless(
        self,
        name: str,
        handler: str,
        code: Any,
        env_tags: dict | None = None,
        runtime: str = "python3.11",
        memory: int = 512,
        timeout: int = 300,
        **kwargs
    ) -> Any:
        """
        Create Lambda function.

        This is a thin wrapper around pulumi_aws.lambda_.Function.
        For advanced features, use pulumi_aws directly (Layer 3).

        Args:
            name: Function name
            handler: Handler (e.g., "index.handler")
            code: Function code (Pulumi Archive)
            env_tags: Tags from environment
            runtime: Lambda runtime
            memory: Memory in MB
            timeout: Timeout in seconds
            **kwargs: Additional args passed to pulumi_aws.lambda_.Function

        Returns:
            Pulumi Lambda function resource
        """
        try:
            import pulumi_aws as aws
        except ImportError:
            raise ImportError(
                "pulumi_aws not installed. Run: pip install glacier-pipeline[aws]"
            )

        tags = {**(env_tags or {}), **kwargs.pop("tags", {})}

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
                tags=tags
            )
            kwargs["role"] = role.arn

        return aws.lambda_.Function(
            name,
            name=name,
            handler=handler,
            code=code,
            runtime=runtime,
            memory_size=memory,
            timeout=timeout,
            tags=tags,
            **kwargs
        )

    def database(
        self,
        name: str,
        engine: str = "postgres",
        env_tags: dict | None = None,
        instance_class: str = "db.t3.micro",
        allocated_storage: int = 20,
        **kwargs
    ) -> Any:
        """
        Create RDS instance.

        This is a thin wrapper around pulumi_aws.rds.Instance.
        For advanced features, use pulumi_aws directly (Layer 3).

        Args:
            name: Instance identifier
            engine: Database engine
            env_tags: Tags from environment
            instance_class: Instance class
            allocated_storage: Storage in GB
            **kwargs: Additional args passed to pulumi_aws.rds.Instance

        Returns:
            Pulumi RDS instance resource
        """
        try:
            import pulumi_aws as aws
        except ImportError:
            raise ImportError(
                "pulumi_aws not installed. Run: pip install glacier-pipeline[aws]"
            )

        tags = {**(env_tags or {}), **kwargs.pop("tags", {})}

        return aws.rds.Instance(
            name,
            identifier=name,
            engine=engine,
            instance_class=instance_class,
            allocated_storage=allocated_storage,
            tags=tags,
            **kwargs
        )

    def __repr__(self):
        return f"AWSProvider(account={self.account}, region={self.region})"
