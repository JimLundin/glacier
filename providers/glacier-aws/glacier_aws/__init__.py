"""
Glacier AWS Provider.

Implements the Provider interface for AWS, creating Pulumi AWS resources.
"""

from glacier_aws.provider import AWSProvider
from glacier_aws.executor import AWSExecutor

__all__ = [
    "AWSProvider",
    "AWSExecutor",
]

__version__ = "0.1.0"
