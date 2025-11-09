# Escape Hatch: Advanced Features Without Pulumi Imports

## Core Principle

**Pulumi is a compilation target, not a runtime dependency.**

Users should be able to build pipelines without importing Pulumi. The compiler generates Pulumi code. Pulumi is only needed if users explicitly choose advanced escape hatches.

```
┌────────────────────────────────────────────────────┐
│  User Pipeline Code                                │
│  • No Pulumi imports                               │
│  • Glacier abstractions only                       │
│  • Provider-agnostic                               │
└────────────────┬───────────────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────────┐
│  Compiler (glacier_aws.AWSCompiler)                │
│  • Translates Glacier → Pulumi                     │
│  • Generates Pulumi code                           │
│  • Pulumi is internal implementation detail        │
└────────────────┬───────────────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────────┐
│  Generated Pulumi Program (__main__.py)            │
│  • import pulumi_aws as aws                        │
│  • S3 buckets, Lambda functions, etc.             │
│  • Ready to deploy with `pulumi up`                │
└────────────────────────────────────────────────────┘
```

---

## Three Escape Hatch Patterns

When Glacier's abstractions aren't enough, you have three options:

### Pattern 1: Configuration-Based (Recommended)

**✅ No Pulumi imports needed**
**✅ Declarative configuration**
**✅ Compiler translates to Pulumi**

```python
from glacier_aws import AWSEnvironment
from glacier.escape_hatch import AdvancedStorageConfig, ObjectLockConfig

aws_prod = AWSEnvironment(account_id="...", region="us-east-1")

# Specify WHAT you want, not HOW to implement it
data = Dataset(
    "compliance_data",
    storage=aws_prod.storage.s3(
        bucket="data",
        # Advanced features without Pulumi imports!
        advanced_config=AdvancedStorageConfig(
            object_lock=ObjectLockConfig(
                mode="GOVERNANCE",
                retention_days=365,
            ),
            replication=ReplicationConfig(
                destination_bucket="dr-bucket",
                destination_region="us-west-2",
            ),
            lifecycle_tiers=[
                ("STANDARD", 0),
                ("STANDARD_IA", 30),
                ("GLACIER", 90),
                ("DEEP_ARCHIVE", 365),
            ],
            custom_encryption=EncryptionConfig(
                algorithm="aws:kms",
                kms_key_rotation=True,
            ),
        )
    )
)

# Compiler translates this to Pulumi resources:
# - aws.s3.BucketObjectLockConfigurationV2
# - aws.s3.BucketReplicationConfig
# - aws.s3.BucketLifecycleConfigurationV2
# - aws.kms.Key with rotation enabled
# - aws.s3.BucketServerSideEncryptionConfigurationV2
```

**When to use:**
- Common advanced features (object lock, replication, lifecycle)
- Want to keep pipeline provider-agnostic
- Don't want Pulumi as a dependency

---

### Pattern 2: Post-Compilation Hooks

**✅ Modify generated Pulumi resources**
**✅ Pulumi imported only in hook function**
**✅ Full Pulumi power**

```python
from glacier import Dataset
from glacier.escape_hatch import PulumiCustomization

# Regular Glacier storage
data = Dataset(
    "data",
    storage=aws_prod.storage.s3(bucket="data")
)

# Define customization hook
def customize_bucket(bucket, context):
    """
    Receives generated Pulumi bucket, can modify it.

    Pulumi is imported HERE, not in main pipeline code.
    """
    import pulumi_aws as aws  # Import only if using escape hatch
    import pulumi

    # Add VPC endpoint (not in Glacier abstraction)
    vpc_endpoint = aws.ec2.VpcEndpoint(
        f"{context.resource_name}-endpoint",
        vpc_id=context.environment.vpc_id,
        service_name=f"com.amazonaws.{context.environment.region}.s3",
    )

    # Add bucket policy for VPC-only access
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
                    "Resource": "{args[0]}/*",
                    "Condition": {{
                        "StringNotEquals": {{
                            "aws:sourceVpce": "{args[1]}"
                        }}
                    }}
                }}]
            }}'''
        ),
    )

    return bucket

# Apply during compilation
infra = pipeline.compile(
    compiler,
    customizations={
        "data": PulumiCustomization(
            resource_name="data",
            customize_fn=customize_bucket,
        ),
    }
)
```

**When to use:**
- Provider-specific features not in Glacier
- Need to modify generated resources
- Complex logic based on other resources
- Want full Pulumi control for specific resources

---

### Pattern 3: Pulumi Program Injection

**✅ Add custom Pulumi code after export**
**✅ Full control over final infrastructure**
**✅ Can use existing Pulumi modules**

```python
# Step 1: Export Glacier pipeline to Pulumi project
infra = pipeline.compile(compiler)
infra.export_pulumi("./infra")

# Generated:
# ./infra/
#   __main__.py      ← Glacier-generated Pulumi code
#   Pulumi.yaml
#   requirements.txt

# Step 2: Inject custom Pulumi code
from glacier.escape_hatch import PulumiProgramInjector

injector = PulumiProgramInjector("./infra")

injector.add_custom_code('''
# Add custom infrastructure outside Glacier's scope
import pulumi_aws as aws
import pulumi

# Complex VPC setup
custom_vpc = aws.ec2.Vpc(
    "custom-vpc",
    cidr_block="10.0.0.0/16",
    enable_dns_hostnames=True,
)

# Transit gateway for multi-VPC
transit_gw = aws.ec2transitgateway.TransitGateway(
    "transit-gw",
    description="Multi-account routing",
)

# Export for Glacier resources to reference
pulumi.export("custom_vpc_id", custom_vpc.id)
pulumi.export("transit_gateway_id", transit_gw.id)
''')

injector.save()

# Now ./infra/__main__.py contains both Glacier and custom code
```

**When to use:**
- Infrastructure outside Glacier's scope (VPCs, transit gateways)
- Want to use existing Pulumi modules
- Gradual Glacier adoption
- Complex networking requirements

---

## Comparison

| Feature | Config-Based | Hooks | Injection |
|---------|-------------|-------|-----------|
| Pulumi imports | ❌ None | ⚠️ In hook function | ⚠️ In custom code |
| Pulumi dependency | ❌ Not needed | ⚠️ If using hook | ⚠️ Required |
| Provider-agnostic | ✅ Yes | ⚠️ Provider-specific | ⚠️ Provider-specific |
| Complexity | ✅ Low | ⚠️ Medium | ⚠️ High |
| Control level | ⚠️ Limited to config | ✅ Full Pulumi | ✅ Complete |
| Best for | Common features | Resource modifications | Custom infrastructure |

---

## Detailed: Configuration-Based Escape Hatch

The recommended approach for most advanced features.

### Object Lock (Compliance)

```python
from glacier.escape_hatch import AdvancedStorageConfig, ObjectLockConfig

storage = aws_prod.storage.s3(
    bucket="compliance-data",
    advanced_config=AdvancedStorageConfig(
        object_lock=ObjectLockConfig(
            mode="GOVERNANCE",  # or "COMPLIANCE"
            retention_days=365,
        )
    )
)
```

**Compiler generates:**
```python
import pulumi_aws as aws

bucket = aws.s3.BucketV2("compliance-data", ...)

object_lock = aws.s3.BucketObjectLockConfigurationV2(
    "compliance-data-lock",
    bucket=bucket.id,
    object_lock_enabled="Enabled",
    rule=aws.s3.BucketObjectLockConfigurationV2RuleArgs(
        default_retention=aws.s3.BucketObjectLockConfigurationV2RuleDefaultRetentionArgs(
            mode="GOVERNANCE",
            days=365,
        ),
    ),
)
```

### Cross-Region Replication

```python
from glacier.escape_hatch import ReplicationConfig

storage = aws_prod.storage.s3(
    bucket="primary-data",
    advanced_config=AdvancedStorageConfig(
        replication=ReplicationConfig(
            destination_bucket="dr-data",
            destination_region="us-west-2",
            storage_class="STANDARD_IA",
        )
    )
)
```

**Compiler generates:**
```python
# Replication role
replication_role = aws.iam.Role(...)

# Destination bucket
dr_bucket = aws.s3.BucketV2("dr-data", ...)

# Replication config
replication = aws.s3.BucketReplicationConfig(
    "primary-data-replication",
    bucket=primary_bucket.id,
    role=replication_role.arn,
    rules=[aws.s3.BucketReplicationConfigRuleArgs(...)],
)
```

### Multi-Tier Lifecycle

```python
storage = aws_prod.storage.s3(
    bucket="archival-data",
    advanced_config=AdvancedStorageConfig(
        lifecycle_tiers=[
            ("STANDARD", 0),
            ("STANDARD_IA", 30),
            ("GLACIER", 90),
            ("DEEP_ARCHIVE", 365),
        ]
    )
)
```

**Compiler generates:**
```python
lifecycle = aws.s3.BucketLifecycleConfigurationV2(
    "archival-data-lifecycle",
    bucket=bucket.id,
    rules=[
        aws.s3.BucketLifecycleConfigurationV2RuleArgs(
            id="tiered-storage",
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
        ),
    ],
)
```

### Custom Encryption

```python
from glacier.escape_hatch import EncryptionConfig

storage = aws_prod.storage.s3(
    bucket="encrypted-data",
    advanced_config=AdvancedStorageConfig(
        custom_encryption=EncryptionConfig(
            algorithm="aws:kms",
            kms_key_rotation=True,
        )
    )
)
```

**Compiler generates:**
```python
# KMS key with rotation
kms_key = aws.kms.Key(
    "encrypted-data-key",
    enable_key_rotation=True,
)

# Bucket encryption
encryption = aws.s3.BucketServerSideEncryptionConfigurationV2(
    "encrypted-data-encryption",
    bucket=bucket.id,
    rules=[aws.s3.BucketServerSideEncryptionConfigurationV2RuleArgs(
        apply_server_side_encryption_by_default=aws.s3.BucketServerSideEncryptionConfigurationV2RuleApplyServerSideEncryptionByDefaultArgs(
            sse_algorithm="aws:kms",
            kms_master_key_id=kms_key.arn,
        ),
    )],
)
```

---

## Key Advantages

### No Forced Dependencies

```python
# ✅ No Pulumi import!
data = Dataset("data", storage=aws_prod.storage.s3(bucket="data"))

# ❌ Old (wrong) approach forced Pulumi:
# import pulumi_aws as aws
# bucket = aws.s3.BucketV2(...)
```

### Compiler Handles Translation

Users specify **what** they want, compiler figures out **how**:

```python
# User writes:
advanced_config=AdvancedStorageConfig(object_lock=ObjectLockConfig(...))

# Compiler generates:
aws.s3.BucketObjectLockConfigurationV2(...)
aws.s3.BucketVersioningV2(...)  # Required for object lock
# ... plus all necessary dependencies
```

### Progressive Enhancement

```python
# Start simple
storage = aws_prod.storage.s3(bucket="data")

# Add features as needed (still no Pulumi!)
storage = aws_prod.storage.s3(
    bucket="data",
    advanced_config=AdvancedStorageConfig(...)
)

# Only drop to Pulumi hooks if absolutely necessary
```

---

## Installation

Pulumi is an **optional dependency**:

```bash
# Core Glacier (no Pulumi needed)
pip install glacier-pipeline

# With AWS support (no Pulumi needed for basic usage)
pip install glacier-pipeline[aws]

# With Pulumi (only if using escape hatches)
pip install glacier-pipeline[aws] pulumi pulumi-aws
```

Users only install Pulumi if they use escape hatches!

---

## Summary

**Glacier's philosophy:**
- **Make common things easy** - Simple abstractions cover 80% of use cases
- **Make everything possible** - Escape hatches for the remaining 20%
- **No forced dependencies** - Pulumi only needed if using escape hatches
- **Compilation target** - Pulumi is an implementation detail, not user-facing

**Three escape hatch levels:**
1. **Configuration-based** - No Pulumi, declarative config (recommended)
2. **Post-compilation hooks** - Pulumi in hook functions (advanced)
3. **Program injection** - Add custom Pulumi code (expert)

**Users choose their level of control based on needs.**

---

For examples, see:
- [examples/escape_hatch_patterns.py](./examples/escape_hatch_patterns.py)
- [glacier/escape_hatch.py](./glacier/escape_hatch.py)
