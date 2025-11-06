"""
Multi-Source Join Example for Glacier

Demonstrates how to build pipelines with multiple data sources (joins).
Shows how Pipeline() handles multi-source transforms and returns chainable Buckets.
"""

import polars as pl
from glacier import Provider, Pipeline
from glacier.config import AwsConfig, SparkConfig

# =============================================================================
# 1. SETUP
# =============================================================================

provider = Provider(config=AwsConfig(region="us-east-1"))

# Use Spark for distributed join processing
spark_exec = provider.spark(config=SparkConfig(
    cluster_size="medium",
    workers=3
))

# Use local for simple aggregations
local_exec = provider.local()

# =============================================================================
# 2. DEFINE STORAGE
# =============================================================================

# Source data
orders = provider.bucket(
    bucket="company-data",
    path="raw/orders.parquet"
)

customers = provider.bucket(
    bucket="company-data",
    path="raw/customers.parquet"
)

products = provider.bucket(
    bucket="company-data",
    path="raw/products.parquet"
)

# Intermediate storage
orders_with_customers = provider.bucket(
    bucket="company-data",
    path="processed/orders_with_customers.parquet"
)

fully_enriched_orders = provider.bucket(
    bucket="company-data",
    path="processed/fully_enriched_orders.parquet"
)

# Final output
customer_lifetime_value = provider.bucket(
    bucket="company-data",
    path="output/customer_ltv.parquet"
)

# =============================================================================
# 3. DEFINE TASKS
# =============================================================================

@spark_exec.task()
def join_orders_customers(
    orders_df: pl.LazyFrame,
    customers_df: pl.LazyFrame
) -> pl.LazyFrame:
    """
    Join orders with customer data.

    Note: Parameter names (orders_df, customers_df) must match the kwargs
    used when creating Pipeline(orders_df=..., customers_df=...)
    """
    return orders_df.join(
        customers_df,
        on="customer_id",
        how="left"
    ).select([
        "order_id",
        "order_date",
        "customer_id",
        "customer_name",
        "customer_tier",
        "product_id",
        "quantity",
        "order_amount"
    ])


@spark_exec.task()
def enrich_with_products(
    orders_df: pl.LazyFrame,
    products_df: pl.LazyFrame
) -> pl.LazyFrame:
    """
    Add product information to orders.

    Note: This is another multi-source transform, but we can chain it
    after the first join because Pipeline.to() returns a Bucket!
    """
    return orders_df.join(
        products_df,
        on="product_id",
        how="left"
    ).select([
        "order_id",
        "order_date",
        "customer_id",
        "customer_name",
        "customer_tier",
        "product_id",
        "product_name",
        "product_category",
        "quantity",
        "order_amount",
        "unit_price"
    ])


@local_exec.task()
def calculate_customer_ltv(df: pl.LazyFrame) -> pl.LazyFrame:
    """
    Calculate customer lifetime value.

    This is a single-source transform that can chain directly from
    the multi-source result!
    """
    return (
        df
        .group_by(["customer_id", "customer_name", "customer_tier"])
        .agg([
            pl.col("order_amount").sum().alias("total_spent"),
            pl.col("order_id").n_unique().alias("order_count"),
            pl.col("order_amount").mean().alias("avg_order_value"),
            pl.col("order_date").min().alias("first_order_date"),
            pl.col("order_date").max().alias("last_order_date")
        ])
        .with_columns([
            (pl.col("total_spent") / pl.col("order_count")).alias("value_per_order")
        ])
        .sort("total_spent", descending=True)
    )

# =============================================================================
# 4. BUILD PIPELINE (multi-source with chaining)
# =============================================================================

# PATTERN 1: Multi-source → single result
# Use Pipeline() for joins, it returns a Bucket
step1_pipeline = (
    Pipeline(orders_df=orders, customers_df=customers)  # Multi-source
    .transform(join_orders_customers)                    # Join transform
    .to(orders_with_customers)                          # Returns Bucket!
    .with_name("orders_customer_join", "Join orders with customer data")
)

# PATTERN 2: Chaining multi-source operations
# The result from step1 is a Bucket, so we can use it in another Pipeline()
step2_pipeline = (
    Pipeline(orders_df=orders_with_customers, products_df=products)  # Another multi-source
    .transform(enrich_with_products)                                 # Another join
    .to(fully_enriched_orders)                                       # Returns Bucket!
    .with_name("product_enrichment", "Add product information to orders")
)

# PATTERN 3: Single-source chaining after multi-source
# Now we have a single bucket (fully_enriched_orders), so chain directly!
final_pipeline = (
    fully_enriched_orders                # Single bucket
    .transform(calculate_customer_ltv)   # Single-source transform
    .to(customer_lifetime_value)         # Final output
    .with_name("customer_ltv_calculation", "Calculate customer lifetime value")
)

# PATTERN 4: Complete end-to-end pipeline definition
# You can also define the entire pipeline as one expression:
complete_pipeline = (
    # First join: orders + customers
    Pipeline(orders_df=orders, customers_df=customers)
    .transform(join_orders_customers)
    .to(orders_with_customers)

    # This is now a Bucket, but we need another join, so can't chain .transform()
    # Instead, we'll build separate pipelines and run them in sequence
)

# For the complete flow, we need to build it in stages:
def build_complete_pipeline():
    """
    Build and return all pipeline stages.

    Since we have multiple multi-source operations, we build them as separate
    pipeline definitions that depend on each other.
    """

    # Stage 1: Join orders with customers
    stage1 = (
        Pipeline(orders_df=orders, customers_df=customers)
        .transform(join_orders_customers)
        .to(orders_with_customers)
        .with_name("stage1_customer_join")
    )

    # Stage 2: Add product information
    stage2 = (
        Pipeline(orders_df=orders_with_customers, products_df=products)
        .transform(enrich_with_products)
        .to(fully_enriched_orders)
        .with_name("stage2_product_enrichment")
    )

    # Stage 3: Calculate final metrics (single-source, can chain!)
    stage3 = (
        fully_enriched_orders
        .transform(calculate_customer_ltv)
        .to(customer_lifetime_value)
        .with_name("stage3_ltv_calculation")
    )

    return [stage1, stage2, stage3]

# =============================================================================
# 5. EXECUTE PIPELINE
# =============================================================================

def run_pipeline():
    """Execute the complete multi-stage pipeline."""

    print("=" * 80)
    print("MULTI-SOURCE JOIN PIPELINE")
    print("=" * 80)

    # Get all pipeline stages
    stages = build_complete_pipeline()

    # Execute each stage in order
    for i, stage in enumerate(stages, 1):
        pipeline_name = stage._metadata.get("name", f"stage{i}")
        print(f"\n[Stage {i}/3] Running {pipeline_name}...")
        stage.run(mode="cloud")
        print(f"✓ {pipeline_name} completed")

    print("\n" + "=" * 80)
    print("PIPELINE COMPLETED SUCCESSFULLY")
    print("=" * 80)
    print(f"\nFinal output written to: {customer_lifetime_value.get_uri()}")


def visualize_pipeline():
    """Show the pipeline structure."""

    print("\nPipeline Visualization:")
    print("=" * 80)

    stages = build_complete_pipeline()

    for i, stage in enumerate(stages, 1):
        name = stage._metadata.get("name", f"stage{i}")
        print(f"\n[Stage {i}] {name}:")
        print(stage.visualize())


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python multi_source_join_example.py [run|visualize]")
        sys.exit(1)

    command = sys.argv[1]

    if command == "run":
        run_pipeline()
    elif command == "visualize":
        visualize_pipeline()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
