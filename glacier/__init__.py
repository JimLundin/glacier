"""
Glacier: Code-centric data pipeline library with infrastructure-from-code generation.

Glacier provides cloud-agnostic abstractions for building data pipelines that can
run on any cloud platform (AWS, Azure, GCP) or locally.

Key concepts:
- GlacierEnv: Central orchestrator using dependency injection (environment-first pattern)
- Providers: Factory for creating cloud-agnostic resources
- Resources: Generic abstractions (Bucket, Serverless) that work across clouds
- Config: Provider-specific configuration classes (AwsConfig, GcpConfig, etc.)
- Tasks & Pipelines: Composable data transformation units

Environment-First Pattern (Recommended):
    from glacier import GlacierEnv
    from glacier.providers import AWSProvider
    from glacier.config import AwsConfig
    import polars as pl

    # 1. Create provider with config
    provider = AWSProvider(config=AwsConfig(region="us-east-1"))

    # 2. Create environment
    env = GlacierEnv(provider=provider, name="production")

    # 3. Define tasks bound to environment
    @env.task()
    def process(source) -> pl.LazyFrame:
        return source.scan().filter(pl.col("value") > 0)

    # 4. Define pipeline
    @env.pipeline()
    def my_pipeline():
        data = env.provider.bucket("my-bucket", path="data.parquet")
        return process(data)

Classic Pattern (Still Supported):
    from glacier import pipeline, task
    from glacier.providers import AWSProvider
    import polars as pl

    provider = AWSProvider(region="us-east-1")
    data = provider.bucket("my-bucket", path="data.parquet")

    @task
    def process(source) -> pl.LazyFrame:
        return source.scan().filter(pl.col("value") > 0)

    @pipeline(name="my_pipeline")
    def my_pipeline():
        return process(data)
"""

from glacier.core.pipeline import pipeline
from glacier.core.task import task
from glacier.core.context import GlacierContext
from glacier.core.env import GlacierEnv

# Re-export commonly used modules for convenience
from glacier import providers
from glacier import resources
from glacier import config

__version__ = "0.1.0"
__all__ = [
    # Core classes
    "GlacierEnv",
    "GlacierContext",
    # Decorators (classic pattern)
    "pipeline",
    "task",
    # Modules
    "providers",
    "resources",
    "config",
]
