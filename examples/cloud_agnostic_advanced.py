"""
Advanced cloud-agnostic pipeline showing provider-specific configuration.

This example demonstrates:
1. Using generic Bucket and Serverless resources
2. Passing provider-specific config when needed
3. How to write pipelines that work on any cloud platform
4. Best practices for cloud-agnostic design

The key insight: your pipeline code never mentions S3, Azure Blob, or GCS.
You interact only with generic abstractions: Bucket, Serverless, etc.
"""

from glacier import pipeline, task
from glacier.providers import AWSProvider, AzureProvider, GCPProvider
from glacier.config import S3Config, AzureBlobConfig, GCSConfig
from glacier.resources import Bucket
import polars as pl


# Example 1: Basic cloud-agnostic usage
# Just change the provider to switch clouds!
def create_provider_from_env():
    """
    Create the appropriate provider based on environment.

    In a real application, you might:
    - Read from environment variables
    - Use a configuration file
    - Inject via dependency injection
    """
    import os

    cloud = os.getenv("GLACIER_CLOUD_PROVIDER", "aws")

    if cloud == "aws":
        return AWSProvider(region=os.getenv("AWS_REGION", "us-east-1"))
    elif cloud == "azure":
        return AzureProvider(
            resource_group=os.getenv("AZURE_RESOURCE_GROUP", "my-rg"),
            location=os.getenv("AZURE_LOCATION", "eastus"),
        )
    elif cloud == "gcp":
        return GCPProvider(
            project_id=os.getenv("GCP_PROJECT_ID", "my-project"),
            region=os.getenv("GCP_REGION", "us-central1"),
        )
    else:
        raise ValueError(f"Unsupported cloud provider: {cloud}")


# Initialize provider (cloud-agnostic from here on!)
provider = create_provider_from_env()


# Example 2: Basic bucket without provider-specific config
basic_data = provider.bucket(
    bucket="my-data-bucket",
    path="input/data.parquet",
    name="basic_source",
)


# Example 3: Bucket with provider-specific configuration
# Note: The config class matches the provider, but the Bucket is still generic!
configured_data = provider.bucket(
    bucket="my-data-bucket",
    path="optimized/data.parquet",
    name="configured_source",
    # This config is only used if provider is AWS
    # For other providers, it's ignored or adapted
    config=S3Config(
        storage_class="INTELLIGENT_TIERING",
        encryption="AES256",
        versioning=True,
    ),
)


# Example 4: Cloud-agnostic task functions
@task
def load_data(source: Bucket) -> pl.LazyFrame:
    """
    Load data from a bucket.

    This function works with ANY cloud provider because it uses
    the generic Bucket abstraction, not cloud-specific sources.
    """
    return source.scan()


@task(depends_on=[load_data])
def clean_data(df: pl.LazyFrame) -> pl.LazyFrame:
    """Remove null values and duplicates."""
    return df.filter(pl.col("value").is_not_null()).unique()


@task(depends_on=[clean_data])
def transform_data(df: pl.LazyFrame) -> pl.LazyFrame:
    """Apply business logic transformations."""
    return df.with_columns([
        (pl.col("value") * 1.1).alias("adjusted_value"),
        pl.col("timestamp").str.to_datetime().alias("datetime"),
    ])


@task(depends_on=[transform_data])
def aggregate_metrics(df: pl.LazyFrame) -> pl.LazyFrame:
    """Calculate summary metrics."""
    return df.group_by("category").agg([
        pl.col("adjusted_value").sum().alias("total_value"),
        pl.col("adjusted_value").mean().alias("avg_value"),
        pl.count().alias("record_count"),
    ])


@pipeline(
    name="cloud_agnostic_advanced",
    description="Advanced cloud-agnostic pipeline with provider configs",
)
def advanced_pipeline():
    """
    Pipeline that works on any cloud platform.

    Key benefits:
    - No vendor lock-in
    - Easy to test locally then deploy to any cloud
    - Can migrate between clouds with minimal code changes
    - Future-proof for Glacier managed service
    """
    # Load from basic bucket
    data1 = load_data(basic_data)

    # Load from configured bucket
    data2 = load_data(configured_data)

    # Combine and process
    combined = pl.concat([data1, data2])
    cleaned = clean_data(combined)
    transformed = transform_data(cleaned)
    metrics = aggregate_metrics(transformed)

    return metrics


if __name__ == "__main__":
    print("Advanced Cloud-Agnostic Pipeline")
    print("=" * 60)
    print("\nThis example demonstrates:")
    print("1. Provider abstraction - works with ANY cloud!")
    print("2. Optional provider-specific config")
    print("3. Environment-based provider selection")
    print("4. Complete cloud portability")
    print("\nCurrent provider:", provider)
    print("\nTo switch clouds, set environment variable:")
    print("  export GLACIER_CLOUD_PROVIDER=aws")
    print("  export GLACIER_CLOUD_PROVIDER=azure")
    print("  export GLACIER_CLOUD_PROVIDER=gcp")
    print("\nThe SAME pipeline code works with ALL providers!")
    print("\nBenefits:")
    print("- No vendor lock-in")
    print("- Easy cloud migration")
    print("- Test locally, deploy anywhere")
    print("- Ready for Glacier managed service")
