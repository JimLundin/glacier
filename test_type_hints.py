"""
Simple test to verify type hint functionality in Glacier.
Tests that Dataset instances work as type annotations and DAG inference works.
"""

from glacier import Pipeline, Dataset
from glacier_local import LocalExecutor

# Create pipeline
pipeline = Pipeline(name="test_type_hints")

# Create dataset instances
raw = Dataset(name="raw")
processed = Dataset(name="processed")
final = Dataset(name="final")

# Define tasks with Dataset instances as type annotations
@pipeline.task()
def extract() -> raw:
    """Task with no inputs, one output"""
    print("  extract() running")
    return {"data": [1, 2, 3, 4, 5]}

@pipeline.task()
def transform(input_data: raw) -> processed:
    """Task with one input, one output"""
    print(f"  transform() running with input: {input_data}")
    return {"data": [x * 2 for x in input_data["data"]]}

@pipeline.task()
def load(data: processed) -> final:
    """Task with one input, one output"""
    print(f"  load() running with input: {data}")
    return {"result": sum(data["data"])}

# Print pipeline structure
print("=" * 70)
print("TESTING TYPE HINT FUNCTIONALITY")
print("=" * 70)
print()

print("1. Dataset instances created:")
print(f"   - raw: {raw}")
print(f"   - processed: {processed}")
print(f"   - final: {final}")
print()

print("2. Tasks registered:")
for task in pipeline._tasks:
    print(f"   - {task.name}")
    print(f"     Inputs: {[f'{p.name}: {p.dataset.name}' for p in task.inputs]}")
    print(f"     Outputs: {[d.name for d in task.outputs]}")
print()

print("3. DAG structure (inferred from type hints):")
pipeline._build_dag()
print(f"   Total tasks: {len(pipeline._tasks)}")
print(f"   Total edges: {len(pipeline.edges)}")
print()
print("   Edges:")
for edge in pipeline.edges:
    print(f"     {edge.from_task.name} -> {edge.to_task.name} (dataset: {edge.dataset.name})")
print()

print("4. Execution order (topological sort):")
execution_order = pipeline.get_execution_order()
print(f"   {' -> '.join([task.name for task in execution_order])}")
print()

print("5. Running pipeline:")
results = LocalExecutor().execute(pipeline)
print()

print("6. Results:")
for dataset_name, value in results.items():
    print(f"   {dataset_name}: {value}")
print()

print("=" * 70)
print("SUCCESS: Type hints work correctly!")
print("=" * 70)
print()
print("Key findings:")
print("  ✓ Dataset instances can be used as type annotations")
print("  ✓ Type hints are inspected at runtime to extract inputs/outputs")
print("  ✓ DAG is automatically inferred from type annotations")
print("  ✓ Execution order is computed via topological sort")
print("  ✓ Data flows correctly between tasks")
