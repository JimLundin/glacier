"""
Glacier: Code-centric data pipeline library with infrastructure-from-code generation.

⚠️ **ALPHA SOFTWARE** - API may change. No backwards compatibility guarantees until v1.0.

Glacier provides cloud-agnostic abstractions for building data pipelines that can
run on any cloud platform (AWS, Azure, GCP) or locally using dependency injection
and environment-first design.

Key concepts:
- GlacierEnv: Central orchestrator using dependency injection (environment-first pattern)
- Provider: SINGLE class that adapts based on config injection (NO provider subclasses!)
- Config: Configuration classes (AwsConfig, GcpConfig, etc.) determine provider behavior
- Resources: Generic abstractions (Bucket, Serverless) that work across clouds
- Tasks & Pipelines: Environment-bound, composable data transformation units

Environment-First Pattern (Only Supported Pattern):
    from glacier import GlacierEnv, Provider
    from glacier.config import AwsConfig
    import polars as pl

    # 1. Create provider with config injection
    # Config determines behavior - NOT subclasses!
    provider = Provider(config=AwsConfig(region="us-east-1"))

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

    # 5. Execute
    result = my_pipeline.run(mode="local")
"""

from glacier.core.context import GlacierContext
from glacier.core.env import GlacierEnv
from glacier.providers import Provider

# Re-export commonly used modules for convenience
from glacier import resources
from glacier import config

__version__ = "0.1.0-alpha"
__all__ = [
    # Core classes
    "GlacierEnv",
    "GlacierContext",
    "Provider",
    # Modules
    "resources",
    "config",
]
