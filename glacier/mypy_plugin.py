"""
Mypy plugin for Glacier to support Dataset instances as type annotations.

This plugin teaches mypy that Dataset instances can be used as types.

To enable, add to mypy.ini or pyproject.toml:
    [mypy]
    plugins = glacier.mypy_plugin
"""

from typing import Callable, Optional, Type as TypingType
from mypy.plugin import Plugin, AnalyzeTypeContext
from mypy.nodes import CallExpr, NameExpr, MemberExpr, Var
from mypy.types import Type, AnyType, TypeOfAny, Instance, UnboundType
from mypy.plugin import MethodContext


class GlacierPlugin(Plugin):
    """
    Mypy plugin that makes Dataset instances usable as types.

    This plugin intercepts Dataset instantiation and tells mypy to treat
    the result as a type, not just a variable.
    """

    def get_type_analyze_hook(self, fullname: str) -> Optional[Callable[[AnalyzeTypeContext], Type]]:
        """
        Hook called when mypy encounters a type annotation.

        If the annotation is a Dataset instance (detected by name), we tell mypy
        it's valid.
        """
        # This is called for type annotations
        # We'll handle Dataset instances here
        return None  # Will be implemented

    def get_attribute_hook(self, fullname: str) -> Optional[Callable[[MethodContext], Type]]:
        """Hook for attribute access on Dataset instances."""
        return None


def plugin(version: str) -> TypingType[GlacierPlugin]:
    """
    Entry point for mypy plugin system.

    Args:
        version: Mypy version string

    Returns:
        Plugin class
    """
    return GlacierPlugin


# Alternative simpler approach: Just tell users to use typing.cast
# or create a helper function that works with mypy
