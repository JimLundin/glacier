"""
Unified Provider class - behavior determined by config injection.

This module contains the single Provider class that adapts its behavior
based on the configuration object injected into it. NO provider-specific
subclasses exist - configuration determines all behavior.
"""

import os
from typing import Any


class Provider:
    """
    Unified cloud provider that adapts behavior based on injected configuration.

    The Provider class uses dependency injection to determine its behavior.
    Instead of subclasses (AWSProvider, GCPProvider), we inject configuration
    objects (AwsConfig, GcpConfig) that determine the provider's behavior.

    Example:
        from glacier import Provider
        from glacier.config import AwsConfig, GcpConfig, AzureConfig

        # AWS behavior via config injection
        aws_provider = Provider(config=AwsConfig(region="us-east-1"))

        # GCP behavior via config injection
        gcp_provider = Provider(config=GcpConfig(project_id="my-project"))

        # Azure behavior via config injection
        azure_provider = Provider(config=AzureConfig(subscription_id="..."))

        # Same interface, different behavior based on config
        bucket = aws_provider.bucket("data", path="file.parquet")
    """

    def __init__(self, config: Any):
        """
        Initialize provider with configuration.

        Args:
            config: Configuration object (AwsConfig, GcpConfig, AzureConfig, LocalConfig)

        Raises:
            TypeError: If config is None or not a valid config type
            ValueError: If config is invalid or missing required fields

        Example:
            from glacier import Provider
            from glacier.config import AwsConfig

            config = AwsConfig(region="us-east-1", profile="production")
            provider = Provider(config=config)
        """
        if config is None:
            raise TypeError(
                "Provider requires a config object. "
                "Example: Provider(config=AwsConfig(region='us-east-1'))"
            )

        if not hasattr(config, "model_dump"):
            raise TypeError(
                f"Expected a config object (AwsConfig, GcpConfig, etc.), got {type(config)}. "
                "Import from glacier.config"
            )

        self.config = config
        self._provider_type = self._detect_provider_type()
        self._validate_config()

    def _detect_provider_type(self) -> str:
        """
        Detect provider type from config class name.

        Returns:
            Provider type string ("aws", "gcp", "azure", "local")
        """
        config_class_name = self.config.__class__.__name__

        type_map = {
            "AwsConfig": "aws",
            "GcpConfig": "gcp",
            "AzureConfig": "azure",
            "LocalConfig": "local",
        }

        if config_class_name not in type_map:
            raise TypeError(
                f"Unknown config type: {config_class_name}. "
                f"Expected one of: {list(type_map.keys())}"
            )

        return type_map[config_class_name]

    def _validate_config(self) -> None:
        """
        Validate configuration based on provider type.

        Raises:
            ValueError: If configuration is invalid
        """
        if self._provider_type == "aws":
            if not hasattr(self.config, "region") or not self.config.region:
                raise ValueError("AWS config requires 'region'")

        elif self._provider_type == "gcp":
            if not hasattr(self.config, "project_id") or not self.config.project_id:
                raise ValueError("GCP config requires 'project_id'")

        elif self._provider_type == "azure":
            required = ["subscription_id", "resource_group", "location"]
            for field in required:
                if not hasattr(self.config, field) or not getattr(self.config, field):
                    raise ValueError(f"Azure config requires '{field}'")

        elif self._provider_type == "local":
            if not hasattr(self.config, "base_path"):
                raise ValueError("Local config requires 'base_path'")

    def get_provider_type(self) -> str:
        """Return the provider type ("aws", "gcp", "azure", "local")."""
        return self._provider_type

    def bucket(
        self,
        bucket: str,
        path: str,
        format: str = "parquet",
        name: str | None = None,
        config: Any | None = None,
        options: dict[str, Any] | None = None,
    ):
        """
        Create a cloud-agnostic Bucket resource.

        Args:
            bucket: Bucket/container name
            path: Path within bucket
            format: Data format (parquet, csv, json, etc.)
            name: Optional name for this resource
            config: Optional resource-specific configuration (S3Config, AzureBlobConfig, etc.)
            options: Additional options passed to scan functions

        Returns:
            Generic Bucket instance

        Example:
            from glacier import Provider
            from glacier.config import AwsConfig, S3Config

            provider = Provider(config=AwsConfig(region="us-east-1"))

            # Basic bucket
            bucket = provider.bucket("my-data", path="file.parquet")

            # With resource-specific config
            bucket = provider.bucket(
                "my-data",
                path="file.parquet",
                config=S3Config(versioning=True, encryption="AES256")
            )
        """
        from glacier.resources.bucket import Bucket

        return Bucket(
            bucket_name=bucket,
            path=path,
            format=format,
            provider=self,
            config=config,
            name=name,
            options=options,
        )

    def serverless(
        self,
        function_name: str,
        handler: Any | None = None,
        runtime: str | None = None,
        config: Any | None = None,
        **kwargs,
    ):
        """
        Create a cloud-agnostic Serverless execution environment.

        Args:
            function_name: Name of the serverless function
            handler: Handler function or handler path
            runtime: Runtime environment (python3.11, nodejs18, etc.)
            config: Optional resource-specific configuration (LambdaConfig, etc.)
            **kwargs: Additional configuration options

        Returns:
            Generic Serverless instance

        Example:
            from glacier import Provider
            from glacier.config import AwsConfig, LambdaConfig

            provider = Provider(config=AwsConfig(region="us-east-1"))

            func = provider.serverless(
                "my-function",
                runtime="python3.11",
                config=LambdaConfig(memory=1024, timeout=300)
            )
        """
        from glacier.resources.serverless import Serverless

        return Serverless(
            function_name=function_name,
            handler=handler,
            runtime=runtime,
            provider=self,
            config=config,
            **kwargs,
        )

    def _create_bucket_adapter(self, bucket):
        """
        Create cloud-specific bucket adapter based on provider type.

        This is called internally by Bucket resources.
        """
        if self._provider_type == "aws":
            from glacier.adapters.bucket import S3BucketAdapter

            return S3BucketAdapter(bucket)

        elif self._provider_type == "azure":
            from glacier.adapters.bucket import AzureBlobAdapter

            return AzureBlobAdapter(bucket)

        elif self._provider_type == "gcp":
            from glacier.adapters.bucket import GCSBucketAdapter

            return GCSBucketAdapter(bucket)

        elif self._provider_type == "local":
            from glacier.adapters.bucket import LocalBucketAdapter

            return LocalBucketAdapter(bucket)

        else:
            raise ValueError(f"Unsupported provider type: {self._provider_type}")

    def _create_serverless_adapter(self, serverless):
        """
        Create cloud-specific serverless adapter based on provider type.

        This is called internally by Serverless resources.
        """
        if self._provider_type == "aws":
            from glacier.adapters.serverless import LambdaAdapter

            return LambdaAdapter(serverless)

        elif self._provider_type == "azure":
            from glacier.adapters.serverless import AzureFunctionAdapter

            return AzureFunctionAdapter(serverless)

        elif self._provider_type == "gcp":
            from glacier.adapters.serverless import CloudFunctionAdapter

            return CloudFunctionAdapter(serverless)

        elif self._provider_type == "local":
            from glacier.adapters.serverless import LocalServerlessAdapter

            return LocalServerlessAdapter(serverless)

        else:
            raise ValueError(f"Unsupported provider type: {self._provider_type}")

    def get_infrastructure_metadata(self) -> dict[str, Any]:
        """
        Get metadata about infrastructure requirements.

        Used by code generators to create IaC (Terraform, etc.).
        """
        if self._provider_type == "aws":
            return {
                "provider": "aws",
                "region": self.config.region,
                "account_id": getattr(self.config, "account_id", None),
                "profile": getattr(self.config, "profile", None),
                "requires_terraform_backend": True,
                "supported_resources": [
                    "s3_bucket",
                    "iam_role",
                    "iam_policy",
                    "lambda_function",
                    "glue_job",
                ],
            }

        elif self._provider_type == "gcp":
            return {
                "provider": "gcp",
                "project_id": self.config.project_id,
                "region": self.config.region,
                "requires_terraform_backend": True,
                "supported_resources": [
                    "storage_bucket",
                    "iam_service_account",
                    "cloud_function",
                    "dataflow_job",
                ],
            }

        elif self._provider_type == "azure":
            return {
                "provider": "azure",
                "subscription_id": self.config.subscription_id,
                "resource_group": self.config.resource_group,
                "location": self.config.location,
                "requires_terraform_backend": True,
                "supported_resources": [
                    "storage_account",
                    "storage_container",
                    "function_app",
                    "data_factory",
                ],
            }

        elif self._provider_type == "local":
            return {
                "provider": "local",
                "base_path": self.config.base_path,
                "requires_terraform_backend": False,
                "supported_resources": ["local_file"],
            }

        return {}

    def get_tags(self) -> dict[str, str]:
        """Get default tags to apply to resources."""
        if self._provider_type == "aws":
            return self.config.tags if hasattr(self.config, "tags") and self.config.tags else {}
        elif self._provider_type == "gcp":
            # GCP uses labels instead of tags
            return self.config.labels if hasattr(self.config, "labels") and self.config.labels else {}
        elif self._provider_type == "azure":
            return self.config.tags if hasattr(self.config, "tags") and self.config.tags else {}
        return {}

    @classmethod
    def from_env(cls) -> "Provider":
        """
        Create a provider instance from environment variables.

        Reads GLACIER_PROVIDER environment variable to determine which
        config to load, then creates provider with that config.

        Returns:
            Provider instance configured from environment

        Example:
            # With GLACIER_PROVIDER=aws and AWS_REGION=us-east-1
            provider = Provider.from_env()
        """
        from glacier.config import AwsConfig, GcpConfig, AzureConfig, LocalConfig

        provider_type = os.getenv("GLACIER_PROVIDER", "local").lower()

        if provider_type == "aws":
            config = AwsConfig(
                region=os.getenv("AWS_REGION", "us-east-1"),
                profile=os.getenv("AWS_PROFILE"),
                account_id=os.getenv("AWS_ACCOUNT_ID"),
            )
        elif provider_type == "gcp":
            project_id = os.getenv("GCP_PROJECT_ID")
            if not project_id:
                raise ValueError("GCP_PROJECT_ID environment variable required")
            config = GcpConfig(
                project_id=project_id,
                region=os.getenv("GCP_REGION", "us-central1"),
            )
        elif provider_type == "azure":
            subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")
            resource_group = os.getenv("AZURE_RESOURCE_GROUP")
            location = os.getenv("AZURE_LOCATION", "eastus")
            if not subscription_id or not resource_group:
                raise ValueError(
                    "AZURE_SUBSCRIPTION_ID and AZURE_RESOURCE_GROUP environment variables required"
                )
            config = AzureConfig(
                subscription_id=subscription_id,
                resource_group=resource_group,
                location=location,
            )
        elif provider_type == "local":
            config = LocalConfig(base_path=os.getenv("LOCAL_BASE_PATH", "./data"))
        else:
            raise ValueError(
                f"Unknown GLACIER_PROVIDER: {provider_type}. "
                "Expected: aws, gcp, azure, or local"
            )

        return cls(config=config)

    def env(self, name: str = "default", **kwargs):
        """
        Create a GlacierEnv environment bound to this provider.

        Args:
            name: Environment name (e.g., "development", "production")
            **kwargs: Additional arguments for GlacierEnv

        Returns:
            GlacierEnv instance with this provider

        Example:
            from glacier import Provider
            from glacier.config import AwsConfig

            provider = Provider(config=AwsConfig(region="us-east-1"))
            env = provider.env(name="production")

            @env.task()
            def my_task(source):
                return source.scan()
        """
        from glacier.core.env import GlacierEnv

        return GlacierEnv(provider=self, name=name, **kwargs)

    def __repr__(self) -> str:
        region_info = ""
        if hasattr(self.config, "region") and self.config.region:
            region_info = f", region='{self.config.region}'"
        elif hasattr(self.config, "location") and self.config.location:
            region_info = f", location='{self.config.location}'"

        return f"Provider(type='{self._provider_type}'{region_info})"
