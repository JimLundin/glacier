"""
Serverless adapter implementations.

These adapters handle the cloud-specific logic for serverless functions,
allowing the generic Serverless class to work across all providers.
"""

from abc import ABC, abstractmethod
from typing import Any, TYPE_CHECKING
from glacier.resources.serverless import ServerlessMetadata

if TYPE_CHECKING:
    from glacier.resources.serverless import Serverless


class ServerlessAdapter(ABC):
    """
    Base class for cloud-specific serverless adapters.

    Each cloud provider implements this to provide the actual
    serverless function logic.
    """

    def __init__(self, serverless: "Serverless"):
        """
        Initialize the adapter.

        Args:
            serverless: The generic Serverless instance this adapter serves
        """
        self.serverless = serverless

    @abstractmethod
    def invoke(self, payload: dict[str, Any] | None = None) -> Any:
        """
        Invoke the serverless function.

        Args:
            payload: Input data for the function

        Returns:
            Function output
        """
        pass

    @abstractmethod
    def get_metadata(self) -> ServerlessMetadata:
        """
        Get metadata for infrastructure generation.

        Returns:
            ServerlessMetadata describing this function
        """
        pass

    @abstractmethod
    def get_arn_or_id(self) -> str:
        """
        Get the cloud-specific identifier.

        Returns:
            ARN, resource ID, or function name
        """
        pass


class LambdaAdapter(ServerlessAdapter):
    """AWS Lambda adapter for Serverless."""

    def __init__(self, serverless: "Serverless"):
        super().__init__(serverless)
        self.region = (
            serverless.provider.config.region if serverless.provider else "us-east-1"
        )
        self.account_id = (
            serverless.provider.account_id if serverless.provider else None
        )

    def invoke(self, payload: dict[str, Any] | None = None) -> Any:
        """Invoke Lambda function."""
        # TODO: Implement actual Lambda invocation using boto3
        # For now, this is a placeholder for infrastructure generation
        raise NotImplementedError(
            "Lambda invocation requires boto3. "
            "This will be implemented in runtime execution."
        )

    def get_metadata(self) -> ServerlessMetadata:
        """Get Lambda metadata."""
        config_dict = {}
        if self.serverless.config:
            config_dict = self.serverless.config.model_dump(exclude_none=True)

        return ServerlessMetadata(
            resource_type="lambda",
            cloud_provider="aws",
            region=self.region,
            function_name=self.serverless.function_name,
            runtime=self.serverless.runtime or config_dict.get("runtime"),
            memory=config_dict.get("memory"),
            timeout=config_dict.get("timeout"),
            additional_config=config_dict,
        )

    def get_arn_or_id(self) -> str:
        """Get Lambda ARN."""
        if self.account_id and self.region:
            return (
                f"arn:aws:lambda:{self.region}:{self.account_id}:"
                f"function:{self.serverless.function_name}"
            )
        else:
            return self.serverless.function_name


class AzureFunctionAdapter(ServerlessAdapter):
    """Azure Functions adapter for Serverless."""

    def __init__(self, serverless: "Serverless"):
        super().__init__(serverless)
        self.resource_group = (
            serverless.provider.resource_group if serverless.provider else None
        )
        self.subscription_id = (
            serverless.provider.subscription_id if serverless.provider else None
        )
        self.location = (
            serverless.provider.config.region if serverless.provider else "eastus"
        )

    def invoke(self, payload: dict[str, Any] | None = None) -> Any:
        """Invoke Azure Function."""
        # TODO: Implement actual Azure Function invocation
        raise NotImplementedError(
            "Azure Function invocation requires azure-functions. "
            "This will be implemented in runtime execution."
        )

    def get_metadata(self) -> ServerlessMetadata:
        """Get Azure Function metadata."""
        config_dict = {}
        if self.serverless.config:
            config_dict = self.serverless.config.model_dump(exclude_none=True)

        return ServerlessMetadata(
            resource_type="azure_function",
            cloud_provider="azure",
            region=self.location,
            function_name=self.serverless.function_name,
            runtime=config_dict.get("runtime"),
            memory=None,  # Azure doesn't specify memory directly
            timeout=None,
            additional_config={
                **config_dict,
                "resource_group": self.resource_group,
            },
        )

    def get_arn_or_id(self) -> str:
        """Get Azure Function resource ID."""
        if self.subscription_id and self.resource_group:
            return (
                f"/subscriptions/{self.subscription_id}"
                f"/resourceGroups/{self.resource_group}"
                f"/providers/Microsoft.Web/sites/{self.serverless.function_name}"
            )
        else:
            return self.serverless.function_name


class CloudFunctionAdapter(ServerlessAdapter):
    """Google Cloud Functions adapter for Serverless."""

    def __init__(self, serverless: "Serverless"):
        super().__init__(serverless)
        self.project_id = (
            serverless.provider.project_id if serverless.provider else None
        )
        self.region = (
            serverless.provider.config.region if serverless.provider else "us-central1"
        )

    def invoke(self, payload: dict[str, Any] | None = None) -> Any:
        """Invoke Cloud Function."""
        # TODO: Implement actual Cloud Function invocation
        raise NotImplementedError(
            "Cloud Function invocation requires google-cloud-functions. "
            "This will be implemented in runtime execution."
        )

    def get_metadata(self) -> ServerlessMetadata:
        """Get Cloud Function metadata."""
        config_dict = {}
        if self.serverless.config:
            config_dict = self.serverless.config.model_dump(exclude_none=True)

        # Parse memory string to int if present (e.g., "512Mi" -> 512)
        memory = config_dict.get("memory")
        if isinstance(memory, str):
            memory_int = int("".join(filter(str.isdigit, memory)))
        else:
            memory_int = None

        return ServerlessMetadata(
            resource_type="cloud_function",
            cloud_provider="gcp",
            region=self.region,
            function_name=self.serverless.function_name,
            runtime=self.serverless.runtime or config_dict.get("runtime"),
            memory=memory_int,
            timeout=config_dict.get("timeout"),
            additional_config={
                **config_dict,
                "project_id": self.project_id,
            },
        )

    def get_arn_or_id(self) -> str:
        """Get Cloud Function name."""
        if self.project_id and self.region:
            return (
                f"projects/{self.project_id}/locations/{self.region}"
                f"/functions/{self.serverless.function_name}"
            )
        else:
            return self.serverless.function_name
