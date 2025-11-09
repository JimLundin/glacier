"""
Compilation interfaces for Glacier pipelines.

This module provides abstract interfaces for compiling pipelines
to infrastructure-as-code. Provider-specific compilers are injected
as dependencies.
"""

from glacier.compilation.compiler import Compiler, CompiledPipeline, CompilationContext
from glacier.compilation.multicloud import MultiCloudCompiler

__all__ = [
    "Compiler",
    "CompiledPipeline",
    "CompilationContext",
    "MultiCloudCompiler",
]
