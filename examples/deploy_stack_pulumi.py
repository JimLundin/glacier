"""
Stack-Based Multi-Cloud Deployment with Pulumi.

This is the correct model for Glacier deployments:
- Stack is the compilation unit (not individual pipelines)
- Environments create infrastructure resources immediately (Pulumi resources)
- Pipelines define compute logic
- Stack compilation creates compute and orchestration

This example demonstrates:
1. Creating a stack with multiple environments (AWS, GCP)
2. Infrastructure resources created via environments
3. Shared resources (databases, secrets) used across pipelines
4. Multiple pipelines in the same stack
5. Cross-cloud data flows

To deploy:
1. Install: pip install pulumi pulumi-aws pulumi-gcp glacier-pipeline
2. Configure AWS and GCP credentials
3. Run: pulumi up
"""

from glacier import Stack, Dataset
from glacier_aws import AWSProvider
# from glacier_gcp import GCPProvider  # When implemented

# ============================================================================
# Create Stack (the compilation unit)
# ============================================================================

stack = Stack(name="data-platform")

# ============================================================================
# Setup Environments
# ============================================================================

# AWS environment for data ingestion
aws_env = stack.environment(
    provider=AWSProvider(
        account="123456789012",
        region="us-east-1"
    ),
    name="aws-prod"
)

# GCP environment for data processing
# gcp_env = stack.environment(
#     provider=GCPProvider(
#         project="my-project",
#         region="us-central1"
#     ),
#     name="gcp-prod"
# )

# ============================================================================
# Create Infrastructure Resources (via environments)
# ============================================================================

# These create Pulumi resources IMMEDIATELY (no compilation needed)
# They're automatically tracked by the Pulumi runtime

# Shared analytics database (used by multiple pipelines)
analytics_db = aws_env.database(
    name="analytics",
    engine="postgres"
)
stack.track_resource("analytics-db", analytics_db)

# S3 storage for raw data
raw_storage = aws_env.object_storage(
    name="raw-data",
    versioning=True,
    encryption=True
)

# S3 storage for processed data
processed_storage = aws_env.object_storage(
    name="processed-data",
    versioning=True,
    encryption=True
)

# GCS storage for ML features
# feature_storage = gcp_env.object_storage(
#     name="ml-features",
#     versioning=True
# )

# Shared secrets
api_key = aws_env.secret(name="external-api-key")
stack.track_resource("api-key", api_key)

# ============================================================================
# Define Datasets
# ============================================================================

raw_data = Dataset(name="raw_data", storage=raw_storage)
processed_data = Dataset(name="processed_data", storage=processed_storage)
# ml_features = Dataset(name="ml_features", storage=feature_storage)

# ============================================================================
# Pipeline 1: ETL Pipeline
# ============================================================================

etl_pipeline = stack.pipeline(name="etl")

@etl_pipeline.task(environment=aws_env)
def extract() -> raw_data:
    """
    Extract data from external API.
    Runs on AWS Lambda, stores in S3.
    Uses shared api_key secret.
    """
    print("Extracting data via AWS Lambda...")
    # Would use api_key here
    return {"records": [1, 2, 3]}


@etl_pipeline.task(environment=aws_env)
def transform(data: raw_data) -> processed_data:
    """
    Transform and validate data.
    Runs on AWS Lambda, reads S3, writes S3.
    Writes results to analytics_db.
    """
    print("Transforming data via AWS Lambda...")
    # Would write to analytics_db here
    return {"processed": data}


# ============================================================================
# Pipeline 2: ML Feature Pipeline
# ============================================================================

# ml_pipeline = stack.pipeline(name="ml-features")

# @ml_pipeline.task(environment=gcp_env)
# def compute_features(data: processed_data) -> ml_features:
#     """
#     Compute ML features from processed data.
#     Runs on GCP Cloud Function.
#     Reads from S3 (cross-cloud!), writes to GCS.
#     """
#     print("Computing features via GCP Cloud Function...")
#     return {"features": data}

# ============================================================================
# Compile and Deploy Stack
# ============================================================================

# Compile the stack - creates compute and orchestration infrastructure
compiled = stack.compile()

# Export stack outputs
compiled.export_outputs()

# ============================================================================
# Summary
# ============================================================================

print(f"\n{'='*70}")
print("STACK COMPILED SUCCESSFULLY")
print(f"{'='*70}\n")

print(f"Stack: {stack.name}")
print(f"Environments: {len(stack.list_environments())}")
for env_name in stack.list_environments():
    env = stack.get_environment(env_name)
    print(f"  - {env_name} ({env.provider.get_provider_name()})")
print()

print(f"Pipelines: {len(stack.list_pipelines())}")
for pipeline_name in stack.list_pipelines():
    pipeline = stack.get_pipeline(pipeline_name)
    print(f"  - {pipeline_name} ({len(pipeline.tasks)} tasks)")
print()

print(f"Shared Resources: {len(stack.list_resources())}")
for resource_name in stack.list_resources():
    print(f"  - {resource_name}")
print()

print(f"Total Infrastructure: {len(compiled.resources)} Pulumi resources")
by_provider = compiled.get_resources_by_provider()
print("Resources by provider:")
for provider, resource_list in by_provider.items():
    print(f"  {provider.upper()}: {len(resource_list)} resources")
print()

print("What was created:")
print("  1. Infrastructure Resources (from environments):")
print("     - analytics-db (RDS)")
print("     - raw-data bucket (S3)")
print("     - processed-data bucket (S3)")
print("     - external-api-key (Secrets Manager)")
print()
print("  2. Compute Resources (from compilation):")
print("     - etl-extract Lambda function + IAM role")
print("     - etl-transform Lambda function + IAM role")
print("     - CloudWatch log groups")
print()
print("  3. Cross-Cloud Access (when GCP enabled):")
print("     - GCP service account with S3 read permissions")
print("     - AWS IAM role with GCS write permissions")
print()

print("To deploy:")
print("  1. Ensure AWS credentials configured")
# print("  2. Ensure GCP credentials configured")
print("  2. Run: pulumi up")
print()

print("Key Advantages of Stack Model:")
print("  ✓ Infrastructure resources created immediately (no compilation)")
print("  ✓ Shared resources (DB, secrets) used across pipelines")
print("  ✓ Multi-cloud naturally supported")
print("  ✓ Single deployment unit for entire data platform")
print("  ✓ Compilation only creates compute + orchestration")
print()
