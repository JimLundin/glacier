"""
Glacier: Code-centric data pipeline library with infrastructure-from-code generation.

⚠️ **ALPHA SOFTWARE** - API may change. No backwards compatibility guarantees until v1.0.

Glacier provides cloud-agnostic abstractions for building data pipelines that can
run on any cloud platform (AWS, Azure, GCP) or locally using dependency injection
and resource-centric design.

Key concepts:
- Provider: SINGLE class that adapts based on config injection (NO provider subclasses!)
- Config: Configuration classes (AwsConfig, GcpConfig, etc.) determine provider behavior
- Resources: Generic abstractions (Bucket, ExecutionResource) that work across clouds
- Tasks: Created via @executor.task() decorators on execution resources
- Pipelines: Orchestrate tasks using @pipeline decorator or fluent API

Recommended Pattern (Decorator-based):
    from glacier import Provider, pipeline
    from glacier.config import AwsConfig
    import polars as pl

    # 1. Create provider with config injection
    provider = Provider(config=AwsConfig(region="us-east-1"))

    # 2. Create execution resources
    local_exec = provider.local()
    lambda_exec = provider.serverless(config=LambdaConfig(memory=1024))

    # 3. Create storage resources
    data_source = provider.bucket(bucket="data", path="input.parquet")

    # 4. Define tasks bound to execution resources
    @local_exec.task()
    def load(source) -> pl.LazyFrame:
        return source.scan()

    @lambda_exec.task()
    def transform(df: pl.LazyFrame) -> pl.LazyFrame:
        return df.filter(pl.col("value") > 0)

    # 5. Define pipeline
    @pipeline(name="etl")
    def etl_pipeline():
        data = load(data_source)
        result = transform(data)
        return result

    # 6. Execute
    result = etl_pipeline.run(mode="local")

Alternative Pattern (Fluent API):
    from glacier import Provider, Pipeline

    provider = Provider(config=AwsConfig(region="us-east-1"))
    local_exec = provider.local()

    raw = provider.bucket(bucket="data", path="raw.parquet")
    output = provider.bucket(bucket="data", path="output.parquet")

    @local_exec.task()
    def process(df: pl.LazyFrame) -> pl.LazyFrame:
        return df.filter(pl.col("value") > 0)

    # Fluent pipeline composition
    pipeline = (
        Pipeline(name="etl")
        .source(raw)
        .transform(process)
        .to(output)
    )
"""

from glacier.core.context import GlacierContext
from glacier.core.pipeline import Pipeline, pipeline
from glacier.providers import Provider

# Re-export commonly used modules for convenience
from glacier import resources
from glacier import config

# GlacierEnv is kept for advanced use cases but not in primary API
from glacier.core.env import GlacierEnv

__version__ = "0.1.0-alpha"
__all__ = [
    # Core classes (primary API)
    "Provider",
    "Pipeline",
    "pipeline",
    # Context
    "GlacierContext",
    # Modules
    "resources",
    "config",
    # Advanced (not recommended for most users)
    "GlacierEnv",
]
