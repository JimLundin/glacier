"""
Pulumi Escape Hatch Example

This example demonstrates how to use raw Pulumi resources directly
in Glacier pipelines when you need features that Glacier doesn't abstract.

The philosophy: Make common things easy, make everything possible.

Use cases for the escape hatch:
- Provider-specific features not in Glacier
- Complex Pulumi configurations
- Existing Pulumi infrastructure
- Advanced networking/security setups
- Gradual Glacier adoption
"""

from glacier import Pipeline, Dataset, compute

# ============================================================================
# Scenario: You need advanced S3 features that Glacier doesn't expose
# ============================================================================

print("=" * 70)
print("Pulumi Escape Hatch Example")
print("=" * 70)
print()

# Example 1: Simple Glacier abstraction (most common case)
print("Example 1: Using Glacier abstractions (recommended for common cases)")
print("-" * 70)
print()

from glacier_aws import AWSEnvironment

aws_prod = AWSEnvironment(
    account_id="123456789012",
    region="us-east-1",
    environment="prod",
)

# Glacier's simplified API
simple_bucket = aws_prod.storage.s3(
    bucket="simple-data",
    storage_class="INTELLIGENT_TIERING",
    versioning=True,
)

simple_data = Dataset("simple_data", storage=simple_bucket)

print(f"Created: {simple_bucket}")
print("✓ Simple, covers 80% of use cases")
print()


# Example 2: Complex requirements - use Pulumi directly!
print("Example 2: Using Pulumi escape hatch (for advanced features)")
print("-" * 70)
print()

try:
    import pulumi
    import pulumi_aws as aws
    from glacier.pulumi_escape import pulumi_s3_bucket

    # You need advanced S3 features:
    # - Custom KMS encryption with key rotation
    # - Complex lifecycle policies
    # - Advanced CORS configuration
    # - Object lock for compliance
    # - Replication to multiple regions

    # Use Pulumi directly - full power!
    kms_key = aws.kms.Key(
        "data-encryption-key",
        description="Encryption key for sensitive data",
        enable_key_rotation=True,
        tags={"Purpose": "data-encryption", "Compliance": "SOC2"},
    )

    complex_bucket = aws.s3.BucketV2(
        "complex-data-bucket",
        bucket="complex-data-bucket",
        tags={"Environment": "production", "Compliance": "HIPAA"},
    )

    # Object lock for compliance (not in Glacier's abstraction)
    object_lock = aws.s3.BucketObjectLockConfigurationV2(
        "complex-bucket-lock",
        bucket=complex_bucket.id,
        object_lock_enabled="Enabled",
        rule=aws.s3.BucketObjectLockConfigurationV2RuleArgs(
            default_retention=aws.s3.BucketObjectLockConfigurationV2RuleDefaultRetentionArgs(
                mode="GOVERNANCE",
                days=365,
            ),
        ),
    )

    # Server-side encryption with KMS
    encryption = aws.s3.BucketServerSideEncryptionConfigurationV2(
        "complex-bucket-encryption",
        bucket=complex_bucket.id,
        rules=[aws.s3.BucketServerSideEncryptionConfigurationV2RuleArgs(
            apply_server_side_encryption_by_default=aws.s3.BucketServerSideEncryptionConfigurationV2RuleApplyServerSideEncryptionByDefaultArgs(
                sse_algorithm="aws:kms",
                kms_master_key_id=kms_key.arn,
            ),
            bucket_key_enabled=True,
        )],
    )

    # Complex lifecycle policy
    lifecycle = aws.s3.BucketLifecycleConfigurationV2(
        "complex-bucket-lifecycle",
        bucket=complex_bucket.id,
        rules=[
            aws.s3.BucketLifecycleConfigurationV2RuleArgs(
                id="archive-old-data",
                status="Enabled",
                transitions=[
                    aws.s3.BucketLifecycleConfigurationV2RuleTransitionArgs(
                        days=30,
                        storage_class="STANDARD_IA",
                    ),
                    aws.s3.BucketLifecycleConfigurationV2RuleTransitionArgs(
                        days=90,
                        storage_class="GLACIER",
                    ),
                    aws.s3.BucketLifecycleConfigurationV2RuleTransitionArgs(
                        days=365,
                        storage_class="DEEP_ARCHIVE",
                    ),
                ],
                expiration=aws.s3.BucketLifecycleConfigurationV2RuleExpirationArgs(
                    days=2555,  # 7 years for compliance
                ),
            ),
        ],
    )

    # Replication to DR region
    replication_role = aws.iam.Role(
        "replication-role",
        assume_role_policy=pulumi.Output.all().apply(
            lambda _: """{
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {"Service": "s3.amazonaws.com"},
                    "Action": "sts:AssumeRole"
                }]
            }"""
        ),
    )

    dr_bucket = aws.s3.BucketV2(
        "dr-bucket",
        bucket="complex-data-bucket-dr",
        tags={"Purpose": "disaster-recovery"},
        opts=pulumi.ResourceOptions(provider=aws.Provider("dr", region="us-west-2")),
    )

    replication = aws.s3.BucketReplicationConfig(
        "complex-bucket-replication",
        bucket=complex_bucket.id,
        role=replication_role.arn,
        rules=[aws.s3.BucketReplicationConfigRuleArgs(
            id="replicate-all",
            status="Enabled",
            destination=aws.s3.BucketReplicationConfigRuleDestinationArgs(
                bucket=dr_bucket.arn,
                storage_class="STANDARD_IA",
            ),
        )],
    )

    # Wrap the Pulumi bucket for Glacier
    complex_storage = pulumi_s3_bucket(complex_bucket)

    # Use in Glacier pipeline normally
    complex_data = Dataset("complex_data", storage=complex_storage)

    print(f"Created: {complex_storage}")
    print("✓ Full Pulumi power when you need it!")
    print()
    print("Features used that Glacier doesn't abstract:")
    print("  • KMS encryption with key rotation")
    print("  • Object lock for compliance (HIPAA/SOC2)")
    print("  • Multi-tier lifecycle (IA → Glacier → Deep Archive)")
    print("  • Cross-region replication for DR")
    print("  • Custom IAM roles")
    print()

except ImportError:
    print("⚠️  Pulumi not installed. This is just a demonstration.")
    print()
    print("The pattern:")
    print()
    print("```python")
    print("import pulumi_aws as aws")
    print("from glacier.pulumi_escape import pulumi_s3_bucket")
    print()
    print("# Full Pulumi resource")
    print("bucket = aws.s3.BucketV2('my-bucket', ...)")
    print()
    print("# Wrap for Glacier")
    print("storage = pulumi_s3_bucket(bucket)")
    print("data = Dataset('data', storage=storage)")
    print("```")
    print()


# Example 3: Mixing Glacier and Pulumi resources
print("Example 3: Mixing simplified and escape hatch resources")
print("-" * 70)
print()

# Create pipeline
pipeline = Pipeline(name="mixed-approach")

# Simple resources - Glacier abstraction
simple_input = Dataset(
    "simple_input",
    storage=aws_prod.storage.s3(bucket="simple-input"),
)

# Complex resources - Pulumi escape hatch
# complex_output = Dataset(
#     "complex_output",
#     storage=complex_storage,  # From Pulumi above
# )

@pipeline.task(compute=compute.serverless(memory=512))
def extract() -> simple_input:
    """Use Glacier abstraction for simple case"""
    return fetch_data()

# For compute, you could also use Pulumi directly:
# @pipeline.task(compute=pulumi_lambda(my_lambda_function))
# def advanced_process(data: complex_data) -> result:
#     return complex_processing(data)

print("✓ Use Glacier abstractions where they fit")
print("✓ Drop to Pulumi for advanced features")
print("✓ Mix and match freely!")
print()


# Example 4: Existing Pulumi Infrastructure
print("Example 4: Adopting Glacier with existing Pulumi infrastructure")
print("-" * 70)
print()

print("If you already have Pulumi infrastructure, just wrap it:")
print()
print("```python")
print("# Your existing Pulumi code")
print("existing_bucket = aws.s3.BucketV2('legacy-bucket', ...)")
print("existing_db = aws.rds.Instance('legacy-db', ...)")
print()
print("# Wrap for Glacier")
print("from glacier.pulumi_escape import pulumi_s3_bucket, PulumiStorageResource")
print()
print("legacy_data = Dataset(")
print("    'legacy_data',")
print("    storage=pulumi_s3_bucket(existing_bucket)")
print(")")
print()
print("# Now use in Glacier pipeline")
print("@pipeline.task(compute=compute.serverless())")
print("def process(data: legacy_data) -> output:")
print("    return transform(data)")
print("```")
print()
print("✓ Gradual Glacier adoption")
print("✓ Reuse existing infrastructure")
print("✓ No need to rewrite everything")
print()


print("=" * 70)
print("Key Principles")
print("=" * 70)
print()
print("1. Start with Glacier abstractions (simple, covers most cases)")
print("2. Use Pulumi escape hatch when you need:")
print("   • Provider-specific features")
print("   • Complex configurations")
print("   • Existing Pulumi infrastructure")
print("3. Mix and match freely in the same pipeline")
print("4. Glacier handles orchestration, Pulumi handles infrastructure details")
print()
print("Simple things easy. Everything possible.")
print()


def main():
    """Main entry point"""
    pass


if __name__ == "__main__":
    main()
