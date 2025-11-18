"""
Environment and Provider Pattern Examples for Testing.

This module demonstrates different ways to use environments and providers
in Glacier. Environments provide provider-agnostic resource creation and
task execution configuration.
"""

import pandas as pd
from glacier import Pipeline, Dataset, Environment
from glacier_aws import AWSProvider


# =============================================================================
# Pattern 1: Implicit Environment (Uses Defaults)
# =============================================================================
def example_implicit_environment():
    """
    Pipeline using default environment (no explicit configuration).

    This is Layer 1 - simplest pattern for local development.
    """
    pipeline = Pipeline(name="implicit_env")

    raw = Dataset("raw")
    processed = Dataset("processed")

    @pipeline.task()
    def extract() -> raw:
        """Uses default environment."""
        return pd.DataFrame({"value": [1, 2, 3]})

    @pipeline.task()
    def transform(data: raw) -> processed:
        """Uses default environment."""
        return data * 2

    return pipeline


# =============================================================================
# Pattern 2: Single Explicit Environment
# =============================================================================
def example_single_environment():
    """
    Pipeline with a single explicit environment.

    This is Layer 2 - provider-agnostic configuration.
    """
    pipeline = Pipeline(name="single_env")

    # Create environment
    aws_prod = Environment(
        provider=AWSProvider(account="123456789012", region="us-east-1"),
        name="production"
    )

    raw = Dataset("raw")
    processed = Dataset("processed")

    @pipeline.task(environment=aws_prod)
    def extract() -> raw:
        """Runs in production environment."""
        return pd.DataFrame({"value": [1, 2, 3]})

    @pipeline.task(environment=aws_prod)
    def transform(data: raw) -> processed:
        """Runs in production environment."""
        return data * 2

    return pipeline, aws_prod


# =============================================================================
# Pattern 3: Multiple Environments (Dev/Prod)
# =============================================================================
def example_multiple_environments():
    """
    Pipeline with multiple environments for different stages.
    """
    pipeline = Pipeline(name="multi_env")

    # Development environment
    dev = Environment(
        provider=AWSProvider(account="111111111111", region="us-west-2"),
        name="development"
    )

    # Production environment
    prod = Environment(
        provider=AWSProvider(account="222222222222", region="us-east-1"),
        name="production"
    )

    raw = Dataset("raw")
    processed = Dataset("processed")
    final = Dataset("final")

    @pipeline.task(environment=dev)
    def extract() -> raw:
        """Extract runs in dev."""
        return pd.DataFrame({"value": [1, 2, 3]})

    @pipeline.task(environment=dev)
    def transform(data: raw) -> processed:
        """Transform runs in dev."""
        return data * 2

    @pipeline.task(environment=prod)
    def load(data: processed) -> final:
        """Load runs in prod."""
        return data.copy()

    return pipeline, dev, prod


# =============================================================================
# Pattern 4: Environment with Storage Resources
# =============================================================================
def example_environment_with_storage():
    """
    Environment used to create storage resources.
    """
    pipeline = Pipeline(name="env_storage")

    # Create environment
    env = Environment(
        provider=AWSProvider(account="123456789012", region="us-east-1"),
        name="prod"
    )

    # Create storage using environment (provider-agnostic!)
    raw_storage = env.object_storage("raw-data")
    processed_storage = env.object_storage("processed-data")

    # Attach storage to datasets
    raw = Dataset("raw", storage=raw_storage)
    processed = Dataset("processed", storage=processed_storage)

    @pipeline.task(environment=env)
    def extract() -> raw:
        """Output stored in raw-data bucket."""
        return pd.DataFrame({"value": [1, 2, 3]})

    @pipeline.task(environment=env)
    def transform(data: raw) -> processed:
        """Output stored in processed-data bucket."""
        return data * 2

    return pipeline, env


# =============================================================================
# Pattern 5: Environment with Database Resources
# =============================================================================
def example_environment_with_database():
    """
    Environment used to create database resources.
    """
    pipeline = Pipeline(name="env_database")

    env = Environment(
        provider=AWSProvider(account="123456789012", region="us-east-1"),
        name="prod"
    )

    # Create database using environment
    db = env.database(
        name="analytics-db",
        engine="postgres",
        instance_class="db.t3.micro"
    )

    source = Dataset("source")
    loaded = Dataset("loaded")

    @pipeline.task(environment=env)
    def extract() -> source:
        """Extract data."""
        return pd.DataFrame({"id": [1, 2, 3], "value": [10, 20, 30]})

    @pipeline.task(environment=env)
    def load_to_db(data: source) -> loaded:
        """Load to database (conceptual)."""
        # In real implementation, would use db connection
        print(f"Loading {len(data)} rows to {db}")
        return data

    return pipeline, env, db


# =============================================================================
# Pattern 6: Environment with Secrets
# =============================================================================
def example_environment_with_secrets():
    """
    Environment used to manage secrets.
    """
    pipeline = Pipeline(name="env_secrets")

    env = Environment(
        provider=AWSProvider(account="123456789012", region="us-east-1"),
        name="prod"
    )

    # Create secrets using environment
    api_key = env.secret(name="external_api_key", secret_string="secret_value_123")
    db_password = env.secret(name="db_password", secret_string="super_secret")

    source = Dataset("source")
    processed = Dataset("processed")

    @pipeline.task(environment=env)
    def extract_from_api() -> source:
        """Uses API key secret (conceptual)."""
        # In real implementation, would access api_key at runtime
        print(f"Using API key from secret: {api_key}")
        return pd.DataFrame({"value": [1, 2, 3]})

    @pipeline.task(environment=env)
    def store_in_db(data: source) -> processed:
        """Uses database password secret (conceptual)."""
        # In real implementation, would access db_password at runtime
        print(f"Using DB password from secret: {db_password}")
        return data

    return pipeline, env


# =============================================================================
# Pattern 7: Mixed Environment and Default
# =============================================================================
def example_mixed_environment():
    """
    Some tasks use explicit environment, others use default.
    """
    pipeline = Pipeline(name="mixed_env")

    # Only create environment for production tasks
    prod = Environment(
        provider=AWSProvider(account="123456789012", region="us-east-1"),
        name="production"
    )

    raw = Dataset("raw")
    processed = Dataset("processed")
    final = Dataset("final")

    @pipeline.task()
    def extract() -> raw:
        """Uses default environment (local)."""
        return pd.DataFrame({"value": [1, 2, 3]})

    @pipeline.task()
    def transform(data: raw) -> processed:
        """Uses default environment (local)."""
        return data * 2

    @pipeline.task(environment=prod)
    def load_to_prod(data: processed) -> final:
        """Uses production environment (AWS)."""
        return data.copy()

    return pipeline, prod


# =============================================================================
# Pattern 8: Environment with Tags
# =============================================================================
def example_environment_tags():
    """
    Environment with metadata tags for resource organization.
    """
    pipeline = Pipeline(name="env_tags")

    # Environment with tags (tags automatically added to resources)
    env = Environment(
        provider=AWSProvider(
            account="123456789012",
            region="us-east-1",
            tags={
                "Team": "DataEngineering",
                "CostCenter": "Analytics",
                "Environment": "Production"
            }
        ),
        name="production"
    )

    raw = Dataset("raw")
    processed = Dataset("processed")

    @pipeline.task(environment=env)
    def extract() -> raw:
        """Resources created will have environment tags."""
        return pd.DataFrame({"value": [1, 2, 3]})

    @pipeline.task(environment=env)
    def transform(data: raw) -> processed:
        """Resources created will have environment tags."""
        return data * 2

    return pipeline, env


# =============================================================================
# Pattern 9: Environment Per Region
# =============================================================================
def example_multi_region_environments():
    """
    Different environments for different regions.
    """
    pipeline = Pipeline(name="multi_region")

    # US East environment
    us_east = Environment(
        provider=AWSProvider(account="123456789012", region="us-east-1"),
        name="us-east-prod"
    )

    # US West environment
    us_west = Environment(
        provider=AWSProvider(account="123456789012", region="us-west-2"),
        name="us-west-prod"
    )

    # EU environment
    eu_central = Environment(
        provider=AWSProvider(account="123456789012", region="eu-central-1"),
        name="eu-central-prod"
    )

    source = Dataset("source")
    us_data = Dataset("us_data")
    eu_data = Dataset("eu_data")

    @pipeline.task(environment=us_east)
    def extract_us_east() -> source:
        """Extract in US East."""
        return pd.DataFrame({"region": ["us-east"], "value": [100]})

    @pipeline.task(environment=us_west)
    def process_us_west(data: source) -> us_data:
        """Process in US West."""
        return data * 2

    @pipeline.task(environment=eu_central)
    def process_eu(data: source) -> eu_data:
        """Process in EU."""
        return data * 3

    return pipeline, us_east, us_west, eu_central


# =============================================================================
# Pattern 10: Environment Isolation (Different Accounts)
# =============================================================================
def example_account_isolation():
    """
    Environments in different AWS accounts for isolation.
    """
    pipeline = Pipeline(name="account_isolation")

    # Development account
    dev_account = Environment(
        provider=AWSProvider(account="111111111111", region="us-east-1"),
        name="dev-account"
    )

    # Staging account
    staging_account = Environment(
        provider=AWSProvider(account="222222222222", region="us-east-1"),
        name="staging-account"
    )

    # Production account
    prod_account = Environment(
        provider=AWSProvider(account="333333333333", region="us-east-1"),
        name="prod-account"
    )

    raw = Dataset("raw")
    processed = Dataset("processed")
    final = Dataset("final")

    @pipeline.task(environment=dev_account)
    def extract() -> raw:
        """Runs in dev account."""
        return pd.DataFrame({"value": [1, 2, 3]})

    @pipeline.task(environment=staging_account)
    def transform(data: raw) -> processed:
        """Runs in staging account."""
        return data * 2

    @pipeline.task(environment=prod_account)
    def load(data: processed) -> final:
        """Runs in production account."""
        return data.copy()

    return pipeline, dev_account, staging_account, prod_account


# =============================================================================
# Test Runner
# =============================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("ENVIRONMENT PATTERN EXAMPLES")
    print("=" * 70)
    print()

    examples = [
        ("Implicit Environment", example_implicit_environment, 1),
        ("Single Explicit Environment", example_single_environment, 2),
        ("Multiple Environments (Dev/Prod)", example_multiple_environments, 3),
        ("Environment with Storage", example_environment_with_storage, 2),
        ("Environment with Database", example_environment_with_database, 3),
        ("Environment with Secrets", example_environment_with_secrets, 2),
        ("Mixed Environment", example_mixed_environment, 2),
        ("Environment Tags", example_environment_tags, 2),
        ("Multi-Region Environments", example_multi_region_environments, 4),
        ("Account Isolation", example_account_isolation, 4),
    ]

    for name, example_fn, expected_returns in examples:
        print(f"Testing: {name}")

        result = example_fn()

        if expected_returns == 1:
            pipeline = result
            print(f"  ✓ Pipeline: {pipeline.name}")
            print(f"  ✓ Tasks: {len(pipeline.tasks)}")
        elif expected_returns == 2:
            pipeline, env = result
            print(f"  ✓ Pipeline: {pipeline.name}")
            print(f"  ✓ Environment: {env.name}")
            print(f"  ✓ Tasks: {len(pipeline.tasks)}")
        elif expected_returns == 3:
            pipeline, env, resource = result
            print(f"  ✓ Pipeline: {pipeline.name}")
            print(f"  ✓ Environment: {env.name}")
            print(f"  ✓ Resource created: {resource}")
            print(f"  ✓ Tasks: {len(pipeline.tasks)}")
        elif expected_returns == 4:
            pipeline = result[0]
            envs = result[1:]
            print(f"  ✓ Pipeline: {pipeline.name}")
            print(f"  ✓ Environments: {len(envs)}")
            for env in envs:
                print(f"    • {env.name}")
            print(f"  ✓ Tasks: {len(pipeline.tasks)}")

        print()

    print("=" * 70)
    print("All environment patterns validated successfully!")
    print("=" * 70)
