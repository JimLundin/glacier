# Glacier Examples

This directory contains example pipelines demonstrating Glacier's features.

## Getting Started

### 1. Generate Sample Data

First, generate the sample data for the examples:

```bash
python examples/generate_sample_data.py
```

This creates `examples/data/sample.parquet` with test data.

### 2. Run a Simple Pipeline

Run the simple example locally:

```bash
glacier run examples/simple_pipeline.py
```

Or run it directly with Python:

```bash
python examples/simple_pipeline.py
```

### 3. Analyze a Pipeline

See the pipeline structure without running it:

```bash
glacier analyze examples/simple_pipeline.py
```

Get JSON output:

```bash
glacier analyze examples/simple_pipeline.py --format json
```

Generate a Mermaid diagram:

```bash
glacier analyze examples/simple_pipeline.py --format mermaid
```

### 4. Generate Infrastructure

Generate Terraform for an S3-based pipeline:

```bash
glacier generate examples/s3_pipeline.py --output ./infra
```

This creates Terraform files in `./infra/` that define:
- S3 buckets for data sources
- IAM policies for access
- All required cloud infrastructure

### 5. Validate a Pipeline

Check for errors without executing:

```bash
glacier validate examples/simple_pipeline.py
```

## Examples

### simple_pipeline.py

A basic ETL pipeline demonstrating:
- Local data sources
- Task decorators
- Data transformations with Polars
- Local execution

**Run it:**
```bash
glacier run examples/simple_pipeline.py
```

### s3_pipeline.py

An advanced pipeline showing:
- Multiple S3 data sources
- Complex task dependencies
- Data joins
- Infrastructure generation

**Analyze it:**
```bash
glacier analyze examples/s3_pipeline.py
```

**Generate infrastructure:**
```bash
glacier generate examples/s3_pipeline.py --output ./my-infra
```

## Key Concepts Demonstrated

### Sources

Sources represent where data comes from. They're explicit objects that:
- Can be analyzed at "compile time" to generate infrastructure
- Provide runtime access to data via Polars LazyFrames

```python
from glacier.sources import S3Source, LocalSource

# S3 source - generates bucket + IAM in Terraform
s3_source = S3Source(
    bucket="my-data",
    path="data.parquet",
    region="us-east-1"
)

# Local source - for development/testing
local_source = LocalSource(
    bucket="./data",
    path="sample.parquet"
)
```

### Tasks

Tasks are the nodes in your pipeline DAG. They're functions decorated with `@task`:

```python
@task
def my_task(source: S3Source) -> pl.LazyFrame:
    return source.scan()
```

Tasks can have explicit dependencies:

```python
@task(depends_on=["load_data"])
def process(df: pl.LazyFrame) -> pl.LazyFrame:
    return df.filter(pl.col("value") > 100)
```

### Pipelines

Pipelines orchestrate tasks:

```python
@pipeline(name="my_pipeline")
def my_pipeline():
    data = load_data(source)
    processed = process(data)
    return processed
```

### Execution Modes

Pipelines can run in different modes:

```python
# Local execution
result = my_pipeline.run(mode="local")

# Analysis (build DAG, no execution)
analysis = my_pipeline.run(mode="analyze")

# Generate infrastructure
infra = my_pipeline.run(mode="generate", output_dir="./infra")
```

## Lazy Evaluation

Glacier uses Polars LazyFrames by default for optimal performance:

```python
@task
def my_task(source: LocalSource) -> pl.LazyFrame:
    # Returns a LazyFrame - no execution yet
    return source.scan()

# Later, in your pipeline:
result = my_pipeline.run(mode="local")
# Still lazy! Only collects when you need it:
df = result.collect()
```

This allows Polars to optimize the entire query plan before execution.

## Next Steps

1. Modify the example pipelines
2. Create your own pipeline
3. Generate infrastructure for your use case
4. Explore different execution modes
5. Deploy to the cloud!

## Need Help?

See the main [Glacier README](../README.md) for more information.
