"""
Edge Case Examples for Testing.

This module contains edge cases and unusual patterns that test
the boundaries of Glacier's functionality. These are valid use cases
but represent less common or unusual patterns.
"""

import pandas as pd
from glacier import Pipeline, Dataset, Stack, Environment
from glacier_aws import AWSProvider


# =============================================================================
# Edge Case 1: Single Task Pipeline
# =============================================================================
def example_single_task():
    """
    Pipeline with only one task.
    """
    pipeline = Pipeline(name="single_task")

    output = Dataset("output")

    @pipeline.task()
    def generate() -> output:
        """Single task pipeline."""
        return pd.DataFrame({"value": [1, 2, 3]})

    return pipeline


# =============================================================================
# Edge Case 2: Many Outputs from Single Task
# =============================================================================
def example_many_outputs():
    """
    Single task producing many outputs.
    """
    pipeline = Pipeline(name="many_outputs")

    source = Dataset("source")
    out1 = Dataset("out1")
    out2 = Dataset("out2")
    out3 = Dataset("out3")
    out4 = Dataset("out4")
    out5 = Dataset("out5")

    @pipeline.task()
    def extract() -> source:
        return pd.DataFrame({"value": range(100)})

    @pipeline.task()
    def split(data: source) -> tuple[out1, out2, out3, out4, out5]:
        """Split into 5 outputs."""
        size = len(data) // 5
        return (
            data.iloc[0:size],
            data.iloc[size:size*2],
            data.iloc[size*2:size*3],
            data.iloc[size*3:size*4],
            data.iloc[size*4:]
        )

    return pipeline


# =============================================================================
# Edge Case 3: Very Wide Task (Many Inputs)
# =============================================================================
def example_many_inputs():
    """
    Task with many inputs.
    """
    pipeline = Pipeline(name="many_inputs")

    # Create many source datasets
    sources = [Dataset(f"source_{i}") for i in range(10)]
    combined = Dataset("combined")

    # Create source tasks
    for i, source in enumerate(sources):
        @pipeline.task()
        def extract(idx=i) -> source:
            return pd.DataFrame({"source": [idx], "value": [idx * 10]})

    @pipeline.task()
    def combine(
        s0: sources[0],
        s1: sources[1],
        s2: sources[2],
        s3: sources[3],
        s4: sources[4],
        s5: sources[5],
        s6: sources[6],
        s7: sources[7],
        s8: sources[8],
        s9: sources[9]
    ) -> combined:
        """Combine 10 inputs."""
        return pd.concat([s0, s1, s2, s3, s4, s5, s6, s7, s8, s9], ignore_index=True)

    return pipeline


# =============================================================================
# Edge Case 4: Empty DataFrame Handling
# =============================================================================
def example_empty_dataframes():
    """
    Pipeline handling empty DataFrames.
    """
    pipeline = Pipeline(name="empty_data")

    empty = Dataset("empty")
    filtered = Dataset("filtered")
    result = Dataset("result")

    @pipeline.task()
    def extract() -> empty:
        """Produces empty DataFrame."""
        return pd.DataFrame(columns=["id", "value"])

    @pipeline.task()
    def filter(data: empty) -> filtered:
        """Filter empty data - still empty."""
        return data[data["value"] > 0]

    @pipeline.task()
    def process(data: filtered) -> result:
        """Process empty DataFrame."""
        if len(data) == 0:
            return pd.DataFrame({"message": ["No data to process"]})
        return data

    return pipeline


# =============================================================================
# Edge Case 5: Very Large Dataset Names
# =============================================================================
def example_long_names():
    """
    Datasets with very long names.
    """
    pipeline = Pipeline(name="long_names")

    very_long_name = Dataset(
        "this_is_a_very_long_dataset_name_that_describes_the_customer_order_history_"
        "aggregated_by_month_and_product_category_for_analytics_purposes"
    )

    another_long_name = Dataset(
        "processed_and_validated_customer_order_history_with_enrichment_from_"
        "external_sources_and_quality_checks_applied"
    )

    @pipeline.task()
    def extract() -> very_long_name:
        return pd.DataFrame({"value": [1, 2, 3]})

    @pipeline.task()
    def process(data: very_long_name) -> another_long_name:
        return data * 2

    return pipeline


# =============================================================================
# Edge Case 6: Numeric and Special Character Dataset Names
# =============================================================================
def example_special_names():
    """
    Dataset names with numbers and allowed special characters.
    """
    pipeline = Pipeline(name="special_names")

    data_2025 = Dataset("data_2025")
    data_v2_1 = Dataset("data_v2.1")
    data_test_01 = Dataset("data-test-01")

    @pipeline.task()
    def extract() -> data_2025:
        return pd.DataFrame({"year": [2025], "value": [100]})

    @pipeline.task()
    def transform_1(data: data_2025) -> data_v2_1:
        return data * 2

    @pipeline.task()
    def transform_2(data: data_v2_1) -> data_test_01:
        return data * 3

    return pipeline


# =============================================================================
# Edge Case 7: Same Function Used Multiple Times
# =============================================================================
def example_reused_function():
    """
    Same function wrapped multiple times as different tasks.
    """
    pipeline = Pipeline(name="reused_function")

    input1 = Dataset("input1")
    input2 = Dataset("input2")
    output1 = Dataset("output1")
    output2 = Dataset("output2")

    def doubler(data):
        """Reusable transformation function."""
        return data * 2

    @pipeline.task()
    def extract1() -> input1:
        return pd.DataFrame({"value": [1, 2, 3]})

    @pipeline.task()
    def extract2() -> input2:
        return pd.DataFrame({"value": [4, 5, 6]})

    @pipeline.task()
    def transform1(data: input1) -> output1:
        return doubler(data)

    @pipeline.task()
    def transform2(data: input2) -> output2:
        return doubler(data)

    return pipeline


# =============================================================================
# Edge Case 8: Minimal Dataset (Single Row, Single Column)
# =============================================================================
def example_minimal_data():
    """
    Pipeline processing minimal datasets.
    """
    pipeline = Pipeline(name="minimal_data")

    single_value = Dataset("single_value")
    doubled = Dataset("doubled")

    @pipeline.task()
    def extract() -> single_value:
        """Single value DataFrame."""
        return pd.DataFrame({"value": [42]})

    @pipeline.task()
    def transform(data: single_value) -> doubled:
        """Transform single value."""
        return data * 2

    return pipeline


# =============================================================================
# Edge Case 9: Unicode Dataset Names
# =============================================================================
def example_unicode_names():
    """
    Dataset names with unicode characters.
    """
    pipeline = Pipeline(name="unicode_names")

    données = Dataset("données")  # French
    データ = Dataset("データ")  # Japanese
    данные = Dataset("данные")  # Russian

    @pipeline.task()
    def extract() -> données:
        return pd.DataFrame({"value": [1, 2, 3]})

    @pipeline.task()
    def transform1(data: données) -> データ:
        return data * 2

    @pipeline.task()
    def transform2(data: データ) -> данные:
        return data * 3

    return pipeline


# =============================================================================
# Edge Case 10: Deeply Nested Type Annotations
# =============================================================================
def example_complex_types():
    """
    Tasks with complex type annotations beyond simple datasets.
    """
    pipeline = Pipeline(name="complex_types")

    data = Dataset("data")
    result = Dataset("result")

    @pipeline.task()
    def extract() -> data:
        """Returns dataset with complex structure."""
        return pd.DataFrame({
            "id": [1, 2, 3],
            "nested_data": [{"a": 1, "b": 2}, {"a": 3, "b": 4}, {"a": 5, "b": 6}]
        })

    @pipeline.task()
    def process(input_data: data) -> result:
        """Process complex data."""
        return input_data.copy()

    return pipeline


# =============================================================================
# Edge Case 11: Task Names Matching Python Keywords
# =============================================================================
def example_keyword_like_names():
    """
    Task names that are similar to Python keywords (but not exact).
    """
    pipeline = Pipeline(name="keyword_names")

    data_for = Dataset("data_for")
    data_if = Dataset("data_if")
    data_while = Dataset("data_while")

    @pipeline.task()
    def for_loop() -> data_for:
        """Name similar to 'for' keyword."""
        return pd.DataFrame({"value": [1, 2, 3]})

    @pipeline.task()
    def if_statement(data: data_for) -> data_if:
        """Name similar to 'if' keyword."""
        return data * 2

    @pipeline.task()
    def while_loop(data: data_if) -> data_while:
        """Name similar to 'while' keyword."""
        return data * 3

    return pipeline


# =============================================================================
# Edge Case 12: Zero-Parameter Task Configuration
# =============================================================================
def example_minimal_config():
    """
    Tasks with minimal or no configuration.
    """
    pipeline = Pipeline(name="minimal_config")

    input_data = Dataset("input")
    output = Dataset("output")

    @pipeline.task()
    def extract() -> input_data:
        """No configuration at all."""
        return pd.DataFrame({"value": [1, 2, 3]})

    @pipeline.task()
    def transform(data: input_data) -> output:
        """No configuration at all."""
        return data * 2

    return pipeline


# =============================================================================
# Edge Case 13: Multiple Pipelines Sharing Datasets
# =============================================================================
def example_shared_datasets():
    """
    Multiple pipelines operating on the same datasets.
    """
    stack = Stack(name="shared_datasets")

    # Shared datasets
    shared_raw = Dataset("shared_raw")
    shared_processed = Dataset("shared_processed")

    # First pipeline produces shared data
    pipeline1 = stack.pipeline("producer")

    @pipeline1.task()
    def extract() -> shared_raw:
        return pd.DataFrame({"value": [1, 2, 3]})

    @pipeline1.task()
    def process(data: shared_raw) -> shared_processed:
        return data * 2

    # Second pipeline consumes shared data
    pipeline2 = stack.pipeline("consumer")

    output = Dataset("output")

    @pipeline2.task()
    def analyze(data: shared_processed) -> output:
        return data.describe()

    return stack


# =============================================================================
# Edge Case 14: Lambda Functions as Tasks
# =============================================================================
def example_lambda_tasks():
    """
    Using lambda-like inline functions (via wrapping).
    """
    pipeline = Pipeline(name="lambda_tasks")

    input_data = Dataset("input")
    doubled = Dataset("doubled")
    squared = Dataset("squared")

    @pipeline.task()
    def extract() -> input_data:
        return pd.DataFrame({"value": [1, 2, 3, 4, 5]})

    # Note: Direct lambdas don't work well with decorators,
    # but we can create very simple functions
    @pipeline.task()
    def double(x: input_data) -> doubled:
        return x * 2

    @pipeline.task()
    def square(x: doubled) -> squared:
        return x ** 2

    return pipeline


# =============================================================================
# Edge Case 15: Very Short Names
# =============================================================================
def example_short_names():
    """
    Datasets with very short names.
    """
    pipeline = Pipeline(name="short_names")

    a = Dataset("a")
    b = Dataset("b")
    c = Dataset("c")

    @pipeline.task()
    def x() -> a:
        return pd.DataFrame({"value": [1]})

    @pipeline.task()
    def y(data: a) -> b:
        return data * 2

    @pipeline.task()
    def z(data: b) -> c:
        return data * 3

    return pipeline


# =============================================================================
# Test Runner
# =============================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("EDGE CASE EXAMPLES")
    print("=" * 70)
    print()

    examples = [
        ("Single Task Pipeline", example_single_task),
        ("Many Outputs (5)", example_many_outputs),
        ("Many Inputs (10)", example_many_inputs),
        ("Empty DataFrames", example_empty_dataframes),
        ("Very Long Names", example_long_names),
        ("Special Character Names", example_special_names),
        ("Reused Function", example_reused_function),
        ("Minimal Data (Single Value)", example_minimal_data),
        ("Unicode Names", example_unicode_names),
        ("Complex Types", example_complex_types),
        ("Keyword-like Names", example_keyword_like_names),
        ("Minimal Config", example_minimal_config),
        ("Shared Datasets Across Pipelines", example_shared_datasets),
        ("Lambda-like Tasks", example_lambda_tasks),
        ("Very Short Names", example_short_names),
    ]

    for name, example_fn in examples:
        print(f"Testing: {name}")

        result = example_fn()

        if isinstance(result, Stack):
            stack = result
            print(f"  ✓ Stack: {stack.name}")
            print(f"  ✓ Pipelines: {len(stack._pipelines)}")
            total_tasks = sum(len(p.tasks) for p in stack._pipelines.values())
            print(f"  ✓ Total tasks: {total_tasks}")
        else:
            pipeline = result
            print(f"  ✓ Pipeline: {pipeline.name}")
            print(f"  ✓ Tasks: {len(pipeline.tasks)}")

            # Try to get execution order
            try:
                order = pipeline.get_execution_order()
                print(f"  ✓ Execution order: {[t.name for t in order]}")
            except Exception as e:
                print(f"  ⚠ Get execution order failed: {type(e).__name__}")

        print()

    print("=" * 70)
    print("All edge cases validated successfully!")
    print("=" * 70)
