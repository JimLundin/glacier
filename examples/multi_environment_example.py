"""
Multi-Environment / Multi-Account Example

This example demonstrates how to handle multiple AWS accounts or
environments (dev, staging, prod) in a single pipeline.

The key insight: Initialize cloud provider ENVIRONMENTS, then create
resources FROM those environments.

Scenario:
- Development environment (separate AWS account)
- Production environment (different AWS account)
- Same pipeline code works for both!
"""

from glacier import Pipeline, Dataset, compute
from glacier.storage import ObjectStorage  # Generic (for simple cases)

# Create pipeline
pipeline = Pipeline(name="analytics")

# ============================================================================
# Option 1: Generic Resources (Simple, Single-Environment)
# ============================================================================

# For simple pipelines that only use one environment, use generic resources
raw_data_generic = Dataset("raw_data", storage=ObjectStorage())

@pipeline.task(compute=compute.serverless(memory=512))
def extract_generic() -> raw_data_generic:
    """This can compile to any environment"""
    return {"records": 100}


# ============================================================================
# Option 2: Environment-Scoped Resources (Multi-Account/Multi-Environment)
# ============================================================================

from glacier_aws import AWSEnvironment

# Development environment (separate AWS account!)
aws_dev = AWSEnvironment(
    account_id="111111111111",
    region="us-west-2",
    profile="development",
    environment="dev",
    naming_prefix="dev",
    tags={
        "Environment": "development",
        "ManagedBy": "glacier",
        "CostCenter": "engineering",
    },
    # Dev uses smaller, cheaper resources
)

# Production environment (different AWS account!)
aws_prod = AWSEnvironment(
    account_id="999999999999",
    region="us-east-1",
    profile="production",
    environment="prod",
    naming_prefix="prod",
    tags={
        "Environment": "production",
        "ManagedBy": "glacier",
        "CostCenter": "operations",
    },
    # Prod might have VPC configuration
    vpc_id="vpc-prod123",
    subnet_ids=["subnet-a", "subnet-b"],
    security_group_ids=["sg-prod"],
)

# Resources belong to SPECIFIC environments
dev_raw_data = Dataset(
    "raw_data",
    storage=aws_dev.storage.s3(
        bucket="dev-analytics-raw",
        storage_class="STANDARD",
        versioning=False,  # Dev doesn't need versioning
    )
)

prod_raw_data = Dataset(
    "raw_data",  # Same logical name, different physical resource!
    storage=aws_prod.storage.s3(
        bucket="prod-analytics-raw",
        storage_class="INTELLIGENT_TIERING",  # Prod optimizes costs
        versioning=True,  # Prod needs versioning
        encryption="aws:kms",
        kms_key_id="arn:aws:kms:us-east-1:999999999999:key/...",
    )
)

dev_processed_data = Dataset(
    "processed_data",
    storage=aws_dev.storage.s3(bucket="dev-analytics-processed")
)

prod_processed_data = Dataset(
    "processed_data",
    storage=aws_prod.storage.s3(
        bucket="prod-analytics-processed",
        storage_class="INTELLIGENT_TIERING",
    )
)

# Tasks can also be environment-specific
@pipeline.task(compute=aws_dev.compute.lambda_(
    memory=512,  # Dev uses smaller instance
    timeout=300,
))
def extract_dev() -> dev_raw_data:
    """Extract in dev environment (account 111111111111)"""
    print("Extracting in DEV environment...")
    return {"records": 100, "env": "dev"}

@pipeline.task(compute=aws_prod.compute.lambda_(
    memory=2048,  # Prod uses larger instance
    timeout=600,
    reserved_concurrency=10,  # Prod has reserved capacity
))
def extract_prod() -> prod_raw_data:
    """Extract in prod environment (account 999999999999)"""
    print("Extracting in PROD environment...")
    return {"records": 10000, "env": "prod"}

@pipeline.task(compute=aws_dev.compute.lambda_(memory=1024))
def process_dev(raw: dev_raw_data) -> dev_processed_data:
    """Process in dev environment"""
    print(f"Processing {raw['records']} records in DEV...")
    return {"processed": raw["records"], "env": "dev"}

@pipeline.task(compute=aws_prod.compute.lambda_(memory=4096))
def process_prod(raw: prod_raw_data) -> prod_processed_data:
    """Process in prod environment"""
    print(f"Processing {raw['records']} records in PROD...")
    return {"processed": raw["records"], "env": "prod"}


# ============================================================================
# Option 3: Cross-Account Access (Advanced)
# ============================================================================

# Sometimes you need to read from prod in dev (for testing)
# The resources track their environment context!

@pipeline.task(compute=aws_dev.compute.lambda_(memory=1024))
def test_with_prod_data(data: prod_raw_data) -> dev_processed_data:
    """
    Dev compute reading from prod storage!

    This is EXPLICIT in the code:
    - Compute: aws_dev (account 111111111111, region us-west-2)
    - Storage: prod_raw_data (account 999999999999, region us-east-1)

    The compiler will:
    1. Detect cross-account access
    2. Generate IAM assume-role policies
    3. Warn about cross-region data transfer costs
    """
    print(f"Dev environment testing with PROD data: {data}")
    return {"processed": data["records"], "env": "dev-testing-prod"}


def main():
    print("=" * 70)
    print("Multi-Environment / Multi-Account Example")
    print("=" * 70)
    print()

    print("Environments configured:")
    print(f"  • Dev:  {aws_dev}")
    print(f"  • Prod: {aws_prod}")
    print()

    # The key benefit: Same pipeline code, different environment deployments!

    print("=" * 70)
    print("Deployment Pattern")
    print("=" * 70)
    print()

    print("The same pipeline can be deployed to different environments:")
    print()
    print("# Deploy to DEV")
    print("compiler = AWSCompiler.from_environment(aws_dev)")
    print("dev_infra = pipeline.compile(compiler)")
    print("dev_infra.export_pulumi('./infra/dev')")
    print()
    print("# Deploy to PROD")
    print("compiler = AWSCompiler.from_environment(aws_prod)")
    print("prod_infra = pipeline.compile(compiler)")
    print("prod_infra.export_pulumi('./infra/prod')")
    print()

    print("=" * 70)
    print("What Gets Generated")
    print("=" * 70)
    print()
    print("Dev Infrastructure (Account 111111111111, us-west-2):")
    print("  • S3 Bucket: dev-analytics-raw (STANDARD storage)")
    print("  • S3 Bucket: dev-analytics-processed")
    print("  • Lambda: dev-extract (512MB, no VPC)")
    print("  • Lambda: dev-process (1024MB)")
    print("  • IAM Roles: dev-extract-role, dev-process-role")
    print()
    print("Prod Infrastructure (Account 999999999999, us-east-1):")
    print("  • S3 Bucket: prod-analytics-raw (INTELLIGENT_TIERING, KMS encrypted)")
    print("  • S3 Bucket: prod-analytics-processed (INTELLIGENT_TIERING)")
    print("  • Lambda: prod-extract (2048MB, reserved concurrency, in VPC)")
    print("  • Lambda: prod-process (4096MB, in VPC)")
    print("  • IAM Roles: prod-extract-role, prod-process-role")
    print("  • VPC Endpoints: S3 VPC endpoint (for private access)")
    print()

    print("=" * 70)
    print("Key Benefits")
    print("=" * 70)
    print("✓ Clear separation: Resources explicitly bound to environments")
    print("✓ Multi-account support: Different AWS accounts = different environments")
    print("✓ Environment-specific config: Dev uses cheaper resources, prod uses optimized")
    print("✓ Same code: Deploy to dev/staging/prod with same pipeline definition")
    print("✓ Cross-account visible: Compiler detects and handles cross-account access")
    print("✓ Pulumi-compatible: Maps directly to Pulumi provider instances")
    print()

    print("=" * 70)
    print("Pulumi Stack Configuration")
    print("=" * 70)
    print()
    print("This maps to Pulumi stacks:")
    print()
    print("# Pulumi.dev.yaml")
    print("config:")
    print("  aws:region: us-west-2")
    print("  aws:profile: development")
    print("  glacier:account_id: '111111111111'")
    print()
    print("# Pulumi.prod.yaml")
    print("config:")
    print("  aws:region: us-east-1")
    print("  aws:profile: production")
    print("  glacier:account_id: '999999999999'")
    print()

    print("=" * 70)
    print("Migration Scenario")
    print("=" * 70)
    print()
    print("You can even migrate between accounts:")
    print()
    print("# Old AWS account")
    print("aws_old = AWSEnvironment(account_id='123456', region='us-east-1')")
    print("old_data = Dataset('data', storage=aws_old.storage.s3(bucket='old-bucket'))")
    print()
    print("# New AWS account")
    print("aws_new = AWSEnvironment(account_id='789012', region='us-west-2')")
    print("new_data = Dataset('data', storage=aws_new.storage.s3(bucket='new-bucket'))")
    print()
    print("@pipeline.task(compute=aws_new.compute.lambda_())")
    print("def migrate(source: old_data) -> new_data:")
    print("    # Reads from old account, writes to new account")
    print("    # Compiler generates cross-account IAM policies")
    print("    return source")
    print()


if __name__ == "__main__":
    main()
