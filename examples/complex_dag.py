"""
Complex DAG Example

Demonstrates:
- Multiple source tasks (parallel extraction)
- Fan-in (multiple inputs to one task)
- Fan-out (one output to multiple tasks)
- Diamond pattern
"""

from glacier import Dataset, task, Pipeline, compute


# Declare datasets
raw_users = Dataset("raw_users")
raw_orders = Dataset("raw_orders")
raw_products = Dataset("raw_products")

clean_users = Dataset("clean_users")
clean_orders = Dataset("clean_orders")

merged_data = Dataset("merged_data")
user_metrics = Dataset("user_metrics")
order_report = Dataset("order_report")


# Source tasks (no inputs, run in parallel)
@task(compute=compute.serverless(memory=512))
def extract_users() -> raw_users:
    """Extract users from API"""
    print("Extracting users...")
    return [
        {"user_id": 1, "name": "Alice", "age": 30},
        {"user_id": 2, "name": "Bob", "age": 25},
    ]


@task(compute=compute.serverless(memory=512))
def extract_orders() -> raw_orders:
    """Extract orders from database"""
    print("Extracting orders...")
    return [
        {"order_id": 101, "user_id": 1, "amount": 100},
        {"order_id": 102, "user_id": 2, "amount": 200},
    ]


@task(compute=compute.serverless(memory=512))
def extract_products() -> raw_products:
    """Extract products from catalog"""
    print("Extracting products...")
    return [
        {"product_id": 1, "name": "Widget"},
        {"product_id": 2, "name": "Gadget"},
    ]


# Transform tasks (single input, single output)
@task(compute=compute.local())
def clean_users_data(users: raw_users) -> clean_users:
    """Clean user data"""
    print(f"Cleaning {len(users)} users...")
    return [{**u, "name": u["name"].upper()} for u in users]


@task(compute=compute.local())
def clean_orders_data(orders: raw_orders) -> clean_orders:
    """Clean order data"""
    print(f"Cleaning {len(orders)} orders...")
    return [{**o, "amount": float(o["amount"])} for o in orders]


# Fan-in task (multiple inputs)
@task(compute=compute.container(image="analytics:latest", cpu=2, memory=4096))
def merge_user_orders(users: clean_users, orders: clean_orders) -> merged_data:
    """Merge users with their orders"""
    print(f"Merging {len(users)} users with {len(orders)} orders...")
    # Simple join simulation
    merged = []
    for order in orders:
        user = next((u for u in users if u["user_id"] == order["user_id"]), None)
        if user:
            merged.append({**order, "user_name": user["name"]})
    return merged


# Fan-out tasks (both depend on merged_data)
@task(compute=compute.local())
def compute_user_metrics(data: merged_data) -> user_metrics:
    """Compute user-level metrics"""
    print(f"Computing metrics from {len(data)} records...")
    return {
        "total_orders": len(data),
        "total_revenue": sum(d["amount"] for d in data),
    }


@task(compute=compute.local())
def generate_order_report(data: merged_data) -> order_report:
    """Generate order report"""
    print(f"Generating report from {len(data)} records...")
    return {
        "orders": data,
        "summary": f"{len(data)} orders processed"
    }


# Create pipeline - DAG inferred automatically
#
# Expected DAG:
#   extract_users --> clean_users_data ----\
#                                           \
#                                            +--> merge_user_orders --+--> compute_user_metrics
#                                           /                         \
#   extract_orders -> clean_orders_data --/                           +--> generate_order_report
#
#   extract_products (orphan - not connected)

pipeline = Pipeline(
    tasks=[
        extract_users, extract_orders, extract_products,
        clean_users_data, clean_orders_data,
        merge_user_orders,
        compute_user_metrics, generate_order_report
    ],
    name="complex-analytics"
)


if __name__ == "__main__":
    print("=" * 70)
    print("COMPLEX DAG EXAMPLE")
    print("=" * 70)
    print()

    # Show the full DAG
    print(pipeline.visualize())
    print()

    # Validate
    print("Validating pipeline...")
    try:
        pipeline.validate()
        print("✓ Pipeline is valid!")
    except ValueError as e:
        print(f"✗ Pipeline validation failed: {e}")
    print()

    # Show execution order
    print("Execution order:")
    try:
        for i, task_obj in enumerate(pipeline.get_execution_order(), 1):
            print(f"  {i}. {task_obj.name}")
    except ValueError as e:
        print(f"  Error: {e}")
    print()

    # Show DAG structure
    print("Source tasks (no dependencies):")
    for t in pipeline.get_source_tasks():
        print(f"  - {t.name}")
    print()

    print("Sink tasks (no consumers):")
    for t in pipeline.get_sink_tasks():
        print(f"  - {t.name}")
    print()

    # Show each task's dependencies
    print("Task dependencies:")
    for task_obj in pipeline.tasks:
        deps = pipeline.get_dependencies(task_obj)
        consumers = pipeline.get_consumers(task_obj)
        print(f"  {task_obj.name}:")
        if deps:
            print(f"    depends on: {[d.name for d in deps]}")
        if consumers:
            print(f"    consumed by: {[c.name for c in consumers]}")
        if not deps and not consumers:
            print(f"    (orphan - not connected to pipeline)")
    print()

    print("=" * 70)
    print("DAG STRUCTURE SUMMARY")
    print("=" * 70)
    print(f"Total tasks: {len(pipeline.tasks)}")
    print(f"Total edges: {len(pipeline.edges)}")
    print(f"Source tasks: {len(pipeline.get_source_tasks())}")
    print(f"Sink tasks: {len(pipeline.get_sink_tasks())}")
