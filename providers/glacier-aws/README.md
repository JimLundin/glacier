# Glacier AWS Provider

AWS provider for Glacier data pipelines.

## Installation

```bash
# Install with glacier
pip install glacier-pipeline[aws]

# Or install directly
pip install glacier-aws
```

## Usage

```python
from glacier import Pipeline, Dataset, compute
from glacier.storage import ObjectStorage
from glacier_aws import AWSCompiler

# Define pipeline
pipeline = Pipeline(name="my-pipeline")

raw_data = Dataset("raw_data", storage=ObjectStorage())
clean_data = Dataset("clean_data", storage=ObjectStorage())

@pipeline.task(compute=compute.serverless(memory=1024))
def extract() -> raw_data:
    return fetch_data()

@pipeline.task(compute=compute.serverless(memory=2048))
def transform(data: raw_data) -> clean_data:
    return process(data)

# Compile to AWS infrastructure
compiler = AWSCompiler(
    region="us-east-1",
    naming_prefix="prod",
    tags={"Environment": "production"}
)

infra = pipeline.compile(compiler)
infra.export_pulumi("./infra")
```

## Features

- **Pulumi-based infrastructure generation**
- **Automatic IAM policy generation**
- **Support for Lambda, S3, RDS, ElastiCache, SQS**
- **Provider-specific validation**

## License

MIT
