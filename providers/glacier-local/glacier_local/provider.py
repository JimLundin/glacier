"""
Local Provider for Glacier.

A minimal provider implementation for local development and testing.
Does not create any cloud resources - suitable for running pipelines locally.
"""

from typing import Any

from glacier.core.environment import Provider


class LocalProvider(Provider):
    """
    Local provider for development and testing.

    This provider doesn't create any cloud resources. It's suitable for:
    - Local pipeline execution
    - Testing pipeline logic
    - Development without cloud dependencies

    For actual deployments, use cloud providers (AWSProvider, AzureProvider, etc.)
    """

    def object_storage(self, name: str, **kwargs) -> dict[str, str]:
        """
        Return local file system path for object storage.

        In local mode, object storage is just a directory path.
        """
        return {
            "type": "local_storage",
            "name": name,
            "path": f"./.glacier/storage/{name}"
        }

    def serverless(self, name: str, handler: str, code: Any, **kwargs) -> dict[str, Any]:
        """
        Return local function reference for serverless.

        In local mode, serverless functions are just Python callables.
        """
        return {
            "type": "local_function",
            "name": name,
            "handler": handler,
            "code": code
        }

    def database(self, name: str, engine: str = "postgres", **kwargs) -> dict[str, str]:
        """
        Return local SQLite path for database.

        In local mode, databases are SQLite files.
        """
        return {
            "type": "local_database",
            "name": name,
            "engine": "sqlite",
            "path": f"./.glacier/databases/{name}.db"
        }

    def secret(self, name: str, secret_string: str | None = None, **kwargs) -> dict[str, Any]:
        """
        Return local environment variable reference for secrets.

        In local mode, secrets are environment variables.
        """
        return {
            "type": "local_secret",
            "name": name,
            "env_var": f"GLACIER_{name.upper()}"
        }

    def get_provider_name(self) -> str:
        """Return provider name."""
        return "local"
