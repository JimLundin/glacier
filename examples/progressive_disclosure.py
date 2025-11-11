"""
Progressive Disclosure Example.

This example demonstrates how Glacier provides three levels of explicitness:
1. Implicit defaults - minimal code for simple cases
2. Explicit environment - specify cloud provider
3. Explicit stack + environment - full control for multi-cloud
"""

# =============================================================================
# Level 1: Implicit (uses defaults)
# =============================================================================
print("=== Level 1: Implicit defaults ===")

from glacier import Dataset, object_storage, pipeline

# Everything uses hidden defaults - no Stack or Environment needed
raw = Dataset("raw")
processed = Dataset("processed")

# Pipeline uses default stack
etl = pipeline("etl")

# Storage uses default environment (local if glacier-local installed)
storage = object_storage("data")

@etl.task()
def extract() -> raw:
    """Task uses default environment."""
    return {"data": [1, 2, 3]}

@etl.task()
def transform(data: raw) -> processed:
    """Task uses default environment."""
    return {"processed": [x * 2 for x in data["data"]]}

print(f"Pipeline: {etl.name}")
print(f"Tasks: {[t.name for t in etl.tasks]}")


# =============================================================================
# Level 2: Explicit Environment (but implicit Stack)
# =============================================================================
print("\n=== Level 2: Explicit environment ===")

from glacier import Environment
from glacier_aws import AWSProvider

# Create environment explicitly (still uses default stack internally)
aws = Environment(
    provider=AWSProvider(account="123456789012", region="us-east-1"),
    name="aws-prod"
)

# Resources use explicit environment
aws_storage = aws.object_storage("production-data")

clean = Dataset("clean")
final = Dataset("final")

# Pipeline can be explicit or use default
prod_pipeline = pipeline("production")

@prod_pipeline.task(environment=aws)
def load(data: processed) -> clean:
    """Task explicitly uses aws environment."""
    return data

@prod_pipeline.task(environment=aws)
def export(data: clean) -> final:
    """Task explicitly uses aws environment."""
    return data

print(f"Environment: {aws}")
print(f"Pipeline: {prod_pipeline.name}")


# =============================================================================
# Level 3: Fully Explicit (Stack + Environment)
# =============================================================================
print("\n=== Level 3: Full control ===")

from glacier import Stack
from glacier_gcp import GCPProvider

# Create stack explicitly
stack = Stack(name="multi-cloud-platform")

# Create multiple environments in the stack
aws_env = stack.environment(
    provider=AWSProvider(account="123456789012", region="us-east-1"),
    name="aws"
)

gcp_env = stack.environment(
    provider=GCPProvider(project="my-project", region="us-central1"),
    name="gcp"
)

# Resources from specific environments
s3_storage = aws_env.object_storage("s3-data")
gcs_storage = gcp_env.object_storage("gcs-data")

aws_data = Dataset("aws_data", storage=s3_storage)
gcp_data = Dataset("gcp_data", storage=gcs_storage)

# Pipeline in explicit stack
multi_cloud = stack.pipeline("cross-cloud")

@multi_cloud.task(environment=aws_env)
def fetch_from_aws() -> aws_data:
    """Task runs on AWS."""
    return {"source": "aws"}

@multi_cloud.task(environment=gcp_env)
def process_on_gcp(data: aws_data) -> gcp_data:
    """Task runs on GCP, reads from AWS."""
    return {"source": "gcp", "input_from": data["source"]}

print(f"Stack: {stack.name}")
print(f"Environments: {list(stack._environments.keys())}")
print(f"Pipelines: {list(stack._pipelines.keys())}")

# Compile and deploy the stack
# compiled = stack.compile()
# compiled.export_outputs()
