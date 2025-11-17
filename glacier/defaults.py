"""
Default stack and environment for implicit usage.

These defaults enable the simplest usage pattern where users don't need to
explicitly create Stack or Environment objects. Factory functions in
glacier.core.factories use these defaults when no parent is specified.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from glacier.core.environment import Environment
    from glacier.core.stack import Stack


# Module-level defaults (lazy-created on first use)
_default_stack: "Stack | None" = None
_default_environment: "Environment | None" = None


def get_default_stack() -> "Stack":
    """
    Get or create the default stack.

    The default stack is used when no explicit stack is provided to factory
    functions. It's created lazily on first access.
    """
    global _default_stack
    if _default_stack is None:
        from glacier.core.stack import Stack
        _default_stack = Stack(name="default")
    return _default_stack


def get_default_environment() -> "Environment":
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
                "  2. Use explicit Environment with a cloud provider:\n"
                "     from glacier import environment\n"
                "     from glacier_aws import AWSProvider\n"
                "     env = environment(AWSProvider(...), 'prod')"
            )
    return _default_environment


def reset_defaults() -> None:
    """
    Reset default stack and environment to None.

    Useful for testing to ensure clean state between tests.
    """
    global _default_stack, _default_environment
    _default_stack = None
    _default_environment = None
