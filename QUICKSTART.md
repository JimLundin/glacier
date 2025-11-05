# Glacier Quick Start Guide

Get started with Glacier in 5 minutes!

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/glacier.git
cd glacier

# Install in development mode
pip install -e .

# Or install from PyPI (when published)
pip install glacier-pipeline
```

## Your First Pipeline

### 1. Create a Pipeline File

Create `my_first_pipeline.py`:

```python
from glacier import pipeline, task
from glacier.sources import LocalSource
import polars as pl

# Define where your data comes from
data_source = LocalSource(
    bucket="./data",
    path="input.csv",
    format="csv"
)

# Define a task to load data
@task
def load_data(source: LocalSource) -> pl.LazyFrame:
    """Load data from source."""
    return source.scan()

# Define a task to clean data
@task(depends_on=["load_data"])
def clean_data(df: pl.LazyFrame) -> pl.LazyFrame:
    """Remove rows with missing values."""
    return df.drop_nulls()

# Define a task to transform data
@task(depends_on=["clean_data"])
def transform(df: pl.LazyFrame) -> pl.LazyFrame:
    """Calculate derived columns."""
    return df.with_columns([
        (pl.col("amount") * 1.1).alias("amount_with_tax")
    ])

# Define the pipeline
@pipeline(name="my_first_pipeline")
def my_pipeline():
    """My first Glacier pipeline."""
    data = load_data(data_source)
    cleaned = clean_data(data)
    result = transform(cleaned)
    return result
```

### 2. Create Sample Data

Create `./data/input.csv`:

```csv
id,name,amount
1,Alice,100
2,Bob,200
3,Charlie,300
```

### 3. Run Your Pipeline

```bash
# Run the pipeline locally
glacier run my_first_pipeline.py
```

Or run it directly with Python:

```python
if __name__ == "__main__":
    result = my_pipeline.run(mode="local")
    print(result.collect())
```

## Going Further

### Analyze Your Pipeline

See the DAG structure:

```bash
glacier analyze my_first_pipeline.py
```

Get JSON output:

```bash
glacier analyze my_first_pipeline.py --format json
```

Generate a Mermaid diagram:

```bash
glacier analyze my_first_pipeline.py --format mermaid
```

### Validate Your Pipeline

Check for errors without running:

```bash
glacier validate my_first_pipeline.py
```

### Use Cloud Storage

Switch to S3:

```python
from glacier.sources import S3Source

data_source = S3Source(
    bucket="my-data-bucket",
    path="data/input.parquet",
    region="us-east-1"
)
```

### Generate Infrastructure

Automatically create Terraform for your pipeline:

```bash
glacier generate my_first_pipeline.py --output ./infra
```

This creates:
- `main.tf` - Main Terraform configuration
- `variables.tf` - Input variables
- `outputs.tf` - Outputs
- `README.md` - Documentation

Then apply it:

```bash
cd infra
terraform init
terraform plan
terraform apply
```

## Key Concepts

### Sources

Sources represent where data comes from:

```python
# Local filesystem
LocalSource(bucket="./data", path="file.parquet")

# AWS S3
S3Source(bucket="my-bucket", path="data.parquet", region="us-east-1")

# Future: GCS, Azure, databases, APIs
```

### Tasks

Tasks are functions decorated with `@task`:

```python
@task
def my_task(input: pl.LazyFrame) -> pl.LazyFrame:
    return input.filter(pl.col("value") > 0)
```

Tasks can have explicit dependencies:

```python
@task(depends_on=["task1", "task2"])
def my_task():
    pass
```

### Pipelines

Pipelines orchestrate tasks:

```python
@pipeline(name="my_pipeline")
def my_pipeline():
    data = load_data(source)
    result = process(data)
    return result
```

### Lazy Evaluation

Glacier uses Polars LazyFrames for optimal performance:

```python
# This returns a LazyFrame - no computation yet
result = my_pipeline.run(mode="local")

# Materialize when needed
df = result.collect()
```

## Common Patterns

### Multiple Sources

```python
sales_data = S3Source(bucket="data", path="sales.parquet")
customer_data = S3Source(bucket="data", path="customers.parquet")

@task
def join_data(sales: pl.LazyFrame, customers: pl.LazyFrame) -> pl.LazyFrame:
    return sales.join(customers, on="customer_id")
```

### Conditional Logic

```python
@task
def process(df: pl.LazyFrame, include_inactive: bool = False) -> pl.LazyFrame:
    if include_inactive:
        return df
    return df.filter(pl.col("status") == "active")
```

### Aggregations

```python
@task
def aggregate(df: pl.LazyFrame) -> pl.LazyFrame:
    return df.group_by("category").agg([
        pl.col("amount").sum(),
        pl.col("amount").mean(),
        pl.count()
    ])
```

## Next Steps

1. Check out the [examples directory](./examples/) for more complex pipelines
2. Read the [DESIGN.md](./DESIGN.md) to understand the architecture
3. Explore the [API documentation](./docs/)
4. Join our community and contribute!

## Troubleshooting

### Pipeline Not Found

Make sure your pipeline is decorated with `@pipeline`:

```python
@pipeline  # Don't forget this!
def my_pipeline():
    pass
```

### Task Dependencies Not Working

Ensure dependency names match task function names:

```python
@task
def load_data():  # Function name is "load_data"
    pass

@task(depends_on=["load_data"])  # Must match exactly
def process():
    pass
```

### LazyFrame Not Materializing

Call `.collect()` to materialize:

```python
result = my_pipeline.run(mode="local")
df = result.collect()  # Now it's a DataFrame
print(df)
```

## Getting Help

- Check the [examples](./examples/)
- Read the [design docs](./DESIGN.md)
- Open an issue on GitHub
- Join our Discord/Slack

Happy pipeline building! 🏔️
