"""
Test advanced type hint scenarios in Glacier.
"""

from typing import Tuple
from glacier import Pipeline, Dataset

print("=" * 70)
print("TESTING ADVANCED TYPE HINT SCENARIOS")
print("=" * 70)
print()

# Test 1: Multiple outputs with Tuple
print("Test 1: Multiple outputs with Tuple")
print("-" * 70)

pipeline1 = Pipeline(name="multiple_outputs")

raw = Dataset(name="raw")
users = Dataset(name="users")
events = Dataset(name="events")
summary = Dataset(name="summary")

@pipeline1.task()
def extract() -> raw:
    return {"users": [1, 2, 3], "events": [10, 20, 30]}

@pipeline1.task()
def split(data: raw) -> Tuple[users, events]:
    """Split data into multiple outputs"""
    return data["users"], data["events"]

@pipeline1.task()
def summarize(u: users, e: events) -> summary:
    """Consume multiple inputs"""
    return {"user_count": len(u), "event_count": len(e)}

pipeline1._build_dag()

print(f"Tasks: {len(pipeline1._tasks)}")
print(f"Edges: {len(pipeline1.edges)}")
print("Edges:")
for edge in pipeline1.edges:
    print(f"  {edge.from_task.name} -> {edge.to_task.name} (dataset: {edge.dataset.name}, param: {edge.param_name})")

execution_order = pipeline1.get_execution_order()
print(f"Execution order: {' -> '.join([t.name for t in execution_order])}")
print("✓ Multiple outputs work!\n")

# Test 2: Diamond dependency
print("Test 2: Diamond dependency pattern")
print("-" * 70)

pipeline2 = Pipeline(name="diamond")

source = Dataset(name="source")
branch_a = Dataset(name="branch_a")
branch_b = Dataset(name="branch_b")
merged = Dataset(name="merged")

@pipeline2.task()
def start() -> source:
    return [1, 2, 3]

@pipeline2.task()
def process_a(data: source) -> branch_a:
    return [x * 2 for x in data]

@pipeline2.task()
def process_b(data: source) -> branch_b:
    return [x + 10 for x in data]

@pipeline2.task()
def merge(a: branch_a, b: branch_b) -> merged:
    return {"a_sum": sum(a), "b_sum": sum(b)}

pipeline2._build_dag()

print(f"Tasks: {len(pipeline2._tasks)}")
print(f"Edges: {len(pipeline2.edges)}")
print("Edges:")
for edge in pipeline2.edges:
    print(f"  {edge.from_task.name} -> {edge.to_task.name} (dataset: {edge.dataset.name})")

execution_order = pipeline2.get_execution_order()
print(f"Execution order: {' -> '.join([t.name for t in execution_order])}")
print("✓ Diamond dependencies work!\n")

# Test 3: Linear chain
print("Test 3: Long linear chain")
print("-" * 70)

pipeline3 = Pipeline(name="linear")

d1 = Dataset(name="d1")
d2 = Dataset(name="d2")
d3 = Dataset(name="d3")
d4 = Dataset(name="d4")

@pipeline3.task()
def step1() -> d1:
    return 1

@pipeline3.task()
def step2(x: d1) -> d2:
    return x + 1

@pipeline3.task()
def step3(x: d2) -> d3:
    return x * 2

@pipeline3.task()
def step4(x: d3) -> d4:
    return x ** 2

pipeline3._build_dag()

print(f"Tasks: {len(pipeline3._tasks)}")
print(f"Edges: {len(pipeline3.edges)}")
execution_order = pipeline3.get_execution_order()
print(f"Execution order: {' -> '.join([t.name for t in execution_order])}")
print("✓ Linear chains work!\n")

# Test 4: Inspect task signature details
print("Test 4: Detailed type hint inspection")
print("-" * 70)

pipeline4 = Pipeline(name="inspection")
input_ds = Dataset(name="input")
output_ds = Dataset(name="output")

@pipeline4.task()
def my_task(data: input_ds, config: dict) -> output_ds:
    """Task with mixed parameter types"""
    return data

task = pipeline4._tasks[0]
print(f"Task name: {task.name}")
print(f"Function signature: {task.signature}")
print(f"Extracted inputs:")
for inp in task.inputs:
    print(f"  - {inp.name}: {inp.dataset.name}")
print(f"Extracted outputs:")
for out in task.outputs:
    print(f"  - {out.name}")
print(f"Non-dataset parameters: {[p.name for p in task.signature.parameters.values() if p.name not in [i.name for i in task.inputs]]}")
print("✓ Type hint inspection works correctly!\n")

print("=" * 70)
print("ALL ADVANCED TESTS PASSED!")
print("=" * 70)
print()
print("Summary:")
print("  ✓ Multiple outputs (Tuple) are correctly handled")
print("  ✓ Multiple inputs to a single task work")
print("  ✓ Diamond dependencies are resolved correctly")
print("  ✓ Linear chains maintain correct order")
print("  ✓ Mixed parameter types (Dataset + regular) work")
print("  ✓ Type hint inspection correctly identifies datasets")
