"""
Task Pattern Examples for Testing.

This module demonstrates different task input/output patterns and
configurations that Glacier supports. Each example shows how tasks
can be configured with various parameters and how they interact with datasets.
"""

import pandas as pd
from glacier import Pipeline, Dataset
from glacier.compute import resources as compute


# =============================================================================
# Pattern 1: Source Task (No Inputs)
# =============================================================================
def example_source_task():
    """
    Task with no inputs - data source/generator.

    This is the entry point for data into a pipeline.
    """
    pipeline = Pipeline(name="source_task")

    output = Dataset("output")

    @pipeline.task()
    def generate_data() -> output:
        """Source task - creates data from scratch."""
        return pd.DataFrame({
            "id": range(1, 101),
            "value": range(100, 200)
        })

    return pipeline


# =============================================================================
# Pattern 2: Single Input, Single Output
# =============================================================================
def example_single_io_task():
    """
    Most common pattern: one input, one output.
    """
    pipeline = Pipeline(name="single_io")

    input_data = Dataset("input")
    output_data = Dataset("output")

    @pipeline.task()
    def extract() -> input_data:
        """Source."""
        return pd.DataFrame({"value": [1, 2, 3]})

    @pipeline.task()
    def transform(data: input_data) -> output_data:
        """Single input, single output."""
        return data * 2

    return pipeline


# =============================================================================
# Pattern 3: Multiple Inputs, Single Output
# =============================================================================
def example_multiple_inputs_task():
    """
    Task that combines multiple datasets.
    """
    pipeline = Pipeline(name="multiple_inputs")

    source_a = Dataset("source_a")
    source_b = Dataset("source_b")
    source_c = Dataset("source_c")
    combined = Dataset("combined")

    @pipeline.task()
    def extract_a() -> source_a:
        """First source."""
        return pd.DataFrame({"id": [1, 2, 3], "a": [10, 20, 30]})

    @pipeline.task()
    def extract_b() -> source_b:
        """Second source."""
        return pd.DataFrame({"id": [1, 2, 3], "b": [100, 200, 300]})

    @pipeline.task()
    def extract_c() -> source_c:
        """Third source."""
        return pd.DataFrame({"id": [1, 2, 3], "c": [1000, 2000, 3000]})

    @pipeline.task()
    def merge_all(a: source_a, b: source_b, c: source_c) -> combined:
        """Multiple inputs combined into one output."""
        result = pd.merge(a, b, on="id")
        result = pd.merge(result, c, on="id")
        return result

    return pipeline


# =============================================================================
# Pattern 4: Single Input, Multiple Outputs
# =============================================================================
def example_multiple_outputs_task():
    """
    Task that splits/partitions data into multiple datasets.
    """
    pipeline = Pipeline(name="multiple_outputs")

    source = Dataset("source")
    even = Dataset("even")
    odd = Dataset("odd")

    @pipeline.task()
    def extract() -> source:
        """Source data."""
        return pd.DataFrame({"id": range(1, 11), "value": range(10, 20)})

    @pipeline.task()
    def split_by_parity(data: source) -> tuple[even, odd]:
        """Single input, multiple outputs."""
        even_rows = data[data["id"] % 2 == 0]
        odd_rows = data[data["id"] % 2 == 1]
        return even_rows, odd_rows

    return pipeline


# =============================================================================
# Pattern 5: Multiple Inputs, Multiple Outputs
# =============================================================================
def example_multiple_io_task():
    """
    Task with multiple inputs and outputs.
    """
    pipeline = Pipeline(name="multiple_io")

    data_a = Dataset("data_a")
    data_b = Dataset("data_b")
    merged = Dataset("merged")
    stats = Dataset("stats")

    @pipeline.task()
    def extract_a() -> data_a:
        """First source."""
        return pd.DataFrame({"id": [1, 2, 3], "value_a": [10, 20, 30]})

    @pipeline.task()
    def extract_b() -> data_b:
        """Second source."""
        return pd.DataFrame({"id": [1, 2, 3], "value_b": [100, 200, 300]})

    @pipeline.task()
    def process(a: data_a, b: data_b) -> tuple[merged, stats]:
        """Multiple inputs and outputs."""
        # Merge the datasets
        merged_data = pd.merge(a, b, on="id")

        # Calculate statistics
        stats_data = pd.DataFrame({
            "metric": ["count", "sum_a", "sum_b"],
            "value": [
                len(merged_data),
                a["value_a"].sum(),
                b["value_b"].sum()
            ]
        })

        return merged_data, stats_data

    return pipeline


# =============================================================================
# Pattern 6: Task with Compute Configuration
# =============================================================================
def example_compute_config_task():
    """
    Tasks with different compute configurations.
    """
    pipeline = Pipeline(name="compute_config")

    raw = Dataset("raw")
    processed = Dataset("processed")
    final = Dataset("final")

    @pipeline.task()
    def extract() -> raw:
        """Default compute (local)."""
        return pd.DataFrame({"value": [1, 2, 3]})

    @pipeline.task(compute=compute.serverless(memory=512, timeout=300))
    def heavy_process(data: raw) -> processed:
        """Task with serverless compute."""
        return data * 1000

    @pipeline.task(compute=compute.container(image="python:3.14", cpu=2, memory=4096))
    def containerized_process(data: processed) -> final:
        """Task with container compute."""
        return data / 100

    return pipeline


# =============================================================================
# Pattern 7: Task with Retries and Timeout
# =============================================================================
def example_task_with_retries():
    """
    Task configured with retries and timeout.
    """
    pipeline = Pipeline(name="retries_timeout")

    source = Dataset("source")
    output = Dataset("output")

    @pipeline.task()
    def extract() -> source:
        """Source."""
        return pd.DataFrame({"value": [1, 2, 3]})

    @pipeline.task(retries=3, timeout=60)
    def unreliable_process(data: source) -> output:
        """Task that might fail - will retry up to 3 times."""
        # Simulate unreliable operation
        import random
        if random.random() < 0.3:
            raise Exception("Simulated failure")
        return data * 2

    return pipeline


# =============================================================================
# Pattern 8: Sink Task (Output Only, No Downstream)
# =============================================================================
def example_sink_task():
    """
    Task that produces output but has no downstream consumers.
    """
    pipeline = Pipeline(name="sink_task")

    processed = Dataset("processed")
    saved = Dataset("saved")

    @pipeline.task()
    def extract() -> processed:
        """Generate data."""
        return pd.DataFrame({"id": [1, 2, 3], "value": [10, 20, 30]})

    @pipeline.task()
    def save_to_storage(data: processed) -> saved:
        """Sink task - final destination."""
        # In real scenario, would write to external storage
        print(f"Saving {len(data)} rows to storage")
        return data

    return pipeline


# =============================================================================
# Pattern 9: Task with No Parameters Beyond Datasets
# =============================================================================
def example_pure_task():
    """
    Task that only operates on datasets, no side effects.
    """
    pipeline = Pipeline(name="pure_task")

    input_data = Dataset("input")
    doubled = Dataset("doubled")
    squared = Dataset("squared")

    @pipeline.task()
    def extract() -> input_data:
        """Source."""
        return pd.DataFrame({"value": [1, 2, 3, 4, 5]})

    @pipeline.task()
    def double(data: input_data) -> doubled:
        """Pure function - deterministic."""
        return data * 2

    @pipeline.task()
    def square(data: doubled) -> squared:
        """Pure function - deterministic."""
        return data ** 2

    return pipeline


# =============================================================================
# Pattern 10: Task Naming Patterns
# =============================================================================
def example_task_naming():
    """
    Different task naming approaches.
    """
    pipeline = Pipeline(name="task_naming")

    raw = Dataset("raw_data")
    clean = Dataset("clean_data")
    enriched = Dataset("enriched_data")

    @pipeline.task()
    def extract_data_from_api() -> raw:
        """Descriptive verb-based name."""
        return pd.DataFrame({"value": [1, 2, 3]})

    @pipeline.task()
    def clean(data: raw) -> clean:
        """Simple action name."""
        return data.dropna()

    @pipeline.task()
    def add_calculated_fields(data: clean) -> enriched:
        """Descriptive transformation name."""
        data = data.copy()
        data["calculated"] = data["value"] * 2
        return data

    return pipeline


# =============================================================================
# Pattern 11: Conditional Logic in Tasks
# =============================================================================
def example_conditional_task():
    """
    Tasks with conditional logic inside.
    """
    pipeline = Pipeline(name="conditional")

    input_data = Dataset("input")
    filtered = Dataset("filtered")
    validated = Dataset("validated")

    @pipeline.task()
    def extract() -> input_data:
        """Source with various data."""
        return pd.DataFrame({
            "id": [1, 2, 3, 4, 5],
            "value": [10, -5, 20, -3, 15],
            "status": ["valid", "invalid", "valid", "valid", "invalid"]
        })

    @pipeline.task()
    def filter_positive(data: input_data) -> filtered:
        """Conditional filtering."""
        return data[data["value"] > 0]

    @pipeline.task()
    def validate_status(data: filtered) -> validated:
        """Conditional validation."""
        valid_data = data[data["status"] == "valid"]
        if len(valid_data) == 0:
            raise ValueError("No valid records found")
        return valid_data

    return pipeline


# =============================================================================
# Pattern 12: Data Aggregation Tasks
# =============================================================================
def example_aggregation_task():
    """
    Tasks that aggregate or summarize data.
    """
    pipeline = Pipeline(name="aggregation")

    raw = Dataset("raw")
    summary = Dataset("summary")
    stats = Dataset("stats")

    @pipeline.task()
    def extract() -> raw:
        """Source data."""
        return pd.DataFrame({
            "category": ["A", "B", "A", "B", "C", "A"],
            "value": [10, 20, 15, 25, 30, 12]
        })

    @pipeline.task()
    def summarize_by_category(data: raw) -> summary:
        """Aggregation task."""
        return data.groupby("category")["value"].sum().reset_index()

    @pipeline.task()
    def calculate_statistics(data: raw) -> stats:
        """Statistical aggregation."""
        return pd.DataFrame({
            "metric": ["count", "mean", "median", "std"],
            "value": [
                len(data),
                data["value"].mean(),
                data["value"].median(),
                data["value"].std()
            ]
        })

    return pipeline


# =============================================================================
# Test Runner
# =============================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("TASK PATTERN EXAMPLES")
    print("=" * 70)
    print()

    examples = [
        ("Source Task (No Inputs)", example_source_task),
        ("Single Input/Output", example_single_io_task),
        ("Multiple Inputs", example_multiple_inputs_task),
        ("Multiple Outputs", example_multiple_outputs_task),
        ("Multiple I/O", example_multiple_io_task),
        ("Compute Config", example_compute_config_task),
        ("Retries/Timeout", example_task_with_retries),
        ("Sink Task", example_sink_task),
        ("Pure Task", example_pure_task),
        ("Task Naming", example_task_naming),
        ("Conditional Logic", example_conditional_task),
        ("Aggregation", example_aggregation_task),
    ]

    for name, example_fn in examples:
        print(f"Testing: {name}")
        pipeline = example_fn()
        print(f"  ✓ Pipeline: {pipeline.name}")
        print(f"  ✓ Tasks: {len(pipeline.tasks)}")

        # Show task details
        for task in pipeline.tasks:
            inputs = [f"{p.name}:{p.dataset.name}" for p in task.inputs]
            outputs = [d.name for d in task.outputs]
            print(f"    • {task.name}: [{', '.join(inputs)}] → [{', '.join(outputs)}]")
        print()

    print("=" * 70)
    print("All task patterns validated successfully!")
    print("=" * 70)
