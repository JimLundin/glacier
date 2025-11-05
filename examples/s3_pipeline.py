"""
AWS S3 pipeline demonstrating cloud-specific configuration.

This pipeline:
1. Reads data from S3 buckets with AWS-specific configurations
2. Performs complex multi-source transformations
3. Demonstrates joins between datasets
4. Can generate Terraform infrastructure automatically

This example demonstrates:
- Provider with AwsConfig (determines data lives in AWS S3)
- S3-specific configuration (storage classes, encryption, versioning)
- Resource registry for shared buckets
- Type-safe pipeline with explicit dependencies

IMPORTANT: GlacierEnv is an execution context (DI container), NOT a deployment
environment. Tags in AwsConfig can include deployment metadata (environment: prod),
but that's for AWS resource tagging, not the execution context.

Run with:
    # Set AWS credentials first
    export AWS_PROFILE=your-profile
    # OR
    export AWS_ACCESS_KEY_ID=...
    export AWS_SECRET_ACCESS_KEY=...

    # Execute pipeline
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
# 1. SETUP: Create execution context with AWS provider
# ============================================================================

# Provider configuration determines WHERE DATA LIVES
# AwsConfig = data in AWS S3
aws_config = AwsConfig(
    region="us-east-1",
    profile="default",  # Or use environment variables
    tags={
        # These tags are applied to AWS resources (for billing, organization, etc.)
        # They do NOT represent the execution environment
        "team": "data-analytics",
        "managed_by": "glacier",
        "project": "customer-analytics",
    },
)

# Create provider with config injection (single Provider class!)
provider = Provider(config=aws_config)

# Create execution context (DI container)
# The 'name' is just an identifier for this context
env = GlacierEnv(provider=provider, name="customer-analytics")

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
# 3. TASKS: Define tasks bound to execution context
# ============================================================================


@env.task()
def load_sales(source) -> pl.LazyFrame:
    """Load sales data from S3 bucket. Executes locally (default executor)."""
    return source.scan()


@env.task()
def load_customers(source) -> pl.LazyFrame:
    """Load customer data from S3 bucket. Executes locally (default executor)."""
    return source.scan()


@env.task()
def filter_recent_sales(df: pl.LazyFrame) -> pl.LazyFrame:
    """Filter sales from 2024. Executes locally."""
    return df.filter(pl.col("date") >= pl.datetime(2024, 1, 1))


@env.task()
def filter_active_customers(df: pl.LazyFrame) -> pl.LazyFrame:
    """Filter to only active customers. Executes locally."""
    return df.filter(pl.col("status") == "active")


@env.task()
def join_sales_with_customers(
    sales: pl.LazyFrame, customers: pl.LazyFrame
) -> pl.LazyFrame:
    """Join sales data with customer information. Executes locally."""
    return sales.join(customers, on="customer_id", how="inner")


@env.task()
def calculate_customer_metrics(df: pl.LazyFrame) -> pl.LazyFrame:
    """Calculate key metrics per customer. Executes locally."""
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
    """Save results to S3. Executes locally."""
    output = env.get("output_target")
    df.collect().write_parquet(output.get_uri())
    print(f"✓ Results saved to {output.get_uri()}")


# ============================================================================
# 4. PIPELINE: Wire everything together
# ============================================================================


@env.pipeline(name="customer_analytics")
def s3_pipeline():
    """
    Customer analytics pipeline using AWS S3.

    This pipeline demonstrates:
    - Data stored in AWS S3 (determined by provider config)
    - All tasks execute locally (default executor="local")
    - S3-specific configurations (storage classes, encryption, versioning)
    - Resource registry for centralized resource management
    - Complex multi-source data processing with joins
    - Infrastructure-from-code generation
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
    print(f"\nExecution Context: {env.name}")
    print(f"Data Location: AWS S3 ({aws_config.region})")
    print(f"Task Execution: Local (all tasks use executor='local')")
    print(f"Registered Resources: {env.list_resources()}")

    print("\n" + "=" * 70)
    print("Key Concepts")
    print("=" * 70)
    print("\n✓ Provider Config determines WHERE DATA LIVES:")
    print("  - AwsConfig → Data in AWS S3")
    print("  - S3-specific configs: storage classes, encryption, versioning")
    print("\n✓ Task Executor determines WHERE CODE RUNS:")
    print("  - Default executor='local' → Code runs in local Python process")
    print("  - Data is read from S3, processed locally, written back to S3")
    print("\n✓ GlacierEnv is a DI Container:")
    print("  - Binds provider, tasks, pipelines, and resources")
    print("  - NOT a deployment environment (dev/staging/prod)")
    print("  - Name is just an identifier")
    print("\n✓ Infrastructure as Code:")
    print("  - Generates Terraform automatically from pipeline definition")
    print("  - Includes S3 buckets, IAM policies, configurations")

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
