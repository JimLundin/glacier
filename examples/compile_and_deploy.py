"""
Pipeline Compilation Example.

This example demonstrates how to:
1. Define a pipeline with datasets and tasks
2. Compile the pipeline to Pulumi resources
3. Access the created resources

Note: This is NOT a Pulumi program itself. It's a demonstration
of the compilation process. To actually deploy, create a Pulumi
program like deploy_with_pulumi.py
"""

from glacier import Pipeline, Dataset

# ============================================================================
# Step 1: Define Pipeline
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
# Step 2: Define Tasks
# ============================================================================
print("=" * 70)
print("STEP 2: DEFINE TASKS")
print("=" * 70)
print()


@pipeline.task()
def extract() -> raw_data:
    """Extract data from external API."""
    print("Extracting data from API...")
    return {"id": [1, 2, 3], "value": [10, 20, 30]}


@pipeline.task()
def process(data: raw_data) -> processed_data:
    """Process raw data."""
    print("Processing raw data...")
    return {"processed": data}


@pipeline.task()
def transform(data: processed_data) -> final_output:
    """Transform and aggregate data."""
    print("Transforming data...")
    return {"transformed": data}


print("✓ Tasks defined:")
print("  - extract: Extracts data from API")
print("  - process: Processes raw data")
print("  - transform: Transforms and aggregates")
print()

# ============================================================================
# Step 3: Compile Pipeline (without Pulumi runtime)
# ============================================================================
print("=" * 70)
print("STEP 3: COMPILE PIPELINE")
print("=" * 70)
print()

print("To compile this pipeline to Pulumi resources, you would:")
print()
print("1. Install Pulumi and pulumi-aws:")
print("   pip install pulumi pulumi-aws")
print()
print("2. Create a Pulumi program (__main__.py):")
print()
print("```python")
print("from glacier import Pipeline, Dataset")
print("from glacier_aws import AWSCompiler")
print()
print("# [Your pipeline definition here]")
print()
print("compiler = AWSCompiler(")
print("    account='123456789012',")
print("    region='us-east-1'")
print(")")
print()
print("compiled = pipeline.compile(compiler)")
print("compiled.export_outputs()")
print("```")
print()
print("3. Run Pulumi:")
print("   pulumi up")
print()

# ============================================================================
# Step 4: What Would Be Created
# ============================================================================
print("=" * 70)
print("STEP 4: RESOURCES THAT WOULD BE CREATED")
print("=" * 70)
print()

print("The AWSCompiler would create these Pulumi resources:")
print()
print("Compute Resources:")
print("  - etl-pipeline-extract: Lambda function")
print("  - etl-pipeline-extract-role: IAM role")
print("  - etl-pipeline-extract-policy: IAM policy")
print("  - etl-pipeline-process: Lambda function")
print("  - etl-pipeline-process-role: IAM role")
print("  - etl-pipeline-process-policy: IAM policy")
print("  - etl-pipeline-transform: Lambda function")
print("  - etl-pipeline-transform-role: IAM role")
print("  - etl-pipeline-transform-policy: IAM policy")
print()
print("Monitoring Resources:")
print("  - etl-pipeline-extract-logs: CloudWatch log group")
print("  - etl-pipeline-process-logs: CloudWatch log group")
print("  - etl-pipeline-transform-logs: CloudWatch log group")
print()

# ============================================================================
# Summary
# ============================================================================
print("=" * 70)
print("SUMMARY")
print("=" * 70)
print()
print("✅ Pipeline definition complete")
print("✅ Ready for compilation")
print()
print("Next steps:")
print("1. See deploy_with_pulumi.py for a complete Pulumi program")
print("2. See README_DEPLOYMENT.md for deployment instructions")
print()
