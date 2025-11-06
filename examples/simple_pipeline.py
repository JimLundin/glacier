"""
Simple pipeline demonstrating Glacier's execution resource pattern.

This pipeline:
1. Loads data from local storage
2. Filters out null values
3. Aggregates by category
4. Returns the result

CORRECT PATTERN:
- Provider creates BOTH storage AND execution resources
- Tasks bound to execution resources: @executor.task()
- Storage: provider.bucket()
- Execution: provider.local(), provider.serverless(), provider.vm(), provider.cluster()

Run with:
    python examples/simple_pipeline.py
"""

from glacier import Provider, pipeline
from glacier.config import LocalConfig
import polars as pl

# ============================================================================
# 1. SETUP: Create provider and resources
# ============================================================================

# Provider configuration determines WHERE DATA LIVES
provider = Provider(config=LocalConfig(base_path="./examples/data"))

# Create EXECUTION resource (where code runs)
# This is a first-class resource, just like storage
local_exec = provider.local()

# Create STORAGE resource (where data lives)
data_source = provider.bucket(bucket="examples/data", path="sample.parquet")

# ============================================================================
# 2. TASKS: Bind tasks to execution resources
# ============================================================================


@local_exec.task()
def load_data(source) -> pl.LazyFrame:
    """Load data from source. Executes on local_exec."""
    return source.scan()


@local_exec.task()
def clean_data(df: pl.LazyFrame) -> pl.LazyFrame:
    """Remove null values. Executes on local_exec."""
    return df.filter(pl.col("value").is_not_null() & pl.col("category").is_not_null())


@local_exec.task()
def aggregate_by_category(df: pl.LazyFrame) -> pl.LazyFrame:
    """Aggregate by category. Executes on local_exec."""
    return df.group_by("category").agg(
        [
            pl.col("value").sum().alias("total_value"),
            pl.col("value").mean().alias("avg_value"),
            pl.count().alias("count"),
        ]
    )


# ============================================================================
# 3. PIPELINE: Wire tasks together
# ============================================================================


@pipeline(name="simple_etl")
def simple_pipeline():
    """
    Simple ETL pipeline.

    All tasks execute on local_exec (local Python process).
    Data is read from local filesystem (determined by provider config).
    """
    raw_data = load_data(data_source)
    cleaned_data = clean_data(raw_data)
    result = aggregate_by_category(cleaned_data)
    return result


# ============================================================================
# 4. EXECUTION
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Simple ETL Pipeline")
    print("=" * 60)
    print(f"\nData Location: Local filesystem (./examples/data)")
    print(f"Code Execution: Local Python process")
    print(f"Provider: {provider}")

    print("\n" + "=" * 60)
    print("Glacier Resource Pattern")
    print("=" * 60)
    print("\n✓ Provider creates resources:")
    print("  - Storage: provider.bucket() → where data lives")
    print("  - Execution: provider.local() → where code runs")
    print("\n✓ Both are first-class resources:")
    print("  - Storage passed to tasks as parameters")
    print("  - Execution binds tasks via @executor.task()")
    print("\n✓ Cloud-agnostic:")
    print("  - Same pattern for all clouds")
    print("  - Config determines actual backend")

    # Run the pipeline
    print("\n" + "=" * 60)
    print("Running pipeline...")
    print("=" * 60)
    result = simple_pipeline.run(mode="local")

    print("\nPipeline Result:")
    print(result.collect())
    print("\n✓ Pipeline completed successfully!")
