"""
Heterogeneous execution pipeline demonstrating mixed execution backends.

This example shows how to:
1. Run different tasks on different execution platforms
2. Mix local, Databricks, DBT, and Spark executors in one pipeline
3. Optimize task placement based on computational requirements
4. Use environment-first pattern with executor specification

This demonstrates one of Glacier's most powerful features: the ability to
seamlessly orchestrate tasks across multiple execution platforms while
maintaining a unified data flow.

Run with:
    python examples/heterogeneous_pipeline.py

Note: This example is illustrative. Full executor support (Databricks, DBT, Spark)
is planned for future releases. Currently, all tasks run locally.
"""

from glacier import GlacierEnv, Provider
from glacier.config import AwsConfig, S3Config
import polars as pl

# ============================================================================
# 1. SETUP: Create environment with AWS provider
# ============================================================================

aws_config = AwsConfig(
    region="us-east-1",
    profile="production",
    tags={
        "environment": "production",
        "pipeline": "heterogeneous-ml",
        "managed_by": "glacier",
    },
)

provider = Provider(config=aws_config)
env = GlacierEnv(provider=provider, name="ml-production")

# Register data sources
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
# 2. TASKS: Define tasks with different executors
# ============================================================================

# Local execution for lightweight I/O operations
@env.task()
def extract_raw_data(source) -> pl.LazyFrame:
    """
    Extract raw transaction data from S3.

    Executor: Local (default)
    Rationale: Simple I/O operation, no heavy computation needed.
    """
    return source.scan()


# DBT for SQL-based transformations
@env.task(executor="dbt")
def transform_with_dbt(df: pl.LazyFrame) -> pl.LazyFrame:
    """
    Transform data using DBT models.

    Executor: DBT
    Rationale: SQL transformations are best handled by DBT for:
    - SQL-based transformation logic
    - Data quality checks
    - Incremental processing
    - Version control of SQL models

    Note: In production, this would execute a DBT model that reads
    from a table, applies transformations, and writes to another table.
    Glacier orchestrates the execution and handles data flow.
    """
    # In actual implementation, this would:
    # 1. Materialize df to a temp table in data warehouse
    # 2. Execute DBT model referencing that table
    # 3. Return the result as LazyFrame
    return df.filter(pl.col("amount") > 0).with_columns(
        [
            pl.col("date").cast(pl.Utf8).str.to_datetime().alias("transaction_date"),
            pl.col("amount").cast(pl.Float64),
        ]
    )


# Spark for large-scale data processing
@env.task(executor="spark")
def aggregate_on_spark(df: pl.LazyFrame) -> pl.LazyFrame:
    """
    Aggregate transaction data using Spark.

    Executor: Spark
    Rationale: Large-scale aggregations benefit from Spark's distributed processing:
    - Handles data that doesn't fit in memory
    - Distributed computation across cluster
    - Fault-tolerant processing
    - Integration with existing Spark infrastructure

    Note: Glacier handles conversion between Polars and Spark DataFrames.
    """
    # In actual implementation, this would:
    # 1. Convert Polars LazyFrame to Spark DataFrame
    # 2. Execute aggregation on Spark cluster
    # 3. Convert result back to Polars LazyFrame
    return df.group_by("customer_id").agg(
        [
            pl.col("amount").sum().alias("total_spent"),
            pl.col("amount").mean().alias("avg_transaction"),
            pl.count().alias("transaction_count"),
        ]
    )


# Local for reading feature store
@env.task()
def load_features(source) -> pl.LazyFrame:
    """
    Load customer features from feature store.

    Executor: Local (default)
    Rationale: Simple data loading operation.
    """
    return source.scan()


# Local for joining (or could be Spark for large datasets)
@env.task()
def join_features(transactions: pl.LazyFrame, features: pl.LazyFrame) -> pl.LazyFrame:
    """
    Join transaction aggregates with customer features.

    Executor: Local (default)
    Rationale: Moderate-sized join can run locally. For larger datasets,
    could use executor="spark".
    """
    return transactions.join(features, on="customer_id", how="left")


# Databricks for ML model training/inference
@env.task(executor="databricks", timeout=1800, retries=3)
def ml_inference_on_databricks(df: pl.LazyFrame) -> pl.LazyFrame:
    """
    Run ML model inference on Databricks.

    Executor: Databricks
    Timeout: 1800 seconds (30 minutes)
    Retries: 3
    Rationale: ML inference benefits from Databricks:
    - Access to GPUs for deep learning models
    - MLflow integration for model versioning
    - Distributed inference for large datasets
    - Managed Spark clusters

    Note: In production, this would:
    1. Load a registered MLflow model
    2. Apply the model to the input data
    3. Return predictions
    """
    # In actual implementation, this would:
    # 1. Transfer data to Databricks
    # 2. Load model from MLflow registry
    # 3. Run batch inference
    # 4. Return predictions as LazyFrame
    return df.with_columns(
        [
            pl.lit(0.85).alias("churn_probability"),
            pl.lit("high_value").alias("customer_segment"),
        ]
    )


# Local for post-processing and saving
@env.task()
def post_process_predictions(df: pl.LazyFrame) -> pl.LazyFrame:
    """
    Post-process predictions and prepare for storage.

    Executor: Local (default)
    Rationale: Lightweight post-processing doesn't need distributed compute.
    """
    return df.with_columns(
        [
            (pl.col("churn_probability") > 0.7).alias("high_risk"),
            pl.lit(pl.datetime.now()).alias("prediction_timestamp"),
        ]
    )


@env.task()
def save_predictions(df: pl.LazyFrame) -> None:
    """
    Save predictions to S3.

    Executor: Local (default)
    Rationale: Simple write operation.
    """
    output = env.get("model_predictions")
    df.collect().write_parquet(output.get_uri())
    print(f"✓ Predictions saved to {output.get_uri()}")


# ============================================================================
# 3. PIPELINE: Orchestrate heterogeneous execution
# ============================================================================


@env.pipeline(name="ml_inference_pipeline")
def ml_inference_pipeline():
    """
    ML inference pipeline with heterogeneous execution.

    This pipeline demonstrates optimal task placement across platforms:
    - Local: I/O operations and lightweight processing
    - DBT: SQL-based transformations and data quality
    - Spark: Large-scale distributed aggregations
    - Databricks: ML model training and inference with GPU support

    Glacier handles:
    - Data transfer between executors
    - Format conversions (Polars ↔ Spark ↔ etc.)
    - Execution orchestration
    - Error handling and retries
    - Resource management

    The result: You write clean pipeline logic, Glacier handles the complexity
    of multi-platform execution.
    """
    # 1. Extract raw data (local)
    raw_source = env.get("raw_data")
    raw_data = extract_raw_data(raw_source)

    # 2. Transform with DBT (runs on data warehouse)
    cleaned_data = transform_with_dbt(raw_data)

    # 3. Aggregate on Spark (distributed processing)
    aggregated = aggregate_on_spark(cleaned_data)

    # 4. Load features (local)
    feature_source = env.get("feature_store")
    features = load_features(feature_source)

    # 5. Join features (local or Spark depending on size)
    joined = join_features(aggregated, features)

    # 6. ML inference on Databricks (GPU-accelerated)
    predictions = ml_inference_on_databricks(joined)

    # 7. Post-process (local)
    final_predictions = post_process_predictions(predictions)

    # 8. Save results (local)
    save_predictions(final_predictions)

    return final_predictions


# ============================================================================
# 4. EXECUTION
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("Heterogeneous Execution Pipeline - ML Inference")
    print("=" * 70)
    print(f"\nEnvironment: {env.name}")
    print(f"Provider: AWS ({aws_config.region})")
    print(f"Registered resources: {env.list_resources()}")

    print("\n" + "=" * 70)
    print("Execution Strategy")
    print("=" * 70)
    print("\n📍 Task Placement by Executor:")
    print("\n  🖥️  Local Executor:")
    print("     - extract_raw_data: I/O from S3")
    print("     - load_features: I/O from S3")
    print("     - join_features: Moderate join operation")
    print("     - post_process_predictions: Lightweight processing")
    print("     - save_predictions: I/O to S3")
    print("\n  🗄️  DBT Executor:")
    print("     - transform_with_dbt: SQL transformations and data quality")
    print("\n  ⚡ Spark Executor:")
    print("     - aggregate_on_spark: Large-scale distributed aggregations")
    print("\n  🔬 Databricks Executor:")
    print("     - ml_inference_on_databricks: ML inference with GPU (30min timeout, 3 retries)")

    print("\n" + "=" * 70)
    print("Benefits of Heterogeneous Execution")
    print("=" * 70)
    print("\n✓ Optimal Resource Utilization:")
    print("  - Run tasks on the best platform for the job")
    print("  - Avoid over-provisioning expensive resources")
    print("  - Pay only for what you need")
    print("\n✓ Best Tools for Each Job:")
    print("  - DBT for SQL transformations")
    print("  - Spark for large-scale processing")
    print("  - Databricks for ML with GPU support")
    print("  - Local for simple operations")
    print("\n✓ Unified Data Flow:")
    print("  - Single pipeline definition")
    print("  - Glacier handles data transfer between platforms")
    print("  - Automatic format conversions")
    print("  - Type-safe interfaces")
    print("\n✓ Infrastructure as Code:")
    print("  - Generate Terraform for all resources")
    print("  - Consistent deployment")
    print("  - Version-controlled infrastructure")

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
