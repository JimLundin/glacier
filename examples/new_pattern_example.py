"""
New Pattern Example: Using @pipeline.task() decorator

This example demonstrates the new recommended pattern:
1. Create pipeline first
2. Register tasks using @pipeline.task() decorator
3. Tasks auto-register with the pipeline
4. Compile or execute with injected providers
"""

from glacier import Pipeline, Dataset, compute
from glacier.storage import ObjectStorage

# Create pipeline FIRST
pipeline = Pipeline(name="user-analytics")

# Declare datasets with storage configuration
raw_users = Dataset(
    "raw_users",
    storage=ObjectStorage(
        access_pattern="frequent",
        versioning=True,
    )
)

clean_users = Dataset(
    "clean_users",
    storage=ObjectStorage(
        access_pattern="frequent",
        # Provider-specific hints (optional)
        aws_storage_class="INTELLIGENT_TIERING",
    )
)

user_metrics = Dataset(
    "user_metrics",
    storage=ObjectStorage(
        access_pattern="infrequent",
    )
)


# Tasks auto-register via @pipeline.task()
@pipeline.task(compute=compute.local())
def extract_users() -> raw_users:
    """Extract users from API"""
    print("Extracting users from API...")
    # Simulate API call
    data = [
        {"id": 1, "name": "Alice", "age": 30, "city": "New York"},
        {"id": 2, "name": "Bob", "age": 25, "city": "San Francisco"},
        {"id": 3, "name": "Charlie", "age": 35, "city": "Seattle"},
        {"id": 4, "name": "Diana", "age": 28, "city": "Boston"},
    ]
    return data


@pipeline.task(compute=compute.serverless(memory=512))
def clean_users(users: raw_users) -> clean_users:
    """Clean and validate user data"""
    print(f"Cleaning {len(users)} users...")
    # Simple cleaning - uppercase names, validate age
    cleaned = [
        {**user, "name": user["name"].upper()}
        for user in users
        if user.get("age", 0) > 0
    ]
    return cleaned


@pipeline.task(compute=compute.serverless(memory=1024, timeout=300))
def compute_metrics(users: clean_users) -> user_metrics:
    """Compute user metrics"""
    print(f"Computing metrics for {len(users)} users...")

    # Calculate metrics
    metrics = {
        "total_users": len(users),
        "average_age": sum(u["age"] for u in users) / len(users),
        "cities": list(set(u["city"] for u in users)),
        "age_distribution": {
            "under_30": sum(1 for u in users if u["age"] < 30),
            "30_and_over": sum(1 for u in users if u["age"] >= 30),
        },
    }
    return metrics


def main():
    """Main entry point"""
    print("=" * 70)
    print("Glacier Pipeline - New Pattern Example")
    print("=" * 70)
    print()

    # Validate pipeline
    print("Validating pipeline...")
    pipeline.validate()
    print("✓ Pipeline is valid!")
    print()

    # Visualize DAG
    print(pipeline.visualize())
    print()

    # Show execution order
    print("Execution order:")
    for i, task in enumerate(pipeline.get_execution_order(), 1):
        print(f"  {i}. {task.name}")
    print()

    # Run locally
    print("=" * 70)
    print("Running pipeline locally...")
    print("=" * 70)
    print()

    try:
        # Import local executor (dependency injection!)
        from glacier_local import LocalExecutor

        executor = LocalExecutor()
        results = pipeline.run(executor)

        print()
        print("=" * 70)
        print("Execution Results:")
        print("=" * 70)
        print()
        print(f"Metrics: {results['user_metrics']}")
        print()

    except ImportError:
        print("⚠️  glacier-local not installed. Install with:")
        print("   pip install glacier-pipeline[local]")
        print()

    # Compile to AWS
    print("=" * 70)
    print("Compiling to AWS infrastructure...")
    print("=" * 70)
    print()

    try:
        # Import AWS compiler (dependency injection!)
        from glacier_aws import AWSCompiler

        compiler = AWSCompiler(
            region="us-east-1",
            naming_prefix="prod",
            tags={
                "Environment": "production",
                "Team": "data-engineering",
                "Pipeline": pipeline.name,
            },
        )

        infra = pipeline.compile(compiler)

        # Export to Pulumi
        output_dir = "./infra_aws"
        infra.export_pulumi(output_dir)

        print(f"✓ Infrastructure code generated in: {output_dir}")
        print()
        print("To deploy:")
        print(f"  cd {output_dir}")
        print("  pulumi up")
        print()

        # Show what was generated
        print("Generated resources:")
        outputs = infra.get_outputs()
        for key, value in outputs.items():
            print(f"  - {key}: {value}")
        print()

    except ImportError:
        print("⚠️  glacier-aws not installed. Install with:")
        print("   pip install glacier-pipeline[aws]")
        print()

    print("=" * 70)
    print("Key Benefits of New Pattern:")
    print("=" * 70)
    print("✓ No manual task registration - @pipeline.task() auto-registers")
    print("✓ Zero provider coupling - import providers only when needed")
    print("✓ Dependency injection - compilers/executors injected at runtime")
    print("✓ Provider hints - optional provider-specific configuration")
    print("✓ Same code, multiple targets - local dev, AWS prod, GCP staging")
    print()


if __name__ == "__main__":
    main()
