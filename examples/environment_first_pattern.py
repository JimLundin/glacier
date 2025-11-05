"""
Example: Environment-First Pattern with Glacier

This example demonstrates the recommended environment-first pattern using
dependency injection and explicit configuration.

The environment-first pattern provides:
- Explicit dependencies (configuration flows through the system)
- Environment isolation (dev, staging, prod environments coexist)
- Type safety (full IDE autocomplete and type checking)
- Testability (easy to inject mock providers)
"""

from glacier import GlacierEnv
from glacier.providers import AWSProvider, LocalProvider
from glacier.config import AwsConfig, LocalConfig
import polars as pl

# ============================================================================
# 1. CONFIGURATION: Define provider config
# ============================================================================

# Production AWS configuration
aws_config = AwsConfig(
    region="us-east-1",
    profile="production",
    tags={
        "environment": "production",
        "managed_by": "glacier",
        "team": "data-engineering",
    },
)

# Development local configuration
local_config = LocalConfig(
    base_path="./data",
    create_dirs=True,
)

# ============================================================================
# 2. PROVIDER: Create providers with config (DI)
# ============================================================================

prod_provider = AWSProvider(config=aws_config)
dev_provider = LocalProvider(config=local_config)

# ============================================================================
# 3. ENVIRONMENT: Create environments with providers
# ============================================================================

# Production environment
prod_env = GlacierEnv(provider=prod_provider, name="production")

# Development environment
dev_env = GlacierEnv(provider=dev_provider, name="development")

# Alternative: Use provider.env() factory method
# prod_env = prod_provider.env(name="production")
# dev_env = dev_provider.env(name="development")

# ============================================================================
# 4. TASKS: Define tasks bound to environment
# ============================================================================

# Define tasks for production environment
@prod_env.task()
def extract_sales(source) -> pl.LazyFrame:
    """Extract sales data from source."""
    return source.scan()


@prod_env.task()
def extract_customers(source) -> pl.LazyFrame:
    """Extract customer data from source."""
    return source.scan()


@prod_env.task()
def join_data(sales: pl.LazyFrame, customers: pl.LazyFrame) -> pl.LazyFrame:
    """Join sales with customer information."""
    return sales.join(customers, on="customer_id", how="left")


@prod_env.task(timeout=600, retries=3)
def aggregate_by_segment(df: pl.LazyFrame) -> pl.DataFrame:
    """Aggregate sales by customer segment with retry logic."""
    return (
        df.group_by("customer_segment")
        .agg(
            [
                pl.sum("amount").alias("total_revenue"),
                pl.count("order_id").alias("order_count"),
                pl.mean("amount").alias("avg_order_value"),
            ]
        )
        .collect()
    )


# Same tasks for development environment
@dev_env.task()
def extract_sales_dev(source) -> pl.LazyFrame:
    """Extract sales data from source (dev)."""
    return source.scan()


@dev_env.task()
def extract_customers_dev(source) -> pl.LazyFrame:
    """Extract customer data from source (dev)."""
    return source.scan()


@dev_env.task()
def join_data_dev(sales: pl.LazyFrame, customers: pl.LazyFrame) -> pl.LazyFrame:
    """Join sales with customer information (dev)."""
    return sales.join(customers, on="customer_id", how="left")


@dev_env.task()
def aggregate_by_segment_dev(df: pl.LazyFrame) -> pl.DataFrame:
    """Aggregate sales by customer segment (dev)."""
    return (
        df.group_by("customer_segment")
        .agg(
            [
                pl.sum("amount").alias("total_revenue"),
                pl.count("order_id").alias("order_count"),
                pl.mean("amount").alias("avg_order_value"),
            ]
        )
        .collect()
    )


# ============================================================================
# 5. PIPELINE: Wire everything together
# ============================================================================


@prod_env.pipeline(name="sales_analysis_prod")
def sales_analysis_pipeline():
    """
    Production sales analysis pipeline.

    Resources created with provider factory pattern.
    Tasks wired via explicit data flow.
    """
    # Create resources using environment's provider
    sales_bucket = prod_env.provider.bucket(
        "sales-data", path="transactions.parquet"
    )

    customer_bucket = prod_env.provider.bucket(
        "customer-data", path="customers.parquet"
    )

    # Data flow defines dependencies
    sales_df = extract_sales(sales_bucket)
    customer_df = extract_customers(customer_bucket)
    joined_df = join_data(sales_df, customer_df)
    result = aggregate_by_segment(joined_df)

    return result


@dev_env.pipeline(name="sales_analysis_dev")
def sales_analysis_pipeline_dev():
    """
    Development sales analysis pipeline.

    Uses local provider for testing.
    """
    # Create resources using environment's provider (local in this case)
    sales_bucket = dev_env.provider.bucket("sales-data", path="transactions.parquet")

    customer_bucket = dev_env.provider.bucket(
        "customer-data", path="customers.parquet"
    )

    # Data flow
    sales_df = extract_sales_dev(sales_bucket)
    customer_df = extract_customers_dev(customer_bucket)
    joined_df = join_data_dev(sales_df, customer_df)
    result = aggregate_by_segment_dev(joined_df)

    return result


# ============================================================================
# 6. REGISTRY PATTERN: Optional centralized resource management
# ============================================================================


def demo_registry_pattern():
    """
    Demonstrate environment registry for shared resources.
    """
    # Create environment
    from glacier.config import AwsConfig

    provider = AWSProvider(config=AwsConfig(region="us-east-1"))
    env = GlacierEnv(provider=provider, name="registry-demo")

    # Register shared resources
    env.register("sales_raw", env.provider.bucket("sales", path="raw/data.parquet"))
    env.register(
        "sales_processed", env.provider.bucket("sales", path="processed/data.parquet")
    )
    env.register("customers", env.provider.bucket("customers", path="data.parquet"))

    # Tasks can retrieve from registry
    @env.task()
    def load_sales() -> pl.LazyFrame:
        """Extract sales from registry."""
        source = env.get("sales_raw")
        return source.scan()

    @env.task()
    def load_customers() -> pl.LazyFrame:
        """Extract customers from registry."""
        source = env.get("customers")
        return source.scan()

    @env.task()
    def save_results(df: pl.LazyFrame) -> None:
        """Save results using registry."""
        target = env.get("sales_processed")
        # In real implementation, would write to target
        print(f"Saving to {target}")

    print(f"Registered resources: {env.list_resources()}")
    print(f"Environment state: {env.get_state()}")


# ============================================================================
# 7. EXECUTION: Run in different modes
# ============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("Glacier Environment-First Pattern Demo")
    print("=" * 80)

    # Show production environment state
    print("\nProduction Environment:")
    print(prod_env)
    print(f"State: {prod_env.get_state()}")

    # Show development environment state
    print("\nDevelopment Environment:")
    print(dev_env)
    print(f"State: {dev_env.get_state()}")

    # Demo registry pattern
    print("\n" + "=" * 80)
    print("Registry Pattern Demo")
    print("=" * 80)
    demo_registry_pattern()

    print("\n" + "=" * 80)
    print("Execution Examples")
    print("=" * 80)

    # Example 1: Local execution (if you have test data)
    # result = sales_analysis_pipeline_dev.run(mode="local")
    # print(result)

    # Example 2: Analyze pipeline structure
    # analysis = sales_analysis_pipeline.run(mode="analyze")
    # print(f"Tasks: {analysis['tasks']}")
    # print(f"DAG: {analysis['dag']}")

    # Example 3: Generate infrastructure
    # infra = sales_analysis_pipeline.run(
    #     mode="generate",
    #     output_dir="./terraform/production"
    # )
    # print(f"Generated: {infra['files']}")

    print("\nDemo complete! Environment-first pattern configured successfully.")
    print("\nKey Benefits:")
    print("  ✓ Explicit dependencies - clear configuration injection")
    print("  ✓ Environment isolation - dev and prod coexist")
    print("  ✓ Type safety - full IDE support")
    print("  ✓ Cloud portability - swap providers easily")
    print("  ✓ Testability - easy to mock providers")
