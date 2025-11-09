"""
Demonstrates the three layers of explicitness in Glacier.

Layer 1: Implicit - everything automatic
Layer 2: Environment - organize by account/region (provider-agnostic!)
Layer 3: Raw Pulumi - full control
"""

import pandas as pd
from glacier import Pipeline, Dataset

# ============================================================================
# Layer 1: IMPLICIT - Simplest possible
# ============================================================================
print("=" * 70)
print("LAYER 1: IMPLICIT - Everything automatic")
print("=" * 70)

pipeline = Pipeline(name="simple_etl")

# No storage configuration - just names
raw = Dataset(name="raw")
clean = Dataset(name="clean")


@pipeline.task()
def extract() -> raw:
    """Extract data"""
    return pd.DataFrame({'id': [1, 2, 3], 'value': [10, 20, 30]})


@pipeline.task()
def transform(data: raw) -> clean:
    """Transform data"""
    return data * 2


print("✓ Pipeline defined")
print("  No cloud config needed")
print("  Perfect for local development\n")

# Run locally
from glacier_local import LocalExecutor

results = LocalExecutor().execute(pipeline)
print(f"Results:\n{results['clean']}\n")


# ============================================================================
# Layer 2: ENVIRONMENT - Provider-agnostic with dependency injection
# ============================================================================
print("=" * 70)
print("LAYER 2: ENVIRONMENT - Provider-agnostic!")
print("=" * 70)

from glacier import Environment
from glacier_aws import AWSProvider

# Inject AWS provider into generic Environment
aws_prod = Environment(
    provider=AWSProvider(account="123456789012", region="us-east-1"),
    name="prod"
)

aws_dev = Environment(
    provider=AWSProvider(account="987654321098", region="us-west-2"),
    name="dev"
)

print(f"✓ Environments defined:")
print(f"  Production: {aws_prod}")
print(f"  Development: {aws_dev}\n")

# Generic methods - work across any provider!
print("Creating resources (provider-agnostic methods):")
print('  storage = aws_prod.object_storage(name="data")')
print('  compute = aws_prod.serverless(name="func", handler="index.handler", code=...)')
print()
print("Behind the scenes:")
print("  → Environment delegates to AWSProvider")
print("  → AWSProvider calls pulumi_aws.s3.BucketV2()")
print("  → Adds environment tags automatically")
print()
print("To switch to Azure:")
print('  azure_prod = Environment(provider=AzureProvider(...), name="prod")')
print('  storage = azure_prod.object_storage(name="data")  # Now Blob Storage!')
print()


# ============================================================================
# Layer 3: RAW PULUMI - Full control (escape hatch)
# ============================================================================
print("=" * 70)
print("LAYER 3: RAW PULUMI - Full control")
print("=" * 70)

print("When you need advanced Pulumi features:")
print()
print("```python")
print("import pulumi_aws as aws")
print()
print("# Use Pulumi directly - no wrappers!")
print("bucket = aws.s3.BucketV2(")
print('    "my-data",')
print('    bucket="my-data",')
print("    versioning=aws.s3.BucketVersioningArgs(")
print("        enabled=True,")
print("        mfa_delete=True  # Advanced feature!")
print("    ),")
print("    lifecycle_rules=[")
print("        aws.s3.BucketLifecycleRuleArgs(")
print("            enabled=True,")
print("            transitions=[{")
print('                "days": 30,')
print('                "storage_class": "GLACIER"')
print("            }]")
print("        )")
print("    ]")
print(")")
print()
print("# Use in pipeline like any other resource")
print('data = Dataset(name="data", storage=bucket)')
print("```")
print()
print("✓ No special wrappers needed")
print("✓ Full Pulumi API available")
print("✓ Mix and match with Layer 2 resources")

# ============================================================================
# Summary
# ============================================================================
print()
print("=" * 70)
print("SUMMARY")
print("=" * 70)
print()
print("Layer 1 → Layer 2            → Layer 3")
print("Simple   → Environment        → Raw Pulumi")
print("          (provider-agnostic!)")
print()
print("Key insight: Environment is now truly provider-agnostic.")
print("Generic methods work across AWS, Azure, GCP.")
print("Switch providers by changing config, not code.")
print()
