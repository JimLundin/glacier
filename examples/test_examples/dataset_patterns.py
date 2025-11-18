"""
Dataset Pattern Examples for Testing.

This module demonstrates different ways to use and configure datasets
in Glacier pipelines. Datasets are the data artifacts that flow through
pipelines and can be configured with storage, compute, and other properties.
"""

import pandas as pd
from glacier import Pipeline, Dataset, Environment
from glacier_aws import AWSProvider


# =============================================================================
# Pattern 1: Simple Named Datasets
# =============================================================================
def example_simple_datasets():
    """
    Basic datasets with just names - no storage configuration.

    This is the simplest pattern, ideal for local development.
    """
    pipeline = Pipeline(name="simple_datasets")

    # Just names - no other configuration
    raw = Dataset("raw_data")
    processed = Dataset("processed_data")
    final = Dataset("final_output")

    @pipeline.task()
    def extract() -> raw:
        return pd.DataFrame({"id": [1, 2, 3], "value": [10, 20, 30]})

    @pipeline.task()
    def transform(data: raw) -> processed:
        return data * 2

    @pipeline.task()
    def load(data: processed) -> final:
        return data.copy()

    return pipeline


# =============================================================================
# Pattern 2: Datasets with Descriptive Names
# =============================================================================
def example_descriptive_dataset_names():
    """
    Using descriptive names that indicate data content and stage.
    """
    pipeline = Pipeline(name="descriptive_names")

    # Descriptive naming patterns
    customer_records_raw = Dataset("customer_records_raw")
    customer_records_cleaned = Dataset("customer_records_cleaned")
    customer_records_enriched = Dataset("customer_records_enriched")
    customer_analytics_summary = Dataset("customer_analytics_summary")

    @pipeline.task()
    def extract_customers() -> customer_records_raw:
        return pd.DataFrame({
            "customer_id": [1, 2, 3],
            "name": ["Alice", "Bob", "Charlie"],
            "email": ["alice@example.com", "bob@example.com", "charlie@example.com"]
        })

    @pipeline.task()
    def clean_customer_data(raw: customer_records_raw) -> customer_records_cleaned:
        return raw.dropna()

    @pipeline.task()
    def enrich_customer_data(cleaned: customer_records_cleaned) -> customer_records_enriched:
        enriched = cleaned.copy()
        enriched["domain"] = enriched["email"].str.split("@").str[1]
        return enriched

    @pipeline.task()
    def summarize_by_domain(enriched: customer_records_enriched) -> customer_analytics_summary:
        return enriched.groupby("domain").size().reset_index(name="count")

    return pipeline


# =============================================================================
# Pattern 3: Datasets with Storage Configuration
# =============================================================================
def example_datasets_with_storage():
    """
    Datasets configured with cloud storage.

    Note: This is conceptual - actual storage creation requires environment.
    """
    pipeline = Pipeline(name="with_storage")

    # Create environment (Layer 2)
    env = Environment(
        provider=AWSProvider(account="123456789012", region="us-east-1"),
        name="prod"
    )

    # Create storage resources
    raw_bucket = env.object_storage("raw-data-bucket")
    processed_bucket = env.object_storage("processed-data-bucket")

    # Attach storage to datasets
    raw = Dataset("raw", storage=raw_bucket)
    processed = Dataset("processed", storage=processed_bucket)
    in_memory = Dataset("temp")  # No storage - ephemeral

    @pipeline.task(environment=env)
    def extract() -> raw:
        """Output stored in S3."""
        return pd.DataFrame({"value": [1, 2, 3]})

    @pipeline.task(environment=env)
    def transform(data: raw) -> in_memory:
        """Output kept in memory."""
        return data * 2

    @pipeline.task(environment=env)
    def load(data: in_memory) -> processed:
        """Output stored in S3."""
        return data.copy()

    return pipeline, env


# =============================================================================
# Pattern 4: Intermediate vs Persisted Datasets
# =============================================================================
def example_intermediate_vs_persisted():
    """
    Mix of ephemeral (intermediate) and persisted datasets.
    """
    pipeline = Pipeline(name="intermediate_persisted")

    # Persisted datasets (would have storage in production)
    source = Dataset("source_data")
    final = Dataset("final_output")

    # Intermediate datasets (no storage needed)
    temp_1 = Dataset("temp_step_1")
    temp_2 = Dataset("temp_step_2")
    temp_3 = Dataset("temp_step_3")

    @pipeline.task()
    def load_source() -> source:
        """Load from persistent storage."""
        return pd.DataFrame({"value": range(100)})

    @pipeline.task()
    def step_1(data: source) -> temp_1:
        """Intermediate transformation."""
        return data * 2

    @pipeline.task()
    def step_2(data: temp_1) -> temp_2:
        """Intermediate transformation."""
        return data + 10

    @pipeline.task()
    def step_3(data: temp_2) -> temp_3:
        """Intermediate transformation."""
        return data / 3

    @pipeline.task()
    def save_final(data: temp_3) -> final:
        """Save to persistent storage."""
        return data.copy()

    return pipeline


# =============================================================================
# Pattern 5: Dataset Reuse (Multiple Consumers)
# =============================================================================
def example_dataset_reuse():
    """
    Single dataset consumed by multiple tasks.
    """
    pipeline = Pipeline(name="dataset_reuse")

    source = Dataset("source")
    aggregated = Dataset("aggregated")
    filtered = Dataset("filtered")
    sampled = Dataset("sampled")

    @pipeline.task()
    def extract() -> source:
        """Single source dataset."""
        return pd.DataFrame({
            "category": ["A", "B", "C", "A", "B"] * 20,
            "value": range(100)
        })

    @pipeline.task()
    def aggregate(data: source) -> aggregated:
        """First consumer of source."""
        return data.groupby("category")["value"].sum().reset_index()

    @pipeline.task()
    def filter_high_values(data: source) -> filtered:
        """Second consumer of source."""
        return data[data["value"] > 50]

    @pipeline.task()
    def sample_data(data: source) -> sampled:
        """Third consumer of source."""
        return data.sample(n=10, random_state=42)

    return pipeline


# =============================================================================
# Pattern 6: Dataset Naming Conventions
# =============================================================================
def example_dataset_naming_conventions():
    """
    Different naming convention patterns.
    """
    pipeline = Pipeline(name="naming_conventions")

    # Snake_case with prefixes
    raw_customer_data = Dataset("raw_customer_data")
    stg_customer_data = Dataset("stg_customer_data")  # staging
    dim_customer = Dataset("dim_customer")  # dimension table

    # Hierarchical naming
    bronze_sales = Dataset("bronze_sales")
    silver_sales = Dataset("silver_sales")
    gold_sales_summary = Dataset("gold_sales_summary")

    @pipeline.task()
    def ingest_raw() -> raw_customer_data:
        return pd.DataFrame({"id": [1, 2, 3]})

    @pipeline.task()
    def stage(raw: raw_customer_data) -> stg_customer_data:
        return raw.copy()

    @pipeline.task()
    def build_dimension(staged: stg_customer_data) -> dim_customer:
        return staged.copy()

    @pipeline.task()
    def ingest_sales() -> bronze_sales:
        return pd.DataFrame({"sale_id": [1, 2, 3], "amount": [100, 200, 150]})

    @pipeline.task()
    def clean_sales(bronze: bronze_sales) -> silver_sales:
        return bronze[bronze["amount"] > 0]

    @pipeline.task()
    def summarize_sales(silver: silver_sales) -> gold_sales_summary:
        return pd.DataFrame({"total": [silver["amount"].sum()]})

    return pipeline


# =============================================================================
# Pattern 7: Typed Datasets (Using Metadata)
# =============================================================================
def example_typed_datasets():
    """
    Datasets representing different data types/formats.
    """
    pipeline = Pipeline(name="typed_datasets")

    # Different logical types
    csv_data = Dataset("customer_data_csv")
    json_events = Dataset("events_json")
    parquet_analytics = Dataset("analytics_parquet")
    dataframe_result = Dataset("result_dataframe")

    @pipeline.task()
    def load_csv() -> csv_data:
        """CSV format data."""
        return pd.DataFrame({"id": [1, 2, 3], "name": ["A", "B", "C"]})

    @pipeline.task()
    def load_json() -> json_events:
        """JSON format data."""
        return pd.DataFrame({
            "event_id": [1, 2, 3],
            "event_type": ["click", "view", "purchase"]
        })

    @pipeline.task()
    def transform_to_parquet(csv: csv_data, events: json_events) -> parquet_analytics:
        """Convert to Parquet format."""
        return pd.merge(csv, events, left_on="id", right_on="event_id")

    @pipeline.task()
    def analyze(data: parquet_analytics) -> dataframe_result:
        """Final DataFrame result."""
        return data.groupby("event_type").size().reset_index(name="count")

    return pipeline


# =============================================================================
# Pattern 8: Partitioned Datasets
# =============================================================================
def example_partitioned_datasets():
    """
    Datasets that represent partitioned data.
    """
    pipeline = Pipeline(name="partitioned")

    full_dataset = Dataset("customer_data_full")
    partition_2023 = Dataset("customer_data_2023")
    partition_2024 = Dataset("customer_data_2024")
    partition_2025 = Dataset("customer_data_2025")
    aggregated = Dataset("yearly_summary")

    @pipeline.task()
    def load_all_data() -> full_dataset:
        """Load complete dataset."""
        return pd.DataFrame({
            "customer_id": range(1, 101),
            "year": [2023] * 33 + [2024] * 33 + [2025] * 34,
            "revenue": range(100, 200)
        })

    @pipeline.task()
    def partition_by_year(
        data: full_dataset
    ) -> tuple[partition_2023, partition_2024, partition_2025]:
        """Split into year partitions."""
        data_2023 = data[data["year"] == 2023]
        data_2024 = data[data["year"] == 2024]
        data_2025 = data[data["year"] == 2025]
        return data_2023, data_2024, data_2025

    @pipeline.task()
    def aggregate_yearly(
        y2023: partition_2023,
        y2024: partition_2024,
        y2025: partition_2025
    ) -> aggregated:
        """Aggregate across partitions."""
        summary = pd.DataFrame({
            "year": [2023, 2024, 2025],
            "total_revenue": [
                y2023["revenue"].sum(),
                y2024["revenue"].sum(),
                y2025["revenue"].sum()
            ]
        })
        return summary

    return pipeline


# =============================================================================
# Pattern 9: Datasets with Lineage
# =============================================================================
def example_dataset_lineage():
    """
    Clear lineage through naming and structure.
    """
    pipeline = Pipeline(name="lineage")

    # Source layer
    src_customers = Dataset("src_customers")
    src_orders = Dataset("src_orders")

    # Bronze layer (raw ingestion)
    bronze_customers = Dataset("bronze_customers")
    bronze_orders = Dataset("bronze_orders")

    # Silver layer (cleaned)
    silver_customers = Dataset("silver_customers")
    silver_orders = Dataset("silver_orders")

    # Gold layer (business logic)
    gold_customer_metrics = Dataset("gold_customer_metrics")

    @pipeline.task()
    def extract_customers() -> src_customers:
        return pd.DataFrame({"customer_id": [1, 2, 3], "name": ["A", "B", "C"]})

    @pipeline.task()
    def extract_orders() -> src_orders:
        return pd.DataFrame({"order_id": [1, 2], "customer_id": [1, 1], "amount": [100, 200]})

    @pipeline.task()
    def ingest_customers(src: src_customers) -> bronze_customers:
        return src.copy()

    @pipeline.task()
    def ingest_orders(src: src_orders) -> bronze_orders:
        return src.copy()

    @pipeline.task()
    def clean_customers(bronze: bronze_customers) -> silver_customers:
        return bronze.dropna()

    @pipeline.task()
    def clean_orders(bronze: bronze_orders) -> silver_orders:
        return bronze[bronze["amount"] > 0]

    @pipeline.task()
    def calculate_metrics(
        customers: silver_customers,
        orders: silver_orders
    ) -> gold_customer_metrics:
        metrics = orders.groupby("customer_id").agg({
            "order_id": "count",
            "amount": "sum"
        }).reset_index()
        metrics.columns = ["customer_id", "order_count", "total_spent"]
        return pd.merge(customers, metrics, on="customer_id")

    return pipeline


# =============================================================================
# Test Runner
# =============================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("DATASET PATTERN EXAMPLES")
    print("=" * 70)
    print()

    examples = [
        ("Simple Named Datasets", example_simple_datasets, None),
        ("Descriptive Names", example_descriptive_dataset_names, None),
        ("Datasets with Storage", example_datasets_with_storage, "returns_tuple"),
        ("Intermediate vs Persisted", example_intermediate_vs_persisted, None),
        ("Dataset Reuse", example_dataset_reuse, None),
        ("Naming Conventions", example_dataset_naming_conventions, None),
        ("Typed Datasets", example_typed_datasets, None),
        ("Partitioned Datasets", example_partitioned_datasets, None),
        ("Dataset Lineage", example_dataset_lineage, None),
    ]

    for name, example_fn, flag in examples:
        print(f"Testing: {name}")

        if flag == "returns_tuple":
            pipeline, env = example_fn()
            print(f"  ✓ Pipeline: {pipeline.name}")
            print(f"  ✓ Environment: {env.name}")
        else:
            pipeline = example_fn()
            print(f"  ✓ Pipeline: {pipeline.name}")

        print(f"  ✓ Tasks: {len(pipeline.tasks)}")
        print(f"  ✓ Datasets: {len(pipeline._dataset_producers)}")

        # Show dataset producers
        for dataset, task in pipeline._dataset_producers.items():
            print(f"    • {dataset.name} ← {task.name}")
        print()

    print("=" * 70)
    print("All dataset patterns validated successfully!")
    print("=" * 70)
