"""
Integration Examples for Testing.

This module contains complete end-to-end examples that demonstrate
real-world usage patterns combining multiple Glacier features.
These serve as integration tests and comprehensive documentation.
"""

import pandas as pd
from glacier import Stack, Pipeline, Dataset, Environment
from glacier_aws import AWSProvider
from glacier.scheduling import cron, on_update
from glacier.monitoring import monitoring, notify_email


# =============================================================================
# Example 1: Complete ETL Pipeline with All Layers
# =============================================================================
def example_complete_etl():
    """
    Complete ETL pipeline demonstrating all three layers.

    - Layer 1: Simple dataset definitions
    - Layer 2: Environment and provider-agnostic resources
    - Layer 3: Explicit stack and full control
    """
    # Layer 3: Create explicit stack
    stack = Stack(name="etl-platform")

    # Layer 2: Create environment with provider
    prod_env = stack.environment(
        provider=AWSProvider(
            account="123456789012",
            region="us-east-1",
            tags={"Team": "DataEngineering", "Project": "ETL"}
        ),
        name="production"
    )

    # Create storage resources
    raw_storage = prod_env.object_storage("raw-data")
    processed_storage = prod_env.object_storage("processed-data")
    final_storage = prod_env.object_storage("final-output")

    # Layer 1: Simple dataset definitions
    raw_customers = Dataset("raw_customers", storage=raw_storage)
    raw_orders = Dataset("raw_orders", storage=raw_storage)
    cleaned_customers = Dataset("cleaned_customers")
    cleaned_orders = Dataset("cleaned_orders")
    customer_metrics = Dataset("customer_metrics", storage=processed_storage)
    final_report = Dataset("final_report", storage=final_storage)

    # Create pipeline
    etl = stack.pipeline("customer-analytics")

    @etl.task(environment=prod_env)
    def extract_customers() -> raw_customers:
        """Extract customer data from source."""
        return pd.DataFrame({
            "customer_id": [1, 2, 3, 4, 5],
            "name": ["Alice", "Bob", "Charlie", "David", "Eve"],
            "email": ["alice@example.com", "bob@example.com", None, "david@example.com", "eve@example.com"],
            "status": ["active", "active", "inactive", "active", "active"]
        })

    @etl.task(environment=prod_env)
    def extract_orders() -> raw_orders:
        """Extract order data from source."""
        return pd.DataFrame({
            "order_id": [1, 2, 3, 4, 5, 6],
            "customer_id": [1, 1, 2, 3, 4, 4],
            "amount": [100, 150, 200, 50, 300, 120],
            "order_date": pd.date_range("2025-01-01", periods=6)
        })

    @etl.task(environment=prod_env)
    def clean_customers(raw: raw_customers) -> cleaned_customers:
        """Clean customer data."""
        cleaned = raw.dropna(subset=["email"])
        cleaned = cleaned[cleaned["status"] == "active"]
        return cleaned

    @etl.task(environment=prod_env)
    def clean_orders(raw: raw_orders) -> cleaned_orders:
        """Clean order data."""
        cleaned = raw[raw["amount"] > 0]
        return cleaned

    @etl.task(environment=prod_env)
    def calculate_customer_metrics(
        customers: cleaned_customers,
        orders: cleaned_orders
    ) -> customer_metrics:
        """Calculate customer metrics."""
        metrics = orders.groupby("customer_id").agg({
            "order_id": "count",
            "amount": ["sum", "mean", "max"]
        }).reset_index()

        metrics.columns = ["customer_id", "order_count", "total_spent", "avg_order", "max_order"]

        # Join with customer data
        result = pd.merge(customers[["customer_id", "name"]], metrics, on="customer_id")
        return result

    @etl.task(environment=prod_env)
    def generate_report(metrics: customer_metrics) -> final_report:
        """Generate final report."""
        report = metrics.copy()
        report["customer_value"] = report["total_spent"] / report["order_count"]
        report = report.sort_values("total_spent", ascending=False)
        return report

    return stack


# =============================================================================
# Example 2: Multi-Pipeline Platform
# =============================================================================
def example_multi_pipeline_platform():
    """
    Platform with multiple interconnected pipelines.
    """
    stack = Stack(name="data-platform")

    # Create environment
    env = stack.environment(
        provider=AWSProvider(account="123456789012", region="us-east-1"),
        name="prod"
    )

    # Ingestion pipelines
    customer_ingestion = stack.pipeline("ingestion.customers")
    product_ingestion = stack.pipeline("ingestion.products")
    sales_ingestion = stack.pipeline("ingestion.sales")

    # Processing pipelines
    customer_processing = stack.pipeline("processing.customers")
    product_processing = stack.pipeline("processing.products")

    # Analytics pipeline
    analytics = stack.pipeline("analytics.sales")

    # Define datasets
    raw_customers = Dataset("raw_customers")
    raw_products = Dataset("raw_products")
    raw_sales = Dataset("raw_sales")

    processed_customers = Dataset("processed_customers")
    processed_products = Dataset("processed_products")

    sales_analytics = Dataset("sales_analytics")

    # Ingestion tasks
    @customer_ingestion.task(environment=env, schedule=cron("0 1 * * *"))
    def ingest_customers() -> raw_customers:
        return pd.DataFrame({"customer_id": [1, 2, 3], "name": ["A", "B", "C"]})

    @product_ingestion.task(environment=env, schedule=cron("0 2 * * *"))
    def ingest_products() -> raw_products:
        return pd.DataFrame({"product_id": [1, 2], "name": ["Widget", "Gadget"], "price": [10, 20]})

    @sales_ingestion.task(environment=env, schedule=cron("0 */6 * * *"))
    def ingest_sales() -> raw_sales:
        return pd.DataFrame({
            "sale_id": [1, 2, 3],
            "customer_id": [1, 2, 1],
            "product_id": [1, 2, 1],
            "quantity": [2, 1, 3]
        })

    # Processing tasks
    @customer_processing.task(environment=env)
    def process_customers(raw: raw_customers) -> processed_customers:
        return raw.dropna()

    @product_processing.task(environment=env)
    def process_products(raw: raw_products) -> processed_products:
        return raw[raw["price"] > 0]

    # Analytics task
    @analytics.task(environment=env)
    def analyze_sales(
        sales: raw_sales,
        customers: processed_customers,
        products: processed_products
    ) -> sales_analytics:
        # Join sales with customers and products
        result = pd.merge(sales, customers, on="customer_id")
        result = pd.merge(result, products, on="product_id")
        result["revenue"] = result["quantity"] * result["price"]
        return result

    return stack


# =============================================================================
# Example 3: Development to Production Workflow
# =============================================================================
def example_dev_to_prod_workflow():
    """
    Pipeline deployed across dev, staging, and prod environments.
    """
    stack = Stack(name="multi-env-deployment")

    # Create environments
    dev = stack.environment(
        provider=AWSProvider(account="111111111111", region="us-west-2"),
        name="development"
    )

    staging = stack.environment(
        provider=AWSProvider(account="222222222222", region="us-east-1"),
        name="staging"
    )

    prod = stack.environment(
        provider=AWSProvider(account="333333333333", region="us-east-1"),
        name="production"
    )

    # Create storage for each environment
    dev_storage = dev.object_storage("data")
    staging_storage = staging.object_storage("data")
    prod_storage = prod.object_storage("data")

    # Create pipeline
    etl = stack.pipeline("etl")

    # Datasets
    raw = Dataset("raw")
    processed = Dataset("processed")
    final = Dataset("final")

    @etl.task(environment=dev)
    def extract() -> raw:
        """Development extraction."""
        return pd.DataFrame({"value": range(10)})

    @etl.task(environment=staging)
    def transform(data: raw) -> processed:
        """Staging transformation."""
        return data * 2

    @etl.task(environment=prod)
    def load(data: processed) -> final:
        """Production load."""
        return data.copy()

    return stack


# =============================================================================
# Example 4: Real-Time and Batch Processing
# =============================================================================
def example_realtime_and_batch():
    """
    Pipeline combining real-time event processing and batch analytics.
    """
    stack = Stack(name="hybrid-processing")

    env = stack.environment(
        provider=AWSProvider(account="123456789012", region="us-east-1"),
        name="prod"
    )

    # Real-time pipeline
    realtime = stack.pipeline("realtime-events")

    events = Dataset("events")
    processed_events = Dataset("processed_events")

    @realtime.task(environment=env, schedule=on_update(events))
    def process_events(raw_events: events) -> processed_events:
        """Process events as they arrive."""
        processed = raw_events.copy()
        processed["processed_at"] = pd.Timestamp.now()
        return processed

    # Batch pipeline
    batch = stack.pipeline("batch-analytics")

    daily_events = Dataset("daily_events")
    analytics = Dataset("analytics")

    @batch.task(environment=env, schedule=cron("0 3 * * *"))
    def aggregate_daily() -> daily_events:
        """Daily aggregation of events."""
        return pd.DataFrame({"date": ["2025-01-01"], "event_count": [1000]})

    @batch.task(environment=env)
    def analyze(data: daily_events) -> analytics:
        """Analyze aggregated data."""
        return data.copy()

    return stack


# =============================================================================
# Example 5: Data Lake Architecture
# =============================================================================
def example_data_lake():
    """
    Multi-layered data lake (Bronze/Silver/Gold).
    """
    stack = Stack(name="data-lake")

    env = stack.environment(
        provider=AWSProvider(account="123456789012", region="us-east-1"),
        name="prod"
    )

    # Create storage for each layer
    bronze_storage = env.object_storage("bronze-layer")
    silver_storage = env.object_storage("silver-layer")
    gold_storage = env.object_storage("gold-layer")

    # Bronze layer (raw ingestion)
    bronze_pipeline = stack.pipeline("bronze-ingestion")

    bronze_customers = Dataset("bronze_customers", storage=bronze_storage)
    bronze_orders = Dataset("bronze_orders", storage=bronze_storage)

    @bronze_pipeline.task(environment=env)
    def ingest_customers() -> bronze_customers:
        return pd.DataFrame({"customer_id": [1, 2, 3], "name": ["A", "B", "C"]})

    @bronze_pipeline.task(environment=env)
    def ingest_orders() -> bronze_orders:
        return pd.DataFrame({"order_id": [1, 2], "customer_id": [1, 1], "amount": [100, 200]})

    # Silver layer (cleaned/validated)
    silver_pipeline = stack.pipeline("silver-processing")

    silver_customers = Dataset("silver_customers", storage=silver_storage)
    silver_orders = Dataset("silver_orders", storage=silver_storage)

    @silver_pipeline.task(environment=env)
    def clean_customers(bronze: bronze_customers) -> silver_customers:
        return bronze.dropna()

    @silver_pipeline.task(environment=env)
    def clean_orders(bronze: bronze_orders) -> silver_orders:
        return bronze[bronze["amount"] > 0]

    # Gold layer (business logic)
    gold_pipeline = stack.pipeline("gold-analytics")

    gold_customer_value = Dataset("gold_customer_value", storage=gold_storage)

    @gold_pipeline.task(environment=env)
    def calculate_value(
        customers: silver_customers,
        orders: silver_orders
    ) -> gold_customer_value:
        metrics = orders.groupby("customer_id")["amount"].sum().reset_index()
        return pd.merge(customers, metrics, on="customer_id")

    return stack


# =============================================================================
# Example 6: Machine Learning Pipeline
# =============================================================================
def example_ml_pipeline():
    """
    Machine learning pipeline with data prep, training, and inference.
    """
    stack = Stack(name="ml-pipeline")

    env = stack.environment(
        provider=AWSProvider(account="123456789012", region="us-east-1"),
        name="prod"
    )

    ml = stack.pipeline("customer-churn-prediction")

    # Datasets
    raw_data = Dataset("raw_data")
    features = Dataset("features")
    training_data = Dataset("training_data")
    test_data = Dataset("test_data")
    model = Dataset("trained_model")
    predictions = Dataset("predictions")

    @ml.task(environment=env)
    def extract_data() -> raw_data:
        """Extract historical customer data."""
        return pd.DataFrame({
            "customer_id": range(1, 101),
            "tenure_months": range(1, 101),
            "monthly_spend": range(50, 150),
            "churned": [i % 5 == 0 for i in range(1, 101)]
        })

    @ml.task(environment=env)
    def engineer_features(raw: raw_data) -> features:
        """Feature engineering."""
        feat = raw.copy()
        feat["spend_per_month"] = feat["monthly_spend"] / feat["tenure_months"]
        feat["high_value"] = feat["monthly_spend"] > 100
        return feat

    @ml.task(environment=env)
    def split_data(data: features) -> tuple[training_data, test_data]:
        """Split into training and test sets."""
        split_point = int(len(data) * 0.8)
        return data.iloc[:split_point], data.iloc[split_point:]

    @ml.task(environment=env)
    def train_model(train: training_data) -> model:
        """Train ML model (conceptual)."""
        # In real implementation, would train actual model
        return {"model_type": "random_forest", "accuracy": 0.85}

    @ml.task(environment=env)
    def predict(trained_model: model, test: test_data) -> predictions:
        """Make predictions (conceptual)."""
        # In real implementation, would use actual model
        preds = test.copy()
        preds["predicted_churn"] = False
        return preds

    return stack


# =============================================================================
# Test Runner
# =============================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("INTEGRATION EXAMPLES (End-to-End)")
    print("=" * 70)
    print()

    examples = [
        ("Complete ETL Pipeline", example_complete_etl),
        ("Multi-Pipeline Platform", example_multi_pipeline_platform),
        ("Dev to Prod Workflow", example_dev_to_prod_workflow),
        ("Real-time and Batch", example_realtime_and_batch),
        ("Data Lake Architecture", example_data_lake),
        ("Machine Learning Pipeline", example_ml_pipeline),
    ]

    for name, example_fn in examples:
        print(f"Testing: {name}")
        stack = example_fn()

        print(f"  ✓ Stack: {stack.name}")
        print(f"  ✓ Pipelines: {len(stack._pipelines)}")
        print(f"  ✓ Environments: {len(stack._environments)}")

        total_tasks = sum(len(p.tasks) for p in stack._pipelines.values())
        print(f"  ✓ Total tasks: {total_tasks}")

        print(f"  Pipelines:")
        for pipeline_name, pipeline in stack._pipelines.items():
            print(f"    • {pipeline_name}: {len(pipeline.tasks)} tasks")

        print()

    print("=" * 70)
    print("All integration examples validated successfully!")
    print("=" * 70)
