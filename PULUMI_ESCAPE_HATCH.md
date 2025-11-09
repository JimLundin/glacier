# Pulumi Escape Hatch

Glacier provides simplified abstractions for common cloud resources, but when you need the full power of Pulumi, you can use **raw Pulumi resources directly**.

## Philosophy: Simple Things Easy, Everything Possible

```
┌─────────────────────────────────────────────────────────┐
│  Glacier Abstractions                                   │
│  ├── 80% of use cases                                   │
│  ├── Simple, declarative API                            │
│  └── Provider-agnostic                                  │
│                                                          │
│  ↓ When you need more...                                │
│                                                          │
│  Pulumi Escape Hatch                                    │
│  ├── 100% of Pulumi features                            │
│  ├── Provider-specific power                            │
│  └── Full control                                       │
└─────────────────────────────────────────────────────────┘
```

---

## When to Use the Escape Hatch

### Use Glacier Abstractions When:
- ✅ Standard storage/compute configurations
- ✅ Provider-agnostic pipelines
- ✅ Simple, common use cases
- ✅ You want to avoid cloud-specific details

### Use Pulumi Escape Hatch When:
- 🔧 Provider-specific features not in Glacier
- 🔧 Complex security/networking requirements
- 🔧 Existing Pulumi infrastructure to integrate
- 🔧 Advanced configurations (replication, encryption, etc.)
- 🔧 Compliance requirements (object lock, audit logging, etc.)

---

## Basic Usage

### 1. Import Pulumi and Create Resources

```python
import pulumi
import pulumi_aws as aws
from glacier.pulumi_escape import pulumi_s3_bucket

# Create raw Pulumi resource
bucket = aws.s3.BucketV2(
    "my-complex-bucket",
    bucket="my-data",
    # Use ANY Pulumi feature!
    object_lock_enabled=True,
    tags={"Compliance": "HIPAA"},
)

# Wrap for Glacier
storage = pulumi_s3_bucket(bucket)

# Use in Glacier pipeline
from glacier import Dataset

data = Dataset("data", storage=storage)
```

### 2. Use in Pipeline

```python
from glacier import Pipeline, compute

pipeline = Pipeline(name="my-pipeline")

@pipeline.task(compute=compute.serverless())
def process() -> data:
    return fetch_data()
```

That's it! Glacier handles the orchestration, Pulumi handles the infrastructure.

---

## Complete Example: Advanced S3 Configuration

```python
import pulumi
import pulumi_aws as aws
from glacier import Pipeline, Dataset, compute
from glacier.pulumi_escape import pulumi_s3_bucket

# Advanced S3 setup with features Glacier doesn't expose

# 1. KMS encryption with key rotation
kms_key = aws.kms.Key(
    "data-key",
    description="Data encryption key",
    enable_key_rotation=True,
    tags={"Purpose": "data-encryption"},
)

# 2. S3 bucket with object lock (compliance requirement)
bucket = aws.s3.BucketV2(
    "compliance-bucket",
    bucket="my-compliance-data",
)

# 3. Object lock configuration
object_lock = aws.s3.BucketObjectLockConfigurationV2(
    "bucket-lock",
    bucket=bucket.id,
    object_lock_enabled="Enabled",
    rule=aws.s3.BucketObjectLockConfigurationV2RuleArgs(
        default_retention=aws.s3.BucketObjectLockConfigurationV2RuleDefaultRetentionArgs(
            mode="GOVERNANCE",
            days=365,  # Retain for 1 year minimum
        ),
    ),
)

# 4. Server-side encryption with KMS
encryption = aws.s3.BucketServerSideEncryptionConfigurationV2(
    "bucket-encryption",
    bucket=bucket.id,
    rules=[aws.s3.BucketServerSideEncryptionConfigurationV2RuleArgs(
        apply_server_side_encryption_by_default=aws.s3.BucketServerSideEncryptionConfigurationV2RuleApplyServerSideEncryptionByDefaultArgs(
            sse_algorithm="aws:kms",
            kms_master_key_id=kms_key.arn,
        ),
    )],
)

# 5. Complex lifecycle policy
lifecycle = aws.s3.BucketLifecycleConfigurationV2(
    "bucket-lifecycle",
    bucket=bucket.id,
    rules=[
        aws.s3.BucketLifecycleConfigurationV2RuleArgs(
            id="tiered-storage",
            status="Enabled",
            transitions=[
                # 30 days → Infrequent Access
                aws.s3.BucketLifecycleConfigurationV2RuleTransitionArgs(
                    days=30,
                    storage_class="STANDARD_IA",
                ),
                # 90 days → Glacier
                aws.s3.BucketLifecycleConfigurationV2RuleTransitionArgs(
                    days=90,
                    storage_class="GLACIER",
                ),
                # 365 days → Deep Archive
                aws.s3.BucketLifecycleConfigurationV2RuleTransitionArgs(
                    days=365,
                    storage_class="DEEP_ARCHIVE",
                ),
            ],
            # Delete after 7 years (compliance)
            expiration=aws.s3.BucketLifecycleConfigurationV2RuleExpirationArgs(
                days=2555,
            ),
        ),
    ],
)

# 6. Cross-region replication for DR
dr_bucket = aws.s3.BucketV2(
    "dr-bucket",
    bucket="my-compliance-data-dr",
    opts=pulumi.ResourceOptions(
        provider=aws.Provider("dr", region="us-west-2")
    ),
)

replication_role = aws.iam.Role(
    "replication-role",
    assume_role_policy="""{
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "s3.amazonaws.com"},
            "Action": "sts:AssumeRole"
        }]
    }""",
)

replication = aws.s3.BucketReplicationConfig(
    "bucket-replication",
    bucket=bucket.id,
    role=replication_role.arn,
    rules=[aws.s3.BucketReplicationConfigRuleArgs(
        id="dr-replication",
        status="Enabled",
        destination=aws.s3.BucketReplicationConfigRuleDestinationArgs(
            bucket=dr_bucket.arn,
            storage_class="STANDARD_IA",
        ),
    )],
)

# 7. Wrap for Glacier
compliance_storage = pulumi_s3_bucket(bucket)

# 8. Use in Glacier pipeline normally
data = Dataset("compliance_data", storage=compliance_storage)

pipeline = Pipeline(name="compliance-pipeline")

@pipeline.task(compute=compute.serverless())
def process() -> data:
    return fetch_sensitive_data()
```

All the Pulumi complexity is hidden in the resource definition. The Glacier pipeline stays clean and simple.

---

## Mixing Glacier and Pulumi Resources

You can freely mix simplified Glacier resources with Pulumi escape hatches:

```python
from glacier_aws import AWSEnvironment
from glacier.pulumi_escape import pulumi_s3_bucket
import pulumi_aws as aws

aws_prod = AWSEnvironment(account_id="123456", region="us-east-1")

pipeline = Pipeline(name="mixed")

# Simple case: Use Glacier abstraction
simple_bucket = aws_prod.storage.s3(bucket="simple-data")
simple_data = Dataset("simple", storage=simple_bucket)

# Complex case: Use Pulumi
complex_bucket = aws.s3.BucketV2("complex", ...)  # All Pulumi features
complex_storage = pulumi_s3_bucket(complex_bucket)
complex_data = Dataset("complex", storage=complex_storage)

@pipeline.task(compute=compute.serverless())
def process_simple() -> simple_data:
    return fetch()

@pipeline.task(compute=compute.serverless())
def process_complex(data: complex_data) -> output:
    return transform(data)
```

---

## Integrating Existing Pulumi Infrastructure

If you already have Pulumi infrastructure, just wrap it:

```python
# Your existing Pulumi code
existing_bucket = aws.s3.BucketV2("legacy-bucket", ...)
existing_lambda = aws.lambda_.Function("legacy-function", ...)

# Wrap for Glacier
from glacier.pulumi_escape import pulumi_s3_bucket, pulumi_lambda

legacy_storage = pulumi_s3_bucket(existing_bucket)
legacy_compute = pulumi_lambda(existing_lambda)

# Use in Glacier pipeline
legacy_data = Dataset("legacy", storage=legacy_storage)

@pipeline.task(compute=legacy_compute)
def process(data: input_data) -> legacy_data:
    return transform(data)
```

This enables **gradual adoption** - you don't have to rewrite everything at once.

---

## API Reference

### pulumi_s3_bucket

```python
from glacier.pulumi_escape import pulumi_s3_bucket
import pulumi_aws as aws

bucket = aws.s3.BucketV2("my-bucket", ...)
storage = pulumi_s3_bucket(bucket)

# Use in Dataset
data = Dataset("data", storage=storage)
```

### pulumi_gcs_bucket

```python
from glacier.pulumi_escape import pulumi_gcs_bucket
import pulumi_gcp as gcp

bucket = gcp.storage.Bucket("my-bucket", ...)
storage = pulumi_gcs_bucket(bucket)

data = Dataset("data", storage=storage)
```

### pulumi_lambda

```python
from glacier.pulumi_escape import pulumi_lambda
import pulumi_aws as aws

function = aws.lambda_.Function("my-function", ...)
compute = pulumi_lambda(function)

@pipeline.task(compute=compute)
def process() -> output:
    return transform()
```

### pulumi_cloud_function

```python
from glacier.pulumi_escape import pulumi_cloud_function
import pulumi_gcp as gcp

function = gcp.cloudfunctions.Function("my-function", ...)
compute = pulumi_cloud_function(function)

@pipeline.task(compute=compute)
def process() -> output:
    return transform()
```

### PulumiStorageResource (Generic)

For any Pulumi resource:

```python
from glacier.pulumi_escape import PulumiStorageResource

storage = PulumiStorageResource(
    pulumi_resource=your_pulumi_resource,
    provider="aws",  # or "gcp", "azure"
    storage_type="object_storage",  # or "database", "cache", etc.
    metadata={"custom": "info"},
)

data = Dataset("data", storage=storage)
```

### PulumiComputeResource (Generic)

```python
from glacier.pulumi_escape import PulumiComputeResource

compute_resource = PulumiComputeResource(
    pulumi_resource=your_pulumi_resource,
    provider="aws",
    compute_type="serverless",  # or "container", etc.
    metadata={"custom": "info"},
)

@pipeline.task(compute=compute_resource)
def process() -> output:
    return transform()
```

---

## Use Cases

### 1. Compliance Requirements

```python
# HIPAA/SOC2 requires object lock, specific encryption, audit logging
bucket = aws.s3.BucketV2("hipaa-bucket", ...)
# ... configure object lock, encryption, logging ...

storage = pulumi_s3_bucket(bucket)
data = Dataset("patient_data", storage=storage)
```

### 2. Advanced Networking

```python
# Complex VPC setup, private endpoints, transit gateway
vpc = aws.ec2.Vpc("custom-vpc", ...)
endpoints = aws.ec2.VpcEndpoint("s3-endpoint", ...)

# Use in Lambda
lambda_func = aws.lambda_.Function(
    "my-function",
    vpc_config=aws.lambda_.FunctionVpcConfigArgs(
        subnet_ids=vpc.private_subnet_ids,
        security_group_ids=[sg.id],
    ),
)

compute = pulumi_lambda(lambda_func)
```

### 3. Multi-Region Replication

```python
# Primary bucket
primary = aws.s3.BucketV2("primary", ...)

# DR bucket in different region
dr = aws.s3.BucketV2(
    "dr",
    opts=pulumi.ResourceOptions(provider=aws.Provider("dr", region="us-west-2"))
)

# Configure replication...
replication = aws.s3.BucketReplicationConfig(...)

storage = pulumi_s3_bucket(primary)
```

### 4. Existing Infrastructure

```python
# Import existing Pulumi resources
bucket = aws.s3.BucketV2.get("existing", id="my-existing-bucket-id")

# Use in Glacier
storage = pulumi_s3_bucket(bucket)
data = Dataset("legacy_data", storage=storage)
```

---

## Compiler Behavior

When the compiler encounters Pulumi resources:

1. **Detects** the wrapped Pulumi resource
2. **Validates** provider compatibility
3. **Passes through** to Pulumi (doesn't try to recreate)
4. **Generates** connections/permissions around it

Example:

```python
# Pulumi resource
complex_bucket = aws.s3.BucketV2("complex", ...)
storage = pulumi_s3_bucket(complex_bucket)

data = Dataset("data", storage=storage)

@pipeline.task(compute=aws_prod.compute.lambda_())
def process() -> data:
    return fetch()

# Compiler generates:
# - IAM policy for Lambda to access the complex_bucket
# - Does NOT recreate the bucket (uses existing Pulumi resource)
# - Generates Lambda function with appropriate permissions
```

---

## Best Practices

### 1. Start Simple

```python
# Good: Start with Glacier abstractions
bucket = aws_prod.storage.s3(bucket="data")

# Only escalate to Pulumi when needed
```

### 2. Isolate Complexity

```python
# Good: Isolate Pulumi complexity in separate module
from my_pulumi_resources import compliance_bucket

storage = pulumi_s3_bucket(compliance_bucket)

# Pipeline stays clean
```

### 3. Document Why

```python
# Good: Explain why Pulumi is needed
# Using Pulumi escape hatch for:
# - HIPAA compliance (object lock required)
# - Cross-region replication (DR requirement)
# - Custom KMS encryption (security requirement)
complex_storage = pulumi_s3_bucket(compliance_bucket)
```

### 4. Mix Judiciously

```python
# Good: Use Glacier where it fits, Pulumi where needed
simple_data = Dataset("simple", storage=aws_prod.storage.s3(...))  # Glacier
complex_data = Dataset("complex", storage=pulumi_s3_bucket(...))  # Pulumi
```

---

## Limitations

- ⚠️ Pulumi resources bypass Glacier's provider-agnostic guarantees
- ⚠️ Cannot auto-migrate Pulumi resources between providers
- ⚠️ Requires Pulumi knowledge for advanced features
- ⚠️ More verbose than Glacier abstractions

**When to accept these limitations:** When the alternative is not using Glacier at all!

---

## Summary

The Pulumi escape hatch provides:

✅ **Full Pulumi power** when you need it
✅ **Gradual adoption** - integrate existing Pulumi infrastructure
✅ **No limitations** - access any provider feature
✅ **Clean pipelines** - complexity isolated in resource definitions
✅ **Best of both worlds** - simple for common cases, powerful for edge cases

**Philosophy:** Make common things easy (Glacier abstractions), make everything possible (Pulumi escape hatch).

---

For examples, see:
- [examples/pulumi_escape_hatch_example.py](./examples/pulumi_escape_hatch_example.py)
- [Pulumi Documentation](https://www.pulumi.com/docs/)
