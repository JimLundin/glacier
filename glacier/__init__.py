"""
Glacier: Code-centric data pipeline library with infrastructure-from-code generation.
"""

from glacier.core.pipeline import pipeline
from glacier.core.task import task
from glacier.core.context import GlacierContext

__version__ = "0.1.0"
__all__ = ["pipeline", "task", "GlacierContext"]
