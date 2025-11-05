# Glacier 🏔️

A code-centric data pipeline library built on Polars with infrastructure-from-code generation.

## Philosophy

**Infrastructure from Code** - Define your data pipelines in Python, and Glacier automatically generates the required cloud infrastructure (Terraform, IAM policies, etc.) by analyzing your code.

## Key Features

- 🎯 **Code-Centric DX**: Define pipelines using intuitive Python decorators
- 🔄 **Multi-Environment**: Run locally, in AWS, GCP, or hybrid setups
- ⚡ **Polars-Native**: Built on Polars LazyFrames for optimal performance
- 🏗️ **Infrastructure Generation**: Auto-generate Terraform from pipeline definitions
- 🔌 **Adapter Pattern**: Swap storage backends (S3, GCS, local) seamlessly
- 📊 **DAG Resolution**: Automatic dependency graph construction and validation

## Quick Start

```python
from glacier import pipeline, task
from glacier.sources import S3Source, LocalSource
import polars as pl

# Define a source
data_source = S3Source(
    bucket="my-data-bucket",
    path="raw/data.parquet",
    region="us-east-1"
)

# Define transformation tasks
@task
def load_data(source: S3Source) -> pl.LazyFrame:
    return source.scan()

@task
def clean_data(df: pl.LazyFrame) -> pl.LazyFrame:
    return df.filter(pl.col("value").is_not_null())

@task
def aggregate(df: pl.LazyFrame) -> pl.LazyFrame:
    return df.group_by("category").agg(pl.col("value").sum())

# Define the pipeline
@pipeline(name="my_pipeline")
def my_pipeline():
    df = load_data(data_source)
    cleaned = clean_data(df)
    result = aggregate(cleaned)
    return result

# Run locally
if __name__ == "__main__":
    result = my_pipeline.run()
    print(result.collect())
```

## CLI Usage

```bash
# Run pipeline locally
glacier run my_pipeline.py

# Generate infrastructure code
glacier generate my_pipeline.py --output ./infra

# Deploy to cloud
glacier deploy my_pipeline.py --env production
```

## Installation

```bash
pip install glacier-pipeline
```

## Development

```bash
# Install in development mode
pip install -e .

# Run tests
pytest tests/
```

## License

MIT
