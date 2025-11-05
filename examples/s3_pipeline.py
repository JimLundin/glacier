"""
AWS S3 pipeline demonstrating cloud-specific configuration.

This pipeline:
1. Reads data from S3 buckets with AWS-specific configurations
2. Performs complex multi-source transformations
3. Demonstrates joins between datasets
4. Can generate Terraform infrastructure automatically

This example shows the environment-first pattern with:
- Provider with AwsConfig for cloud-specific settings
- S3-specific configuration (storage classes, encryption, etc.)
- Environment registry for shared resources
- Type-safe pipeline with explicit dependencies

Run with:
    # Set AWS credentials first
    export AWS_PROFILE=your-profile
    # OR
    export AWS_ACCESS_KEY_ID=...
    export AWS_SECRET_ACCESS_KEY=...

    # Execute locally (requires AWS credentials)
    python examples/s3_pipeline.py
    # OR
    glacier run examples/s3_pipeline.py

    # Generate Terraform infrastructure
    glacier generate examples/s3_pipeline.py --output ./infra

    # Analyze the pipeline DAG
    glacier analyze examples/s3_pipeline.py
"""

from glacier import GlacierEnv, Provider
from glacier.config import AwsConfig, S3Config
import polars as pl

# ============================================================================
# 1. SETUP: Create environment with AWS provider
# ============================================================================

# Create AWS provider configuration
aws_config = AwsConfig(
    region="us-east-1",
    profile="default",  # Or use environment variables
    tags={
        "environment": "production",
        "team": "data-analytics",
        "managed_by": "glacier",
    },
)

# Create provider with config injection (single Provider class!)
provider = Provider(config=aws_config)

# Create environment
env = GlacierEnv(provider=provider, name="production")

# ============================================================================
# 2. RESOURCES: Register shared S3 buckets with specific configs
# ============================================================================

# Sales data with intelligent tiering for cost optimization
env.register(
    "sales_source",
    env.provider.bucket(
        bucket="my-company-data",
        path="sales/2024/sales.parquet",
        config=S3Config(
            storage_class="INTELLIGENT_TIERING",
            encryption="AES256",
            versioning=True,
        ),
    ),
)

# Customer data with standard storage
env.register(
    "customer_source",
    env.provider.bucket(
        bucket="my-company-data",
        path="customers/customers.parquet",
        config=S3Config(
            storage_class="STANDARD",
            encryption="AES256",
            versioning=True,
        ),
    ),
)

# Output location for results
env.register(
    "output_target",
    env.provider.bucket(
        bucket="my-company-analytics",
        path="customer-metrics/latest.parquet",
        config=S3Config(
            storage_class="STANDARD",
            encryption="AES256",
        ),
    ),
)

# ============================================================================
# 3. TASKS: Define environment-bound tasks
# ============================================================================


@env.task()
def load_sales(source) -> pl.LazyFrame:
    """Load sales data from S3 bucket."""
    return source.scan()


@env.task()
def load_customers(source) -> pl.LazyFrame:
    """Load customer data from S3 bucket."""
    return source.scan()


@env.task()
def filter_recent_sales(df: pl.LazyFrame) -> pl.LazyFrame:
    """Filter sales from 2024."""
    return df.filter(pl.col("date") >= pl.datetime(2024, 1, 1))


@env.task()
def filter_active_customers(df: pl.LazyFrame) -> pl.LazyFrame:
    """Filter to only active customers."""
    return df.filter(pl.col("status") == "active")


@env.task()
def join_sales_with_customers(
    sales: pl.LazyFrame, customers: pl.LazyFrame
) -> pl.LazyFrame:
    """Join sales data with customer information."""
    return sales.join(customers, on="customer_id", how="inner")


@env.task()
def calculate_customer_metrics(df: pl.LazyFrame) -> pl.LazyFrame:
    """Calculate key metrics per customer."""
    return df.group_by("customer_id").agg(
        [
            pl.col("amount").sum().alias("total_revenue"),
            pl.col("amount").mean().alias("avg_order_value"),
            pl.count().alias("order_count"),
            pl.col("customer_name").first(),
        ]
    )


@env.task()
def save_results(df: pl.LazyFrame) -> None:
    """Save results to S3."""
    output = env.get("output_target")
    df.collect().write_parquet(output.get_uri())
    print(f"✓ Results saved to {output.get_uri()}")


# ============================================================================
# 4. PIPELINE: Wire everything together
# ============================================================================


@env.pipeline(name="customer_analytics")
def s3_pipeline():
    """
    Production customer analytics pipeline on AWS S3.

    This pipeline demonstrates:
    - AWS S3-specific configurations (storage classes, encryption, versioning)
    - Environment registry for resource management
    - Complex multi-source data processing
    - Joins between datasets
    - Infrastructure-from-code generation
    - Environment-first pattern for testability
    """
    # Retrieve registered resources
    sales_source = env.get("sales_source")
    customer_source = env.get("customer_source")

    # Data flow defines task dependencies
    sales = load_sales(sales_source)
    customers = load_customers(customer_source)

    # Filter data
    recent_sales = filter_recent_sales(sales)
    active_customers = filter_active_customers(customers)

    # Join and aggregate
    joined = join_sales_with_customers(recent_sales, active_customers)
    metrics = calculate_customer_metrics(joined)

    # Save results
    save_results(metrics)

    return metrics


# ============================================================================
# 5. EXECUTION
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("AWS S3 Customer Analytics Pipeline")
    print("=" * 70)
    print(f"\nEnvironment: {env.name}")
    print(f"Provider: AWS ({aws_config.region})")
    print(f"Registered resources: {env.list_resources()}")

    print("\n" + "=" * 70)
    print("Pipeline Features")
    print("=" * 70)
    print("\n✓ AWS S3-specific configurations:")
    print("  - Intelligent tiering for cost optimization")
    print("  - AES256 encryption for security")
    print("  - Versioning enabled for data lineage")
    print("\n✓ Environment-first pattern:")
    print("  - Explicit provider configuration")
    print("  - Resource registry for shared buckets")
    print("  - Type-safe task definitions")
    print("\n✓ Infrastructure as code:")
    print("  - Generates Terraform automatically")
    print("  - Includes IAM policies and bucket configs")

    print("\n" + "=" * 70)
    print("How to Run")
    print("=" * 70)
    print("\n1. Set AWS credentials:")
    print("   export AWS_PROFILE=your-profile")
    print("\n2. Execute pipeline:")
    print("   python examples/s3_pipeline.py")
    print("\n3. Generate infrastructure:")
    print("   glacier generate examples/s3_pipeline.py --output ./infra")
    print("\n4. Analyze pipeline:")
    print("   glacier analyze examples/s3_pipeline.py")

    print("\n" + "=" * 70)

    # Uncomment to actually run the pipeline (requires AWS credentials and data)
    # print("\nRunning pipeline...")
    # result = s3_pipeline.run(mode="local")
    # print("\nPipeline Result:")
    # print(result.collect())
