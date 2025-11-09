"""
Escape Hatch Patterns: Three Ways to Use Advanced Features

Key principle: Users should NOT need to import Pulumi unless they choose to.
Pulumi is a compilation target, not a runtime dependency.

This example shows three escape hatch patterns:
1. Configuration-based (recommended) - No Pulumi imports
2. Post-compilation hooks - Pulumi imports only in hook functions
3. Pulumi program injection - Add custom Pulumi code after export
"""

from glacier import Pipeline, Dataset, compute
from glacier_aws import AWSEnvironment

# Create environment and pipeline
aws_prod = AWSEnvironment(
    account_id="123456789012",
    region="us-east-1",
    environment="prod",
)

pipeline = Pipeline(name="advanced-pipeline")

print("=" * 70)
print("Escape Hatch Patterns: Advanced Features Without Pulumi Imports")
print("=" * 70)
print()

# ============================================================================
# Pattern 1: Configuration-Based (Recommended)
# ============================================================================

print("Pattern 1: Configuration-Based Escape Hatch")
print("-" * 70)
print("✓ No Pulumi imports in user code")
print("✓ Declarative configuration")
print("✓ Compiler translates to Pulumi")
print()

from glacier.escape_hatch import (
    AdvancedStorageConfig,
    ObjectLockConfig,
    ReplicationConfig,
    EncryptionConfig,
)

# User specifies WHAT they want, not HOW to implement it
compliance_data = Dataset(
    "compliance_data",
    storage=aws_prod.storage.s3(
        bucket="compliance-data",
        versioning=True,
        # Advanced features without Pulumi!
        advanced_config=AdvancedStorageConfig(
            # Object lock for compliance (HIPAA/SOC2)
            object_lock=ObjectLockConfig(
                mode="GOVERNANCE",
                retention_days=365,
            ),
            # Cross-region replication for DR
            replication=ReplicationConfig(
                destination_bucket="compliance-data-dr",
                destination_region="us-west-2",
                storage_class="STANDARD_IA",
            ),
            # Multi-tier lifecycle
            lifecycle_tiers=[
                ("STANDARD", 0),        # Day 0
                ("STANDARD_IA", 30),    # After 30 days
                ("GLACIER", 90),        # After 90 days
                ("DEEP_ARCHIVE", 365),  # After 1 year
            ],
            # KMS encryption with key rotation
            custom_encryption=EncryptionConfig(
                algorithm="aws:kms",
                kms_key_rotation=True,
            ),
        )
    )
)

print("Created compliance dataset with:")
print("  • Object lock (365 day retention)")
print("  • Cross-region replication to us-west-2")
print("  • Multi-tier lifecycle (4 tiers)")
print("  • KMS encryption with key rotation")
print()
print("✓ No Pulumi imports needed!")
print("✓ Compiler generates all Pulumi resources")
print()

# ============================================================================
# Pattern 2: Post-Compilation Hooks (For Complex Cases)
# ============================================================================

print("Pattern 2: Post-Compilation Hooks")
print("-" * 70)
print("✓ Modify generated Pulumi resources")
print("✓ Pulumi imported only in hook function")
print("✓ Full Pulumi power when needed")
print()

# Regular Glacier storage
advanced_data = Dataset(
    "advanced_data",
    storage=aws_prod.storage.s3(bucket="advanced-data", versioning=True)
)

# Define customization hook (Pulumi imported HERE, not in main code)
def customize_advanced_bucket(bucket, context):
    """
    This function receives the generated Pulumi S3 bucket
    and can modify it using full Pulumi APIs.

    Pulumi is imported inside this function, so users only
    need Pulumi installed if they use this escape hatch.
    """
    # Pulumi import happens here!
    try:
        import pulumi_aws as aws
        import pulumi

        print("    Applying custom Pulumi modifications...")

        # Add VPC endpoint (not in Glacier abstraction)
        vpc_endpoint = aws.ec2.VpcEndpoint(
            f"{context.resource_name}-endpoint",
            vpc_id=context.environment.vpc_id,
            service_name=f"com.amazonaws.{context.environment.region}.s3",
            vpc_endpoint_type="Gateway",
        )

        # Add bucket policy for VPC endpoint only
        bucket_policy = aws.s3.BucketPolicy(
            f"{context.resource_name}-policy",
            bucket=bucket.id,
            policy=pulumi.Output.all(bucket.arn, vpc_endpoint.id).apply(
                lambda args: f'''{{
                    "Version": "2012-10-17",
                    "Statement": [{{
                        "Effect": "Deny",
                        "Principal": "*",
                        "Action": "s3:*",
                        "Resource": [
                            "{args[0]}",
                            "{args[0]}/*"
                        ],
                        "Condition": {{
                            "StringNotEquals": {{
                                "aws:sourceVpce": "{args[1]}"
                            }}
                        }}
                    }}]
                }}'''
            ),
        )

        print("    ✓ Added VPC endpoint")
        print("    ✓ Added bucket policy (VPC-only access)")

        return bucket

    except ImportError:
        print("    ⚠️  Pulumi not installed, skipping customization")
        return bucket


# Apply during compilation
print("Compilation with hook:")
print()

from glacier.escape_hatch import PulumiCustomization

try:
    infra = pipeline.compile(
        aws_compiler,
        customizations={
            "advanced_data": PulumiCustomization(
                resource_name="advanced_data",
                customize_fn=customize_advanced_bucket,
            ),
        }
    )
    print()
    print("✓ Customization applied at compile time")
except Exception as e:
    print(f"Note: {e}")
    print("(This is just a demonstration)")

print()

# ============================================================================
# Pattern 3: Pulumi Program Injection (After Export)
# ============================================================================

print("Pattern 3: Pulumi Program Injection")
print("-" * 70)
print("✓ Export Glacier pipeline to Pulumi")
print("✓ Add custom Pulumi code to generated project")
print("✓ Full control over final infrastructure")
print()

# Regular Glacier pipeline (no Pulumi)
simple_data = Dataset(
    "simple_data",
    storage=aws_prod.storage.s3(bucket="simple-data")
)

@pipeline.task(compute=compute.serverless(memory=512))
def process() -> simple_data:
    return fetch_data()

print("Step 1: Export pipeline to Pulumi project")
print()

# infra = pipeline.compile(aws_compiler)
# infra.export_pulumi("./infra")

print("  Generated: ./infra/")
print("    - __main__.py  (Pulumi program)")
print("    - Pulumi.yaml  (project config)")
print("    - requirements.txt")
print()

print("Step 2: Inject custom Pulumi code")
print()

from glacier.escape_hatch import PulumiProgramInjector

# Now user can add custom Pulumi code
# injector = PulumiProgramInjector("./infra")
#
# injector.add_custom_code('''
# # Add custom infrastructure not in Glacier
# import pulumi_aws as aws
# import pulumi
#
# # Custom VPC with complex routing
# custom_vpc = aws.ec2.Vpc(
#     "custom-vpc",
#     cidr_block="10.0.0.0/16",
#     enable_dns_hostnames=True,
#     enable_dns_support=True,
# )
#
# # Internet gateway
# igw = aws.ec2.InternetGateway(
#     "igw",
#     vpc_id=custom_vpc.id,
# )
#
# # Transit gateway for multi-VPC
# transit_gw = aws.ec2transitgateway.TransitGateway(
#     "transit-gw",
#     description="Multi-VPC transit gateway",
# )
#
# # Export for Glacier resources to reference
# pulumi.export("custom_vpc_id", custom_vpc.id)
# pulumi.export("transit_gateway_id", transit_gw.id)
# ''')
#
# injector.save()

print("  Added custom Pulumi code to __main__.py:")
print("    - Custom VPC with complex routing")
print("    - Internet gateway")
print("    - Transit gateway for multi-VPC")
print()
print("  Glacier resources can reference these via Pulumi exports")
print()

print("✓ Full Pulumi power for complex infrastructure")
print("✓ Glacier handles pipeline orchestration")
print()

# ============================================================================
# Comparison: When to Use Each Pattern
# ============================================================================

print("=" * 70)
print("When to Use Each Pattern")
print("=" * 70)
print()

print("Pattern 1: Configuration-Based (Recommended)")
print("  Use when:")
print("    • Feature is common (object lock, replication, lifecycle)")
print("    • Want provider-agnostic pipeline")
print("    • Don't want to install Pulumi")
print("  Benefits:")
print("    • No Pulumi dependency")
print("    • Declarative configuration")
print("    • Compiler handles translation")
print()

print("Pattern 2: Post-Compilation Hooks")
print("  Use when:")
print("    • Need provider-specific features")
print("    • Want to modify generated resources")
print("    • Complex logic based on other resources")
print("  Benefits:")
print("    • Full Pulumi power")
print("    • Access to generated resources")
print("    • Can reference other resources")
print()

print("Pattern 3: Pulumi Program Injection")
print("  Use when:")
print("    • Need infrastructure outside Glacier's scope")
print("    • Complex networking (VPCs, transit gateways)")
print("    • Existing Pulumi modules to integrate")
print("  Benefits:")
print("    • Complete control")
print("    • Can use Pulumi modules")
print("    • Gradual Glacier adoption")
print()

# ============================================================================
# Key Principle
# ============================================================================

print("=" * 70)
print("Key Principle")
print("=" * 70)
print()
print("Pulumi is a COMPILATION TARGET, not a runtime dependency.")
print()
print("Users write:")
print("  storage = aws_prod.storage.s3(bucket='data')  ← No Pulumi!")
print()
print("Compiler generates:")
print("  bucket = aws.s3.BucketV2('data', ...)  ← Pulumi code")
print()
print("Users only need Pulumi installed if they use escape hatches.")
print()
print("Simple things easy. Complex things possible. No forced dependencies.")
print()


def main():
    pass


if __name__ == "__main__":
    main()
