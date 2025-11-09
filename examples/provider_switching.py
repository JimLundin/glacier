"""
Demonstrates provider switching with Environment.

The Environment is provider-agnostic. You inject the provider config,
and the same code works across AWS, Azure, GCP, etc.
"""

import pandas as pd
from glacier import Pipeline, Dataset, Environment

# ============================================================================
# Define pipeline once (provider-agnostic)
# ============================================================================
print("=" * 70)
print("DEFINING PIPELINE (provider-agnostic)")
print("=" * 70)

pipeline = Pipeline(name="etl")

# Define datasets (no provider mentioned)
raw = Dataset(name="raw")
clean = Dataset(name="clean")


@pipeline.task()
def extract() -> raw:
    return pd.DataFrame({'id': [1, 2, 3], 'value': [10, 20, 30]})


@pipeline.task()
def transform(data: raw) -> clean:
    return data * 2


print("✓ Pipeline defined")
print("  No provider coupling!")
print()

# ============================================================================
# Deploy to AWS - inject AWS provider
# ============================================================================
print("=" * 70)
print("DEPLOY TO AWS")
print("=" * 70)

from glacier_aws import AWSProvider

# Create environment with AWS provider
aws_env = Environment(
    provider=AWSProvider(account="123456789012", region="us-east-1"),
    name="prod"
)

print(f"✓ Environment: {aws_env}")
print()

# Use generic methods - they delegate to AWS provider
print("Creating AWS resources (generic methods):")
print("  storage = aws_env.object_storage(name='data')")
print("    → Creates S3 bucket via pulumi_aws.s3.BucketV2")
print()
print("  compute = aws_env.serverless(name='func', handler='index.handler', code=...)")
print("    → Creates Lambda via pulumi_aws.lambda_.Function")
print()

# Attach storage to dataset
# aws_storage = aws_env.object_storage(name="raw-data")
# raw_with_storage = Dataset(name="raw", storage=aws_storage)

# ============================================================================
# Switch to Azure - just change provider config!
# ============================================================================
print("=" * 70)
print("SWITCH TO AZURE")
print("=" * 70)

# Note: glacier_azure would be implemented similarly to glacier_aws
print("To switch to Azure, just change the provider:")
print()
print("```python")
print("from glacier_azure import AzureProvider")
print()
print("azure_env = Environment(")
print('    provider=AzureProvider(subscription="xyz", region="eastus"),')
print('    name="prod"')
print(")")
print()
print("# Same exact code!")
print("storage = azure_env.object_storage(name='data')")
print("  → Now creates Blob Storage")
print()
print("compute = azure_env.serverless(name='func', handler='index.handler', code=...)")
print("  → Now creates Azure Function")
print("```")
print()

# ============================================================================
# Multi-cloud - different providers for different environments
# ============================================================================
print("=" * 70)
print("MULTI-CLOUD: Different providers per environment")
print("=" * 70)

# Dev on AWS, Prod on Azure (or vice versa)
print("```python")
print("from glacier_aws import AWSProvider")
print("from glacier_azure import AzureProvider")
print()
print("dev = Environment(")
print('    provider=AWSProvider(account="111", region="us-east-1"),')
print('    name="dev"')
print(")")
print()
print("prod = Environment(")
print('    provider=AzureProvider(subscription="xyz", region="eastus"),')
print('    name="prod"')
print(")")
print()
print("# Same pipeline, different providers")
print("dev_storage = dev.object_storage(name='data')    # → S3")
print("prod_storage = prod.object_storage(name='data')  # → Blob Storage")
print("```")
print()

# ============================================================================
# Summary
# ============================================================================
print("=" * 70)
print("SUMMARY")
print("=" * 70)
print()
print("✓ Environment is provider-agnostic")
print("✓ Generic methods: object_storage(), serverless(), database()")
print("✓ Provider config injected via dependency injection")
print("✓ Switch providers by changing config, not code")
print("✓ Supports multi-cloud (different providers per environment)")
print()
print("Layer 2 (Environment) now truly provider-agnostic!")
