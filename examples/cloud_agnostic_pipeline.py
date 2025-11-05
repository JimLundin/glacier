"""
Cloud-agnostic pipeline demonstrating provider portability.

This example shows how to write a pipeline that works with ANY cloud provider
(AWS, Azure, GCP, or local filesystem) by simply changing the provider configuration.

Key insight: Provider config determines WHERE DATA LIVES, not where code runs.
All tasks in this example execute locally (default executor="local"), but data
can live in any cloud storage system.

This demonstrates Glacier's core value proposition: write once, deploy anywhere.

Run with different providers:
    # Local filesystem
    export GLACIER_CLOUD=local
    python examples/cloud_agnostic_pipeline.py

    # AWS S3
    export GLACIER_CLOUD=aws
    export AWS_PROFILE=your-profile
    python examples/cloud_agnostic_pipeline.py

    # Azure Blob Storage
    export GLACIER_CLOUD=azure
    export AZURE_SUBSCRIPTION_ID=...
    export AZURE_RESOURCE_GROUP=...
    python examples/cloud_agnostic_pipeline.py

    # Google Cloud Storage
    export GLACIER_CLOUD=gcp
    export GCP_PROJECT_ID=...
    python examples/cloud_agnostic_pipeline.py
"""

from glacier import GlacierEnv, Provider
from glacier.config import AwsConfig, AzureConfig, GcpConfig, LocalConfig, S3Config
import polars as pl
import os

# ============================================================================
# 1. CONFIGURATION: Select provider based on environment variable
# ============================================================================


def create_provider_from_env() -> Provider:
    """
    Create provider based on GLACIER_CLOUD environment variable.

    This demonstrates the 12-factor app pattern for configuration.
    The provider config determines WHERE DATA LIVES, not where code runs.
    """
    cloud = os.getenv("GLACIER_CLOUD", "local").lower()

    if cloud == "aws":
        config = AwsConfig(
            region=os.getenv("AWS_REGION", "us-east-1"),
            profile=os.getenv("AWS_PROFILE", "default"),
            tags={"project": "data-pipeline", "managed_by": "glacier"},
        )
    elif cloud == "azure":
        config = AzureConfig(
            subscription_id=os.getenv("AZURE_SUBSCRIPTION_ID", ""),
            resource_group=os.getenv("AZURE_RESOURCE_GROUP", "glacier-rg"),
            location=os.getenv("AZURE_LOCATION", "eastus"),
            tags={"project": "data-pipeline", "managed_by": "glacier"},
        )
    elif cloud == "gcp":
        config = GcpConfig(
            project_id=os.getenv("GCP_PROJECT_ID", "my-project"),
            region=os.getenv("GCP_REGION", "us-central1"),
            labels={"project": "data-pipeline", "managed_by": "glacier"},
        )
    elif cloud == "local":
        config = LocalConfig(
            base_path=os.getenv("GLACIER_LOCAL_PATH", "./data"),
            create_dirs=True,
        )
    else:
        raise ValueError(
            f"Unknown GLACIER_CLOUD: {cloud}. Use: aws, azure, gcp, or local"
        )

    # Single Provider class - behavior determined by config!
    return Provider(config=config)


# Create provider (determines where data lives)
provider = create_provider_from_env()

# Create execution context (DI container)
env = GlacierEnv(provider=provider, name="cloud-agnostic-pipeline")

# ============================================================================
# 2. TASKS: Cloud-agnostic task definitions
# ============================================================================

# These tasks work with ANY cloud provider because they use the provider
# abstraction. The provider config determines where data lives, and tasks
# don't need to know the details.


@env.task()
def load_sales(source) -> pl.LazyFrame:
    """
    Load sales data.

    Works with ANY storage backend (S3, Azure Blob, GCS, local filesystem)
    because it uses the provider abstraction.

    Executes locally (default executor="local").
    """
    return source.scan()


@env.task()
def load_customers(source) -> pl.LazyFrame:
    """Load customer data. Works with any storage backend. Executes locally."""
    return source.scan()


@env.task()
def clean_sales(df: pl.LazyFrame) -> pl.LazyFrame:
    """Clean sales data. Executes locally."""
    return df.filter(
        pl.col("amount").is_not_null() & (pl.col("amount") > 0)
    ).with_columns([pl.col("date").cast(pl.Utf8).str.to_datetime().alias("sale_date")])


@env.task()
def clean_customers(df: pl.LazyFrame) -> pl.LazyFrame:
    """Clean customer data. Executes locally."""
    return df.filter(
        pl.col("customer_id").is_not_null() & pl.col("customer_name").is_not_null()
    )


@env.task()
def join_data(sales: pl.LazyFrame, customers: pl.LazyFrame) -> pl.LazyFrame:
    """Join sales with customers. Executes locally."""
    return sales.join(customers, on="customer_id", how="left")


@env.task()
def calculate_metrics(df: pl.LazyFrame) -> pl.LazyFrame:
    """Calculate customer metrics. Executes locally."""
    return df.group_by("customer_id").agg(
        [
            pl.col("customer_name").first(),
            pl.col("amount").sum().alias("total_revenue"),
            pl.col("amount").mean().alias("avg_order_value"),
            pl.count().alias("order_count"),
        ]
    )


# ============================================================================
# 3. PIPELINE: Cloud-agnostic pipeline definition
# ============================================================================


@env.pipeline(name="customer_analytics")
def analytics_pipeline():
    """
    Cloud-agnostic customer analytics pipeline.

    This pipeline works identically on ALL cloud providers:
    - AWS S3
    - Azure Blob Storage
    - Google Cloud Storage
    - Local filesystem

    Switch providers by changing the GLACIER_CLOUD environment variable.
    No code changes required!

    All tasks execute locally (executor="local"), but data can live anywhere.
    """
    # Create cloud-agnostic data sources
    # Provider knows where to find them based on its config
    sales_source = env.provider.bucket(bucket="company-data", path="sales.parquet")

    customer_source = env.provider.bucket(bucket="company-data", path="customers.parquet")

    # Data flow (identical logic regardless of cloud provider!)
    sales = load_sales(sales_source)
    customers = load_customers(customer_source)

    clean_sales_df = clean_sales(sales)
    clean_customers_df = clean_customers(customers)

    joined = join_data(clean_sales_df, clean_customers_df)
    metrics = calculate_metrics(joined)

    return metrics


# ============================================================================
# 4. EXECUTION
# ============================================================================

if __name__ == "__main__":
    cloud_name = os.getenv("GLACIER_CLOUD", "local").upper()

    print("=" * 70)
    print("Cloud-Agnostic Customer Analytics Pipeline")
    print("=" * 70)
    print(f"\n🌍 Data Storage: {cloud_name}")
    print(f"   Provider: {provider}")
    print(f"   Config: {type(provider.config).__name__}")
    print(f"\n⚙️  Code Execution: LOCAL")
    print(f"   All tasks run in local Python process (executor='local')")
    print(f"\n📦 Execution Context: {env.name}")
    print(f"   (DI container, not deployment environment)")

    print("\n" + "=" * 70)
    print("Key Concepts")
    print("=" * 70)
    print("\n✓ Provider Config determines WHERE DATA LIVES:")
    print("  - AwsConfig → AWS S3")
    print("  - AzureConfig → Azure Blob Storage")
    print("  - GcpConfig → Google Cloud Storage")
    print("  - LocalConfig → Local filesystem")
    print("\n✓ Task Executor determines WHERE CODE RUNS:")
    print("  - executor='local' → Local Python process (default)")
    print("  - executor='databricks' → Databricks cluster (future)")
    print("  - executor='spark' → Spark cluster (future)")
    print("\n✓ Cloud Portability:")
    print("  - Same pipeline code works with ALL providers")
    print("  - Switch clouds by changing provider config only")
    print("  - No vendor lock-in")
    print("\n✓ Deployment environments (dev/staging/prod):")
    print("  - NOT part of Glacier library")
    print("  - Handle via infrastructure (separate Terraform workspaces, etc.)")
    print("  - Provider tags can include deployment metadata for AWS resources")

    print("\n" + "=" * 70)
    print("How to Switch Clouds")
    print("=" * 70)
    print("\n1. Local filesystem:")
    print("   export GLACIER_CLOUD=local")
    print("   python examples/cloud_agnostic_pipeline.py")
    print("\n2. AWS S3:")
    print("   export GLACIER_CLOUD=aws")
    print("   export AWS_PROFILE=your-profile")
    print("   python examples/cloud_agnostic_pipeline.py")
    print("\n3. Azure Blob Storage:")
    print("   export GLACIER_CLOUD=azure")
    print("   export AZURE_SUBSCRIPTION_ID=...")
    print("   export AZURE_RESOURCE_GROUP=...")
    print("   python examples/cloud_agnostic_pipeline.py")
    print("\n4. Google Cloud Storage:")
    print("   export GLACIER_CLOUD=gcp")
    print("   export GCP_PROJECT_ID=...")
    print("   python examples/cloud_agnostic_pipeline.py")

    print("\n" + "=" * 70)

    # Uncomment to run (requires appropriate cloud credentials and data)
    # print(f"\n▶️  Running pipeline with {cloud_name} storage...")
    # result = analytics_pipeline.run(mode="local")
    # print("\n✅ Pipeline completed!")
    # print("\nResults:")
    # print(result.collect())
