"""
Secret Resources: Provider-agnostic secret management.

These resources define secure credential storage without being tied
to a specific provider implementation.
"""

from abc import ABC
from typing import Literal
from dataclasses import dataclass


class SecretResource(ABC):
    """
    Abstract base class for secret resources.

    Secret resources define secure credential storage without
    being tied to a specific provider (AWS Secrets Manager,
    Azure Key Vault, GCP Secret Manager, local env vars, etc.).
    """
    pass


@dataclass
class Secret(SecretResource):
    """
    Generic secret for storing sensitive values.

    Maps to:
    - AWS Secrets Manager
    - Azure Key Vault
    - GCP Secret Manager
    - Environment variables locally

    Secrets can store:
    - Database passwords
    - API keys
    - Service account credentials
    - OAuth tokens
    - Any sensitive configuration
    """

    name: str
    """Secret name/identifier"""

    description: str | None = None
    """Optional description of what this secret is for"""

    rotation_days: int | None = None
    """Optional automatic rotation period in days"""

    type: Literal["string", "binary", "json"] = "string"
    """Secret value type"""

    tags: dict[str, str] | None = None
    """Optional tags for organization"""

    def __repr__(self):
        rotation = f", rotation={self.rotation_days}d" if self.rotation_days else ""
        return f"Secret(name={self.name}{rotation})"


# Convenience factory function
def secret(
    name: str,
    description: str | None = None,
    rotation_days: int | None = None,
    type: Literal["string", "binary", "json"] = "string",
    tags: dict[str, str] | None = None,
) -> Secret:
    """
    Create a secret resource.

    Args:
        name: Secret name/identifier
        description: Optional description of what this secret is for
        rotation_days: Optional automatic rotation period in days
        type: Secret value type (string, binary, json)
        tags: Optional tags for organization

    Returns:
        Secret resource

    Example:
        # Layer 1: Simple secret
        db_password = secret(name="db_password")

        # Layer 2: With rotation and description
        api_key = secret(
            name="api_key",
            description="External API authentication key",
            rotation_days=90
        )

        # Use in environment
        from glacier import Environment
        from glacier_aws import AWSProvider

        env = Environment(provider=AWSProvider(...))
        secret_resource = env.secret(name="my_secret", secret_string="value")
    """
    return Secret(
        name=name,
        description=description,
        rotation_days=rotation_days,
        type=type,
        tags=tags,
    )
