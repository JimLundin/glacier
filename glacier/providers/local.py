"""
Local provider for development and testing.
"""

from typing import Any
from glacier.providers.base import Provider, ProviderConfig


class LocalProvider(Provider):
    """
    Local filesystem provider for development and testing.

    Uses the local filesystem instead of cloud storage. Useful for:
    - Local development
    - Testing pipelines
    - Small-scale processing
    - CI/CD testing

    Example:
        provider = LocalProvider(base_path="./data")

        source = provider.bucket_source(
            bucket="input",
            path="file.parquet"
        )
        # Creates a LocalSource at ./data/input/file.parquet
    """

    def __init__(
        self,
        base_path: str = "./data",
        config: ProviderConfig | None = None,
        **kwargs,
    ):
        """
        Initialize local provider.

        Args:
            base_path: Base directory for all data
            config: Provider configuration (optional)
            **kwargs: Additional configuration
        """
        self.base_path = base_path

        if config is None:
            config = ProviderConfig(
                provider_type="local",
                region=None,
                credentials={"base_path": base_path},
                tags=kwargs.get("tags"),
            )

        super().__init__(config, **kwargs)

    def _load_config_from_env(self, **kwargs) -> ProviderConfig:
        """Load local configuration."""
        base_path = kwargs.get("base_path", "./data")

        return ProviderConfig(
            provider_type="local",
            region=None,
            credentials={"base_path": base_path},
            tags=kwargs.get("tags"),
        )

    def _validate_config(self) -> None:
        """Validate local configuration."""
        # No validation needed for local provider
        pass

    def bucket_source(
        self,
        bucket: str,
        path: str,
        format: str = "parquet",
        name: str | None = None,
        options: dict[str, Any] | None = None,
    ):
        """
        Create a local filesystem source.

        Args:
            bucket: Directory name (analogous to bucket)
            path: Path within directory
            format: Data format
            name: Optional name
            options: Additional options

        Returns:
            LocalSource instance
        """
        from glacier.sources.local import LocalSource

        # Combine base_path with bucket
        full_bucket = f"{self.base_path}/{bucket}"

        return LocalSource(
            bucket=full_bucket,
            path=path,
            format=format,
            name=name,
            options=options,
            provider=self,
        )

    def get_infrastructure_metadata(self) -> dict[str, Any]:
        """Get local infrastructure metadata."""
        return {
            "provider": "local",
            "base_path": self.base_path,
            "requires_terraform_backend": False,
            "supported_resources": ["local_file", "local_directory"],
        }

    def get_provider_type(self) -> str:
        """Return provider type."""
        return "local"
