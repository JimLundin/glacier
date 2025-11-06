"""
Heterogeneous execution pipeline demonstrating multiple execution resources.

This example shows how to:
1. Create different execution resources from the provider
2. Bind tasks to different execution resources
3. Mix local, serverless, VM, and cluster execution in one pipeline

CORRECT PATTERN:
- Execution resources are first-class objects: provider.local(), provider.serverless(), provider.vm(), provider.cluster()
- Each takes optional config: DatabricksConfig, SparkConfig, LambdaConfig, etc.
- Tasks bound to execution resources: @executor.task()
- Same pattern as storage resources

Run with:
    python examples/heterogeneous_pipeline.py
"""

from glacier import Provider, pipeline
from glacier.config import (
    AwsConfig,
    S3Config,
    LambdaConfig,
    DatabricksConfig,
    SparkConfig,
)
import polars as pl

# ============================================================================
# 1. SETUP: Create provider and execution resources
# ============================================================================

# Provider config determines WHERE DATA LIVES
provider = Provider(config=AwsConfig(region="us-east-1"))

# Create EXECUTION resources (where code runs)
# These are generic abstractions - config determines the actual backend

# Local execution
local_exec = provider.local()

# Serverless execution (Lambda/Cloud Functions/Azure Functions)
lambda_exec = provider.serverless(
    config=LambdaConfig(
        memory=1024,
        timeout=300,
        runtime="python3.11",
    )
)

# Cluster execution (Databricks/EMR/Dataproc)
databricks_exec = provider.cluster(
    config=DatabricksConfig(
        cluster_id="cluster-123",
        instance_type="i3.xlarge",
        num_workers=4,
        spark_version="3.4",
    )
)

# Alternative cluster with different config
spark_exec = provider.cluster(
    config=SparkConfig(
        master="yarn",
        num_executors=10,
        executor_memory="4g",
    )
)

# Create STORAGE resources (where data lives)
raw_data = provider.bucket(
    bucket="ml-data-lake",
    path="raw/transactions.parquet",
    config=S3Config(storage_class="STANDARD", encryption="AES256"),
)

feature_store = provider.bucket(
    bucket="ml-data-lake",
    path="features/customer_features.parquet",
    config=S3Config(storage_class="INTELLIGENT_TIERING", encryption="AES256"),
)

output_bucket = provider.bucket(
    bucket="ml-data-lake",
    path="predictions/latest.parquet",
    config=S3Config(storage_class="STANDARD", encryption="AES256"),
)

# ============================================================================
# 2. TASKS: Bind to different execution resources
# ============================================================================


@local_exec.task()
def extract_raw_data(source) -> pl.LazyFrame:
    """
    Extract raw data.

    EXECUTION: Local Python process
    DATA: AWS S3
    """
    return source.scan()


@lambda_exec.task()
def transform_with_lambda(df: pl.LazyFrame) -> pl.LazyFrame:
    """
    Lightweight transformation using Lambda.

    EXECUTION: AWS Lambda (serverless)
    DATA: Passed in-memory, results returned
    """
    return df.filter(pl.col("amount") > 0).with_columns(
        [
            pl.col("date").cast(pl.Utf8).str.to_datetime().alias("transaction_date"),
            pl.col("amount").cast(pl.Float64),
        ]
    )


@spark_exec.task()
def aggregate_on_spark(df: pl.LazyFrame) -> pl.LazyFrame:
    """
    Large-scale aggregation on Spark cluster.

    EXECUTION: Spark cluster (EMR/Dataproc/standalone)
    DATA: Converted to Spark DataFrame, processed, converted back
    """
    return df.group_by("customer_id").agg(
        [
            pl.col("amount").sum().alias("total_spent"),
            pl.col("amount").mean().alias("avg_transaction"),
            pl.count().alias("transaction_count"),
        ]
    )


@local_exec.task()
def load_features(source) -> pl.LazyFrame:
    """
    Load features from S3.

    EXECUTION: Local Python process
    DATA: AWS S3
    """
    return source.scan()


@local_exec.task()
def join_features(transactions: pl.LazyFrame, features: pl.LazyFrame) -> pl.LazyFrame:
    """
    Join transaction aggregates with features.

    EXECUTION: Local Python process
    DATA: In-memory
    """
    return transactions.join(features, on="customer_id", how="left")


@databricks_exec.task()
def ml_inference_on_databricks(df: pl.LazyFrame) -> pl.LazyFrame:
    """
    ML inference on Databricks cluster.

    EXECUTION: Databricks cluster (with GPU support)
    DATA: Transferred to Databricks, processed, results returned
    CONFIG: DatabricksConfig specifies cluster, GPUs, Spark version
    """
    return df.with_columns(
        [
            pl.lit(0.85).alias("churn_probability"),
            pl.lit("high_value").alias("customer_segment"),
        ]
    )


@local_exec.task()
def post_process_predictions(df: pl.LazyFrame) -> pl.LazyFrame:
    """
    Post-process predictions.

    EXECUTION: Local Python process
    DATA: In-memory
    """
    return df.with_columns(
        [
            (pl.col("churn_probability") > 0.7).alias("high_risk"),
            pl.lit(pl.datetime.now()).alias("prediction_timestamp"),
        ]
    )


@local_exec.task()
def save_predictions(df: pl.LazyFrame) -> None:
    """
    Save predictions to S3.

    EXECUTION: Local Python process
    DATA: Written to AWS S3
    """
    df.collect().write_parquet(output_bucket.get_uri())
    print(f"✓ Predictions saved to {output_bucket.get_uri()}")


# ============================================================================
# 3. PIPELINE: Orchestrate heterogeneous execution
# ============================================================================


@pipeline(name="ml_inference")
def ml_inference_pipeline():
    """
    ML inference pipeline with heterogeneous execution.

    This pipeline demonstrates:
    - Multiple execution resources in one pipeline
    - Tasks execute on different platforms (local, Lambda, Spark, Databricks)
    - ALL data reads/writes from AWS S3 (determined by provider config)
    - Glacier handles data transfer between execution resources

    Execution flow:
    1. extract_raw_data → local_exec
    2. transform_with_lambda → lambda_exec
    3. aggregate_on_spark → spark_exec
    4. load_features → local_exec
    5. join_features → local_exec
    6. ml_inference_on_databricks → databricks_exec
    7. post_process_predictions → local_exec
    8. save_predictions → local_exec
    """
    # Extract (local)
    raw = extract_raw_data(raw_data)

    # Transform (Lambda)
    cleaned = transform_with_lambda(raw)

    # Aggregate (Spark)
    aggregated = aggregate_on_spark(cleaned)

    # Load features (local)
    features = load_features(feature_store)

    # Join (local)
    joined = join_features(aggregated, features)

    # ML inference (Databricks)
    predictions = ml_inference_on_databricks(joined)

    # Post-process (local)
    final_predictions = post_process_predictions(predictions)

    # Save (local)
    save_predictions(final_predictions)

    return final_predictions


# ============================================================================
# 4. EXECUTION
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("Heterogeneous Execution Pipeline")
    print("=" * 70)

    print("\n📍 Execution Resources Created:")
    print(f"   - local_exec: {local_exec}")
    print(f"   - lambda_exec: {lambda_exec}")
    print(f"   - spark_exec: {spark_exec}")
    print(f"   - databricks_exec: {databricks_exec}")

    print("\n📦 Storage Resources Created:")
    print(f"   - raw_data: {raw_data}")
    print(f"   - feature_store: {feature_store}")
    print(f"   - output_bucket: {output_bucket}")

    print("\n" + "=" * 70)
    print("Glacier Resource Pattern")
    print("=" * 70)
    print("\n✓ Provider creates TWO types of resources:")
    print("\n  1. STORAGE (where data lives):")
    print("     - provider.bucket(config=S3Config/GCSConfig/AzureBlobConfig)")
    print("     - Generic abstraction, config determines backend")
    print("\n  2. EXECUTION (where code runs):")
    print("     - provider.local() → Local Python process")
    print("     - provider.serverless(config=LambdaConfig) → Lambda/Cloud Functions")
    print("     - provider.vm(config=EC2Config) → EC2/Compute Engine")
    print("     - provider.cluster(config=DatabricksConfig/SparkConfig) → Clusters")
    print("     - Generic abstractions, config determines backend")

    print("\n✓ Tasks bound to execution resources:")
    print("     - @local_exec.task() → runs on local")
    print("     - @lambda_exec.task() → runs on Lambda")
    print("     - @databricks_exec.task() → runs on Databricks")

    print("\n✓ Cloud-agnostic:")
    print("     - Same pattern across all clouds")
    print("     - Config injection determines actual backend")
    print("     - No vendor lock-in")

    print("\n" + "=" * 70)
    print("Execution Flow")
    print("=" * 70)
    print("\n  1. extract_raw_data → local_exec (local Python)")
    print("  2. transform_with_lambda → lambda_exec (AWS Lambda)")
    print("  3. aggregate_on_spark → spark_exec (Spark cluster)")
    print("  4. load_features → local_exec (local Python)")
    print("  5. join_features → local_exec (local Python)")
    print("  6. ml_inference_on_databricks → databricks_exec (Databricks)")
    print("  7. post_process_predictions → local_exec (local Python)")
    print("  8. save_predictions → local_exec (local Python)")

    print("\n" + "=" * 70)

    # Uncomment to run
    # print("\n▶️  Running pipeline...")
    # result = ml_inference_pipeline.run(mode="local")
    # print("\n✅ Pipeline completed!")
