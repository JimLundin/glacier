"""
Glacier AWS Provider.

This package provides AWS-specific implementations for Glacier pipelines,
including Pulumi-based infrastructure compilation and execution.
"""

from glacier_aws.compiler import AWSCompiler
from glacier_aws.executor import AWSExecutor

__all__ = [
    "AWSCompiler",
    "AWSExecutor",
]

__version__ = "0.1.0"
