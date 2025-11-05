"""
AWS provider implementation.
"""

import os
from typing import Any
from glacier.providers.base import Provider, ProviderConfig


class AWSProvider(Provider):
    """
    AWS cloud provider.

    Creates AWS-specific resources (S3, IAM, etc.) and generates
    Terraform for AWS infrastructure.

    Example:
        from glacier.config import AwsConfig

        # With config (required)
        aws_config = AwsConfig(
            region="us-east-1",
            profile="production",
            tags={"environment": "prod"}
        )
        provider = AWSProvider(config=aws_config)

        # From environment variables
        provider = AWSProvider.from_env()

        # Create environment
        env = provider.env(name="production")
    """

    def __init__(self, config: Any):
        """
        Initialize AWS provider.

        Args:
            config: AwsConfig instance (required)

        Raises:
            TypeError: If config is not provided or is not an AwsConfig

        Example:
            from glacier.config import AwsConfig

            config = AwsConfig(region="us-east-1", profile="prod")
            provider = AWSProvider(config=config)
        """
        if config is None:
            raise TypeError(
                "AWSProvider requires an AwsConfig. "
                "Example: AWSProvider(config=AwsConfig(region='us-east-1'))"
            )

        if not hasattr(config, "model_dump"):
            raise TypeError(
                f"Expected AwsConfig, got {type(config)}. "
                "Use AwsConfig from glacier.config"
            )

        # Extract attributes from AwsConfig
        self.region = config.region
        self.profile = config.profile
        self.account_id = config.account_id

        # Convert AwsConfig to ProviderConfig for base class
        provider_config = ProviderConfig(
            provider_type="aws",
            region=config.region,
            credentials={
                "profile": config.profile,
                "account_id": config.account_id,
                "assume_role_arn": config.assume_role_arn,
                "session_duration": config.session_duration,
            },
            tags=config.tags if config.tags else None,
        )

        super().__init__(provider_config)

    def _load_config_from_env(self, **kwargs) -> ProviderConfig:
        """
        Load AWS configuration from environment variables.

        This is called by from_env() classmethod.
        """
        from glacier.config import AwsConfig

        # Create AwsConfig from environment variables
        aws_config = AwsConfig(
            region=os.getenv("AWS_REGION", "us-east-1"),
            profile=os.getenv("AWS_PROFILE"),
            account_id=os.getenv("AWS_ACCOUNT_ID"),
        )

        # Convert to ProviderConfig
        return ProviderConfig(
            provider_type="aws",
            region=aws_config.region,
            credentials={
                "profile": aws_config.profile,
                "account_id": aws_config.account_id,
                "assume_role_arn": aws_config.assume_role_arn,
                "session_duration": aws_config.session_duration,
            },
            tags=aws_config.tags if aws_config.tags else None,
        )

    def _validate_config(self) -> None:
        """Validate AWS configuration."""
        if not self.config.region:
            raise ValueError("AWS region must be specified")

    def _create_bucket_adapter(self, bucket):
        """Create an S3 bucket adapter."""
        from glacier.adapters.bucket import S3BucketAdapter

        return S3BucketAdapter(bucket)

    def _create_serverless_adapter(self, serverless):
        """Create a Lambda adapter."""
        from glacier.adapters.serverless import LambdaAdapter

        return LambdaAdapter(serverless)

    def get_infrastructure_metadata(self) -> dict[str, Any]:
        """Get AWS infrastructure metadata."""
        return {
            "provider": "aws",
            "region": self.config.region,
            "account_id": self.account_id,
            "profile": self.profile,
            "requires_terraform_backend": True,
            "supported_resources": [
                "s3_bucket",
                "iam_role",
                "iam_policy",
                "lambda_function",
                "glue_job",
            ],
        }

    def get_provider_type(self) -> str:
        """Return provider type."""
        return "aws"
