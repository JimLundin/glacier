"""
End-to-End Pipeline Compilation and Deployment.

This example demonstrates:
1. Defining a pipeline with datasets and tasks
2. Configuring storage and compute resources
3. Adding scheduling and monitoring
4. Compiling the pipeline to AWS Pulumi resources
5. Exporting deployable infrastructure code
6. Deploying with Pulumi CLI

Steps to deploy:
1. Run this script to generate Pulumi program
2. cd into the generated directory
3. Run: pulumi login (configure backend)
4. Run: pulumi stack init dev (create stack)
5. Run: pulumi up (deploy infrastructure)
"""

import pandas as pd
from glacier import Pipeline, Dataset, Environment
from glacier.scheduling import cron, on_update
from glacier.monitoring import monitoring, notify_email
from glacier_aws import AWSProvider, AWSCompiler

# ============================================================================
# Step 1: Define Pipeline with Datasets
# ============================================================================
print("=" * 70)
print("STEP 1: DEFINE PIPELINE")
print("=" * 70)
print()

pipeline = Pipeline(name="etl_pipeline")

# Define datasets
raw_data = Dataset(name="raw_data")
processed_data = Dataset(name="processed_data")
final_output = Dataset(name="final_output")

print("✓ Pipeline created: etl_pipeline")
print("✓ Datasets defined: raw_data, processed_data, final_output")
print()

# ============================================================================
# Step 2: Configure Environment with Storage
# ============================================================================
print("=" * 70)
print("STEP 2: CONFIGURE ENVIRONMENT")
print("=" * 70)
print()

# Create AWS environment
env = Environment(
    provider=AWSProvider(
        account="123456789012",  # Replace with your AWS account ID
        region="us-east-1"
    ),
    name="production"
)

# Configure storage for datasets (S3 buckets)
raw_storage = env.object_storage(
    name="raw-data-bucket",
    versioning=True,
    encryption=True
)

output_storage = env.object_storage(
    name="output-data-bucket",
    versioning=True,
    encryption=True
)

# Update datasets with storage
raw_data_with_storage = Dataset(
    name="raw_data",
    storage=raw_storage
)
final_output_with_storage = Dataset(
    name="final_output",
    storage=output_storage
)

print("✓ AWS environment configured")
print(f"  - Account: 123456789012")
print(f"  - Region: us-east-1")
print("✓ Storage resources created:")
print("  - raw-data-bucket (S3, versioning, encryption)")
print("  - output-data-bucket (S3, versioning, encryption)")
print()

# ============================================================================
# Step 3: Define Tasks with Scheduling and Monitoring
# ============================================================================
print("=" * 70)
print("STEP 3: DEFINE TASKS")
print("=" * 70)
print()

# Configure monitoring
pipeline_monitoring = monitoring(
    log_level="INFO",
    log_retention_days=90,
    enable_metrics=True,
    alert_on_failure=True,
    notifications=[
        notify_email("team@example.com", name="Team Email"),
    ]
)


@pipeline.task(schedule=cron("0 2 * * *"))  # Daily at 2 AM
def extract() -> raw_data:
    """
    Extract data from external API.
    Scheduled to run daily at 2 AM UTC.
    """
    print("Extracting data from API...")
    return pd.DataFrame({"id": [1, 2, 3], "value": [10, 20, 30]})


@pipeline.task(schedule=on_update(raw_data))  # Triggered on data upload
def process(data: raw_data) -> processed_data:
    """
    Process raw data when uploaded.
    Triggered when raw_data dataset is updated.
    """
    print("Processing raw data...")
    return data * 1.5


@pipeline.task()  # Manual trigger (part of DAG)
def transform(data: processed_data) -> final_output:
    """
    Transform and aggregate data.
    Runs as part of DAG when dependencies are satisfied.
    """
    print("Transforming data...")
    return data * 2


print("✓ Tasks defined:")
print("  - extract: Daily at 2 AM (cron)")
print("  - process: Event-triggered on raw_data updates")
print("  - transform: Manual (DAG execution)")
print()

# ============================================================================
# Step 4: Compile Pipeline to AWS Pulumi Resources
# ============================================================================
print("=" * 70)
print("STEP 4: COMPILE PIPELINE")
print("=" * 70)
print()

# Create AWS compiler
compiler = AWSCompiler(
    account="123456789012",  # Replace with your AWS account ID
    region="us-east-1",
    project_name="glacier-etl",
    lambda_runtime="python3.11",
    lambda_memory=512,
    lambda_timeout=300
)

print("✓ Compiler configured:")
print("  - Provider: AWS")
print("  - Region: us-east-1")
print("  - Lambda runtime: python3.11")
print("  - Lambda memory: 512 MB")
print("  - Lambda timeout: 300 seconds")
print()

print("Compiling pipeline...")
compiled = pipeline.compile(compiler)

print("✓ Compilation successful!")
print(f"  - Provider: {compiled.provider_name}")
print(f"  - Resources: {len(compiled.resources)}")
print(f"  - Tasks: {compiled.metadata.get('task_count', 0)}")
print(f"  - Datasets: {compiled.metadata.get('dataset_count', 0)}")
print()

print("Compiled resources:")
for i, resource_name in enumerate(compiled.list_resources(), 1):
    resource_def = compiled.get_resource(resource_name)
    resource_type = resource_def.get("type", "unknown")
    print(f"  {i}. {resource_name} ({resource_type})")
print()

# ============================================================================
# Step 5: Export Pulumi Program
# ============================================================================
print("=" * 70)
print("STEP 5: EXPORT PULUMI PROGRAM")
print("=" * 70)
print()

output_dir = "./pulumi_output/glacier-etl"
exported_path = compiled.export_pulumi(output_dir)

print(f"✓ Pulumi program exported to: {exported_path}")
print()
print("Generated files:")
print(f"  - {exported_path}/__main__.py (Pulumi program)")
print(f"  - {exported_path}/Pulumi.yaml (Pulumi project config)")
print(f"  - {exported_path}/requirements.txt (Python dependencies)")
print()

# ============================================================================
# Step 6: Deployment Instructions
# ============================================================================
print("=" * 70)
print("STEP 6: DEPLOY WITH PULUMI")
print("=" * 70)
print()

print("To deploy this infrastructure to AWS:")
print()
print("1. Install Pulumi CLI:")
print("   $ curl -fsSL https://get.pulumi.com | sh")
print()
print("2. Configure AWS credentials:")
print("   $ aws configure")
print()
print("3. Navigate to generated directory:")
print(f"   $ cd {exported_path}")
print()
print("4. Install Python dependencies:")
print("   $ pip install -r requirements.txt")
print()
print("5. Configure Pulumi backend (optional):")
print("   $ pulumi login  # Uses Pulumi Cloud (free tier available)")
print("   # OR for local backend:")
print("   $ pulumi login file://~/.pulumi")
print()
print("6. Create a new stack:")
print("   $ pulumi stack init dev")
print()
print("7. Preview infrastructure changes:")
print("   $ pulumi preview")
print()
print("8. Deploy infrastructure:")
print("   $ pulumi up")
print()
print("9. View deployed resources:")
print("   $ pulumi stack output")
print("   $ pulumi stack export")
print()
print("10. Destroy infrastructure (when done):")
print("    $ pulumi destroy")
print()

# ============================================================================
# Summary
# ============================================================================
print("=" * 70)
print("SUMMARY")
print("=" * 70)
print()
print("✅ Pipeline compiled successfully")
print("✅ Pulumi program generated")
print("✅ Ready for deployment")
print()
print(f"Next steps: cd {exported_path} && pulumi up")
print()
