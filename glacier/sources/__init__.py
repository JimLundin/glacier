"""
Source abstractions for Glacier pipelines.
"""

from glacier.sources.base import Source
from glacier.sources.bucket import BucketSource
from glacier.sources.s3 import S3Source
from glacier.sources.azure import AzureBlobSource
from glacier.sources.gcs import GCSSource
from glacier.sources.local import LocalSource

__all__ = [
    "Source",
    "BucketSource",
    "S3Source",
    "AzureBlobSource",
    "GCSSource",
    "LocalSource",
]
