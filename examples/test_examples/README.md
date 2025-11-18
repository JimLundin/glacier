# Glacier Test Examples

This directory contains comprehensive usage examples for the Glacier data pipeline framework. These examples are designed to:

1. **Document** all major features and patterns
2. **Test** various scenarios and edge cases
3. **Serve as templates** for building real pipelines
4. **Validate** the framework's behavior

## Organization

The examples are organized by category:

### 1. DAG Patterns (`dag_patterns.py`)

Different DAG topology patterns that Glacier supports:

- **Linear Pipeline**: Simple A → B → C chains
- **Branching**: One task feeding multiple downstream tasks
- **Joining**: Multiple tasks feeding one downstream task
- **Diamond Pattern**: Branch then join
- **Multiple Outputs**: Single task producing multiple datasets
- **Complex Multi-Stage**: Realistic multi-stage pipelines
- **Wide Pipeline**: Many parallel tasks
- **Deep Pipeline**: Long sequential chains

**Use for**: Testing DAG inference, topological sorting, execution order

### 2. Task Patterns (`task_patterns.py`)

Different task input/output combinations and configurations:

- Source tasks (no inputs)
- Single input/output tasks
- Multiple inputs/outputs
- Compute configurations
- Retries and timeouts
- Sink tasks
- Pure functions
- Conditional logic
- Aggregations

**Use for**: Testing task metadata extraction, parameter handling, compute config

### 3. Dataset Patterns (`dataset_patterns.py`)

Different ways to use and configure datasets:

- Simple named datasets
- Descriptive naming conventions
- Datasets with storage
- Intermediate vs persisted datasets
- Dataset reuse (multiple consumers)
- Typed datasets
- Partitioned datasets
- Dataset lineage patterns

**Use for**: Testing dataset creation, storage attachment, naming

### 4. Error Cases (`error_cases.py`)

Cases that should fail or raise errors:

- Circular dependencies
- Multiple producers for same dataset
- Missing producers
- Disconnected pipeline segments
- Empty pipelines
- Invalid configurations
- Execution failures

**Use for**: Negative testing, validation logic, error handling

### 5. Environment Patterns (`environment_patterns.py`)

Different environment and provider usage patterns:

- Implicit (default) environment
- Single explicit environment
- Multiple environments (dev/staging/prod)
- Environment with storage, databases, secrets
- Mixed environment usage
- Environment tags
- Multi-region environments
- Account isolation

**Use for**: Testing provider abstraction, environment isolation, resource creation

### 6. Stack Patterns (`stack_patterns.py`)

Stack organization and deployment patterns:

- Implicit (default) stack
- Explicit stack creation
- Multiple pipelines in a stack
- Multiple environments in a stack
- Multi-cloud stacks
- Shared resources
- Hierarchical organization
- Stack compilation

**Use for**: Testing stack organization, deployment, multi-cloud support

### 7. Integration Examples (`integration_examples.py`)

Complete end-to-end examples demonstrating real-world scenarios:

- Complete ETL pipeline (all 3 layers)
- Multi-pipeline platform
- Dev to prod workflow
- Real-time and batch processing
- Data lake architecture (Bronze/Silver/Gold)
- Machine learning pipeline

**Use for**: Integration testing, documentation, real-world validation

### 8. Edge Cases (`edge_cases.py`)

Unusual but valid patterns testing boundaries:

- Single task pipelines
- Many inputs/outputs
- Empty DataFrames
- Very long/short names
- Unicode names
- Special characters
- Shared datasets across pipelines
- Minimal configurations

**Use for**: Boundary testing, robustness validation

## Running Examples

### Run Individual Example Files

```bash
# Run DAG patterns
python3 examples/test_examples/dag_patterns.py

# Run task patterns
python3 examples/test_examples/task_patterns.py

# Run dataset patterns
python3 examples/test_examples/dataset_patterns.py

# etc...
```

### Run All Examples

```bash
# Run all test examples
python3 examples/test_examples/run_all.py
```

### Run Specific Examples

```python
# Import and use specific examples
from examples.test_examples.dag_patterns import example_linear_pipeline
from glacier_local import LocalExecutor

pipeline = example_linear_pipeline()
results = LocalExecutor().execute(pipeline)
print(results)
```

## Using Examples for Testing

These examples can be used to create automated tests:

```python
import pytest
from examples.test_examples.dag_patterns import (
    example_linear_pipeline,
    example_diamond_pipeline
)

def test_linear_pipeline():
    """Test that linear pipeline builds correctly."""
    pipeline = example_linear_pipeline()
    assert len(pipeline.tasks) == 3
    assert len(pipeline.edges) == 2

def test_diamond_pipeline():
    """Test diamond pattern DAG inference."""
    pipeline = example_diamond_pipeline()
    assert len(pipeline.tasks) == 4
    # Verify DAG structure
    order = pipeline._topological_sort()
    assert len(order) == 4
```

## Example Categories by Use Case

### Learning Glacier

Start with these examples to learn Glacier:

1. `dag_patterns.py` - Linear, Branching, Joining
2. `task_patterns.py` - Single I/O, Multiple I/O
3. `environment_patterns.py` - Implicit, Single Environment
4. `integration_examples.py` - Complete ETL

### Testing Core Features

For testing DAG inference:
- `dag_patterns.py` - All patterns
- `error_cases.py` - Circular dependencies, Multiple producers

For testing task execution:
- `task_patterns.py` - All patterns
- `error_cases.py` - Execution failures

For testing environments:
- `environment_patterns.py` - All patterns
- `stack_patterns.py` - Multi-environment

### Building Real Pipelines

Use these as templates:

- Simple ETL: `integration_examples.py` - Complete ETL
- Data Lake: `integration_examples.py` - Data Lake Architecture
- ML Pipeline: `integration_examples.py` - Machine Learning Pipeline
- Multi-Cloud: `stack_patterns.py` - Multi-Cloud Stack

## Notes

- Most examples use pandas DataFrames for simplicity
- Examples marked with "conceptual" indicate where real implementation would differ
- Error case examples are expected to fail - they validate error handling
- All examples follow Python 3.14 typing standards (no `__future__` imports)

## Contributing Examples

When adding new examples:

1. Place in appropriate category file
2. Follow naming pattern: `example_<description>`
3. Include docstring explaining the pattern
4. Add to test runner in `run_all.py`
5. Update this README

## Dependencies

Required:
- `glacier` - Core framework
- `glacier_local` - For running examples locally

Optional:
- `glacier_aws` - For AWS environment examples
- `glacier_gcp` - For GCP environment examples
- `pandas` - Used in most examples for data processing
