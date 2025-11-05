"""
Multi-cloud pipeline demonstrating deployment to multiple cloud providers.

This example shows how to:
1. Define a pipeline once with reusable task logic
2. Deploy the same pipeline to different cloud environments
3. Use environment-first pattern for multi-cloud deployments
4. Test locally before deploying to any cloud

This demonstrates Glacier's core value proposition: write once, deploy anywhere.

Run with:
    # Test locally first
    python examples/multi_cloud_pipeline.py

    # Then deploy to AWS
    export DEPLOY_TARGET=aws
    python examples/multi_cloud_pipeline.py

    # Or deploy to Azure
    export DEPLOY_TARGET=azure
    python examples/multi_cloud_pipeline.py

    # Or deploy to GCP
    export DEPLOY_TARGET=gcp
    python examples/multi_cloud_pipeline.py
"""

from glacier import GlacierEnv, Provider
from glacier.config import AwsConfig, AzureConfig, GcpConfig, LocalConfig, S3Config
import polars as pl
import os

# ============================================================================
# 1. CONFIGURATION: Define all environments
# ============================================================================

# Local environment for testing
local_provider = Provider(config=LocalConfig(base_path="./data", create_dirs=True))
local_env = GlacierEnv(provider=local_provider, name="local")

# AWS production environment
aws_provider = Provider(
    config=AwsConfig(
        region="us-east-1",
        profile="production",
        tags={"environment": "production", "cloud": "aws", "managed_by": "glacier"},
    )
)
aws_env = GlacierEnv(provider=aws_provider, name="aws-production")

# Azure production environment
azure_provider = Provider(
    config=AzureConfig(
        resource_group="glacier-prod-rg",
        location="eastus",
        subscription_id=os.getenv("AZURE_SUBSCRIPTION_ID", ""),
        tags={"environment": "production", "cloud": "azure", "managed_by": "glacier"},
    )
)
azure_env = GlacierEnv(provider=azure_provider, name="azure-production")

# GCP production environment
gcp_provider = Provider(
    config=GcpConfig(
        project_id="glacier-prod",
        region="us-central1",
        labels={"environment": "production", "cloud": "gcp", "managed_by": "glacier"},
    )
)
gcp_env = GlacierEnv(provider=gcp_provider, name="gcp-production")

# ============================================================================
# 2. TASK FACTORY: Define reusable task logic
# ============================================================================


def create_pipeline_tasks(env: GlacierEnv):
    """
    Factory function to create tasks bound to a specific environment.

    This pattern allows you to define task logic ONCE and deploy to
    multiple clouds by binding to different environments.
    """

    @env.task()
    def extract_sales(source) -> pl.LazyFrame:
        """Extract sales data from source."""
        return source.scan()

    @env.task()
    def extract_customers(source) -> pl.LazyFrame:
        """Extract customer data from source."""
        return source.scan()

    @env.task()
    def clean_sales(df: pl.LazyFrame) -> pl.LazyFrame:
        """Clean and validate sales data."""
        return df.filter(
            pl.col("amount").is_not_null() & (pl.col("amount") > 0)
        ).with_columns(
            [
                pl.col("date").cast(pl.Utf8).str.to_datetime().alias("sale_date"),
                pl.col("amount").cast(pl.Float64),
            ]
        )

    @env.task()
    def clean_customers(df: pl.LazyFrame) -> pl.LazyFrame:
        """Clean and validate customer data."""
        return df.filter(
            pl.col("customer_id").is_not_null() & pl.col("customer_name").is_not_null()
        )

    @env.task()
    def join_data(sales: pl.LazyFrame, customers: pl.LazyFrame) -> pl.LazyFrame:
        """Join sales with customer information."""
        return sales.join(customers, on="customer_id", how="left")

    @env.task()
    def calculate_metrics(df: pl.LazyFrame) -> pl.LazyFrame:
        """Calculate customer lifetime value and metrics."""
        return df.group_by("customer_id").agg(
            [
                pl.col("customer_name").first(),
                pl.col("amount").sum().alias("lifetime_value"),
                pl.col("amount").mean().alias("avg_order_value"),
                pl.count().alias("total_orders"),
                pl.col("sale_date").min().alias("first_purchase"),
                pl.col("sale_date").max().alias("last_purchase"),
            ]
        )

    return {
        "extract_sales": extract_sales,
        "extract_customers": extract_customers,
        "clean_sales": clean_sales,
        "clean_customers": clean_customers,
        "join_data": join_data,
        "calculate_metrics": calculate_metrics,
    }


# ============================================================================
# 3. PIPELINE FACTORY: Create pipelines for each environment
# ============================================================================


def create_customer_analytics_pipeline(env: GlacierEnv, tasks: dict):
    """
    Factory function to create a pipeline for a specific environment.

    This demonstrates the power of environment-first design:
    - Same logic, different infrastructure
    - Zero code duplication
    - Easy to test locally before cloud deployment
    """

    @env.pipeline(name="customer_analytics")
    def customer_analytics_pipeline():
        """
        Customer analytics pipeline.

        Calculates customer lifetime value and key metrics from
        sales and customer data.
        """
        # Create resources using environment's provider
        # Paths are the same, but actual storage differs by cloud!
        sales_source = env.provider.bucket(
            bucket="company-data", path="sales/sales.parquet"
        )

        customer_source = env.provider.bucket(
            bucket="company-data", path="customers/customers.parquet"
        )

        # Data flow (identical logic across all clouds!)
        sales = tasks["extract_sales"](sales_source)
        customers = tasks["extract_customers"](customer_source)

        clean_sales_df = tasks["clean_sales"](sales)
        clean_customers_df = tasks["clean_customers"](customers)

        joined = tasks["join_data"](clean_sales_df, clean_customers_df)
        metrics = tasks["calculate_metrics"](joined)

        return metrics

    return customer_analytics_pipeline


# ============================================================================
# 4. SETUP: Create pipeline instances for each environment
# ============================================================================

# Create tasks for each environment
local_tasks = create_pipeline_tasks(local_env)
aws_tasks = create_pipeline_tasks(aws_env)
azure_tasks = create_pipeline_tasks(azure_env)
gcp_tasks = create_pipeline_tasks(gcp_env)

# Create pipelines for each environment
local_pipeline = create_customer_analytics_pipeline(local_env, local_tasks)
aws_pipeline = create_customer_analytics_pipeline(aws_env, aws_tasks)
azure_pipeline = create_customer_analytics_pipeline(azure_env, azure_tasks)
gcp_pipeline = create_customer_analytics_pipeline(gcp_env, gcp_tasks)

# ============================================================================
# 5. EXECUTION: Select environment based on configuration
# ============================================================================


def main():
    """
    Main execution function.

    Demonstrates how to select the deployment target at runtime
    based on environment variables or configuration.
    """
    deploy_target = os.getenv("DEPLOY_TARGET", "local").lower()

    # Map deploy targets to pipelines and environments
    targets = {
        "local": (local_pipeline, local_env, "Local filesystem"),
        "aws": (aws_pipeline, aws_env, "AWS S3"),
        "azure": (azure_pipeline, azure_env, "Azure Blob Storage"),
        "gcp": (gcp_pipeline, gcp_env, "Google Cloud Storage"),
    }

    if deploy_target not in targets:
        print(f"❌ Invalid deploy target: {deploy_target}")
        print(f"   Valid options: {', '.join(targets.keys())}")
        return

    pipeline, env, storage = targets[deploy_target]

    print("=" * 70)
    print("Multi-Cloud Customer Analytics Pipeline")
    print("=" * 70)
    print(f"\n🎯 Deployment Target: {deploy_target.upper()}")
    print(f"   Environment: {env.name}")
    print(f"   Storage: {storage}")
    print(f"   Provider Config: {type(env.provider.config).__name__}")

    print("\n" + "=" * 70)
    print("Multi-Cloud Architecture Benefits")
    print("=" * 70)
    print("\n✓ Write Once, Deploy Anywhere:")
    print("  - Same task logic for all clouds")
    print("  - Zero code duplication")
    print("  - Single source of truth")
    print("\n✓ Environment Isolation:")
    print("  - Test locally before cloud deployment")
    print("  - Independent dev/staging/prod environments")
    print("  - No cross-environment contamination")
    print("\n✓ Cloud Portability:")
    print("  - Switch clouds with environment variable")
    print("  - No vendor lock-in")
    print("  - Easy cloud migration")
    print("\n✓ Infrastructure as Code:")
    print("  - Generate Terraform for any cloud")
    print("  - Consistent infrastructure across clouds")
    print("  - Automated deployment")

    print("\n" + "=" * 70)
    print("How to Use")
    print("=" * 70)
    print("\n1. Test locally:")
    print("   export DEPLOY_TARGET=local")
    print("   python examples/multi_cloud_pipeline.py")
    print("\n2. Deploy to AWS:")
    print("   export DEPLOY_TARGET=aws")
    print("   glacier generate examples/multi_cloud_pipeline.py --output ./aws-infra")
    print("   # Apply Terraform")
    print("   python examples/multi_cloud_pipeline.py")
    print("\n3. Deploy to Azure:")
    print("   export DEPLOY_TARGET=azure")
    print("   glacier generate examples/multi_cloud_pipeline.py --output ./azure-infra")
    print("   # Apply Terraform")
    print("   python examples/multi_cloud_pipeline.py")
    print("\n4. Deploy to GCP:")
    print("   export DEPLOY_TARGET=gcp")
    print("   glacier generate examples/multi_cloud_pipeline.py --output ./gcp-infra")
    print("   # Apply Terraform")
    print("   python examples/multi_cloud_pipeline.py")

    print("\n" + "=" * 70)
    print("Environment Summary")
    print("=" * 70)
    print(f"\n📦 Local: {local_env.name}")
    print(f"   Config: {type(local_env.provider.config).__name__}")
    print(f"\n☁️  AWS: {aws_env.name}")
    print(f"   Config: {type(aws_env.provider.config).__name__}")
    print(f"   Region: {aws_env.provider.config.region}")
    print(f"\n☁️  Azure: {azure_env.name}")
    print(f"   Config: {type(azure_env.provider.config).__name__}")
    print(f"   Location: {azure_env.provider.config.location}")
    print(f"\n☁️  GCP: {gcp_env.name}")
    print(f"   Config: {type(gcp_env.provider.config).__name__}")
    print(f"   Region: {gcp_env.provider.config.region}")

    print("\n" + "=" * 70)

    # Uncomment to actually run the pipeline (requires data)
    # print(f"\n▶️  Running pipeline on {deploy_target}...")
    # result = pipeline.run(mode="local")
    # print("\n✅ Pipeline completed!")
    # print("\nResults:")
    # print(result.collect())


if __name__ == "__main__":
    main()
