"""
Complete Pipeline Examples - Corrected Pattern

This file demonstrates the correct pattern for defining data pipelines in Glacier.

Key principles:
1. Always start with Pipeline(name=...) factory
2. Use .source() for single source, .sources() for multi-source
3. Chain .transform().to() for each step
4. NO execution in this script - only definition
5. Pipeline objects are captured for code generation
"""

import polars as pl
from glacier import Provider, Pipeline
from glacier.config import AwsConfig, LambdaConfig, SparkConfig

# =============================================================================
# SETUP: Provider and Execution Resources
# =============================================================================

provider = Provider(config=AwsConfig(
    region="us-east-1",
    account_id="123456789012"
))

# Define execution resources where tasks will run
local_exec = provider.local()

lambda_exec = provider.serverless(config=LambdaConfig(
    memory=1024,
    timeout=300
))

spark_exec = provider.spark(config=SparkConfig(
    cluster_size="medium",
    workers=3
))

# =============================================================================
# STORAGE RESOURCES: Define all buckets
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

# Intermediate storage
cleaned_sales = provider.bucket(
    bucket="company-data-lake",
    path="processed/cleaned_sales.parquet"
)

cleaned_customers = provider.bucket(
    bucket="company-data-lake",
    path="processed/cleaned_customers.parquet"
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
# TASK DEFINITIONS
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
def clean_customers(df: pl.LazyFrame) -> pl.LazyFrame:
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


# --- Join Tasks (Spark Execution) ---

@spark_exec.task()
def join_sales_with_customers(
    sales_df: pl.LazyFrame,
    customers_df: pl.LazyFrame
) -> pl.LazyFrame:
    """
    Join cleaned sales data with customer information.

    Note: Parameter names (sales_df, customers_df) must match
    the kwargs used in .sources(sales_df=..., customers_df=...)
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
    """Add product information to sales data."""
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
        "sale_amount"
    ])


# --- Aggregation Tasks (Lambda) ---

@lambda_exec.task()
def calculate_regional_summary(df: pl.LazyFrame) -> pl.LazyFrame:
    """Calculate regional sales summary."""
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
    """Calculate product performance metrics."""
    return (
        df
        .group_by(["product_id", "product_name", "product_category"])
        .agg([
            pl.col("sale_amount").sum().alias("total_revenue"),
            pl.col("quantity").sum().alias("units_sold"),
            (pl.col("sale_amount") / pl.col("quantity")).mean().alias("avg_sale_price")
        ])
        .sort("total_revenue", descending=True)
        .head(100)
    )


# =============================================================================
# PIPELINE DEFINITIONS
# =============================================================================

# --- Example 1: Single-Source Data Cleaning Pipeline ---

sales_cleaning_pipeline = (
    Pipeline(name="sales_cleaning_pipeline")
    .source(raw_sales)
    .transform(clean_sales_data)
    .to(cleaned_sales)
)

customers_cleaning_pipeline = (
    Pipeline(name="customers_cleaning_pipeline")
    .source(raw_customers)
    .transform(clean_customers)
    .to(cleaned_customers)
)


# --- Example 2: Multi-Source Join Pipeline ---

# First join: sales + customers
sales_enrichment_step1 = (
    Pipeline(name="sales_customer_join")
    .sources(sales_df=cleaned_sales, customers_df=cleaned_customers)
    .transform(join_sales_with_customers)
    .to(sales_with_customers)
)

# Second join: add products
sales_enrichment_step2 = (
    Pipeline(name="sales_product_enrichment")
    .sources(sales_df=sales_with_customers, products_df=raw_products)
    .transform(enrich_with_product_info)
    .to(enriched_sales)
)


# --- Example 3: Analytics Pipelines (Single-Source) ---

regional_analytics_pipeline = (
    Pipeline(name="regional_analytics")
    .source(enriched_sales)
    .transform(calculate_regional_summary)
    .to(regional_summary)
)

product_analytics_pipeline = (
    Pipeline(name="product_analytics")
    .source(enriched_sales)
    .transform(calculate_product_performance)
    .to(product_performance)
)


# --- Example 4: Multi-Stage Single-Source Pipeline ---

@local_exec.task()
def extract_high_value(df: pl.LazyFrame) -> pl.LazyFrame:
    """Extract high-value transactions."""
    return df.filter(pl.col("sale_amount") > 1000)


@lambda_exec.task()
def calculate_customer_segments(df: pl.LazyFrame) -> pl.LazyFrame:
    """Segment customers by purchase behavior."""
    return (
        df
        .group_by("customer_id")
        .agg([
            pl.col("sale_amount").sum().alias("total_spent"),
            pl.col("sale_id").count().alias("purchase_count")
        ])
        .with_columns([
            pl.when(pl.col("total_spent") > 10000)
            .then(pl.lit("premium"))
            .when(pl.col("total_spent") > 5000)
            .then(pl.lit("gold"))
            .otherwise(pl.lit("standard"))
            .alias("segment")
        ])
    )


high_value_temp = provider.bucket("company-data-lake", "temp/high_value.parquet")
customer_segments = provider.bucket("company-data-lake", "output/customer_segments.parquet")

customer_segmentation_pipeline = (
    Pipeline(name="customer_segmentation")
    .source(enriched_sales)
    .transform(extract_high_value)
    .to(high_value_temp)
    .transform(calculate_customer_segments)
    .to(customer_segments)
)


# =============================================================================
# PIPELINE DEFINITION COMPLETE
# =============================================================================

# All pipeline objects defined above will be captured by the code generator.
# The code generator will:
# 1. Execute this file to instantiate Pipeline objects
# 2. Find all Pipeline instances (sales_cleaning_pipeline, etc.)
# 3. Generate infrastructure code (Terraform, CloudFormation, etc.)
# 4. Deploy pipelines to cloud infrastructure

# NO EXECUTION HAPPENS HERE
# This script only defines the pipeline structure
# Actual execution happens in deployed infrastructure (Lambda, Airflow, etc.)

# To generate infrastructure:
# $ glacier generate pipelines.py --output ./terraform

# The following Pipeline objects will be found:
# - sales_cleaning_pipeline
# - customers_cleaning_pipeline
# - sales_enrichment_step1
# - sales_enrichment_step2
# - regional_analytics_pipeline
# - product_analytics_pipeline
# - customer_segmentation_pipeline
