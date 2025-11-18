"""
DAG Pattern Examples for Testing.

This module contains examples of different DAG topologies that Glacier supports.
Each example demonstrates a specific DAG pattern and can be used for testing
the pipeline's DAG inference and validation logic.
"""

import pandas as pd
from glacier import Pipeline, Dataset


# =============================================================================
# Pattern 1: Linear Pipeline (A → B → C)
# =============================================================================
def example_linear_pipeline():
    """
    Simplest pattern: linear chain of tasks.

    DAG: extract → transform → load
    """
    pipeline = Pipeline(name="linear")

    raw = Dataset("raw")
    processed = Dataset("processed")
    final = Dataset("final")

    @pipeline.task()
    def extract() -> raw:
        """Source task - no inputs."""
        return pd.DataFrame({"id": [1, 2, 3], "value": [10, 20, 30]})

    @pipeline.task()
    def transform(data: raw) -> processed:
        """Middle task - one input, one output."""
        return data * 2

    @pipeline.task()
    def load(data: processed) -> final:
        """Sink task - one input, one output."""
        return data.copy()

    return pipeline


# =============================================================================
# Pattern 2: Branching (A → B, A → C)
# =============================================================================
def example_branching_pipeline():
    """
    One task produces output consumed by multiple tasks.

    DAG:
           ┌→ process_a → output_a
    extract┤
           └→ process_b → output_b
    """
    pipeline = Pipeline(name="branching")

    raw = Dataset("raw")
    output_a = Dataset("output_a")
    output_b = Dataset("output_b")

    @pipeline.task()
    def extract() -> raw:
        """Single source feeding multiple consumers."""
        return pd.DataFrame({"id": [1, 2, 3], "value": [10, 20, 30]})

    @pipeline.task()
    def process_a(data: raw) -> output_a:
        """First branch."""
        return data * 2

    @pipeline.task()
    def process_b(data: raw) -> output_b:
        """Second branch."""
        return data * 3

    return pipeline


# =============================================================================
# Pattern 3: Joining (A → C, B → C)
# =============================================================================
def example_joining_pipeline():
    """
    Multiple tasks feed into a single task.

    DAG:
    extract_a → data_a ┐
                       ├→ merge → result
    extract_b → data_b ┘
    """
    pipeline = Pipeline(name="joining")

    data_a = Dataset("data_a")
    data_b = Dataset("data_b")
    result = Dataset("result")

    @pipeline.task()
    def extract_a() -> data_a:
        """First source."""
        return pd.DataFrame({"id": [1, 2], "a": [10, 20]})

    @pipeline.task()
    def extract_b() -> data_b:
        """Second source."""
        return pd.DataFrame({"id": [1, 2], "b": [100, 200]})

    @pipeline.task()
    def merge(left: data_a, right: data_b) -> result:
        """Join task - multiple inputs, one output."""
        return pd.merge(left, right, on="id")

    return pipeline


# =============================================================================
# Pattern 4: Diamond (A → B, A → C, B → D, C → D)
# =============================================================================
def example_diamond_pipeline():
    """
    Classic diamond pattern: branch then join.

    DAG:
           ┌→ process_1 → intermediate_1 ┐
    source ┤                              ├→ combine → final
           └→ process_2 → intermediate_2 ┘
    """
    pipeline = Pipeline(name="diamond")

    source = Dataset("source")
    intermediate_1 = Dataset("intermediate_1")
    intermediate_2 = Dataset("intermediate_2")
    final = Dataset("final")

    @pipeline.task()
    def extract() -> source:
        """Single source."""
        return pd.DataFrame({"id": [1, 2, 3], "value": [10, 20, 30]})

    @pipeline.task()
    def process_1(data: source) -> intermediate_1:
        """First parallel path."""
        return data * 2

    @pipeline.task()
    def process_2(data: source) -> intermediate_2:
        """Second parallel path."""
        return data * 3

    @pipeline.task()
    def combine(a: intermediate_1, b: intermediate_2) -> final:
        """Join point."""
        return a + b

    return pipeline


# =============================================================================
# Pattern 5: Multiple Outputs (Single Task)
# =============================================================================
def example_multiple_outputs_pipeline():
    """
    Single task produces multiple datasets.

    DAG:
           ┌→ left → process_left → output_left
    split  ┤
           └→ right → process_right → output_right
    """
    pipeline = Pipeline(name="multiple_outputs")

    source = Dataset("source")
    left = Dataset("left")
    right = Dataset("right")
    output_left = Dataset("output_left")
    output_right = Dataset("output_right")

    @pipeline.task()
    def extract() -> source:
        """Source task."""
        return pd.DataFrame({"id": [1, 2, 3, 4], "value": [10, 20, 30, 40]})

    @pipeline.task()
    def split(data: source) -> tuple[left, right]:
        """Task with multiple outputs."""
        mid = len(data) // 2
        return data.iloc[:mid], data.iloc[mid:]

    @pipeline.task()
    def process_left(data: left) -> output_left:
        """Process left partition."""
        return data * 2

    @pipeline.task()
    def process_right(data: right) -> output_right:
        """Process right partition."""
        return data * 3

    return pipeline


# =============================================================================
# Pattern 6: Complex Multi-Stage DAG
# =============================================================================
def example_complex_pipeline():
    """
    Complex DAG with multiple stages, branches, and joins.

    DAG:
                    ┌→ enrich_a → enriched_a ┐
    extract → raw → │                        ├→ join_1 → intermediate ┐
                    └→ enrich_b → enriched_b ┘                        │
                                                                       ├→ final_merge → output
    external → validated → transform → cleaned ────────────────────────┘
    """
    pipeline = Pipeline(name="complex")

    raw = Dataset("raw")
    enriched_a = Dataset("enriched_a")
    enriched_b = Dataset("enriched_b")
    intermediate = Dataset("intermediate")
    external = Dataset("external")
    validated = Dataset("validated")
    cleaned = Dataset("cleaned")
    output = Dataset("output")

    @pipeline.task()
    def extract() -> raw:
        """Main data source."""
        return pd.DataFrame({"id": [1, 2, 3], "value": [10, 20, 30]})

    @pipeline.task()
    def enrich_a(data: raw) -> enriched_a:
        """First enrichment path."""
        data = data.copy()
        data["enriched_a"] = data["value"] * 2
        return data

    @pipeline.task()
    def enrich_b(data: raw) -> enriched_b:
        """Second enrichment path."""
        data = data.copy()
        data["enriched_b"] = data["value"] * 3
        return data

    @pipeline.task()
    def join_1(a: enriched_a, b: enriched_b) -> intermediate:
        """First join."""
        return pd.merge(a, b, on=["id", "value"])

    @pipeline.task()
    def fetch_external() -> external:
        """External data source."""
        return pd.DataFrame({"id": [1, 2, 3], "external_flag": [True, False, True]})

    @pipeline.task()
    def validate(data: external) -> validated:
        """Validation step."""
        return data[data["external_flag"] == True]

    @pipeline.task()
    def transform(data: validated) -> cleaned:
        """Transform validated data."""
        return data.copy()

    @pipeline.task()
    def final_merge(main: intermediate, supplemental: cleaned) -> output:
        """Final merge of all paths."""
        return pd.merge(main, supplemental, on="id", how="left")

    return pipeline


# =============================================================================
# Pattern 7: Wide DAG (Many Parallel Tasks)
# =============================================================================
def example_wide_pipeline():
    """
    Many parallel tasks from single source.

    DAG:
           ┌→ task_1 → out_1 ┐
           ├→ task_2 → out_2 │
    source ├→ task_3 → out_3 ├→ combine → final
           ├→ task_4 → out_4 │
           └→ task_5 → out_5 ┘
    """
    pipeline = Pipeline(name="wide")

    source = Dataset("source")
    outputs = [Dataset(f"out_{i}") for i in range(1, 6)]
    final = Dataset("final")

    @pipeline.task()
    def extract() -> source:
        """Single source."""
        return pd.DataFrame({"value": [10]})

    # Create 5 parallel tasks
    for i in range(5):
        output = outputs[i]

        @pipeline.task()
        def process(data: source, multiplier=i+1) -> output:
            """Parallel processing."""
            return data * multiplier

    @pipeline.task()
    def combine(
        d1: outputs[0],
        d2: outputs[1],
        d3: outputs[2],
        d4: outputs[3],
        d5: outputs[4]
    ) -> final:
        """Combine all parallel results."""
        return d1 + d2 + d3 + d4 + d5

    return pipeline


# =============================================================================
# Pattern 8: Deep DAG (Long Chain)
# =============================================================================
def example_deep_pipeline():
    """
    Long sequential chain of tasks.

    DAG: step_0 → step_1 → step_2 → ... → step_9 → step_10
    """
    pipeline = Pipeline(name="deep")

    datasets = [Dataset(f"step_{i}") for i in range(11)]

    @pipeline.task()
    def start() -> datasets[0]:
        """Initial step."""
        return pd.DataFrame({"value": [1]})

    # Create chain of 10 transformation steps
    for i in range(10):
        input_ds = datasets[i]
        output_ds = datasets[i + 1]

        @pipeline.task()
        def step(data: input_ds) -> output_ds:
            """Sequential transformation."""
            return data + 1

    return pipeline


# =============================================================================
# Test Runner
# =============================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("DAG PATTERN EXAMPLES")
    print("=" * 70)
    print()

    examples = [
        ("Linear Pipeline", example_linear_pipeline),
        ("Branching Pipeline", example_branching_pipeline),
        ("Joining Pipeline", example_joining_pipeline),
        ("Diamond Pipeline", example_diamond_pipeline),
        ("Multiple Outputs", example_multiple_outputs_pipeline),
        ("Complex Multi-Stage", example_complex_pipeline),
        ("Wide Pipeline (Many Parallel)", example_wide_pipeline),
        ("Deep Pipeline (Long Chain)", example_deep_pipeline),
    ]

    for name, example_fn in examples:
        print(f"Testing: {name}")
        pipeline = example_fn()
        print(f"  ✓ Pipeline: {pipeline.name}")
        print(f"  ✓ Tasks: {len(pipeline.tasks)}")
        print(f"  ✓ Edges: {len(pipeline.edges)}")

        # Get execution order
        order = pipeline.get_execution_order()
        print(f"  ✓ Execution order: {[t.name for t in order]}")
        print()

    print("=" * 70)
    print("All DAG patterns validated successfully!")
    print("=" * 70)
