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
        # Simple configuration
        provider = AWSProvider(region="us-east-1")

        # With AwsConfig (recommended for environment-first pattern)
        from glacier.config import AwsConfig

        aws_config = AwsConfig(
            region="us-east-1",
            profile="production",
            tags={"environment": "prod"}
        )
        provider = AWSProvider(config=aws_config)

        # From environment
        provider = AWSProvider.from_env()

        # Create environment
        env = provider.env(name="production")
    """

    def __init__(
        self,
        region: str | None = None,
        profile: str | None = None,
        account_id: str | None = None,
        config: Any | None = None,
        **kwargs,
    ):
        """
        Initialize AWS provider.

        Args:
            region: AWS region (optional if config provided)
            profile: AWS profile name (optional)
            account_id: AWS account ID (optional)
            config: AwsConfig or ProviderConfig instance (optional)
            **kwargs: Additional configuration
        """
        # Handle new AwsConfig class
        if config is not None and hasattr(config, "model_dump"):
            # It's an AwsConfig (Pydantic model)
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
                    "assume_role_arn": getattr(config, "assume_role_arn", None),
                    "session_duration": getattr(config, "session_duration", 3600),
                },
                tags=config.tags if config.tags else None,
            )
        elif config is not None:
            # It's a ProviderConfig (backward compatibility)
            self.region = config.region
            self.profile = config.credentials.get("profile") if config.credentials else None
            self.account_id = config.credentials.get("account_id") if config.credentials else None
            provider_config = config
        else:
            # Old-style constructor args
            self.region = region or "us-east-1"
            self.profile = profile
            self.account_id = account_id

            provider_config = ProviderConfig(
                provider_type="aws",
                region=self.region,
                credentials={
                    "profile": profile,
                    "account_id": account_id,
                },
                tags=kwargs.get("tags"),
            )

        super().__init__(provider_config, **kwargs)

    def _load_config_from_env(self, **kwargs) -> ProviderConfig:
        """Load AWS configuration from environment variables."""
        region = kwargs.get("region") or os.getenv("AWS_REGION", "us-east-1")
        profile = kwargs.get("profile") or os.getenv("AWS_PROFILE")
        account_id = kwargs.get("account_id") or os.getenv("AWS_ACCOUNT_ID")

        return ProviderConfig(
            provider_type="aws",
            region=region,
            credentials={
                "profile": profile,
                "account_id": account_id,
            },
            tags=kwargs.get("tags"),
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
