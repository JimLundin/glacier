"""
Simple ETL Pipeline Example

Demonstrates the basic pattern:
- Declare datasets
- Define tasks with type hints
- Pipeline automatically infers DAG
"""

from glacier import Dataset, task, Pipeline, compute


# 1. Declare datasets
raw_users = Dataset("raw_users")
clean_users = Dataset("clean_users")
user_metrics = Dataset("user_metrics")


# 2. Define tasks - signatures declare data flow
@task(compute=compute.local())
def extract_users() -> raw_users:
    """Extract users from API"""
    print("Extracting users from API...")
    # Simulate API call
    data = [
        {"id": 1, "name": "Alice", "age": 30},
        {"id": 2, "name": "Bob", "age": 25},
        {"id": 3, "name": "Charlie", "age": 35},
    ]
    return data


@task(compute=compute.local())
def clean_users(users: raw_users) -> clean_users:
    """Clean and validate user data"""
    print(f"Cleaning {len(users)} users...")
    # Simple cleaning - uppercase names
    cleaned = [
        {**user, "name": user["name"].upper()}
        for user in users
    ]
    return cleaned


@task(compute=compute.serverless(memory=512))
def compute_metrics(users: clean_users) -> user_metrics:
    """Compute user metrics"""
    print(f"Computing metrics for {len(users)} users...")
    metrics = {
        "total_users": len(users),
        "average_age": sum(u["age"] for u in users) / len(users),
    }
    return metrics


# 3. Create pipeline - DAG inferred from signatures
# extract_users() -> raw_users -> clean_users() -> clean_users -> compute_metrics()
pipeline = Pipeline(
    tasks=[extract_users, clean_users, compute_metrics],
    name="user-analytics"
)


if __name__ == "__main__":
    # Validate the pipeline
    print("Pipeline:")
    print(pipeline)
    print()

    # Show the DAG
    print(pipeline.visualize())
    print()

    # Validate structure
    print("Validating pipeline...")
    pipeline.validate()
    print("✓ Pipeline is valid!")
    print()

    # Show execution order
    print("Execution order:")
    for i, task in enumerate(pipeline.get_execution_order(), 1):
        print(f"  {i}. {task.name}")
    print()

    # Show source and sink tasks
    print(f"Source tasks: {[t.name for t in pipeline.get_source_tasks()]}")
    print(f"Sink tasks: {[t.name for t in pipeline.get_sink_tasks()]}")
