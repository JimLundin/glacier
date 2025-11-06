"""
Cloud-agnostic pipeline demonstrating provider portability.

This example shows how the same pipeline code works with ANY provider
(AWS, Azure, GCP, or local) by simply changing the provider configuration.

CORRECT PATTERN:
- Provider config determines WHERE DATA LIVES (AWS S3, Azure Blob, GCP, local)
- Execution resources determine WHERE CODE RUNS (local, serverless, VM, cluster)
- Both storage and execution are first-class resources from provider
- Same code, different configs = cloud portability

Run with different providers:
    # Local
    export GLACIER_CLOUD=local
    python examples/cloud_agnostic_pipeline.py

    # AWS
    export GLACIER_CLOUD=aws
    export AWS_PROFILE=your-profile
    python examples/cloud_agnostic_pipeline.py

    # Azure
    export GLACIER_CLOUD=azure
    export AZURE_SUBSCRIPTION_ID=...
    python examples/cloud_agnostic_pipeline.py

    # GCP
    export GLACIER_CLOUD=gcp
    export GCP_PROJECT_ID=...
    python examples/cloud_agnostic_pipeline.py
"""

from glacier import Provider, pipeline
from glacier.config import AwsConfig, AzureConfig, GcpConfig, LocalConfig
import polars as pl
import os

# ============================================================================
# 1. CONFIGURATION: Dynamic provider selection
# ============================================================================


def create_provider_from_env() -> Provider:
    """Create provider based on GLACIER_CLOUD environment variable."""
    cloud = os.getenv("GLACIER_CLOUD", "local").lower()

    if cloud == "aws":
        config = AwsConfig(
            region=os.getenv("AWS_REGION", "us-east-1"),
            profile=os.getenv("AWS_PROFILE", "default"),
        )
    elif cloud == "azure":
        config = AzureConfig(
            subscription_id=os.getenv("AZURE_SUBSCRIPTION_ID", ""),
            resource_group=os.getenv("AZURE_RESOURCE_GROUP", "glacier-rg"),
            location=os.getenv("AZURE_LOCATION", "eastus"),
        )
    elif cloud == "gcp":
        config = GcpConfig(
            project_id=os.getenv("GCP_PROJECT_ID", "my-project"),
            region=os.getenv("GCP_REGION", "us-central1"),
        )
    elif cloud == "local":
        config = LocalConfig(base_path=os.getenv("GLACIER_LOCAL_PATH", "./data"))
    else:
        raise ValueError(f"Unknown GLACIER_CLOUD: {cloud}")

    return Provider(config=config)


# Create provider (config determines where data lives)
provider = create_provider_from_env()

# Create execution resource (local for all providers in this example)
local_exec = provider.local()

# Create storage resources (provider determines backend: S3/Blob/GCS/local)
sales_bucket = provider.bucket(bucket="company-data", path="sales.parquet")
customer_bucket = provider.bucket(bucket="company-data", path="customers.parquet")

# ============================================================================
# 2. TASKS: Bound to execution resource
# ============================================================================


@local_exec.task()
def load_sales(source) -> pl.LazyFrame:
    """
    Load sales data.

    Works with ANY storage (S3, Azure Blob, GCS, local) because
    it uses the provider abstraction.

    EXECUTION: Local Python process (local_exec)
    DATA: Determined by provider config (S3/Blob/GCS/local)
    """
    return source.scan()


@local_exec.task()
def load_customers(source) -> pl.LazyFrame:
    """Load customer data. Works with any storage."""
    return source.scan()


@local_exec.task()
def clean_sales(df: pl.LazyFrame) -> pl.LazyFrame:
    """Clean sales data."""
    return df.filter(pl.col("amount").is_not_null() & (pl.col("amount") > 0))


@local_exec.task()
def clean_customers(df: pl.LazyFrame) -> pl.LazyFrame:
    """Clean customer data."""
    return df.filter(
        pl.col("customer_id").is_not_null() & pl.col("customer_name").is_not_null()
    )


@local_exec.task()
def join_data(sales: pl.LazyFrame, customers: pl.LazyFrame) -> pl.LazyFrame:
    """Join sales with customers."""
    return sales.join(customers, on="customer_id", how="left")


@local_exec.task()
def calculate_metrics(df: pl.LazyFrame) -> pl.LazyFrame:
    """Calculate customer metrics."""
    return df.group_by("customer_id").agg(
        [
            pl.col("customer_name").first(),
            pl.col("amount").sum().alias("total_revenue"),
            pl.col("amount").mean().alias("avg_order_value"),
            pl.count().alias("order_count"),
        ]
    )


# ============================================================================
# 3. PIPELINE: Cloud-agnostic orchestration
# ============================================================================


@pipeline(name="customer_analytics")
def analytics_pipeline():
    """
    Cloud-agnostic customer analytics pipeline.

    This pipeline works identically with ALL providers:
    - AWS S3
    - Azure Blob Storage
    - Google Cloud Storage
    - Local filesystem

    Switch by changing GLACIER_CLOUD environment variable.
    NO CODE CHANGES required!
    """
    # Load data (from any storage backend)
    sales = load_sales(sales_bucket)
    customers = load_customers(customer_bucket)

    # Process (identical logic regardless of provider)
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
    print(f"\n🌍 Current Configuration:")
    print(f"   Cloud: {cloud_name}")
    print(f"   Provider: {provider}")
    print(f"   Config Type: {type(provider.config).__name__}")

    print("\n" + "=" * 70)
    print("Glacier Resource Pattern")
    print("=" * 70)
    print("\n✓ Provider creates resources:")
    print("\n  STORAGE (where data lives):")
    print("    - provider.bucket()")
    print("    - Config determines backend:")
    print("      • AwsConfig → AWS S3")
    print("      • AzureConfig → Azure Blob Storage")
    print("      • GcpConfig → Google Cloud Storage")
    print("      • LocalConfig → Local filesystem")
    print("\n  EXECUTION (where code runs):")
    print("    - provider.local() → Local Python process")
    print("    - provider.serverless(config=...) → Lambda/Cloud Functions/Azure Functions")
    print("    - provider.vm(config=...) → EC2/Compute Engine/Azure VM")
    print("    - provider.cluster(config=...) → Databricks/EMR/Dataproc")
    print("\n✓ Tasks bound to execution resources:")
    print("    - @local_exec.task() → runs on local_exec")
    print("    - @lambda_exec.task() → runs on lambda_exec")
    print("\n✓ Cloud Portability:")
    print("    - Same pipeline code for ALL clouds")
    print("    - Switch via provider config only")
    print("    - No vendor lock-in")

    print("\n" + "=" * 70)
    print("How to Switch Clouds")
    print("=" * 70)
    print("\n1. Local filesystem:")
    print("   export GLACIER_CLOUD=local")
    print("\n2. AWS S3:")
    print("   export GLACIER_CLOUD=aws")
    print("   export AWS_PROFILE=your-profile")
    print("\n3. Azure Blob:")
    print("   export GLACIER_CLOUD=azure")
    print("   export AZURE_SUBSCRIPTION_ID=...")
    print("\n4. Google Cloud Storage:")
    print("   export GLACIER_CLOUD=gcp")
    print("   export GCP_PROJECT_ID=...")

    print("\n" + "=" * 70)

    # Uncomment to run
    # print(f"\n▶️  Running pipeline on {cloud_name}...")
    # result = analytics_pipeline.run(mode="local")
    # print("\n✅ Pipeline completed!")
    # print(result.collect())
