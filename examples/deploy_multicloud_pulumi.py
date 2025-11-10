"""
Multi-Cloud Pipeline Deployment with Pulumi.

This example demonstrates:
1. Defining a pipeline that spans AWS and GCP
2. Tasks running in different clouds
3. Cross-cloud data flows (S3 → GCP Cloud Function)
4. Single Pulumi program compiling all resources

To deploy:
1. Install dependencies: pip install pulumi pulumi-aws pulumi-gcp glacier-pipeline
2. Configure AWS and GCP credentials
3. Run: pulumi up
"""

from glacier import Pipeline, Dataset, Environment
from glacier_aws import AWSProvider
# from glacier_gcp import GCPProvider  # When implemented
from glacier.compilation import PulumiCompiler

# ============================================================================
# Setup: Multi-Cloud Environments
# ============================================================================

# AWS environment for raw data ingestion
aws_env = Environment(
    provider=AWSProvider(
        account="123456789012",
        region="us-east-1"
    ),
    name="aws-prod"
)

# GCP environment for data processing
# gcp_env = Environment(
#     provider=GCPProvider(
#         project="my-project",
#         region="us-central1"
#     ),
#     name="gcp-prod"
# )

# ============================================================================
# Define Pipeline with Cross-Cloud Data Flow
# ============================================================================

pipeline = Pipeline(name="multicloud-etl")

# Datasets with storage in different clouds
raw_data = Dataset(name="raw_data")  # Will be in S3
# processed_data = Dataset(name="processed_data")  # Will be in GCS

# ============================================================================
# Tasks in Different Clouds
# ============================================================================

# Task 1: Extract data, store in S3 (AWS)
@pipeline.task(environment=aws_env)
def extract() -> raw_data:
    """
    Extract data from external API.
    Runs on AWS Lambda, stores in S3.
    """
    print("Extracting data via AWS Lambda...")
    return {"records": [1, 2, 3]}


# Task 2: Process data from S3, store in GCS (GCP)
# @pipeline.task(environment=gcp_env)
# def process(data: raw_data) -> processed_data:
#     """
#     Process data from AWS S3.
#     Runs on GCP Cloud Function, reads S3 (cross-cloud!), writes to GCS.
#     """
#     print("Processing data via GCP Cloud Function...")
#     # Cloud Function will need AWS credentials to read S3
#     return {"processed": data}

# ============================================================================
# Compile to Pulumi Resources
# ============================================================================

# The PulumiCompiler inspects each task's environment to determine
# which provider to use, then creates appropriate resources
compiler = PulumiCompiler()

# This creates:
# - AWS Lambda for extract() task
# - S3 bucket for raw_data
# - IAM roles and policies for Lambda
# - CloudWatch log groups
#
# When GCP tasks are added:
# - GCP Cloud Function for process() task
# - GCS bucket for processed_data
# - Service accounts and IAM bindings
# - Cross-cloud IAM (GCP service account with AWS S3 access)

compiled = pipeline.compile(compiler)

# Export stack outputs
compiled.export_outputs()

# ============================================================================
# Summary
# ============================================================================

print(f"\n{'='*70}")
print("MULTI-CLOUD PIPELINE COMPILED")
print(f"{'='*70}\n")

print(f"Pipeline: {pipeline.name}")
print(f"Tasks: {len(pipeline.tasks)}")
print(f"Datasets: {len(pipeline.datasets)}")
print(f"Resources created: {len(compiled.resources)}")
print()

# Group resources by provider
by_provider = compiled.get_resources_by_provider()
print("Resources by provider:")
for provider, resource_names in by_provider.items():
    print(f"  {provider.upper()}: {len(resource_names)} resources")
    for name in resource_names:
        print(f"    - {name}")
print()

print("Data flow:")
print("  1. extract() runs on AWS Lambda")
print("  2. Stores data in S3")
# print("  3. process() runs on GCP Cloud Function")
# print("  4. Reads from S3 (cross-cloud access)")
# print("  5. Stores result in GCS")
print()

print("To deploy:")
print("  1. Ensure AWS credentials configured")
# print("  2. Ensure GCP credentials configured")
print("  2. Run: pulumi up")
print()
