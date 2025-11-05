"""
Heterogeneous execution pipeline demonstrating mixed execution backends.

This example shows how to:
1. Run different tasks on different EXECUTION PLATFORMS
2. Mix local, Databricks, DBT, and Spark executors in one pipeline
3. Optimize task placement based on computational requirements

This demonstrates one of Glacier's most powerful features: the ability to
seamlessly orchestrate tasks across multiple execution platforms while
maintaining a unified data flow.

Key concepts:
- Provider config determines WHERE DATA LIVES (AWS S3 in this example)
- Task executor determines WHERE CODE RUNS (local, databricks, spark, dbt)
- Different tasks in the SAME pipeline can run on DIFFERENT executors

Run with:
    python examples/heterogeneous_pipeline.py

Note: This example is illustrative. Full executor support (Databricks, DBT, Spark)
is planned for future releases. Currently, all tasks run locally.
"""

from glacier import GlacierEnv, Provider
from glacier.config import AwsConfig, S3Config
import polars as pl

# ============================================================================
# 1. SETUP: Create execution context
# ============================================================================

# Provider config determines WHERE DATA LIVES
# AwsConfig = data in AWS S3
aws_config = AwsConfig(
    region="us-east-1",
    profile="default",
    tags={
        "project": "ml-inference",
        "managed_by": "glacier",
    },
)

provider = Provider(config=aws_config)

# Create execution context (DI container)
env = GlacierEnv(provider=provider, name="ml-inference-pipeline")

# Register data sources (all in AWS S3 based on provider config)
env.register(
    "raw_data",
    env.provider.bucket(
        bucket="ml-data-lake",
        path="raw/transactions.parquet",
        config=S3Config(storage_class="STANDARD", encryption="AES256"),
    ),
)

env.register(
    "feature_store",
    env.provider.bucket(
        bucket="ml-data-lake",
        path="features/customer_features.parquet",
        config=S3Config(storage_class="INTELLIGENT_TIERING", encryption="AES256"),
    ),
)

env.register(
    "model_predictions",
    env.provider.bucket(
        bucket="ml-data-lake",
        path="predictions/latest.parquet",
        config=S3Config(storage_class="STANDARD", encryption="AES256"),
    ),
)

# ============================================================================
# 2. TASKS: Define tasks with different EXECUTORS
# ============================================================================

# Executor determines WHERE CODE RUNS, not where data lives


@env.task()  # Default: executor="local"
def extract_raw_data(source) -> pl.LazyFrame:
    """
    Extract raw transaction data.

    EXECUTION: Local Python process (executor="local", default)
    DATA: AWS S3 (determined by provider config)
    RATIONALE: Simple I/O operation, no heavy computation needed.
    """
    return source.scan()


@env.task(executor="dbt")
def transform_with_dbt(df: pl.LazyFrame) -> pl.LazyFrame:
    """
    Transform data using DBT models.

    EXECUTION: DBT (executor="dbt") - runs in data warehouse
    DATA: AWS S3 (determined by provider config)
    RATIONALE: SQL transformations best handled by DBT:
    - SQL-based transformation logic
    - Data quality checks
    - Incremental processing
    - Version control of SQL models

    Note: In production, Glacier would:
    1. Materialize df to temp table in data warehouse
    2. Execute DBT model referencing that table
    3. Return result as LazyFrame
    """
    # Illustrative implementation (actual would run DBT)
    return df.filter(pl.col("amount") > 0).with_columns(
        [
            pl.col("date").cast(pl.Utf8).str.to_datetime().alias("transaction_date"),
            pl.col("amount").cast(pl.Float64),
        ]
    )


@env.task(executor="spark")
def aggregate_on_spark(df: pl.LazyFrame) -> pl.LazyFrame:
    """
    Aggregate transaction data using Spark.

    EXECUTION: Spark cluster (executor="spark")
    DATA: AWS S3 (determined by provider config)
    RATIONALE: Large-scale aggregations benefit from Spark:
    - Handles data that doesn't fit in single-machine memory
    - Distributed computation across cluster
    - Fault-tolerant processing
    - Integration with existing Spark infrastructure

    Note: Glacier handles conversion between Polars and Spark DataFrames.
    """
    # Illustrative implementation (actual would run on Spark)
    return df.group_by("customer_id").agg(
        [
            pl.col("amount").sum().alias("total_spent"),
            pl.col("amount").mean().alias("avg_transaction"),
            pl.count().alias("transaction_count"),
        ]
    )


@env.task()  # executor="local"
def load_features(source) -> pl.LazyFrame:
    """
    Load customer features from feature store.

    EXECUTION: Local Python process (executor="local")
    DATA: AWS S3 (determined by provider config)
    RATIONALE: Simple data loading operation.
    """
    return source.scan()


@env.task()  # executor="local"
def join_features(transactions: pl.LazyFrame, features: pl.LazyFrame) -> pl.LazyFrame:
    """
    Join transaction aggregates with customer features.

    EXECUTION: Local Python process (executor="local")
    DATA: In-memory (results from previous tasks)
    RATIONALE: Moderate-sized join can run locally.

    Note: For larger datasets, could use executor="spark" instead.
    """
    return transactions.join(features, on="customer_id", how="left")


@env.task(executor="databricks", timeout=1800, retries=3)
def ml_inference_on_databricks(df: pl.LazyFrame) -> pl.LazyFrame:
    """
    Run ML model inference on Databricks.

    EXECUTION: Databricks cluster (executor="databricks")
    DATA: Transferred to Databricks, results returned
    TIMEOUT: 1800 seconds (30 minutes)
    RETRIES: 3 attempts
    RATIONALE: ML inference benefits from Databricks:
    - Access to GPUs for deep learning models
    - MLflow integration for model versioning
    - Distributed inference for large datasets
    - Managed Spark clusters

    Note: In production, Glacier would:
    1. Transfer data to Databricks
    2. Load model from MLflow registry
    3. Run batch inference
    4. Return predictions as LazyFrame
    """
    # Illustrative implementation (actual would run on Databricks)
    return df.with_columns(
        [
            pl.lit(0.85).alias("churn_probability"),
            pl.lit("high_value").alias("customer_segment"),
        ]
    )


@env.task()  # executor="local"
def post_process_predictions(df: pl.LazyFrame) -> pl.LazyFrame:
    """
    Post-process predictions.

    EXECUTION: Local Python process (executor="local")
    DATA: In-memory (results from Databricks task)
    RATIONALE: Lightweight post-processing doesn't need distributed compute.
    """
    return df.with_columns(
        [
            (pl.col("churn_probability") > 0.7).alias("high_risk"),
            pl.lit(pl.datetime.now()).alias("prediction_timestamp"),
        ]
    )


@env.task()  # executor="local"
def save_predictions(df: pl.LazyFrame) -> None:
    """
    Save predictions to S3.

    EXECUTION: Local Python process (executor="local")
    DATA: Written to AWS S3 (determined by provider config)
    RATIONALE: Simple write operation.
    """
    output = env.get("model_predictions")
    df.collect().write_parquet(output.get_uri())
    print(f"✓ Predictions saved to {output.get_uri()}")


# ============================================================================
# 3. PIPELINE: Orchestrate heterogeneous execution
# ============================================================================


@env.pipeline(name="ml_inference")
def ml_inference_pipeline():
    """
    ML inference pipeline with heterogeneous execution.

    This pipeline demonstrates optimal task placement across execution platforms:
    - Local: I/O operations and lightweight processing
    - DBT: SQL-based transformations and data quality
    - Spark: Large-scale distributed aggregations
    - Databricks: ML model training and inference with GPU support

    ALL tasks read/write from AWS S3 (determined by provider config), but
    code executes on different platforms (determined by task executor).

    Glacier handles:
    - Data transfer between executors
    - Format conversions (Polars ↔ Spark ↔ etc.)
    - Execution orchestration
    - Error handling and retries
    - Resource management
    """
    # 1. Extract raw data (executor="local")
    raw_source = env.get("raw_data")
    raw_data = extract_raw_data(raw_source)

    # 2. Transform with DBT (executor="dbt", runs in data warehouse)
    cleaned_data = transform_with_dbt(raw_data)

    # 3. Aggregate on Spark (executor="spark", runs on Spark cluster)
    aggregated = aggregate_on_spark(cleaned_data)

    # 4. Load features (executor="local")
    feature_source = env.get("feature_store")
    features = load_features(feature_source)

    # 5. Join features (executor="local")
    joined = join_features(aggregated, features)

    # 6. ML inference on Databricks (executor="databricks", runs on Databricks)
    predictions = ml_inference_on_databricks(joined)

    # 7. Post-process (executor="local")
    final_predictions = post_process_predictions(predictions)

    # 8. Save results (executor="local", writes to S3)
    save_predictions(final_predictions)

    return final_predictions


# ============================================================================
# 4. EXECUTION
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("Heterogeneous Execution Pipeline - ML Inference")
    print("=" * 70)
    print(f"\nExecution Context: {env.name}")
    print(f"Data Location: AWS S3 ({aws_config.region})")
    print(f"Registered Resources: {env.list_resources()}")

    print("\n" + "=" * 70)
    print("Execution Strategy")
    print("=" * 70)
    print("\n📍 Task Placement by Executor:")
    print("\n  🖥️  Local Executor (executor='local'):")
    print("     - extract_raw_data: I/O from S3")
    print("     - load_features: I/O from S3")
    print("     - join_features: Moderate join operation")
    print("     - post_process_predictions: Lightweight processing")
    print("     - save_predictions: I/O to S3")
    print("\n  🗄️  DBT Executor (executor='dbt'):")
    print("     - transform_with_dbt: SQL transformations in data warehouse")
    print("\n  ⚡ Spark Executor (executor='spark'):")
    print("     - aggregate_on_spark: Large-scale distributed aggregations")
    print("\n  🔬 Databricks Executor (executor='databricks'):")
    print("     - ml_inference_on_databricks: ML inference with GPU")
    print("       (30min timeout, 3 retries)")

    print("\n" + "=" * 70)
    print("Key Concepts")
    print("=" * 70)
    print("\n✓ Provider Config determines WHERE DATA LIVES:")
    print("  - AwsConfig → Data in AWS S3")
    print("  - All tasks read/write from S3")
    print("\n✓ Task Executor determines WHERE CODE RUNS:")
    print("  - executor='local' → Local Python process")
    print("  - executor='dbt' → Data warehouse")
    print("  - executor='spark' → Spark cluster")
    print("  - executor='databricks' → Databricks cluster")
    print("\n✓ Heterogeneous Execution Benefits:")
    print("  - Optimal resource utilization (right tool for each job)")
    print("  - Cost optimization (don't over-provision)")
    print("  - Unified data flow across platforms")
    print("  - Glacier handles data transfer and format conversion")
    print("\n✓ GlacierEnv is NOT a deployment environment:")
    print("  - It's a DI container for tasks, pipelines, and resources")
    print("  - Deployment environments (dev/staging/prod) are infrastructure concerns")

    print("\n" + "=" * 70)
    print("How to Use")
    print("=" * 70)
    print("\n1. Analyze the pipeline:")
    print("   glacier analyze examples/heterogeneous_pipeline.py")
    print("\n2. Generate infrastructure:")
    print("   glacier generate examples/heterogeneous_pipeline.py --output ./infra")
    print("\n3. Deploy infrastructure:")
    print("   cd infra && terraform init && terraform apply")
    print("\n4. Run the pipeline:")
    print("   python examples/heterogeneous_pipeline.py")
    print("\n   Glacier will automatically:")
    print("   - Execute local tasks in the current process")
    print("   - Submit DBT models to your data warehouse")
    print("   - Launch Spark jobs on your cluster")
    print("   - Execute Databricks notebooks for ML inference")
    print("   - Orchestrate data flow between all platforms")

    print("\n" + "=" * 70)
    print("Executor Support Status")
    print("=" * 70)
    print("\n  ✅ local     - Ready (default executor)")
    print("  🚧 dbt       - Planned (Phase 3)")
    print("  🚧 spark     - Planned (Phase 3)")
    print("  🚧 databricks - Planned (Phase 3)")
    print("  🚧 airflow   - Planned (Phase 3)")
    print("\n  Note: Currently all tasks run locally. Full executor support")
    print("  is coming in Phase 3 of the roadmap.")

    print("\n" + "=" * 70)

    # Uncomment to run (currently all runs locally)
    # print("\n▶️  Running pipeline...")
    # result = ml_inference_pipeline.run(mode="local")
    # print("\n✅ Pipeline completed!")
    # print("\nPredictions:")
    # print(result.collect())
