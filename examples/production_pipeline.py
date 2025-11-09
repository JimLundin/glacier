"""
Demonstrates production-ready pipeline features:
- Secrets management for API keys and credentials
- Scheduling for automated execution
- Monitoring with logging, metrics, and alerts

This example shows how to build a real-world ETL pipeline with
proper observability and security practices.
"""

import pandas as pd
from glacier import Pipeline, Dataset, Environment
from glacier.scheduling import cron, on_update, manual
from glacier.monitoring import monitoring, notify_email, notify_slack
from glacier.secrets import secret

# ============================================================================
# Setup: Monitoring and Alerting
# ============================================================================
print("=" * 70)
print("PRODUCTION PIPELINE SETUP")
print("=" * 70)
print()

# Configure monitoring with alerts
pipeline_monitoring = monitoring(
    log_level="INFO",
    log_retention_days=90,
    enable_metrics=True,
    alert_on_failure=True,
    notifications=[
        notify_email("team@example.com", name="Team Email"),
        notify_slack(
            "https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
            name="Engineering Slack",
        ),
    ],
)

print(f"✓ Monitoring configured: {pipeline_monitoring}")
print(f"  - Log level: INFO, retention: 90 days")
print(f"  - Metrics: enabled")
print(f"  - Alerts: 2 notification channels")
print()

# ============================================================================
# Define Pipeline with Monitoring
# ============================================================================

pipeline = Pipeline(name="production_etl")

# Define datasets
raw_data = Dataset(name="raw_data")
api_data = Dataset(name="api_data")
validated_data = Dataset(name="validated_data")
enriched_data = Dataset(name="enriched_data")
final_output = Dataset(name="final_output")

print("✓ Pipeline and datasets defined")
print()

# ============================================================================
# Layer 1: Simple Tasks with Scheduling
# ============================================================================
print("=" * 70)
print("TASK DEFINITIONS WITH SCHEDULING")
print("=" * 70)
print()


@pipeline.task(schedule=cron("0 2 * * *"))  # Daily at 2 AM
def extract_data() -> raw_data:
    """
    Extract data from external API.
    Scheduled to run daily at 2 AM UTC.
    """
    print("Extracting data from API...")
    # In real pipeline, would use API credentials from secrets
    return pd.DataFrame({"id": [1, 2, 3], "value": [10, 20, 30]})


print("✓ extract_data: Daily at 2 AM UTC")
print('  Schedule: cron("0 2 * * *")')
print()


@pipeline.task(schedule=on_update(raw_data, filter_pattern="*.csv"))
def process_uploaded_file(data: raw_data) -> api_data:
    """
    Process files when raw_data dataset is updated.
    Triggered when CSV files are uploaded to raw_data storage.
    Demonstrates selective triggering - only triggers on raw_data updates.
    """
    print(f"Processing updated raw_data...")
    # In real pipeline, data would be the updated dataset
    return data * 1.5


print("✓ process_uploaded_file: Event-triggered on raw_data updates")
print('  Trigger: on_update(raw_data, filter_pattern="*.csv")')
print()


@pipeline.task()  # Manual trigger by default
def validate(data: api_data) -> validated_data:
    """
    Validate data quality.
    Manual trigger - runs as part of DAG when dependencies satisfied.
    """
    print("Validating data...")
    # Data quality checks
    assert not data.empty, "Data cannot be empty"
    assert "id" in data.columns, "Missing required column: id"
    return data


print("✓ validate: Manual (runs as part of DAG)")
print()


@pipeline.task(schedule=cron("0 */6 * * *"))  # Every 6 hours
def enrich(data: validated_data) -> enriched_data:
    """
    Enrich data with external sources.
    Scheduled to run every 6 hours.
    """
    print("Enriching data...")
    data["enriched"] = True
    return data


print("✓ enrich: Every 6 hours")
print('  Schedule: cron("0 */6 * * *")')
print()


@pipeline.task()
def transform(data: enriched_data) -> final_output:
    """
    Final transformation and aggregation.
    Manual trigger - runs as part of DAG.
    """
    print("Transforming data...")
    return data * 2


print("✓ transform: Manual (runs as part of DAG)")
print()

# ============================================================================
# Additional Scheduling Patterns (for reference)
# ============================================================================
print("=" * 70)
print("EVENT TRIGGER PATTERNS")
print("=" * 70)
print()

print("Example scheduling patterns:")
print()
print("# Pattern 1: Trigger on specific dataset")
print("@pipeline.task(schedule=on_update(raw_data))")
print("def process(data: raw_data, ref: reference_data) -> output:")
print("    # Triggers ONLY when raw_data updates")
print("    # Changes to reference_data do NOT trigger this task")
print()
print("# Pattern 2: Trigger on multiple datasets")
print("@pipeline.task(schedule=on_update([raw_data, api_data]))")
print("def merge(data1: raw_data, data2: api_data, static: static_data) -> output:")
print("    # Triggers when EITHER raw_data OR api_data updates")
print("    # Changes to static_data do NOT trigger this task")
print()
print("# Pattern 3: Trigger on ANY input dataset (default)")
print("@pipeline.task(schedule=on_update())")
print("def process_any(data1: raw_data, data2: api_data) -> output:")
print("    # Triggers when ANY input dataset updates")
print("    # Equivalent to on_update([raw_data, api_data])")
print()

# ============================================================================
# Layer 2: Environment with Secrets
# ============================================================================
print("=" * 70)
print("ENVIRONMENT WITH SECRETS")
print("=" * 70)
print()

print("Example: Using secrets in production environment")
print()
print("```python")
print("from glacier import Environment")
print("from glacier_aws import AWSProvider")
print()
print("# Setup environment with provider")
print("env = Environment(")
print('    provider=AWSProvider(account="123456789012", region="us-east-1"),')
print('    name="prod"')
print(")")
print()
print("# Create secrets for sensitive data")
print('db_password = env.secret(name="db_password", secret_string="***")')
print('api_key = env.secret(name="external_api_key", secret_string="***")')
print()
print("# Use secrets in storage configuration")
print("database = env.database(")
print('    name="warehouse",')
print('    engine="postgres",')
print("    master_password=db_password,")
print(")")
print()
print("# Tasks can reference secrets")
print("@pipeline.task()")
print("def fetch_from_api(api_key: api_key) -> data:")
print("    # Runtime injects actual secret value")
print("    response = requests.get(url, headers={'Authorization': api_key})")
print("    return response.json()")
print("```")
print()

# ============================================================================
# Task-Level Monitoring Overrides
# ============================================================================
print("=" * 70)
print("TASK-LEVEL MONITORING")
print("=" * 70)
print()

print("Example: Override monitoring for specific tasks")
print()
print("```python")
print("# Debug logging for troublesome task")
print("@pipeline.task(")
print('    monitoring=monitoring(log_level="DEBUG", log_retention_days=7)')
print(")")
print("def debug_task() -> data:")
print("    ...")
print()
print("# Alert on slow execution")
print("@pipeline.task(")
print("    monitoring=monitoring(")
print("        alert_on_failure=True,")
print("        notifications=[notify_email('critical@example.com')]")
print("    )")
print(")")
print("def critical_task() -> data:")
print("    ...")
print("```")
print()

# ============================================================================
# Run Locally for Development
# ============================================================================
print("=" * 70)
print("LOCAL EXECUTION")
print("=" * 70)
print()

from glacier_local import LocalExecutor

print("Running pipeline locally (development mode)...")
print()

# For demo, we'll just run the manual tasks
results = LocalExecutor().execute(pipeline)

print("Results:")
print(f"  validated_data: {results['validated_data'].shape}")
print(f"  final_output: {results['final_output'].shape}")
print()

# ============================================================================
# Summary
# ============================================================================
print("=" * 70)
print("SUMMARY: PRODUCTION FEATURES")
print("=" * 70)
print()
print("1. SECRETS")
print("   ✓ Secure credential storage")
print("   ✓ env.secret() creates secrets in provider")
print("   ✓ Reference in tasks and storage configs")
print()
print("2. SCHEDULING")
print("   ✓ Cron-based: cron('0 2 * * *')")
print("   ✓ Event-based: on_update(dataset, filter=...)")
print("   ✓ Dataset-centric triggers:")
print("     - on_update(raw_data) = trigger on specific dataset")
print("     - on_update([ds1, ds2]) = trigger on multiple datasets")
print("     - on_update() = trigger on ANY input dataset")
print("   ✓ Manual: default for DAG tasks")
print()
print("3. MONITORING")
print("   ✓ Logging with retention policies")
print("   ✓ Metrics collection (duration, success rate, etc.)")
print("   ✓ Alerts via email, Slack, webhooks")
print("   ✓ Pipeline-level and task-level configs")
print()
print("All features are provider-agnostic!")
print("Switch AWS → Azure → GCP by changing provider only.")
print()
