"""
Example: New Decorator-Based API Pattern

This example demonstrates the new recommended pattern for Glacier pipelines
using the @executor.task() and @pipeline decorators.

Key features:
- Execution resources created from Provider
- Tasks bound to execution resources via @executor.task()
- Pipeline orchestration via @pipeline decorator
- Cloud-agnostic design
"""

from glacier import Provider, pipeline
from glacier.config import LocalConfig
import polars as pl


def main():
    print("=" * 70)
    print("Glacier - New Decorator-Based API Pattern")
    print("=" * 70)

    # 1. Create provider with config injection
    print("\n1. Creating provider with LocalConfig...")
    provider = Provider(config=LocalConfig(base_path="./examples/data"))
    print(f"   Provider created: {provider}")

    # 2. Create execution resources
    print("\n2. Creating execution resources...")
    local_exec = provider.local()
    print(f"   Local executor: {local_exec}")

    # 3. Create storage resources
    print("\n3. Creating storage resources...")
    data_source = provider.bucket(bucket="examples/data", path="sample.parquet")
    print(f"   Data source: {data_source}")

    # 4. Define tasks bound to execution resources
    print("\n4. Defining tasks bound to execution resources...")

    @local_exec.task()
    def load_data(source) -> pl.LazyFrame:
        """Load data from source bucket."""
        print("   → Executing load_data task...")
        return source.scan()

    @local_exec.task()
    def filter_data(df: pl.LazyFrame) -> pl.LazyFrame:
        """Filter data to include only positive values."""
        print("   → Executing filter_data task...")
        return df.filter(pl.col("value") > 0)

    @local_exec.task()
    def aggregate_data(df: pl.LazyFrame) -> pl.LazyFrame:
        """Aggregate data by category."""
        print("   → Executing aggregate_data task...")
        return df.group_by("category").agg(pl.col("value").sum())

    print(f"   Defined tasks: load_data, filter_data, aggregate_data")
    print(f"   load_data executor: {load_data.get_executor_type()}")
    print(f"   filter_data executor: {filter_data.get_executor_type()}")

    # 5. Define pipeline
    print("\n5. Defining pipeline using @pipeline decorator...")

    @pipeline(name="simple_etl", description="Simple ETL pipeline")
    def simple_etl():
        """
        Simple ETL pipeline that:
        1. Loads data from source
        2. Filters to positive values
        3. Aggregates by category
        """
        data = load_data(data_source)
        filtered = filter_data(data)
        result = aggregate_data(filtered)
        return result

    print(f"   Pipeline created: {simple_etl}")
    print(f"   Pipeline name: {simple_etl.name}")
    print(f"   Pipeline description: {simple_etl.description}")

    # 6. Execute pipeline
    print("\n6. Executing pipeline in local mode...")
    try:
        result = simple_etl.run(mode="local")
        print("\n7. Pipeline execution completed!")
        print("\n   Result:")
        print(result.collect())
    except Exception as e:
        print(f"\n   Error during execution: {e}")
        print("   Note: This is expected if sample data doesn't exist.")
        print("   Run generate_sample_data.py first to create test data.")

    print("\n" + "=" * 70)
    print("Example completed!")
    print("=" * 70)


if __name__ == "__main__":
    main()
