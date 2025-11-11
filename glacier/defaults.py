"""
Default stack and environment for implicit usage.

These defaults enable the simplest usage pattern where users don't need to
explicitly create Stack or Environment objects. For more control, use the
explicit Stack and Environment APIs.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from glacier.core.environment import Environment
    from glacier.core.stack import Stack
    import pulumi


# Module-level defaults (lazy-created on first use)
_default_stack: 'Stack | None' = None
_default_environment: 'Environment | None' = None


def get_default_stack() -> 'Stack':
    """
    Get or create the default stack.

    The default stack is used when no explicit stack is provided.
    It's created lazily on first access.
    """
    global _default_stack
    if _default_stack is None:
        from glacier.core.stack import Stack
        _default_stack = Stack(name="default")
    return _default_stack


def get_default_environment() -> 'Environment':
    """
    Get or create the default environment.

    The default environment uses LocalProvider if glacier-local is installed,
    otherwise raises an error suggesting explicit Environment creation.
    """
    global _default_environment
    if _default_environment is None:
        try:
            from glacier_local.provider import LocalProvider
            from glacier.core.environment import Environment

            provider = LocalProvider()
            _default_environment = Environment(
                provider=provider,
                name="local"
            )
        except ImportError:
            raise ImportError(
                "Default environment requires glacier-local. Either:\n"
                "  1. Install glacier-local: pip install glacier-local\n"
                "  2. Use explicit Stack/Environment with a cloud provider:\n"
                "     from glacier import Stack\n"
                "     from glacier_aws import AWSProvider\n"
                "     stack = Stack('my-stack')\n"
                "     env = stack.environment(AWSProvider(...), 'aws')"
            )
    return _default_environment


# Module-level factory functions that use defaults

def object_storage(name: str, **kwargs) -> 'pulumi.Resource':
    """
    Create object storage using the default environment.

    For explicit control, use:
        env = stack.environment(provider, name)
        storage = env.object_storage(name)
    """
    env = get_default_environment()
    return env.object_storage(name, **kwargs)


def database(name: str, **kwargs) -> 'pulumi.Resource':
    """
    Create database using the default environment.

    For explicit control, use:
        env = stack.environment(provider, name)
        db = env.database(name)
    """
    env = get_default_environment()
    return env.database(name, **kwargs)


def secret(name: str, **kwargs) -> 'pulumi.Resource':
    """
    Create secret using the default environment.

    For explicit control, use:
        env = stack.environment(provider, name)
        secret = env.secret(name)
    """
    env = get_default_environment()
    return env.secret(name, **kwargs)


def pipeline(name: str):
    """
    Create pipeline in the default stack.

    For explicit control, use:
        stack = Stack('my-stack')
        pipeline = stack.pipeline(name)
    """
    from glacier.core.pipeline import Pipeline

    stack = get_default_stack()
    return stack.pipeline(name)
