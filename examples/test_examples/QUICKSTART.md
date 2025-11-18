# Quick Start Guide - Glacier Test Examples

Get started with Glacier test examples in 5 minutes.

## Installation

Make sure you have the required dependencies:

```bash
# Install core Glacier
pip install -e glacier/

# Install local executor for running examples
pip install -e providers/glacier-local/

# Install pandas (used in examples)
pip install pandas

# Optional: Install AWS provider for environment examples
pip install -e providers/glacier-aws/
```

## Run Your First Example

### 1. Simple Linear Pipeline

```bash
cd examples/test_examples
python3 -c "
from dag_patterns import example_linear_pipeline
from glacier_local import LocalExecutor

# Create pipeline
pipeline = example_linear_pipeline()
print(f'Pipeline: {pipeline.name}')
print(f'Tasks: {len(pipeline.tasks)}')

# Execute locally
executor = LocalExecutor()
results = executor.execute(pipeline)

# View results
print('\nResults:')
for dataset_name, data in results.items():
    print(f'{dataset_name}:')
    print(data)
    print()
"
```

### 2. Explore DAG Patterns

```python
from dag_patterns import (
    example_linear_pipeline,
    example_branching_pipeline,
    example_diamond_pipeline
)

# Try different patterns
for example_fn in [example_linear_pipeline, example_branching_pipeline, example_diamond_pipeline]:
    pipeline = example_fn()
    print(f"{pipeline.name}: {len(pipeline.tasks)} tasks")
```

### 3. Test Error Handling

```python
from error_cases import example_circular_dependency

# This should fail with a cycle error
try:
    pipeline = example_circular_dependency()
    tasks = pipeline.tasks  # Triggers DAG build
except Exception as e:
    print(f"Caught expected error: {type(e).__name__}")
```

### 4. Environment Configuration

```python
from environment_patterns import example_single_environment

# Create pipeline with explicit environment
pipeline, env = example_single_environment()
print(f"Pipeline: {pipeline.name}")
print(f"Environment: {env.name}")
```

### 5. Run All Examples

```bash
# Run the master test runner
python3 run_all.py

# Or with verbose output
python3 run_all.py --verbose
```

## Understanding the Examples

### Example Function Pattern

All examples follow this pattern:

```python
def example_some_pattern():
    """
    Description of what this example demonstrates.
    """
    # Create pipeline/stack
    pipeline = Pipeline(name="example")

    # Define datasets
    input_data = Dataset("input")
    output_data = Dataset("output")

    # Define tasks
    @pipeline.task()
    def some_task(data: input_data) -> output_data:
        return transform(data)

    # Return for testing
    return pipeline
```

### Running Individual Examples

```python
# Import the example
from dag_patterns import example_linear_pipeline

# Run it
pipeline = example_linear_pipeline()

# Inspect it
print(f"Tasks: {[t.name for t in pipeline.tasks]}")
print(f"Edges: {len(pipeline.edges)}")

# Execute it (if using local executor)
from glacier_local import LocalExecutor
results = LocalExecutor().execute(pipeline)
```

## Example Categories

| Category | File | Purpose |
|----------|------|---------|
| DAG Patterns | `dag_patterns.py` | Different DAG topologies |
| Task Patterns | `task_patterns.py` | Task configurations |
| Datasets | `dataset_patterns.py` | Dataset usage patterns |
| Errors | `error_cases.py` | Error handling (negative tests) |
| Environments | `environment_patterns.py` | Provider configuration |
| Stacks | `stack_patterns.py` | Stack organization |
| Integration | `integration_examples.py` | End-to-end scenarios |
| Edge Cases | `edge_cases.py` | Boundary conditions |

## Using Examples for Tests

Convert examples into pytest tests:

```python
# test_glacier.py
import pytest
from examples.test_examples.dag_patterns import example_linear_pipeline

def test_linear_pipeline_structure():
    pipeline = example_linear_pipeline()
    assert len(pipeline.tasks) == 3
    assert len(pipeline.edges) == 2

def test_linear_pipeline_execution():
    from glacier_local import LocalExecutor

    pipeline = example_linear_pipeline()
    results = LocalExecutor().execute(pipeline)

    assert "final" in results
    assert len(results["final"]) == 3
```

## Next Steps

1. **Explore** different example categories
2. **Modify** examples to understand behavior
3. **Create** your own pipelines based on patterns
4. **Test** using examples as templates

## Troubleshooting

### Import Errors

If you get import errors:

```bash
# Make sure you're in the right directory
cd examples/test_examples

# Or use Python path
export PYTHONPATH=/path/to/glacier:$PYTHONPATH
```

### Missing Dependencies

```bash
# Install all optional dependencies
pip install pandas
pip install -e providers/glacier-aws/
pip install -e providers/glacier-gcp/
```

### Example Fails

Some examples in `error_cases.py` are **expected to fail** - that's the point! They test error handling.

## Getting Help

- Read the main documentation: `../../CLAUDE.md`
- Check the README: `README.md`
- Run examples individually to understand them
- Use `--verbose` flag for detailed output

## Contributing

When creating new examples:

1. Follow the naming pattern: `example_<description>`
2. Add comprehensive docstrings
3. Place in appropriate category file
4. Update README.md
5. Add to `run_all.py`
