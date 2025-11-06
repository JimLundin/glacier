"""
Simple Pipeline Example for Glacier

A minimal example showing the basic pattern for building data pipelines.
"""

import polars as pl
from glacier import Provider
from glacier.config import AwsConfig

# =============================================================================
# 1. SETUP
# =============================================================================

# Create provider
provider = Provider(config=AwsConfig(region="us-east-1"))

# Create execution resource
local_exec = provider.local()

# =============================================================================
# 2. DEFINE STORAGE
# =============================================================================

raw_data = provider.bucket(
    bucket="my-data-bucket",
    path="raw/data.parquet"
)

cleaned_data = provider.bucket(
    bucket="my-data-bucket",
    path="processed/cleaned.parquet"
)

output_data = provider.bucket(
    bucket="my-data-bucket",
    path="output/result.parquet"
)

# =============================================================================
# 3. DEFINE TASKS
# =============================================================================

@local_exec.task()
def clean_data(df: pl.LazyFrame) -> pl.LazyFrame:
    """Remove null values and filter data."""
    return (
        df
        .filter(pl.col("value").is_not_null())
        .filter(pl.col("value") > 0)
    )


@local_exec.task()
def calculate_metrics(df: pl.LazyFrame) -> pl.LazyFrame:
    """Calculate summary metrics."""
    return (
        df
        .group_by("category")
        .agg([
            pl.col("value").sum().alias("total"),
            pl.col("value").mean().alias("average"),
            pl.col("value").count().alias("count")
        ])
    )

# =============================================================================
# 4. BUILD PIPELINE (using chainable storage pattern)
# =============================================================================

# Chain buckets directly - clean and readable!
my_pipeline = (
    raw_data                        # Start with raw data bucket
    .transform(clean_data)          # Apply cleaning transformation
    .to(cleaned_data)               # Write to intermediate storage
    .transform(calculate_metrics)   # Apply metrics calculation
    .to(output_data)                # Write to final output
    .with_name("simple_etl")        # Add pipeline name for identification
)

# =============================================================================
# 5. EXECUTE PIPELINE
# =============================================================================

if __name__ == "__main__":
    # Run locally
    print("Running pipeline...")
    my_pipeline.run(mode="local")
    print("✓ Pipeline completed successfully!")

    # Or generate infrastructure code
    # my_pipeline.run(mode="generate", output_dir="./terraform")

    # Or visualize the pipeline
    # print(my_pipeline.visualize())
