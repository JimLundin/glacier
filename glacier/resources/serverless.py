"""
Generic Serverless execution environment abstraction.

The Serverless class provides a unified interface for serverless functions
across AWS Lambda, Azure Functions, Google Cloud Functions, etc.
"""

from typing import Any, TYPE_CHECKING, Callable
from abc import ABC, abstractmethod
from pydantic import BaseModel

if TYPE_CHECKING:
    from glacier.providers.base import Provider
    from glacier.config.serverless import ServerlessConfig


class ServerlessMetadata(BaseModel):
    """Metadata about a serverless function for infrastructure generation."""

    resource_type: str
    cloud_provider: str | None = None
    region: str | None = None
    function_name: str
    runtime: str | None = None
    memory: int | None = None
    timeout: int | None = None
    additional_config: dict[str, Any] = {}

    class Config:
        arbitrary_types_allowed = True


class Serverless:
    """
    Cloud-agnostic serverless execution environment.

    This class provides a generic interface for serverless functions that works
    across all cloud providers. The actual implementation is delegated to
    provider-specific adapters.

    Users should never instantiate this directly - instead, use:
        provider.serverless(name, handler, ...)

    Example:
        # Works with any provider!
        provider = AWSProvider()  # or AzureProvider, GCPProvider, etc.
        func = provider.serverless(
            "my-function",
            handler=my_handler_function,
            runtime="python3.11"
        )

        # Can optionally pass provider-specific config
        func = provider.serverless(
            "my-function",
            handler=my_handler_function,
            config=LambdaConfig(
                memory=1024,
                timeout=300,
                layers=["arn:aws:lambda:..."]
            )
        )

        # Use in pipeline
        @task(executor="serverless")
        def process_data(df: pl.LazyFrame) -> pl.LazyFrame:
            return df.filter(pl.col("value") > 0)
    """

    def __init__(
        self,
        function_name: str,
        handler: Callable | str | None = None,
        runtime: str | None = None,
        provider: "Provider | None" = None,
        config: "ServerlessConfig | None" = None,
        **kwargs,
    ):
        """
        Initialize a generic Serverless function.

        Note: Users should not call this directly. Use provider.serverless() instead.

        Args:
            function_name: Name of the serverless function
            handler: Handler function or handler path
            runtime: Runtime environment (python3.11, nodejs18, etc.)
            provider: Provider that created this function
            config: Optional provider-specific configuration
            **kwargs: Additional configuration options
        """
        self.function_name = function_name
        self.handler = handler
        self.runtime = runtime
        self.provider = provider
        self.config = config
        self.additional_config = kwargs

        # Lazy-initialize the adapter
        self._adapter = None

    def _get_adapter(self):
        """
        Get the cloud-specific adapter for this serverless function.

        This delegates to the provider to create the appropriate adapter
        (Lambda, Azure Functions, Cloud Functions, etc.) based on the provider type.
        """
        if self._adapter is None:
            if self.provider is None:
                raise ValueError(
                    "Serverless must be created through a Provider instance. "
                    "Use provider.serverless(...) instead of Serverless(...)"
                )
            self._adapter = self.provider._create_serverless_adapter(self)
        return self._adapter

    def invoke(self, payload: dict[str, Any] | None = None) -> Any:
        """
        Invoke the serverless function with a payload.

        Args:
            payload: Input data for the function

        Returns:
            The function's output
        """
        adapter = self._get_adapter()
        return adapter.invoke(payload)

    def get_metadata(self) -> ServerlessMetadata:
        """
        Return metadata for infrastructure generation.

        This is used during the "compile" phase to understand what
        infrastructure is needed (functions, IAM roles, etc.).
        """
        adapter = self._get_adapter()
        return adapter.get_metadata()

    def get_arn_or_id(self) -> str:
        """
        Get the cloud-specific identifier for this function.

        Returns:
            - AWS: Lambda ARN
            - Azure: Function App resource ID
            - GCP: Cloud Function name
        """
        adapter = self._get_adapter()
        return adapter.get_arn_or_id()

    def __repr__(self) -> str:
        provider_type = self.provider.get_provider_type() if self.provider else "unknown"
        return (
            f"Serverless(name='{self.function_name}', "
            f"runtime='{self.runtime}', provider='{provider_type}')"
        )


class ServerlessAdapter(ABC):
    """
    Base class for cloud-specific serverless adapters.

    Providers implement this to handle the actual cloud-specific logic.
    """

    def __init__(self, serverless: Serverless):
        self.serverless = serverless

    @abstractmethod
    def invoke(self, payload: dict[str, Any] | None = None) -> Any:
        """Invoke the function."""
        pass

    @abstractmethod
    def get_metadata(self) -> ServerlessMetadata:
        """Get metadata for infrastructure generation."""
        pass

    @abstractmethod
    def get_arn_or_id(self) -> str:
        """Get the cloud-specific identifier."""
        pass
