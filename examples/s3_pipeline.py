"""
Cloud-agnostic pipeline demonstrating Glacier's provider abstraction.

This pipeline:
1. Reads data from bucket sources (works with ANY cloud provider!)
2. Performs transformations
3. Can generate Terraform infrastructure automatically

The same code works with AWS S3, Azure Blob, GCS, or local filesystem
by simply changing the provider!

Run with:
    # Execute locally (requires cloud credentials)
    glacier run examples/s3_pipeline.py

    # Generate infrastructure
    glacier generate examples/s3_pipeline.py --output ./infra

    # Analyze the pipeline
    glacier analyze examples/s3_pipeline.py
"""

from glacier import pipeline, task
from glacier.providers import AWSProvider
from glacier.resources import Bucket
import polars as pl

# Create a provider - swap this line to change cloud providers!
# provider = AWSProvider(region="us-east-1")
# provider = AzureProvider(resource_group="my-rg", location="eastus")
# provider = GCPProvider(project_id="my-project", region="us-central1")
# provider = LocalProvider(base_path="./data")
provider = AWSProvider(region="us-east-1")

# Define cloud-agnostic bucket sources
# These work with ANY provider - no cloud-specific code!
sales_data = provider.bucket(
    bucket="my-company-data",
    path="sales/2024/sales.parquet",
    name="sales_source",
)

customer_data = provider.bucket(
    bucket="my-company-data",
    path="customers/customers.parquet",
    name="customer_source",
)


@task
def load_sales(source: Bucket) -> pl.LazyFrame:
    """Load sales data from bucket (cloud-agnostic!)."""
    return source.scan()


@task
def load_customers(source: Bucket) -> pl.LazyFrame:
    """Load customer data from bucket (cloud-agnostic!)."""
    return source.scan()


@task(depends_on=["load_sales"])
def filter_recent_sales(df: pl.LazyFrame) -> pl.LazyFrame:
    """Filter sales from the last 30 days."""
    return df.filter(pl.col("date") >= pl.datetime(2024, 1, 1))


@task(depends_on=["load_customers"])
def filter_active_customers(df: pl.LazyFrame) -> pl.LazyFrame:
    """Filter to only active customers."""
    return df.filter(pl.col("status") == "active")


@task(depends_on=["filter_recent_sales", "filter_active_customers"])
def join_sales_with_customers(sales: pl.LazyFrame, customers: pl.LazyFrame) -> pl.LazyFrame:
    """Join sales data with customer information."""
    return sales.join(customers, on="customer_id", how="inner")


@task(depends_on=["join_sales_with_customers"])
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


@pipeline(
    name="cloud_agnostic_customer_analytics",
    description="Cloud-agnostic customer analytics pipeline",
    config={
        "environment": "production",
        "region": "us-east-1",
    },
)
def s3_pipeline():
    """
    Main pipeline for customer analytics.

    This pipeline demonstrates:
    - Cloud-agnostic bucket sources (works with ANY provider!)
    - Complex transformations
    - Joins between datasets
    - Infrastructure-from-code generation
    - Provider abstraction pattern
    """
    # Load data from buckets (cloud-agnostic!)
    sales = load_sales(sales_data)
    customers = load_customers(customer_data)

    # Filter data
    recent_sales = filter_recent_sales(sales)
    active_customers = filter_active_customers(customers)

    # Join and aggregate
    joined = join_sales_with_customers(recent_sales, active_customers)
    metrics = calculate_customer_metrics(joined)

    return metrics


if __name__ == "__main__":
    # When you run this pipeline, Glacier can:
    # 1. Execute it locally (with cloud credentials)
    # 2. Generate Terraform for buckets and IAM policies
    # 3. Visualize the DAG
    # 4. Work with ANY cloud provider by changing one line!

    print("Cloud-Agnostic Pipeline Example")
    print("=" * 50)
    print("\nThis pipeline demonstrates:")
    print("- Cloud-agnostic bucket sources")
    print("- Provider abstraction (AWS, Azure, GCP, Local)")
    print("- Complex task dependencies")
    print("- Infrastructure generation from code")
    print("\nTo switch clouds, just change the provider:")
    print("  provider = AWSProvider(region='us-east-1')")
    print("  provider = AzureProvider(resource_group='my-rg')")
    print("  provider = GCPProvider(project_id='my-project')")
    print("\nTry running:")
    print("  glacier analyze examples/s3_pipeline.py")
    print("  glacier generate examples/s3_pipeline.py")
