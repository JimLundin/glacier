"""
Error and Validation Examples for Testing.

This module contains examples that should fail or raise errors.
These are critical for testing error handling, validation logic,
and edge cases in the Glacier pipeline framework.

Each example demonstrates a specific error condition that should be caught
and handled appropriately by the framework.
"""

import pandas as pd
from glacier import Pipeline, Dataset


# =============================================================================
# Error 1: Circular Dependency
# =============================================================================
def example_circular_dependency():
    """
    Creates a circular dependency in the DAG.

    This should be detected and raise an error during DAG validation.

    DAG: A → B → C → A (cycle!)
    """
    pipeline = Pipeline(name="circular")

    dataset_a = Dataset("dataset_a")
    dataset_b = Dataset("dataset_b")
    dataset_c = Dataset("dataset_c")

    @pipeline.task()
    def task_a(data: dataset_c) -> dataset_a:
        """Depends on C."""
        return data * 2

    @pipeline.task()
    def task_b(data: dataset_a) -> dataset_b:
        """Depends on A."""
        return data * 3

    @pipeline.task()
    def task_c(data: dataset_b) -> dataset_c:
        """Depends on B, creates cycle."""
        return data * 4

    return pipeline


# =============================================================================
# Error 2: Self-Circular Dependency
# =============================================================================
def example_self_circular():
    """
    Task depends on its own output.

    DAG: A → A (self-loop)
    """
    pipeline = Pipeline(name="self_circular")

    dataset_a = Dataset("dataset_a")

    @pipeline.task()
    def recursive_task(data: dataset_a) -> dataset_a:
        """Depends on itself - creates self-loop."""
        return data * 2

    return pipeline


# =============================================================================
# Error 3: Multiple Producers for Same Dataset
# =============================================================================
def example_multiple_producers():
    """
    Two tasks produce the same dataset.

    This violates the single-producer constraint.
    """
    pipeline = Pipeline(name="multiple_producers")

    raw = Dataset("raw")
    output = Dataset("output")

    @pipeline.task()
    def extract() -> raw:
        return pd.DataFrame({"value": [1, 2, 3]})

    @pipeline.task()
    def producer_1(data: raw) -> output:
        """First producer of 'output'."""
        return data * 2

    @pipeline.task()
    def producer_2(data: raw) -> output:
        """Second producer of 'output' - ERROR!"""
        return data * 3

    return pipeline


# =============================================================================
# Error 4: Missing Input Dataset (No Producer)
# =============================================================================
def example_missing_producer():
    """
    Task consumes a dataset that is never produced.
    """
    pipeline = Pipeline(name="missing_producer")

    input_data = Dataset("input_data")  # Never produced!
    output = Dataset("output")

    @pipeline.task()
    def transform(data: input_data) -> output:
        """Consumes dataset that has no producer."""
        return data * 2

    return pipeline


# =============================================================================
# Error 5: Disconnected Pipeline Segments
# =============================================================================
def example_disconnected_segments():
    """
    Pipeline has disconnected components.

    This may or may not be an error depending on requirements,
    but it's worth testing.
    """
    pipeline = Pipeline(name="disconnected")

    # First segment
    data_a = Dataset("data_a")
    output_a = Dataset("output_a")

    # Second segment (disconnected)
    data_b = Dataset("data_b")
    output_b = Dataset("output_b")

    @pipeline.task()
    def extract_a() -> data_a:
        return pd.DataFrame({"value": [1, 2, 3]})

    @pipeline.task()
    def process_a(data: data_a) -> output_a:
        return data * 2

    @pipeline.task()
    def extract_b() -> data_b:
        """Disconnected from first segment."""
        return pd.DataFrame({"value": [4, 5, 6]})

    @pipeline.task()
    def process_b(data: data_b) -> output_b:
        return data * 3

    return pipeline


# =============================================================================
# Error 6: Empty Pipeline (No Tasks)
# =============================================================================
def example_empty_pipeline():
    """
    Pipeline with no tasks.
    """
    pipeline = Pipeline(name="empty")
    return pipeline


# =============================================================================
# Error 7: Task with No Outputs
# =============================================================================
def example_task_no_outputs():
    """
    Task has inputs but no output annotation.

    This might be valid for side-effect tasks, but worth testing.
    """
    pipeline = Pipeline(name="no_outputs")

    input_data = Dataset("input_data")

    @pipeline.task()
    def extract() -> input_data:
        return pd.DataFrame({"value": [1, 2, 3]})

    @pipeline.task()
    def sink_task(data: input_data):
        """No return type annotation - no outputs!"""
        print(f"Processing {len(data)} rows")
        # No return statement

    return pipeline


# =============================================================================
# Error 8: Mismatched Return Type
# =============================================================================
def example_mismatched_return():
    """
    Task declares multiple outputs but returns single value.
    """
    pipeline = Pipeline(name="mismatched_return")

    source = Dataset("source")
    output_a = Dataset("output_a")
    output_b = Dataset("output_b")

    @pipeline.task()
    def extract() -> source:
        return pd.DataFrame({"value": [1, 2, 3]})

    @pipeline.task()
    def process(data: source) -> tuple[output_a, output_b]:
        """Declares two outputs but might return wrong number."""
        # Should return tuple, but might return single value
        return data * 2  # ERROR: Should return (data, data) or similar

    return pipeline


# =============================================================================
# Error 9: Invalid Dataset Name
# =============================================================================
def example_invalid_dataset_names():
    """
    Datasets with problematic names.
    """
    pipeline = Pipeline(name="invalid_names")

    # Various potentially problematic names
    empty_name = Dataset("")  # Empty string
    whitespace = Dataset("  ")  # Only whitespace
    special_chars = Dataset("data-set!@#$%")  # Special characters

    @pipeline.task()
    def extract() -> empty_name:
        return pd.DataFrame({"value": [1, 2, 3]})

    @pipeline.task()
    def transform_1(data: empty_name) -> whitespace:
        return data * 2

    @pipeline.task()
    def transform_2(data: whitespace) -> special_chars:
        return data * 3

    return pipeline


# =============================================================================
# Error 10: Duplicate Dataset Names (Different Instances)
# =============================================================================
def example_duplicate_dataset_instances():
    """
    Multiple Dataset instances with the same name.

    This tests whether datasets are compared by name or by identity.
    """
    pipeline = Pipeline(name="duplicate_names")

    # Two different instances with same name
    data_1 = Dataset("data")
    data_2 = Dataset("data")  # Same name, different instance

    output = Dataset("output")

    @pipeline.task()
    def extract() -> data_1:
        """Produces first 'data' instance."""
        return pd.DataFrame({"value": [1, 2, 3]})

    @pipeline.task()
    def transform(data: data_2) -> output:
        """Consumes second 'data' instance - should work due to name matching."""
        return data * 2

    return pipeline


# =============================================================================
# Error 11: Very Long DAG Chain (Performance Test)
# =============================================================================
def example_very_long_chain():
    """
    Extremely long sequential chain to test performance limits.
    """
    pipeline = Pipeline(name="long_chain")

    num_steps = 1000
    datasets = [Dataset(f"step_{i}") for i in range(num_steps)]

    @pipeline.task()
    def start() -> datasets[0]:
        return pd.DataFrame({"value": [1]})

    for i in range(num_steps - 1):
        input_ds = datasets[i]
        output_ds = datasets[i + 1]

        @pipeline.task()
        def step(data: input_ds) -> output_ds:
            return data + 1

    return pipeline


# =============================================================================
# Error 12: Task Execution Failure
# =============================================================================
def example_task_execution_failure():
    """
    Task that raises an error during execution.
    """
    pipeline = Pipeline(name="execution_failure")

    input_data = Dataset("input")
    output = Dataset("output")

    @pipeline.task()
    def extract() -> input_data:
        return pd.DataFrame({"value": [1, 2, 3]})

    @pipeline.task()
    def failing_task(data: input_data) -> output:
        """Task that intentionally fails."""
        raise ValueError("Intentional failure for testing")

    return pipeline


# =============================================================================
# Error 13: Type Annotation Without Dataset Instance
# =============================================================================
def example_wrong_annotation_type():
    """
    Task with type annotation that's not a Dataset.
    """
    pipeline = Pipeline(name="wrong_annotation")

    valid_input = Dataset("input")
    valid_output = Dataset("output")

    @pipeline.task()
    def extract() -> valid_input:
        return pd.DataFrame({"value": [1, 2, 3]})

    @pipeline.task()
    def process(data: valid_input) -> int:
        """Returns int instead of Dataset - should be caught."""
        return 42

    return pipeline


# =============================================================================
# Error 14: None as Dataset
# =============================================================================
def example_none_dataset():
    """
    Using None in dataset positions.
    """
    pipeline = Pipeline(name="none_dataset")

    input_data = Dataset("input")

    @pipeline.task()
    def extract() -> input_data:
        return pd.DataFrame({"value": [1, 2, 3]})

    @pipeline.task()
    def process(data: input_data) -> None:
        """None as output type."""
        return None

    return pipeline


# =============================================================================
# Test Runner
# =============================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("ERROR CASE EXAMPLES (Expected to Fail)")
    print("=" * 70)
    print()

    error_cases = [
        ("Circular Dependency", example_circular_dependency, "cycle_error"),
        ("Self Circular", example_self_circular, "cycle_error"),
        ("Multiple Producers", example_multiple_producers, "validation_error"),
        ("Missing Producer", example_missing_producer, "validation_error"),
        ("Disconnected Segments", example_disconnected_segments, "may_be_valid"),
        ("Empty Pipeline", example_empty_pipeline, "may_be_valid"),
        ("Task No Outputs", example_task_no_outputs, "may_be_valid"),
        ("Mismatched Return", example_mismatched_return, "runtime_error"),
        ("Invalid Dataset Names", example_invalid_dataset_names, "may_be_valid"),
        ("Duplicate Dataset Instances", example_duplicate_dataset_instances, "may_be_valid"),
        ("Very Long Chain", example_very_long_chain, "performance_test"),
        ("Task Execution Failure", example_task_execution_failure, "runtime_error"),
        ("Wrong Annotation Type", example_wrong_annotation_type, "may_be_valid"),
        ("None Dataset", example_none_dataset, "may_be_valid"),
    ]

    for name, example_fn, error_type in error_cases:
        print(f"Testing: {name} ({error_type})")
        try:
            pipeline = example_fn()
            print(f"  ⚠ Pipeline created: {pipeline.name}")

            # Try to access tasks (triggers DAG build)
            try:
                tasks = pipeline.tasks
                print(f"  ⚠ DAG built successfully with {len(tasks)} tasks")

                # Try to get execution order
                try:
                    order = pipeline.get_execution_order()
                    print(f"  ⚠ Execution order succeeded: {len(order)} tasks")
                except Exception as e:
                    print(f"  ✓ Execution order failed (expected): {type(e).__name__}")

            except Exception as e:
                print(f"  ✓ DAG build failed (expected): {type(e).__name__}: {e}")

        except Exception as e:
            print(f"  ✓ Pipeline creation failed (expected): {type(e).__name__}: {e}")

        print()

    print("=" * 70)
    print("Error case testing complete!")
    print("Note: Some cases may succeed if they represent valid edge cases.")
    print("=" * 70)
