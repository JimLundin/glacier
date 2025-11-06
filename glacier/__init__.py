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
- Pipelines: Composed using builder/fluent API pattern

Builder Pattern (Pipeline Composition):
    from glacier import Provider, Pipeline
    from glacier.config import AwsConfig
    import polars as pl

    # 1. Create provider with config injection
    provider = Provider(config=AwsConfig(region="us-east-1"))

    # 2. Create execution resources
    local_exec = provider.local()
    lambda_exec = provider.serverless(config=LambdaConfig(memory=1024))

    # 3. Create storage resources
    raw_data = provider.bucket(bucket="data", path="raw.parquet")
    filtered_data = provider.bucket(bucket="data", path="filtered.parquet")
    output_data = provider.bucket(bucket="data", path="output.parquet")

    # 4. Define tasks bound to execution resources
    @local_exec.task()
    def filter_positive(df: pl.LazyFrame) -> pl.LazyFrame:
        return df.filter(pl.col("value") > 0)

    @lambda_exec.task()
    def aggregate(df: pl.LazyFrame) -> pl.LazyFrame:
        return df.group_by("category").agg(pl.col("value").sum())

    # 5. Build pipeline using fluent API
    pipeline = (
        Pipeline(name="etl")
        .source(raw_data)
        .transform(filter_positive)
        .to(filtered_data)
        .transform(aggregate)
        .to(output_data)
    )

    # 6. Generate DAG or execute
    dag = pipeline.to_dag()
"""

from glacier.core.context import GlacierContext
from glacier.core.pipeline import Pipeline
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
    # Context
    "GlacierContext",
    # Modules
    "resources",
    "config",
    # Advanced (not recommended for most users)
    "GlacierEnv",
]
