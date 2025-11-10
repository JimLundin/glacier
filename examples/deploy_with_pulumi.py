"""
Deploy a Glacier pipeline with Pulumi.

This is a Pulumi program (__main__.py) that compiles and deploys
a Glacier pipeline to AWS infrastructure.

To use:
1. Save this file as __main__.py in a directory
2. Create Pulumi.yaml in the same directory
3. Run: pulumi up

The compiler creates actual Pulumi resources that are automatically
registered with the Pulumi runtime.
"""

from glacier import Pipeline, Dataset
from glacier_aws import AWSCompiler

# ============================================================================
# Define Pipeline
# ============================================================================

pipeline = Pipeline(name="etl-pipeline")

# Define datasets
raw = Dataset(name="raw")
processed = Dataset(name="processed")
final = Dataset(name="final")

# Define tasks
@pipeline.task()
def extract() -> raw:
    """Extract data from external API."""
    return {"data": [1, 2, 3]}

@pipeline.task()
def process(data: raw) -> processed:
    """Process raw data."""
    return {"processed": data}

@pipeline.task()
def transform(data: processed) -> final:
    """Transform and aggregate data."""
    return {"transformed": data}

# ============================================================================
# Compile to Pulumi Resources
# ============================================================================

# Create compiler
compiler = AWSCompiler(
    account="123456789012",  # Replace with your AWS account ID
    region="us-east-1",
    lambda_runtime="python3.11",
    lambda_memory=512,
    lambda_timeout=300
)

# Compile pipeline - this creates actual Pulumi resources
compiled = pipeline.compile(compiler)

# Export stack outputs
compiled.export_outputs()

# ============================================================================
# Summary
# ============================================================================

print(f"Pipeline '{pipeline.name}' compiled successfully!")
print(f"Created {len(compiled.resources)} Pulumi resources:")
for resource_name in compiled.list_resources():
    print(f"  - {resource_name}")
