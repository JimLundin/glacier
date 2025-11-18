"""
Stack Pattern Examples for Testing.

This module demonstrates different ways to use stacks in Glacier.
Stacks are the top-level organizational unit that can contain multiple
pipelines and environments, and are used for deployment.

This is Layer 3 - full control over infrastructure organization.
"""

import pandas as pd
from glacier import Stack, Pipeline, Dataset, Environment
from glacier_aws import AWSProvider
from glacier_gcp import GCPProvider


# =============================================================================
# Pattern 1: Implicit Stack (Uses Default)
# =============================================================================
def example_implicit_stack():
    """
    Using the default stack implicitly.

    This is Layer 1 - no stack configuration needed.
    """
    from glacier import pipeline

    # Factory function uses default stack internally
    etl = pipeline("etl")

    raw = Dataset("raw")
    processed = Dataset("processed")

    @etl.task()
    def extract() -> raw:
        return pd.DataFrame({"value": [1, 2, 3]})

    @etl.task()
    def transform(data: raw) -> processed:
        return data * 2

    return etl


# =============================================================================
# Pattern 2: Single Explicit Stack
# =============================================================================
def example_single_stack():
    """
    Explicitly creating a stack.

    This is Layer 3 - full control over stack configuration.
    """
    # Create stack explicitly
    stack = Stack(name="data-platform")

    # Create pipeline in stack
    etl = stack.pipeline("etl")

    raw = Dataset("raw")
    processed = Dataset("processed")

    @etl.task()
    def extract() -> raw:
        return pd.DataFrame({"value": [1, 2, 3]})

    @etl.task()
    def transform(data: raw) -> processed:
        return data * 2

    return stack


# =============================================================================
# Pattern 3: Stack with Multiple Pipelines
# =============================================================================
def example_stack_multiple_pipelines():
    """
    Single stack containing multiple independent pipelines.
    """
    stack = Stack(name="analytics-platform")

    # Create multiple pipelines
    customer_pipeline = stack.pipeline("customer-analytics")
    sales_pipeline = stack.pipeline("sales-analytics")
    inventory_pipeline = stack.pipeline("inventory-tracking")

    # Customer pipeline
    customer_raw = Dataset("customer_raw")
    customer_clean = Dataset("customer_clean")

    @customer_pipeline.task()
    def extract_customers() -> customer_raw:
        return pd.DataFrame({"customer_id": [1, 2, 3], "name": ["A", "B", "C"]})

    @customer_pipeline.task()
    def clean_customers(data: customer_raw) -> customer_clean:
        return data.dropna()

    # Sales pipeline
    sales_raw = Dataset("sales_raw")
    sales_aggregated = Dataset("sales_aggregated")

    @sales_pipeline.task()
    def extract_sales() -> sales_raw:
        return pd.DataFrame({"sale_id": [1, 2], "amount": [100, 200]})

    @sales_pipeline.task()
    def aggregate_sales(data: sales_raw) -> sales_aggregated:
        return pd.DataFrame({"total": [data["amount"].sum()]})

    # Inventory pipeline
    inventory_raw = Dataset("inventory_raw")
    inventory_status = Dataset("inventory_status")

    @inventory_pipeline.task()
    def extract_inventory() -> inventory_raw:
        return pd.DataFrame({"product_id": [1, 2, 3], "quantity": [10, 5, 15]})

    @inventory_pipeline.task()
    def check_status(data: inventory_raw) -> inventory_status:
        data = data.copy()
        data["status"] = data["quantity"].apply(lambda x: "low" if x < 10 else "ok")
        return data

    return stack


# =============================================================================
# Pattern 4: Stack with Single Environment
# =============================================================================
def example_stack_single_environment():
    """
    Stack with one environment for all resources.
    """
    stack = Stack(name="prod-stack")

    # Create environment in stack
    prod_env = stack.environment(
        provider=AWSProvider(account="123456789012", region="us-east-1"),
        name="production"
    )

    # Create pipeline
    etl = stack.pipeline("etl")

    raw = Dataset("raw")
    processed = Dataset("processed")

    @etl.task(environment=prod_env)
    def extract() -> raw:
        return pd.DataFrame({"value": [1, 2, 3]})

    @etl.task(environment=prod_env)
    def transform(data: raw) -> processed:
        return data * 2

    return stack


# =============================================================================
# Pattern 5: Stack with Multiple Environments
# =============================================================================
def example_stack_multiple_environments():
    """
    Single stack with multiple environments.

    Typical for deploying same pipelines across dev/staging/prod.
    """
    stack = Stack(name="multi-env-stack")

    # Create multiple environments in stack
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

    # Create pipeline
    etl = stack.pipeline("etl")

    raw = Dataset("raw")
    processed = Dataset("processed")
    final = Dataset("final")

    @etl.task(environment=dev)
    def extract() -> raw:
        return pd.DataFrame({"value": [1, 2, 3]})

    @etl.task(environment=staging)
    def transform(data: raw) -> processed:
        return data * 2

    @etl.task(environment=prod)
    def load(data: processed) -> final:
        return data.copy()

    return stack


# =============================================================================
# Pattern 6: Multi-Cloud Stack
# =============================================================================
def example_multi_cloud_stack():
    """
    Stack with environments from different cloud providers.

    Demonstrates true provider-agnostic design.
    """
    stack = Stack(name="multi-cloud")

    # AWS environment
    aws_env = stack.environment(
        provider=AWSProvider(account="123456789012", region="us-east-1"),
        name="aws"
    )

    # GCP environment
    gcp_env = stack.environment(
        provider=GCPProvider(project="my-project", region="us-central1"),
        name="gcp"
    )

    # Create pipeline
    cross_cloud = stack.pipeline("cross-cloud-etl")

    aws_data = Dataset("aws_data")
    gcp_data = Dataset("gcp_data")
    combined = Dataset("combined")

    @cross_cloud.task(environment=aws_env)
    def extract_from_aws() -> aws_data:
        """Runs on AWS."""
        return pd.DataFrame({"source": ["aws"], "value": [100]})

    @cross_cloud.task(environment=gcp_env)
    def process_on_gcp(data: aws_data) -> gcp_data:
        """Runs on GCP, reads AWS data."""
        gcp_result = data.copy()
        gcp_result["processed_by"] = "gcp"
        return gcp_result

    @cross_cloud.task(environment=aws_env)
    def combine_back_on_aws(data: gcp_data) -> combined:
        """Runs on AWS, reads GCP result."""
        return data.copy()

    return stack


# =============================================================================
# Pattern 7: Stack with Shared Resources
# =============================================================================
def example_stack_shared_resources():
    """
    Stack where multiple pipelines share resources.
    """
    stack = Stack(name="shared-resources")

    # Create environment
    env = stack.environment(
        provider=AWSProvider(account="123456789012", region="us-east-1"),
        name="prod"
    )

    # Create shared storage
    shared_storage = env.object_storage("shared-data")

    # First pipeline
    pipeline_1 = stack.pipeline("pipeline-1")
    data_1 = Dataset("data_1", storage=shared_storage)

    @pipeline_1.task(environment=env)
    def produce_data_1() -> data_1:
        return pd.DataFrame({"pipeline": [1], "value": [100]})

    # Second pipeline
    pipeline_2 = stack.pipeline("pipeline-2")
    data_2 = Dataset("data_2", storage=shared_storage)

    @pipeline_2.task(environment=env)
    def produce_data_2() -> data_2:
        return pd.DataFrame({"pipeline": [2], "value": [200]})

    # Third pipeline consumes from both
    pipeline_3 = stack.pipeline("pipeline-3")
    combined = Dataset("combined")

    @pipeline_3.task(environment=env)
    def combine(d1: data_1, d2: data_2) -> combined:
        return pd.concat([d1, d2], ignore_index=True)

    return stack


# =============================================================================
# Pattern 8: Hierarchical Stack Organization
# =============================================================================
def example_hierarchical_stack():
    """
    Stack organized by business domain hierarchy.
    """
    stack = Stack(name="enterprise-platform")

    # Create environment
    env = stack.environment(
        provider=AWSProvider(account="123456789012", region="us-east-1"),
        name="prod"
    )

    # Customer domain
    customer_ingestion = stack.pipeline("customer.ingestion")
    customer_enrichment = stack.pipeline("customer.enrichment")

    # Sales domain
    sales_ingestion = stack.pipeline("sales.ingestion")
    sales_analytics = stack.pipeline("sales.analytics")

    # Cross-domain
    reporting = stack.pipeline("reporting.executive")

    # Define a simple pipeline in each domain
    customer_raw = Dataset("customer.raw")
    customer_enriched = Dataset("customer.enriched")

    @customer_ingestion.task(environment=env)
    def ingest_customers() -> customer_raw:
        return pd.DataFrame({"customer_id": [1, 2, 3]})

    @customer_enrichment.task(environment=env)
    def enrich_customers(raw: customer_raw) -> customer_enriched:
        return raw.copy()

    return stack


# =============================================================================
# Pattern 9: Stack Compilation
# =============================================================================
def example_stack_compilation():
    """
    Stack that will be compiled for deployment.
    """
    stack = Stack(name="deployable-stack")

    # Create environment
    env = stack.environment(
        provider=AWSProvider(account="123456789012", region="us-east-1"),
        name="prod"
    )

    # Create storage
    storage = env.object_storage("data-bucket")

    # Create pipeline
    etl = stack.pipeline("etl")

    raw = Dataset("raw", storage=storage)
    processed = Dataset("processed", storage=storage)

    @etl.task(environment=env)
    def extract() -> raw:
        return pd.DataFrame({"value": [1, 2, 3]})

    @etl.task(environment=env)
    def transform(data: raw) -> processed:
        return data * 2

    # Compile the stack (prepares for deployment)
    # compiled = stack.compile()
    # Note: Actual compilation commented out for testing

    return stack


# =============================================================================
# Pattern 10: Empty Stack (Minimal)
# =============================================================================
def example_empty_stack():
    """
    Empty stack - minimal configuration.
    """
    stack = Stack(name="minimal-stack")
    return stack


# =============================================================================
# Test Runner
# =============================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("STACK PATTERN EXAMPLES")
    print("=" * 70)
    print()

    examples = [
        ("Implicit Stack", example_implicit_stack),
        ("Single Explicit Stack", example_single_stack),
        ("Stack with Multiple Pipelines", example_stack_multiple_pipelines),
        ("Stack with Single Environment", example_stack_single_environment),
        ("Stack with Multiple Environments", example_stack_multiple_environments),
        ("Multi-Cloud Stack", example_multi_cloud_stack),
        ("Stack with Shared Resources", example_stack_shared_resources),
        ("Hierarchical Stack Organization", example_hierarchical_stack),
        ("Stack Compilation", example_stack_compilation),
        ("Empty Stack", example_empty_stack),
    ]

    for name, example_fn in examples:
        print(f"Testing: {name}")

        result = example_fn()

        if isinstance(result, Stack):
            stack = result
            print(f"  ✓ Stack: {stack.name}")
            print(f"  ✓ Pipelines: {len(stack._pipelines)}")
            print(f"  ✓ Environments: {len(stack._environments)}")

            if stack._pipelines:
                print(f"  Pipeline names:")
                for pipeline_name in stack._pipelines.keys():
                    print(f"    • {pipeline_name}")

            if stack._environments:
                print(f"  Environment names:")
                for env_name in stack._environments.keys():
                    print(f"    • {env_name}")
        else:
            # For implicit stack case (returns pipeline)
            pipeline = result
            print(f"  ✓ Pipeline: {pipeline.name}")
            print(f"  ✓ Tasks: {len(pipeline.tasks)}")

        print()

    print("=" * 70)
    print("All stack patterns validated successfully!")
    print("=" * 70)
