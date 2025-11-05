"""
Simple example pipeline demonstrating Glacier's basic features.

This pipeline:
1. Loads data from a local parquet file
2. Filters out null values
3. Aggregates by category
4. Returns the result

Run with:
    glacier run examples/simple_pipeline.py
"""

from glacier import pipeline, task
from glacier.sources import LocalSource
import polars as pl

# Define a local data source
data_source = LocalSource(
    bucket="./examples/data",
    path="sample.parquet",
    format="parquet",
    name="sample_data",
)


@task
def load_data(source: LocalSource) -> pl.LazyFrame:
    """Load data from the source."""
    return source.scan()


@task(depends_on=["load_data"])
def clean_data(df: pl.LazyFrame) -> pl.LazyFrame:
    """Remove rows with null values in critical columns."""
    return df.filter(pl.col("value").is_not_null() & pl.col("category").is_not_null())


@task(depends_on=["clean_data"])
def aggregate_by_category(df: pl.LazyFrame) -> pl.LazyFrame:
    """Aggregate values by category."""
    return df.group_by("category").agg(
        [
            pl.col("value").sum().alias("total_value"),
            pl.col("value").mean().alias("avg_value"),
            pl.count().alias("count"),
        ]
    )


@pipeline(
    name="simple_etl",
    description="A simple ETL pipeline demonstrating Glacier basics",
)
def simple_pipeline():
    """
    Main pipeline function.

    This orchestrates the tasks and defines the data flow.
    """
    # Load the data
    raw_data = load_data(data_source)

    # Clean it
    cleaned_data = clean_data(raw_data)

    # Aggregate
    result = aggregate_by_category(cleaned_data)

    return result


if __name__ == "__main__":
    # Run the pipeline locally
    result = simple_pipeline.run(mode="local")

    # Materialize and display the result
    print("\nPipeline Result:")
    print(result.collect())
