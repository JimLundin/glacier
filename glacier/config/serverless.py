"""
Configuration classes for serverless execution environments.

These allow provider-specific options for cloud functions while keeping
the pipeline code cloud-agnostic.
"""

from typing import Any
from pydantic import BaseModel, Field


class ServerlessConfig(BaseModel):
    """
    Base configuration for serverless execution environments.

    This is the cloud-agnostic base class for serverless functions.
    """

    class Config:
        arbitrary_types_allowed = True
        extra = "allow"


class LambdaConfig(ServerlessConfig):
    """
    AWS Lambda-specific configuration.

    Example:
        provider = AWSProvider()
        func = provider.serverless(
            "my-function",
            config=LambdaConfig(
                memory=1024,
                timeout=300,
                runtime="python3.11"
            )
        )
    """

    memory: int | None = Field(
        None,
        description="Memory allocation in MB (128-10240)"
    )
    timeout: int | None = Field(
        None,
        description="Timeout in seconds (1-900)"
    )
    runtime: str | None = Field(
        None,
        description="Lambda runtime (python3.11, python3.10, etc.)"
    )
    handler: str | None = Field(
        None,
        description="Handler function (module.function)"
    )
    layers: list[str] | None = Field(
        None,
        description="Lambda layer ARNs"
    )
    environment_variables: dict[str, str] | None = Field(
        None,
        description="Environment variables"
    )
    vpc_config: dict[str, Any] | None = Field(
        None,
        description="VPC configuration"
    )
    reserved_concurrent_executions: int | None = Field(
        None,
        description="Reserved concurrent executions"
    )
    dead_letter_config: dict[str, str] | None = Field(
        None,
        description="Dead letter queue configuration"
    )
    ephemeral_storage: int | None = Field(
        None,
        description="Ephemeral storage in MB (512-10240)"
    )
    architecture: str | None = Field(
        None,
        description="Instruction set architecture (x86_64, arm64)"
    )


class AzureFunctionConfig(ServerlessConfig):
    """
    Azure Functions-specific configuration.

    Example:
        provider = AzureProvider()
        func = provider.serverless(
            "my-function",
            config=AzureFunctionConfig(
                runtime="python",
                runtime_version="3.11",
                sku="Y1"
            )
        )
    """

    runtime: str | None = Field(
        None,
        description="Runtime stack (python, node, dotnet, java)"
    )
    runtime_version: str | None = Field(
        None,
        description="Runtime version"
    )
    sku: str | None = Field(
        None,
        description="Pricing tier (Y1=Consumption, EP1/EP2/EP3=Elastic Premium)"
    )
    app_settings: dict[str, str] | None = Field(
        None,
        description="Application settings"
    )
    storage_account: str | None = Field(
        None,
        description="Storage account name"
    )
    daily_memory_time_quota: int | None = Field(
        None,
        description="Daily memory-time quota in GB-seconds"
    )
    cors: dict[str, Any] | None = Field(
        None,
        description="CORS configuration"
    )
    always_on: bool | None = Field(
        None,
        description="Keep app always on (not available for Consumption)"
    )


class CloudFunctionConfig(ServerlessConfig):
    """
    Google Cloud Functions-specific configuration.

    Example:
        provider = GCPProvider()
        func = provider.serverless(
            "my-function",
            config=CloudFunctionConfig(
                memory="512Mi",
                timeout=300,
                runtime="python311"
            )
        )
    """

    memory: str | None = Field(
        None,
        description="Memory allocation (e.g., '256Mi', '512Mi', '1Gi')"
    )
    timeout: int | None = Field(
        None,
        description="Timeout in seconds (max 540 for gen1, 3600 for gen2)"
    )
    runtime: str | None = Field(
        None,
        description="Runtime (python311, python310, nodejs18, etc.)"
    )
    entry_point: str | None = Field(
        None,
        description="Function entry point"
    )
    environment_variables: dict[str, str] | None = Field(
        None,
        description="Environment variables"
    )
    vpc_connector: str | None = Field(
        None,
        description="VPC connector name"
    )
    ingress_settings: str | None = Field(
        None,
        description="Ingress settings (ALLOW_ALL, ALLOW_INTERNAL_ONLY, ALLOW_INTERNAL_AND_GCLB)"
    )
    max_instances: int | None = Field(
        None,
        description="Maximum number of instances"
    )
    min_instances: int | None = Field(
        None,
        description="Minimum number of instances"
    )
    service_account: str | None = Field(
        None,
        description="Service account email"
    )
    labels: dict[str, str] | None = Field(
        None,
        description="Function labels"
    )
    generation: int | None = Field(
        None,
        description="Cloud Functions generation (1 or 2)"
    )
