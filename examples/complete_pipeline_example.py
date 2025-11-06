"""
Complete Data Pipeline Example for Glacier

This example demonstrates how to build a complete data pipeline using Glacier's
chainable storage pattern. It includes:
- Provider and execution resource setup
- Storage resource definitions
- Task definitions with decorators
- Single-source pipeline composition
- Multi-source pipeline composition (joins)
- Pipeline execution
"""

import polars as pl
from glacier import Provider
from glacier.config import AwsConfig, LambdaConfig, SparkConfig

# =============================================================================
# 1. SETUP: Provider and Execution Resources
# =============================================================================

# Create provider with cloud configuration
provider = Provider(config=AwsConfig(
    region="us-east-1",
    account_id="123456789012"
))

# Define execution resources where tasks will run
local_exec = provider.local()  # Local Python execution

lambda_exec = provider.serverless(config=LambdaConfig(
    memory=1024,
    timeout=300,
    runtime="python3.11"
))

spark_exec = provider.spark(config=SparkConfig(
    cluster_size="medium",
    workers=3,
    instance_type="m5.xlarge"
))

# =============================================================================
# 2. STORAGE RESOURCES: Define all buckets used in the pipeline
# =============================================================================

# Raw data sources
raw_sales = provider.bucket(
    bucket="company-data-lake",
    path="raw/sales/2024/sales.parquet"
)

raw_customers = provider.bucket(
    bucket="company-data-lake",
    path="raw/customers/customers.parquet"
)

raw_products = provider.bucket(
    bucket="company-data-lake",
    path="raw/products/products.parquet"
)

# Intermediate storage (for checkpointing and multi-stage processing)
cleaned_sales = provider.bucket(
    bucket="company-data-lake",
    path="processed/cleaned_sales.parquet"
)

sales_with_customers = provider.bucket(
    bucket="company-data-lake",
    path="processed/sales_with_customers.parquet"
)

enriched_sales = provider.bucket(
    bucket="company-data-lake",
    path="processed/enriched_sales.parquet"
)

# Final outputs
regional_summary = provider.bucket(
    bucket="company-data-lake",
    path="output/regional_summary.parquet"
)

product_performance = provider.bucket(
    bucket="company-data-lake",
    path="output/product_performance.parquet"
)

# =============================================================================
# 3. TASK DEFINITIONS: Define all transformations using decorators
# =============================================================================

# --- Data Cleaning Tasks (Local Execution) ---

@local_exec.task()
def clean_sales_data(df: pl.LazyFrame) -> pl.LazyFrame:
    """
    Clean raw sales data:
    - Remove null sales amounts
    - Filter out negative quantities
    - Standardize date formats
    """
    return (
        df
        .filter(pl.col("sale_amount").is_not_null())
        .filter(pl.col("quantity") > 0)
        .with_columns([
            pl.col("sale_date").str.to_date("%Y-%m-%d").alias("sale_date")
        ])
    )


@local_exec.task()
def validate_customers(df: pl.LazyFrame) -> pl.LazyFrame:
    """
    Validate customer data:
    - Remove duplicates
    - Filter out invalid customer IDs
    """
    return (
        df
        .filter(pl.col("customer_id").is_not_null())
        .unique(subset=["customer_id"], keep="first")
    )


# --- Join Tasks (Spark Execution for large datasets) ---

@spark_exec.task()
def join_sales_with_customers(
    sales_df: pl.LazyFrame,
    customers_df: pl.LazyFrame
) -> pl.LazyFrame:
    """
    Join cleaned sales data with customer information.
    Uses Spark for distributed processing of large datasets.
    """
    return sales_df.join(
        customers_df,
        on="customer_id",
        how="left"
    ).select([
        "sale_id",
        "sale_date",
        "customer_id",
        "customer_name",
        "customer_region",
        "product_id",
        "quantity",
        "sale_amount"
    ])


@spark_exec.task()
def enrich_with_product_info(
    sales_df: pl.LazyFrame,
    products_df: pl.LazyFrame
) -> pl.LazyFrame:
    """
    Add product information to sales data.
    """
    return sales_df.join(
        products_df,
        on="product_id",
        how="left"
    ).select([
        "sale_id",
        "sale_date",
        "customer_id",
        "customer_name",
        "customer_region",
        "product_id",
        "product_name",
        "product_category",
        "quantity",
        "sale_amount",
        "unit_price"
    ])


# --- Aggregation Tasks (Lambda for serverless scaling) ---

@lambda_exec.task()
def calculate_regional_summary(df: pl.LazyFrame) -> pl.LazyFrame:
    """
    Calculate regional sales summary:
    - Total sales by region
    - Average order value
    - Customer count
    """
    return (
        df
        .group_by("customer_region")
        .agg([
            pl.col("sale_amount").sum().alias("total_sales"),
            pl.col("sale_amount").mean().alias("avg_order_value"),
            pl.col("customer_id").n_unique().alias("unique_customers"),
            pl.col("sale_id").count().alias("order_count")
        ])
        .sort("total_sales", descending=True)
    )


@lambda_exec.task()
def calculate_product_performance(df: pl.LazyFrame) -> pl.LazyFrame:
    """
    Calculate product performance metrics:
    - Total revenue by product
    - Units sold
    - Average sale price
    """
    return (
        df
        .group_by(["product_id", "product_name", "product_category"])
        .agg([
            pl.col("sale_amount").sum().alias("total_revenue"),
            pl.col("quantity").sum().alias("units_sold"),
            (pl.col("sale_amount") / pl.col("quantity")).mean().alias("avg_sale_price")
        ])
        .sort("total_revenue", descending=True)
        .head(100)  # Top 100 products
    )


# =============================================================================
# 4. PIPELINE COMPOSITION: Build pipelines using chainable pattern
# =============================================================================

# --- Pipeline 1: Single-source data cleaning pipeline ---
# This pipeline cleans raw sales data using simple chaining

cleaning_pipeline = (
    raw_sales
    .transform(clean_sales_data)
    .to(cleaned_sales)
    .with_name("sales_cleaning_pipeline", "Clean and validate raw sales data")
)

# --- Pipeline 2: Multi-source join pipeline ---
# This pipeline joins sales with customers, then enriches with products
# Uses Pipeline() for multi-source, returns Bucket for continued chaining

# First, prepare cleaned customer data (separate mini-pipeline)
cleaned_customers = (
    raw_customers
    .transform(validate_customers)
    .to(provider.bucket("company-data-lake", "processed/cleaned_customers.parquet"))
)

# Main enrichment pipeline: Join sales + customers, then join with products
from glacier import Pipeline

enrichment_pipeline = (
    Pipeline(sales_df=cleaned_sales, customers_df=cleaned_customers)
    .transform(join_sales_with_customers)
    .to(sales_with_customers)  # Returns Bucket - can continue chaining!
)

# Continue from the joined data to add product information
full_enrichment_pipeline = (
    Pipeline(sales_df=sales_with_customers, products_df=raw_products)
    .transform(enrich_with_product_info)
    .to(enriched_sales)
    .with_name("sales_enrichment_pipeline", "Join sales with customer and product data")
)

# --- Pipeline 3: Analytics pipelines (single-source from enriched data) ---

regional_analytics_pipeline = (
    enriched_sales
    .transform(calculate_regional_summary)
    .to(regional_summary)
    .with_name("regional_analytics", "Calculate regional sales summaries")
)

product_analytics_pipeline = (
    enriched_sales
    .transform(calculate_product_performance)
    .to(product_performance)
    .with_name("product_analytics", "Calculate product performance metrics")
)

# --- Master Pipeline: Complete end-to-end pipeline ---
# This shows how to build the entire pipeline as one definition
# (though in practice you might run these separately)

master_pipeline = (
    raw_sales
    .transform(clean_sales_data)
    .to(cleaned_sales)
    .with_name("master_etl_pipeline", "Complete sales analytics ETL pipeline")
)

# =============================================================================
# 5. PIPELINE EXECUTION: Run pipelines in different modes
# =============================================================================

def run_all_pipelines():
    """Execute all pipelines in sequence."""

    print("=" * 80)
    print("EXECUTING GLACIER PIPELINES")
    print("=" * 80)

    # Run data cleaning
    print("\n[1/5] Running data cleaning pipeline...")
    cleaning_pipeline.run(mode="local")
    print("✓ Sales data cleaned")

    # Clean customers (prerequisite for enrichment)
    print("\n[2/5] Running customer validation...")
    cleaned_customers.run(mode="local")
    print("✓ Customer data validated")

    # Run enrichment (joins)
    print("\n[3/5] Running sales enrichment pipeline...")
    full_enrichment_pipeline.run(mode="cloud")
    print("✓ Sales data enriched with customer and product info")

    # Run analytics
    print("\n[4/5] Running regional analytics...")
    regional_analytics_pipeline.run(mode="cloud")
    print("✓ Regional summaries calculated")

    print("\n[5/5] Running product analytics...")
    product_analytics_pipeline.run(mode="cloud")
    print("✓ Product performance metrics calculated")

    print("\n" + "=" * 80)
    print("ALL PIPELINES COMPLETED SUCCESSFULLY")
    print("=" * 80)


def generate_infrastructure():
    """Generate infrastructure code (Terraform) for all pipelines."""

    print("Generating infrastructure code...")

    pipelines = [
        ("cleaning", cleaning_pipeline),
        ("enrichment", full_enrichment_pipeline),
        ("regional_analytics", regional_analytics_pipeline),
        ("product_analytics", product_analytics_pipeline)
    ]

    for name, pipeline in pipelines:
        print(f"  - Generating Terraform for {name}...")
        pipeline.run(mode="generate", output_dir=f"./terraform/{name}")

    print("✓ Infrastructure code generated")


def visualize_pipelines():
    """Generate visualization diagrams for all pipelines."""

    print("\nPipeline Visualizations:")
    print("=" * 80)

    print("\n[Cleaning Pipeline]")
    print(cleaning_pipeline.visualize())

    print("\n[Enrichment Pipeline]")
    print(full_enrichment_pipeline.visualize())

    print("\n[Regional Analytics Pipeline]")
    print(regional_analytics_pipeline.visualize())

    print("\n[Product Analytics Pipeline]")
    print(product_analytics_pipeline.visualize())


def analyze_pipeline_costs():
    """Analyze estimated costs for running pipelines."""

    print("\nPipeline Cost Analysis:")
    print("=" * 80)

    pipelines = [
        ("Cleaning", cleaning_pipeline),
        ("Enrichment", full_enrichment_pipeline),
        ("Regional Analytics", regional_analytics_pipeline),
        ("Product Analytics", product_analytics_pipeline)
    ]

    for name, pipeline in pipelines:
        analysis = pipeline.run(mode="analyze")
        print(f"\n{name}:")
        print(f"  - Estimated cost: ${analysis.estimated_cost():.2f}")
        print(f"  - Estimated duration: {analysis.estimated_duration()}s")
        print(f"  - Resource usage: {analysis.resource_summary()}")


# =============================================================================
# 6. MAIN EXECUTION
# =============================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python complete_pipeline_example.py [run|generate|visualize|analyze]")
        sys.exit(1)

    command = sys.argv[1]

    if command == "run":
        run_all_pipelines()
    elif command == "generate":
        generate_infrastructure()
    elif command == "visualize":
        visualize_pipelines()
    elif command == "analyze":
        analyze_pipeline_costs()
    else:
        print(f"Unknown command: {command}")
        print("Available commands: run, generate, visualize, analyze")
        sys.exit(1)
