"""
Example: New Fluent API Pattern

This example demonstrates the new fluent API pattern for Glacier pipelines
using Pipeline().source().transform().to() chaining.

Key features:
- Execution resources created from Provider
- Tasks bound to execution resources via @executor.task()
- Pipeline composition via fluent API
- Clean, readable pipeline structure
"""

from glacier import Provider, Pipeline
from glacier.config import LocalConfig
import polars as pl


def main():
    print("=" * 70)
    print("Glacier - New Fluent API Pattern")
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
    raw_data = provider.bucket(bucket="examples/data", path="sample.parquet")
    filtered_data = provider.bucket(
        bucket="examples/data", path="filtered_sample.parquet"
    )
    output_data = provider.bucket(
        bucket="examples/data", path="aggregated_sample.parquet"
    )
    print(f"   Raw data: {raw_data}")
    print(f"   Filtered data: {filtered_data}")
    print(f"   Output data: {output_data}")

    # 4. Define tasks bound to execution resources
    print("\n4. Defining tasks bound to execution resources...")

    @local_exec.task()
    def filter_positive(df: pl.LazyFrame) -> pl.LazyFrame:
        """Filter data to include only positive values."""
        print("   → Executing filter_positive task...")
        return df.filter(pl.col("value") > 0)

    @local_exec.task()
    def aggregate_by_category(df: pl.LazyFrame) -> pl.LazyFrame:
        """Aggregate data by category."""
        print("   → Executing aggregate_by_category task...")
        return df.group_by("category").agg(pl.col("value").sum())

    print(f"   Defined tasks: filter_positive, aggregate_by_category")

    # 5. Define pipeline using fluent API
    print("\n5. Defining pipeline using fluent API...")

    etl_pipeline = (
        Pipeline(name="fluent_etl", description="ETL pipeline using fluent API")
        .source(raw_data)
        .transform(filter_positive)
        .to(filtered_data)
        .transform(aggregate_by_category)
        .to(output_data)
    )

    print(f"   Pipeline created: {etl_pipeline}")
    print(f"   Pipeline name: {etl_pipeline.name}")
    print(f"   Pipeline steps: {len(etl_pipeline._steps)}")

    # 6. Build DAG from pipeline
    print("\n6. Building DAG from pipeline...")
    try:
        dag = etl_pipeline.to_dag()
        print(f"   DAG created with {len(dag.nodes)} nodes")

        # Show pipeline structure
        print("\n   Pipeline structure:")
        for i, step in enumerate(etl_pipeline._steps, 1):
            print(f"   Step {i}:")
            print(f"     Task: {step.task.name}")
            print(f"     Sources: {list(step.sources.keys())}")
            print(f"     Target: {step.target.path}")

    except Exception as e:
        print(f"\n   Error building DAG: {e}")

    print("\n" + "=" * 70)
    print("Example completed!")
    print("\nKey observations:")
    print("- Pipeline composition is clean and readable")
    print("- Each .transform().to() pair creates one step")
    print("- Output of one step becomes input to the next")
    print("- Tasks are bound to execution resources (local_exec)")
    print("=" * 70)


if __name__ == "__main__":
    main()
