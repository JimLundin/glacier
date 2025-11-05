"""
Simple example pipeline demonstrating Glacier's basic features.

This pipeline:
1. Loads data from a local parquet file
2. Filters out null values
3. Aggregates by category
4. Returns the result

This example demonstrates the environment-first pattern with:
- Provider with LocalConfig for local development
- GlacierEnv for environment isolation
- Environment-bound tasks
- Type-safe pipeline definition

Run with:
    python examples/simple_pipeline.py
    # OR
    glacier run examples/simple_pipeline.py
"""

from glacier import GlacierEnv, Provider
from glacier.config import LocalConfig
import polars as pl

# ============================================================================
# 1. SETUP: Create environment with local provider
# ============================================================================

# Create local provider configuration
local_config = LocalConfig(
    base_path="./examples/data",
    create_dirs=True,
)

# Create provider with config injection (single Provider class!)
provider = Provider(config=local_config)

# Create environment
env = GlacierEnv(provider=provider, name="local-dev")

# ============================================================================
# 2. TASKS: Define environment-bound tasks
# ============================================================================


@env.task()
def load_data(source) -> pl.LazyFrame:
    """Load data from the source."""
    return source.scan()


@env.task()
def clean_data(df: pl.LazyFrame) -> pl.LazyFrame:
    """Remove rows with null values in critical columns."""
    return df.filter(pl.col("value").is_not_null() & pl.col("category").is_not_null())


@env.task()
def aggregate_by_category(df: pl.LazyFrame) -> pl.LazyFrame:
    """Aggregate values by category."""
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


@env.pipeline(name="simple_etl")
def simple_pipeline():
    """
    Main pipeline function demonstrating Glacier basics.

    This orchestrates the tasks and defines the data flow using
    the environment-first pattern.
    """
    # Create data source using the provider
    data_source = env.provider.bucket(
        bucket="examples/data",
        path="sample.parquet",
    )

    # Data flow defines task dependencies
    raw_data = load_data(data_source)
    cleaned_data = clean_data(raw_data)
    result = aggregate_by_category(cleaned_data)

    return result


# ============================================================================
# 4. EXECUTION
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Simple ETL Pipeline - Glacier Environment-First Pattern")
    print("=" * 60)
    print(f"\nEnvironment: {env.name}")
    print(f"Provider: {env.provider}")
    print(f"Configuration: {local_config}")

    # Run the pipeline locally
    print("\nRunning pipeline...")
    result = simple_pipeline.run(mode="local")

    # Materialize and display the result
    print("\nPipeline Result:")
    print(result.collect())

    print("\n✓ Pipeline completed successfully!")
