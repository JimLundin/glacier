"""
S3-based pipeline demonstrating cloud infrastructure generation.

This pipeline:
1. Reads data from multiple S3 sources
2. Performs transformations
3. Can generate Terraform infrastructure automatically

Run with:
    # Execute locally (requires AWS credentials)
    glacier run examples/s3_pipeline.py

    # Generate infrastructure
    glacier generate examples/s3_pipeline.py --output ./infra

    # Analyze the pipeline
    glacier analyze examples/s3_pipeline.py
"""

from glacier import pipeline, task
from glacier.sources import S3Source
import polars as pl

# Define S3 data sources
sales_data = S3Source(
    bucket="my-company-data",
    path="sales/2024/sales.parquet",
    region="us-east-1",
    name="sales_source",
)

customer_data = S3Source(
    bucket="my-company-data",
    path="customers/customers.parquet",
    region="us-east-1",
    name="customer_source",
)


@task
def load_sales(source: S3Source) -> pl.LazyFrame:
    """Load sales data from S3."""
    return source.scan()


@task
def load_customers(source: S3Source) -> pl.LazyFrame:
    """Load customer data from S3."""
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
    name="s3_customer_analytics",
    description="Customer analytics pipeline using S3 data sources",
    config={
        "environment": "production",
        "region": "us-east-1",
    },
)
def s3_pipeline():
    """
    Main pipeline for customer analytics.

    This pipeline demonstrates:
    - Multiple S3 sources
    - Complex transformations
    - Joins between datasets
    - Infrastructure-from-code generation
    """
    # Load data from S3
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
    # 1. Execute it locally (with AWS credentials)
    # 2. Generate Terraform for S3 buckets and IAM policies
    # 3. Visualize the DAG

    print("S3 Pipeline Example")
    print("=" * 50)
    print("\nThis pipeline demonstrates:")
    print("- Multiple S3 data sources")
    print("- Complex task dependencies")
    print("- Infrastructure generation from code")
    print("\nTry running:")
    print("  glacier analyze examples/s3_pipeline.py")
    print("  glacier generate examples/s3_pipeline.py")
