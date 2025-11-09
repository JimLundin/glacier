"""
Multi-Cloud Pipeline Example

This example demonstrates how to build a pipeline that uses multiple
cloud providers without coupling your code to any specific provider.

Scenario:
- Raw data stored in AWS S3 (existing bucket)
- Processing done on GCP Cloud Functions (cheaper compute)
- Results stored in GCP Cloud Storage (data warehouse)
"""

from glacier import Pipeline, Dataset, compute
from glacier.storage import ObjectStorage  # Generic
from glacier.compilation import MultiCloudCompiler

# Create pipeline
pipeline = Pipeline(name="multicloud-analytics")

# Option 1: Use generic resources (provider chosen at compile time)
raw_data_generic = Dataset(
    "raw_data_generic",
    storage=ObjectStorage(
        resource_name="company-raw-data",
        access_pattern="frequent",
    )
)

# Option 2: Use provider-specific resources for explicit control
# Import ONLY when you need provider-specific features
from glacier_aws.storage import S3
from glacier_aws.compute import Lambda

raw_data_aws = Dataset(
    "raw_data_aws",
    storage=S3(
        bucket="legacy-data-bucket",  # Existing AWS bucket
        region="us-east-1",
        storage_class="INTELLIGENT_TIERING",
    )
)

# Option 3: Mix generic and provider-specific
processed_data = Dataset(
    "processed_data",
    storage=ObjectStorage(  # Generic - will use default provider
        access_pattern="infrequent",
        versioning=True,
    )
)

analytics_results = Dataset(
    "analytics_results",
    storage=ObjectStorage(
        access_pattern="archive",
    )
)


# Tasks can also be provider-specific or generic
@pipeline.task(compute=compute.serverless(memory=512))
def extract_from_aws() -> raw_data_aws:
    """Extract data from existing AWS S3 bucket"""
    print("Extracting from AWS S3...")
    return {"records": 1000, "source": "aws_s3"}


@pipeline.task(compute=compute.serverless(memory=2048, timeout=600))
def process_data(raw: raw_data_aws) -> processed_data:
    """
    Process data using serverless compute.

    NOTE: This will run on GCP (default provider) but read from AWS S3!
    The compiler will detect this cross-cloud transfer and warn you.
    """
    print(f"Processing {raw['records']} records...")
    return {"processed_records": raw["records"], "enriched": True}


@pipeline.task(compute=Lambda(memory=1024, timeout=300))
def generate_analytics(data: processed_data) -> analytics_results:
    """
    Generate analytics using AWS Lambda specifically.

    This task will run on AWS Lambda, even though processed_data
    might be in GCP!
    """
    print(f"Generating analytics from {data['processed_records']} records...")
    return {
        "total_records": data["processed_records"],
        "analytics_version": "2.0",
    }


def main():
    print("=" * 70)
    print("Multi-Cloud Pipeline Example")
    print("=" * 70)
    print()

    # Validate pipeline
    pipeline.validate()
    print("✓ Pipeline structure is valid")
    print()

    # Show the DAG
    print(pipeline.visualize())
    print()

    # Example 1: Single-Cloud Compilation (all AWS)
    print("=" * 70)
    print("Example 1: Single-Cloud Deployment (AWS)")
    print("=" * 70)
    print()

    try:
        from glacier_aws import AWSCompiler

        aws_compiler = AWSCompiler(
            region="us-east-1",
            naming_prefix="prod",
            tags={"Environment": "production"},
        )

        # Compile to AWS - generic resources become AWS resources
        aws_infra = pipeline.compile(aws_compiler)
        aws_infra.export_pulumi("./infra_aws_only")

        print("✓ AWS-only infrastructure generated in: ./infra_aws_only")
        print()

    except ImportError as e:
        print(f"⚠️  Skipping AWS compilation: {e}")
        print()

    # Example 2: Multi-Cloud Compilation
    print("=" * 70)
    print("Example 2: Multi-Cloud Deployment (AWS + GCP)")
    print("=" * 70)
    print()

    try:
        from glacier_aws import AWSCompiler
        # from glacier_gcp import GCPCompiler  # Not implemented yet

        # For demonstration, we'll show the pattern
        print("Pattern for multi-cloud compilation:")
        print()
        print("```python")
        print("from glacier_aws import AWSCompiler")
        print("from glacier_gcp import GCPCompiler")
        print()
        print("compiler = MultiCloudCompiler(")
        print("    providers={")
        print("        'aws': AWSCompiler(region='us-east-1'),")
        print("        'gcp': GCPCompiler(project='my-project'),")
        print("    },")
        print("    default_provider='gcp',  # Generic resources go to GCP")
        print(")")
        print()
        print("# Compilation will:")
        print("# 1. Detect that raw_data_aws uses S3 (AWS)")
        print("# 2. Detect that generate_analytics uses Lambda (AWS)")
        print("# 3. Put other resources on GCP (default)")
        print("# 4. Warn about cross-cloud transfers:")
        print("#    - AWS S3 → GCP compute (process_data)")
        print("#    - GCP storage → AWS Lambda (generate_analytics)")
        print()
        print("infra = pipeline.compile(compiler)")
        print("infra.export_pulumi('./infra_multicloud')")
        print()
        print("# This creates:")
        print("#   ./infra_multicloud/aws/    - AWS resources")
        print("#   ./infra_multicloud/gcp/    - GCP resources")
        print("#   ./infra_multicloud/README.md - Deployment guide")
        print("```")
        print()

        # When GCP compiler is implemented:
        # compiler = MultiCloudCompiler(
        #     providers={
        #         "aws": AWSCompiler(region="us-east-1"),
        #         "gcp": GCPCompiler(project="my-project"),
        #     },
        #     default_provider="gcp",
        # )
        # infra = pipeline.compile(compiler)
        # infra.export_pulumi("./infra_multicloud")

    except ImportError as e:
        print(f"⚠️  Multi-cloud example requires glacier-aws and glacier-gcp")
        print()

    # Example 3: Migration Pattern (AWS → GCP)
    print("=" * 70)
    print("Example 3: Cloud Migration Pattern")
    print("=" * 70)
    print()
    print("You can use the same pipeline code to migrate between clouds:")
    print()
    print("Step 1: Start fully on AWS")
    print("  pipeline.compile(AWSCompiler())")
    print()
    print("Step 2: Gradually move to GCP")
    print("  pipeline.compile(MultiCloudCompiler({")
    print("      'aws': AWSCompiler(),  # Existing resources")
    print("      'gcp': GCPCompiler(),  # New resources")
    print("  }))")
    print()
    print("Step 3: Eventually fully on GCP")
    print("  pipeline.compile(GCPCompiler())")
    print()
    print("The same pipeline definition works at every stage!")
    print()

    print("=" * 70)
    print("Key Benefits of Multi-Cloud Support")
    print("=" * 70)
    print("✓ No provider lock-in - switch providers without code changes")
    print("✓ Gradual migration - move resources incrementally")
    print("✓ Cost optimization - use cheapest provider for each resource")
    print("✓ Compliance - keep data in specific regions/providers")
    print("✓ Resilience - distribute across multiple clouds")
    print("✓ Best-of-breed - use best service from each provider")
    print()


if __name__ == "__main__":
    main()
