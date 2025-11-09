"""
Glacier AWS Provider.

Provides AWS-specific conveniences for Glacier pipelines.
Main export is Environment - a convenience wrapper around Pulumi.
"""

from glacier_aws.environment import Environment
from glacier_aws.executor import AWSExecutor

__all__ = [
    "Environment",
    "AWSExecutor",
]

__version__ = "0.1.0"
