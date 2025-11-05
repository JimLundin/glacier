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
        # Explicit configuration
        provider = AWSProvider(region="us-east-1")

        # From environment (reads AWS_REGION, AWS_PROFILE, etc.)
        provider = AWSProvider.from_env()

        # Create a bucket source
        source = provider.bucket_source(
            bucket="my-data-bucket",
            path="data/file.parquet"
        )
    """

    def __init__(
        self,
        region: str = "us-east-1",
        profile: str | None = None,
        account_id: str | None = None,
        config: ProviderConfig | None = None,
        **kwargs,
    ):
        """
        Initialize AWS provider.

        Args:
            region: AWS region
            profile: AWS profile name (optional)
            account_id: AWS account ID (optional)
            config: Provider configuration (optional)
            **kwargs: Additional configuration
        """
        self.region = region
        self.profile = profile
        self.account_id = account_id

        if config is None:
            config = ProviderConfig(
                provider_type="aws",
                region=region,
                credentials={
                    "profile": profile,
                    "account_id": account_id,
                },
                tags=kwargs.get("tags"),
            )

        super().__init__(config, **kwargs)

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
