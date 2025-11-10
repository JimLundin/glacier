"""
Deploy a pipeline with Pulumi using the Stack model.

Usage:
  Save as __main__.py and run: pulumi up
"""

from glacier import Stack, Dataset
from glacier_aws import AWSProvider

# Stack is the compilation unit
stack = Stack(name="data-platform")

# Environments create infrastructure immediately (Pulumi resources)
aws = stack.environment(
    provider=AWSProvider(account="123456789012", region="us-east-1"),
    name="aws"
)

# Resources created immediately
storage = aws.object_storage("raw-data")
raw = Dataset("raw", storage=storage)
processed = Dataset("processed")

# Pipeline defines compute logic
pipeline = stack.pipeline("etl")

@pipeline.task(environment=aws)
def extract() -> raw:
    return {"data": [1, 2, 3]}

@pipeline.task(environment=aws)
def transform(data: raw) -> processed:
    return {"processed": data}

# Compile creates compute + orchestration
compiled = stack.compile()
compiled.export_outputs()
