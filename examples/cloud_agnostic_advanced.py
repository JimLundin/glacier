"""
Advanced cloud-agnostic pipeline with environment-based provider selection.

This example demonstrates:
1. Dynamic provider selection based on environment variables
2. Provider-specific configurations (S3, Azure Blob, GCS)
3. Complete cloud portability with a single codebase
4. Best practices for cloud-agnostic design

The key insight: Your pipeline code uses the SINGLE Provider class with
config injection. Switch clouds by changing configuration, not code!

Run with:
    # AWS
    export GLACIER_CLOUD_PROVIDER=aws
    export AWS_REGION=us-east-1
    python examples/cloud_agnostic_advanced.py

    # Azure
    export GLACIER_CLOUD_PROVIDER=azure
    export AZURE_RESOURCE_GROUP=my-rg
    export AZURE_LOCATION=eastus
    python examples/cloud_agnostic_advanced.py

    # GCP
    export GLACIER_CLOUD_PROVIDER=gcp
    export GCP_PROJECT_ID=my-project
    export GCP_REGION=us-central1
    python examples/cloud_agnostic_advanced.py

    # Local
    export GLACIER_CLOUD_PROVIDER=local
    python examples/cloud_agnostic_advanced.py
"""

from glacier import GlacierEnv, Provider
from glacier.config import AwsConfig, AzureConfig, GcpConfig, LocalConfig, S3Config
import polars as pl
import os

# ============================================================================
# 1. CONFIGURATION: Dynamic provider selection from environment
# ============================================================================


def create_provider_from_env() -> Provider:
    """
    Create provider based on environment variables.

    This demonstrates the 12-factor app pattern for configuration.
    The SINGLE Provider class adapts its behavior based on the injected config.
    """
    cloud = os.getenv("GLACIER_CLOUD_PROVIDER", "local")

    if cloud == "aws":
        config = AwsConfig(
            region=os.getenv("AWS_REGION", "us-east-1"),
            profile=os.getenv("AWS_PROFILE", "default"),
            tags={"environment": "production", "managed_by": "glacier"},
        )
    elif cloud == "azure":
        config = AzureConfig(
            resource_group=os.getenv("AZURE_RESOURCE_GROUP", "my-rg"),
            location=os.getenv("AZURE_LOCATION", "eastus"),
            subscription_id=os.getenv("AZURE_SUBSCRIPTION_ID", ""),
            tags={"environment": "production", "managed_by": "glacier"},
        )
    elif cloud == "gcp":
        config = GcpConfig(
            project_id=os.getenv("GCP_PROJECT_ID", "my-project"),
            region=os.getenv("GCP_REGION", "us-central1"),
            labels={"environment": "production", "managed_by": "glacier"},
        )
    elif cloud == "local":
        config = LocalConfig(
            base_path=os.getenv("GLACIER_LOCAL_PATH", "./data"),
            create_dirs=True,
        )
    else:
        raise ValueError(f"Unsupported cloud provider: {cloud}. Use: aws, azure, gcp, or local")

    # Single Provider class - behavior determined by config!
    return Provider(config=config)


# Create provider dynamically
provider = create_provider_from_env()

# Create environment
env = GlacierEnv(provider=provider, name="cloud-agnostic")

# ============================================================================
# 2. RESOURCES: Define cloud-agnostic resources
# ============================================================================

# Register basic bucket (works with ANY provider)
env.register(
    "basic_data",
    env.provider.bucket(
        bucket="my-data-bucket",
        path="input/data.parquet",
    ),
)

# Register bucket with provider-specific config
# Note: S3Config only applies if provider is AWS, ignored otherwise
env.register(
    "optimized_data",
    env.provider.bucket(
        bucket="my-data-bucket",
        path="optimized/data.parquet",
        config=S3Config(
            storage_class="INTELLIGENT_TIERING",
            encryption="AES256",
            versioning=True,
        ) if isinstance(provider.config, AwsConfig) else None,
    ),
)

# ============================================================================
# 3. TASKS: Cloud-agnostic task definitions
# ============================================================================


@env.task()
def load_data(source) -> pl.LazyFrame:
    """
    Load data from a bucket.

    This function works with ANY cloud provider because it uses
    the provider abstraction, not cloud-specific APIs.
    """
    return source.scan()


@env.task()
def clean_data(df: pl.LazyFrame) -> pl.LazyFrame:
    """Remove null values and duplicates."""
    return df.filter(pl.col("value").is_not_null()).unique()


@env.task()
def transform_data(df: pl.LazyFrame) -> pl.LazyFrame:
    """Apply business logic transformations."""
    return df.with_columns(
        [
            (pl.col("value") * 1.1).alias("adjusted_value"),
            pl.col("timestamp").cast(pl.Utf8).str.to_datetime().alias("datetime"),
        ]
    )


@env.task()
def aggregate_metrics(df: pl.LazyFrame) -> pl.LazyFrame:
    """Calculate summary metrics."""
    return df.group_by("category").agg(
        [
            pl.col("adjusted_value").sum().alias("total_value"),
            pl.col("adjusted_value").mean().alias("avg_value"),
            pl.count().alias("record_count"),
        ]
    )


# ============================================================================
# 4. PIPELINE: Cloud-agnostic pipeline definition
# ============================================================================


@env.pipeline(name="cloud_agnostic_advanced")
def advanced_pipeline():
    """
    Pipeline that works on ANY cloud platform.

    This pipeline demonstrates:
    - Provider abstraction (works with AWS, Azure, GCP, Local)
    - Environment-based configuration
    - Optional provider-specific optimizations
    - Zero code changes to switch clouds

    Key benefits:
    - No vendor lock-in
    - Easy to test locally then deploy to any cloud
    - Can migrate between clouds by changing environment variables
    - Single codebase for all deployment targets
    """
    # Retrieve registered resources
    basic_source = env.get("basic_data")
    optimized_source = env.get("optimized_data")

    # Load from both sources
    data1 = load_data(basic_source)
    data2 = load_data(optimized_source)

    # Combine and process
    # Note: This logic works identically on ALL cloud providers!
    combined = pl.concat([data1, data2])
    cleaned = clean_data(combined)
    transformed = transform_data(cleaned)
    metrics = aggregate_metrics(transformed)

    return metrics


# ============================================================================
# 5. EXECUTION
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("Advanced Cloud-Agnostic Pipeline")
    print("=" * 70)

    print("\n📍 Current Configuration:")
    print(f"   Provider: {type(provider.config).__name__}")
    print(f"   Environment: {env.name}")
    print(f"   Registered resources: {env.list_resources()}")

    print("\n" + "=" * 70)
    print("Features")
    print("=" * 70)
    print("\n✓ Cloud Portability:")
    print("  - Same code works on AWS, Azure, GCP, and Local")
    print("  - Switch clouds by changing environment variables")
    print("  - No code changes required")
    print("\n✓ Provider Abstraction:")
    print("  - Single Provider class with config injection")
    print("  - Type-safe configuration objects")
    print("  - Optional provider-specific optimizations")
    print("\n✓ Environment-First Pattern:")
    print("  - Explicit configuration management")
    print("  - Easy to test and mock")
    print("  - Supports multiple environments (dev, staging, prod)")

    print("\n" + "=" * 70)
    print("How to Switch Clouds")
    print("=" * 70)
    print("\n1. AWS:")
    print("   export GLACIER_CLOUD_PROVIDER=aws")
    print("   export AWS_REGION=us-east-1")
    print("   export AWS_PROFILE=production")
    print("\n2. Azure:")
    print("   export GLACIER_CLOUD_PROVIDER=azure")
    print("   export AZURE_RESOURCE_GROUP=my-rg")
    print("   export AZURE_LOCATION=eastus")
    print("\n3. GCP:")
    print("   export GLACIER_CLOUD_PROVIDER=gcp")
    print("   export GCP_PROJECT_ID=my-project")
    print("   export GCP_REGION=us-central1")
    print("\n4. Local (for testing):")
    print("   export GLACIER_CLOUD_PROVIDER=local")

    print("\n" + "=" * 70)
    print("Benefits")
    print("=" * 70)
    print("\n✓ No vendor lock-in - switch clouds anytime")
    print("✓ Test locally, deploy anywhere")
    print("✓ Single codebase for all clouds")
    print("✓ Infrastructure generated automatically")
    print("✓ Type-safe configuration")

    print("\n" + "=" * 70)

    # Uncomment to run (requires appropriate cloud credentials and data)
    # print("\nRunning pipeline...")
    # result = advanced_pipeline.run(mode="local")
    # print("\nPipeline Result:")
    # print(result.collect())
