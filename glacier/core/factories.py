"""
Factory functions for creating Glacier objects with optional parent specification.

These are the primary API for creating pipelines, environments, and resources.
Parent objects (Stack, Environment) provide convenience methods that proxy to these.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from glacier.core.stack import Stack
    from glacier.core.environment import Environment, Provider
    from glacier.core.pipeline import Pipeline as PipelineType
    import pulumi


def pipeline(name: str, *, stack: "Stack | None" = None) -> "PipelineType":
    """
    Create a pipeline.

    Args:
        name: Pipeline name
        stack: Optional stack to register with. If None, uses default stack.

    Returns:
        Pipeline instance

    Example (implicit):
        from glacier import pipeline
        etl = pipeline("etl")  # Uses default stack

    Example (explicit):
        from glacier import Stack, pipeline
        stack = Stack("prod")
        etl = pipeline("etl", stack=stack)  # Or: stack.pipeline("etl")
    """
    from glacier.core.pipeline import Pipeline

    if stack is None:
        from glacier.defaults import get_default_stack
        stack = get_default_stack()

    pipe = Pipeline(name=name)
    stack._pipelines[name] = pipe
    return pipe


def environment(
    provider: "Provider",
    name: str,
    *,
    stack: "Stack | None" = None,
    tags: dict[str, str] | None = None
) -> "Environment":
    """
    Create an environment.

    Args:
        provider: Provider implementation (AWSProvider, AzureProvider, etc.)
        name: Environment name (dev, staging, prod, etc.)
        stack: Optional stack to register with. If None, uses default stack.
        tags: Optional tags to apply to all resources

    Returns:
        Environment instance

    Example (implicit):
        from glacier import environment
        from glacier_aws import AWSProvider
        aws = environment(AWSProvider(...), "prod")  # Uses default stack

    Example (explicit):
        from glacier import Stack, environment
        stack = Stack("prod")
        aws = environment(AWSProvider(...), "prod", stack=stack)
        # Or: stack.environment(AWSProvider(...), "prod")
    """
    from glacier.core.environment import Environment

    if stack is None:
        from glacier.defaults import get_default_stack
        stack = get_default_stack()

    env = Environment(provider=provider, name=name, tags=tags)
    stack._environments[name] = env
    return env


def object_storage(
    name: str,
    *,
    environment: "Environment | None" = None,
    **kwargs
) -> "pulumi.Resource":
    """
    Create object storage (S3, Blob Storage, GCS, etc.).

    Args:
        name: Storage name
        environment: Optional environment to create in. If None, uses default.
        **kwargs: Provider-specific options

    Returns:
        Pulumi resource for the object storage

    Example (implicit):
        from glacier import object_storage
        bucket = object_storage("data")  # Uses default environment

    Example (explicit):
        from glacier import environment, object_storage
        aws = environment(AWSProvider(...), "prod")
        bucket = object_storage("data", environment=aws)
        # Or: aws.object_storage("data")
    """
    if environment is None:
        from glacier.defaults import get_default_environment
        environment = get_default_environment()

    return environment.provider.object_storage(
        name=name, env_tags=environment.tags, **kwargs
    )


def database(
    name: str,
    *,
    environment: "Environment | None" = None,
    engine: str = "postgres",
    **kwargs
) -> "pulumi.Resource":
    """
    Create managed database (RDS, Azure SQL, Cloud SQL, etc.).

    Args:
        name: Database identifier
        environment: Optional environment to create in. If None, uses default.
        engine: Database engine (postgres, mysql, etc.)
        **kwargs: Provider-specific options

    Returns:
        Pulumi resource for the database

    Example (implicit):
        from glacier import database
        db = database("users")  # Uses default environment

    Example (explicit):
        from glacier import environment, database
        aws = environment(AWSProvider(...), "prod")
        db = database("users", environment=aws)
        # Or: aws.database("users")
    """
    if environment is None:
        from glacier.defaults import get_default_environment
        environment = get_default_environment()

    return environment.provider.database(
        name=name, engine=engine, env_tags=environment.tags, **kwargs
    )


def secret(
    name: str,
    *,
    environment: "Environment | None" = None,
    secret_string: str | None = None,
    **kwargs
) -> "pulumi.Resource":
    """
    Create secret storage (Secrets Manager, Key Vault, etc.).

    Args:
        name: Secret identifier
        environment: Optional environment to create in. If None, uses default.
        secret_string: Optional secret value to store
        **kwargs: Provider-specific options

    Returns:
        Pulumi resource for the secret

    Example (implicit):
        from glacier import secret
        api_key = secret("api_key")  # Uses default environment

    Example (explicit):
        from glacier import environment, secret
        aws = environment(AWSProvider(...), "prod")
        api_key = secret("api_key", environment=aws)
        # Or: aws.secret("api_key")
    """
    if environment is None:
        from glacier.defaults import get_default_environment
        environment = get_default_environment()

    return environment.provider.secret(
        name=name, secret_string=secret_string, env_tags=environment.tags, **kwargs
    )
