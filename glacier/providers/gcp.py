"""
GCP provider implementation.
"""

import os
from typing import Any
from glacier.providers.base import Provider, ProviderConfig


class GCPProvider(Provider):
    """
    Google Cloud Platform provider.

    Creates GCP-specific resources (GCS, BigQuery, etc.) and generates
    Terraform for GCP infrastructure.

    Example:
        provider = GCPProvider(
            project_id="my-project",
            region="us-central1"
        )

        source = provider.bucket_source(
            bucket="my-data-bucket",
            path="data/file.parquet"
        )
    """

    def __init__(
        self,
        project_id: str,
        region: str = "us-central1",
        credentials_path: str | None = None,
        config: ProviderConfig | None = None,
        **kwargs,
    ):
        """
        Initialize GCP provider.

        Args:
            project_id: GCP project ID
            region: GCP region
            credentials_path: Path to service account key JSON (optional)
            config: Provider configuration (optional)
            **kwargs: Additional configuration
        """
        self.project_id = project_id
        self.region = region
        self.credentials_path = credentials_path

        if config is None:
            config = ProviderConfig(
                provider_type="gcp",
                region=region,
                credentials={
                    "project_id": project_id,
                    "credentials_path": credentials_path,
                },
                tags=kwargs.get("tags"),
            )

        super().__init__(config, **kwargs)

    def _load_config_from_env(self, **kwargs) -> ProviderConfig:
        """Load GCP configuration from environment variables."""
        project_id = kwargs.get("project_id") or os.getenv("GCP_PROJECT_ID")
        region = kwargs.get("region") or os.getenv("GCP_REGION", "us-central1")
        credentials_path = kwargs.get("credentials_path") or os.getenv(
            "GOOGLE_APPLICATION_CREDENTIALS"
        )

        if not project_id:
            raise ValueError(
                "GCP project ID must be specified via project_id parameter "
                "or GCP_PROJECT_ID environment variable"
            )

        return ProviderConfig(
            provider_type="gcp",
            region=region,
            credentials={
                "project_id": project_id,
                "credentials_path": credentials_path,
            },
            tags=kwargs.get("tags"),
        )

    def _validate_config(self) -> None:
        """Validate GCP configuration."""
        if not self.project_id:
            raise ValueError("GCP project ID must be specified")

    def _create_bucket_adapter(self, bucket):
        """Create a GCS bucket adapter."""
        from glacier.adapters.bucket import GCSBucketAdapter

        return GCSBucketAdapter(bucket)

    def _create_serverless_adapter(self, serverless):
        """Create a Cloud Function adapter."""
        from glacier.adapters.serverless import CloudFunctionAdapter

        return CloudFunctionAdapter(serverless)

    def get_infrastructure_metadata(self) -> dict[str, Any]:
        """Get GCP infrastructure metadata."""
        return {
            "provider": "gcp",
            "region": self.config.region,
            "project_id": self.project_id,
            "credentials_path": self.credentials_path,
            "requires_terraform_backend": True,
            "supported_resources": [
                "storage_bucket",
                "service_account",
                "iam_binding",
                "bigquery_dataset",
                "dataflow_job",
            ],
        }

    def get_provider_type(self) -> str:
        """Return provider type."""
        return "gcp"
