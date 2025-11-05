"""
Glacier: Code-centric data pipeline library with infrastructure-from-code generation.

Glacier provides cloud-agnostic abstractions for building data pipelines that can
run on any cloud platform (AWS, Azure, GCP) or locally.

Key concepts:
- Providers: Factory for creating cloud-agnostic resources
- Resources: Generic abstractions (Bucket, Serverless) that work across clouds
- Config: Optional provider-specific configuration classes
- Tasks & Pipelines: Composable data transformation units

Example:
    from glacier import pipeline, task
    from glacier.providers import AWSProvider
    from glacier.resources import Bucket
    import polars as pl

    provider = AWSProvider(region="us-east-1")
    data = provider.bucket("my-bucket", path="data.parquet")

    @task
    def process(source: Bucket) -> pl.LazyFrame:
        return source.scan().filter(pl.col("value") > 0)

    @pipeline(name="my_pipeline")
    def my_pipeline():
        return process(data)
"""

from glacier.core.pipeline import pipeline
from glacier.core.task import task
from glacier.core.context import GlacierContext

# Re-export commonly used modules for convenience
from glacier import providers
from glacier import resources
from glacier import config

__version__ = "0.1.0"
__all__ = [
    "pipeline",
    "task",
    "GlacierContext",
    "providers",
    "resources",
    "config",
]
