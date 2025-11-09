# Glacier Local Provider

Local executor for Glacier data pipelines.

## Installation

```bash
# Install with glacier
pip install glacier-pipeline[local]

# Or install directly
pip install glacier-local
```

## Usage

```python
from glacier import Pipeline, Dataset, compute
from glacier_local import LocalExecutor

# Define pipeline
pipeline = Pipeline(name="my-pipeline")

raw_data = Dataset("raw_data")
clean_data = Dataset("clean_data")

@pipeline.task(compute=compute.local())
def extract() -> raw_data:
    return [1, 2, 3, 4, 5]

@pipeline.task(compute=compute.local())
def transform(data: raw_data) -> clean_data:
    return [x * 2 for x in data]

# Run locally
executor = LocalExecutor()
results = pipeline.run(executor)

print(results["clean_data"])  # [2, 4, 6, 8, 10]
```

## Features

- **In-memory execution**
- **Automatic dependency resolution**
- **Simple debugging**
- **No cloud dependencies**

## License

MIT
