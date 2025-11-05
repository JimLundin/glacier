"""
Provider-specific configuration classes.

These classes provide type-safe configuration for different cloud providers,
enabling the configuration cascade pattern described in the design.
"""

from pydantic import BaseModel, Field
from typing import Any


class AwsConfig(BaseModel):
    """
    AWS Provider Configuration.

    Example:
        aws_config = AwsConfig(
            region="us-east-1",
            profile="production",
            account_id="123456789012",
            tags={
                "environment": "production",
                "managed_by": "glacier",
                "team": "data-engineering"
            }
        )

        provider = AWSProvider(config=aws_config)
    """

    region: str = Field(default="us-east-1", description="AWS region")
    profile: str | None = Field(default=None, description="AWS profile name")
    account_id: str | None = Field(default=None, description="AWS account ID")
    tags: dict[str, str] = Field(
        default_factory=dict, description="Default tags for all resources"
    )
    assume_role_arn: str | None = Field(
        default=None, description="Optional role ARN to assume"
    )
    session_duration: int = Field(
        default=3600, description="Session duration in seconds"
    )

    class Config:
        arbitrary_types_allowed = True


class GcpConfig(BaseModel):
    """
    GCP Provider Configuration.

    Example:
        gcp_config = GcpConfig(
            project_id="my-project",
            region="us-central1",
            credentials_path="/path/to/service-account.json",
            labels={
                "environment": "production",
                "managed_by": "glacier"
            }
        )

        provider = GCPProvider(config=gcp_config)
    """

    project_id: str = Field(..., description="GCP project ID")
    region: str = Field(default="us-central1", description="GCP region")
    zone: str | None = Field(default=None, description="GCP zone")
    credentials_path: str | None = Field(
        default=None, description="Path to service account JSON"
    )
    credentials: dict[str, Any] | None = Field(
        default=None, description="Service account credentials as dict"
    )
    labels: dict[str, str] = Field(
        default_factory=dict, description="Default labels for all resources"
    )

    class Config:
        arbitrary_types_allowed = True


class AzureConfig(BaseModel):
    """
    Azure Provider Configuration.

    Example:
        azure_config = AzureConfig(
            subscription_id="...",
            resource_group="data-engineering",
            location="eastus",
            tags={"environment": "production"}
        )

        provider = AzureProvider(config=azure_config)
    """

    subscription_id: str = Field(..., description="Azure subscription ID")
    resource_group: str = Field(..., description="Azure resource group name")
    location: str = Field(default="eastus", description="Azure location/region")
    tenant_id: str | None = Field(default=None, description="Azure tenant ID")
    client_id: str | None = Field(default=None, description="Service principal client ID")
    client_secret: str | None = Field(
        default=None, description="Service principal client secret"
    )
    tags: dict[str, str] = Field(
        default_factory=dict, description="Default tags for all resources"
    )

    class Config:
        arbitrary_types_allowed = True


class LocalConfig(BaseModel):
    """
    Local Provider Configuration.

    Example:
        local_config = LocalConfig(
            base_path="./data",
            create_dirs=True
        )

        provider = LocalProvider(config=local_config)
    """

    base_path: str = Field(default="./data", description="Base directory for data")
    create_dirs: bool = Field(
        default=True, description="Auto-create directories if they don't exist"
    )
    cache_dir: str | None = Field(
        default=None, description="Optional cache directory"
    )

    class Config:
        arbitrary_types_allowed = True
