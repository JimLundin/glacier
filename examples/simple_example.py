"""
Simple example showing Glacier's core features.

This demonstrates:
1. Define pipelines with type-driven DAG
2. Use our simple configs OR Pulumi resources directly
3. Execute locally or deploy to cloud
"""

import pandas as pd
from glacier.core.pipeline import Pipeline
from glacier.core.dataset import Dataset
from glacier.storage.resources import ObjectStorage

# ============================================================================
# Example 1: Simple pipeline with our configs
# ============================================================================
print("Example 1: Pipeline with our simple configs")
print("=" * 60)

pipeline = Pipeline(name="etl")

# Define datasets with our simple storage config
raw_data = Dataset(
    name="raw",
    storage=ObjectStorage(
        resource_name="raw-data-bucket",
        access_pattern="frequent",
        versioning=True
    )
)

clean_data = Dataset(
    name="clean",
    storage=ObjectStorage(resource_name="clean-data-bucket")
)


@pipeline.task()
def extract() -> raw_data:
    """Extract data"""
    return pd.DataFrame({
        'id': [1, 2, 3],
        'value': [10, 20, 30]
    })


@pipeline.task()
def transform(data: raw_data) -> clean_data:
    """Transform data"""
    return data * 2


print(f"✓ Created pipeline with {len(pipeline.tasks)} tasks")
print(f"  Tasks: {[t.name for t in pipeline.tasks]}")
print(f"  DAG: {pipeline.edges}")

# Execute locally
from glacier_local.executor import LocalExecutor

executor = LocalExecutor()
results = executor.execute(pipeline)

print(f"\n✓ Executed locally:")
print(f"{results['clean']}")

# ============================================================================
# Example 2: Same pipeline but with Pulumi resources
# ============================================================================
print("\n\nExample 2: Pipeline with Pulumi resources directly")
print("=" * 60)

# You can swap in Pulumi resources directly when you need full control:
#
# import pulumi_aws as aws
#
# raw_data = Dataset(
#     name="raw",
#     storage=aws.s3.Bucket(
#         "raw-data-bucket",
#         versioning=aws.s3.BucketVersioningArgs(enabled=True),
#         lifecycle_rules=[
#             aws.s3.BucketLifecycleRuleArgs(
#                 enabled=True,
#                 transitions=[{
#                     "days": 30,
#                     "storage_class": "GLACIER"
#                 }]
#             )
#         ]
#     )
# )

print("✓ When you need Pulumi features, just pass Pulumi resources")
print("  No special wrappers or abstractions needed")
print("  Glacier accepts either our configs or Pulumi resources")

print("\n\nDone!")
