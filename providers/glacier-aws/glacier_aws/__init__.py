"""
Glacier AWS Provider.

Implements the Provider interface for AWS, creating Pulumi AWS resources.
"""

from glacier_aws.provider import AWSProvider
from glacier_aws.executor import AWSExecutor
from glacier_aws.compiler import AWSCompiler

__all__ = [
    "AWSProvider",
    "AWSExecutor",
    "AWSCompiler",
]

__version__ = "0.1.0"
