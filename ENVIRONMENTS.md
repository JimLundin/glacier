## Cloud Environments: Multi-Account & Multi-Region Support

Glacier uses an **environment-based** approach for managing cloud resources across multiple accounts, regions, and environments (dev/staging/prod).

## The Problem with Direct Resource Creation

**❌ Old approach (doesn't work for multi-account):**

```python
from glacier_aws.storage import S3

# Which AWS account does this belong to?
# Which region?
# Which credentials?
bucket = S3(bucket="my-data")  # AMBIGUOUS!
```

**Problems:**
- No way to specify which AWS account
- Can't distinguish dev vs prod
- No credential context
- Doesn't map to Pulumi providers

## The Solution: Environment-Based Resources

**✅ New approach (environment-scoped):**

```python
from glacier_aws import AWSEnvironment

# Create environment contexts
aws_dev = AWSEnvironment(
    account_id="111111111111",
    region="us-west-2",
    profile="development",
    environment="dev",
)

aws_prod = AWSEnvironment(
    account_id="999999999999",
    region="us-east-1",
    profile="production",
    environment="prod",
)

# Resources belong to specific environments
dev_bucket = aws_dev.storage.s3(bucket="dev-data")
prod_bucket = aws_prod.storage.s3(bucket="prod-data")
```

**Benefits:**
- ✅ Clear which account/region
- ✅ Environment-specific configuration
- ✅ Explicit credential context
- ✅ Maps directly to Pulumi providers

---

## Core Concept: Environment

An **Environment** encapsulates:

```python
AWSEnvironment(
    account_id="123456789012",      # Which AWS account
    region="us-east-1",              # Which region
    profile="production",            # Which AWS profile (credentials)
    environment="prod",              # Logical environment name
    naming_prefix="prod",            # Resource naming convention
    tags={"Env": "prod"},            # Default tags
    vpc_id="vpc-123",                # Networking context (optional)
    subnet_ids=["subnet-a"],         # VPC subnets
    security_group_ids=["sg-prod"],  # Security groups
)
```

Think of it as **"a cloud provider account + configuration context"**.

---

## Creating Resources from Environments

Environments provide **factory methods** for creating resources:

### Storage Resources

```python
# S3
bucket = aws_prod.storage.s3(
    bucket="my-bucket",
    storage_class="INTELLIGENT_TIERING",
    versioning=True,
    encryption="aws:kms",
)

# RDS
database = aws_prod.database.rds(
    instance_identifier="my-db",
    engine="postgres",
    instance_class="db.t3.medium",
)

# DynamoDB
table = aws_prod.database.dynamodb(
    table_name="my-table",
)

# EFS
filesystem = aws_prod.storage.efs(
    file_system_name="my-efs",
)
```

### Compute Resources

```python
# Lambda
lambda_func = aws_prod.compute.lambda_(
    memory=1024,
    timeout=300,
    runtime="python3.11",
    layers=["arn:aws:lambda:..."],
)

# ECS
ecs_task = aws_prod.compute.ecs(
    image="myapp:latest",
    cpu=512,
    memory=1024,
)
```

---

## Use Case 1: Dev/Staging/Prod Environments

```python
from glacier import Pipeline, Dataset
from glacier_aws import AWSEnvironment

# Define environments
aws_dev = AWSEnvironment(
    account_id="111111111111",
    region="us-west-2",
    profile="dev",
    environment="dev",
    tags={"Environment": "development"},
)

aws_staging = AWSEnvironment(
    account_id="222222222222",
    region="us-east-1",
    profile="staging",
    environment="staging",
    tags={"Environment": "staging"},
)

aws_prod = AWSEnvironment(
    account_id="999999999999",
    region="us-east-1",
    profile="production",
    environment="prod",
    tags={"Environment": "production", "CostCenter": "ops"},
    # Prod has VPC
    vpc_id="vpc-prod123",
    subnet_ids=["subnet-a", "subnet-b"],
)

# Same pipeline logic, different environments
def create_pipeline(env: AWSEnvironment):
    pipeline = Pipeline(name=f"analytics-{env.environment}")

    raw_data = Dataset(
        "raw_data",
        storage=env.storage.s3(bucket=f"{env.environment}-raw-data")
    )

    clean_data = Dataset(
        "clean_data",
        storage=env.storage.s3(bucket=f"{env.environment}-clean-data")
    )

    @pipeline.task(compute=env.compute.lambda_(memory=512))
    def extract() -> raw_data:
        return fetch_data()

    @pipeline.task(compute=env.compute.lambda_(memory=1024))
    def clean(data: raw_data) -> clean_data:
        return process(data)

    return pipeline

# Deploy to different environments
dev_pipeline = create_pipeline(aws_dev)
staging_pipeline = create_pipeline(aws_staging)
prod_pipeline = create_pipeline(aws_prod)
```

---

## Use Case 2: Multi-Account Access

Sometimes you need to access resources across accounts (e.g., dev reading from prod for testing):

```python
# Dev environment
aws_dev = AWSEnvironment(account_id="111111111111", region="us-west-2")

# Prod environment
aws_prod = AWSEnvironment(account_id="999999999999", region="us-east-1")

# Prod data
prod_data = Dataset(
    "prod_data",
    storage=aws_prod.storage.s3(bucket="prod-data")
)

# Dev processing
@pipeline.task(compute=aws_dev.compute.lambda_(memory=512))
def test_with_prod_data(data: prod_data) -> dev_results:
    """
    This task runs in DEV account (111111111111) but reads
    from PROD account (999999999999).

    The compiler will:
    1. Detect cross-account access
    2. Generate IAM assume-role policies
    3. Set up appropriate permissions
    """
    return test_process(data)
```

The compiler **automatically detects** the cross-account access and generates:

- IAM role in dev account that can assume role in prod
- IAM role in prod account that allows dev to assume it
- Bucket policy in prod allowing dev account access

---

## Use Case 3: Multi-Region Deployment

Deploy the same pipeline to multiple regions:

```python
# Primary region
aws_us = AWSEnvironment(
    account_id="123456789012",
    region="us-east-1",
    environment="prod-us",
)

# DR region
aws_eu = AWSEnvironment(
    account_id="123456789012",  # Same account
    region="eu-west-1",          # Different region!
    environment="prod-eu",
)

# Deploy to both regions
us_pipeline = create_pipeline(aws_us)
eu_pipeline = create_pipeline(aws_eu)

# Compile both
us_infra = us_pipeline.compile(AWSCompiler.from_environment(aws_us))
eu_infra = eu_pipeline.compile(AWSCompiler.from_environment(aws_eu))
```

---

## Use Case 4: Organization with Multiple AWS Accounts

Large organizations often have separate AWS accounts for:
- Development teams
- Different products
- Compliance/regulatory boundaries
- Cost allocation

```python
# Data engineering team account
aws_data_eng = AWSEnvironment(
    account_id="111111111111",
    region="us-east-1",
    profile="data-engineering",
)

# ML team account
aws_ml = AWSEnvironment(
    account_id="222222222222",
    region="us-west-2",
    profile="machine-learning",
)

# Shared data lake account
aws_data_lake = AWSEnvironment(
    account_id="999999999999",
    region="us-east-1",
    profile="data-lake",
)

# Data engineering writes to data lake
@pipeline.task(compute=aws_data_eng.compute.lambda_())
def extract() -> data_lake_dataset:
    # Runs in data-eng account, writes to data-lake account
    pass

# ML team reads from data lake
@pipeline.task(compute=aws_ml.compute.lambda_())
def train(data: data_lake_dataset) -> model:
    # Runs in ML account, reads from data-lake account
    pass
```

---

## Mapping to Pulumi Providers

Environments map **directly** to Pulumi provider instances:

```python
# Glacier environment
aws_prod = AWSEnvironment(
    account_id="123456789012",
    region="us-east-1",
    profile="production",
)

# Generated Pulumi code
import pulumi_aws as aws

# Creates Pulumi provider instance
prod_provider = aws.Provider(
    "prod",
    region="us-east-1",
    profile="production",
    allowed_account_ids=["123456789012"],
)

# Resources use this provider
bucket = aws.s3.BucketV2(
    "my-bucket",
    bucket="prod-data",
    opts=pulumi.ResourceOptions(provider=prod_provider),  # ← Provider binding
)
```

This is why environments are so powerful - they map exactly to how Pulumi works!

---

## Environment Configuration Options

### Basic Configuration

```python
AWSEnvironment(
    account_id="123456789012",  # Required
    region="us-east-1",          # Required
)
```

### Full Configuration

```python
AWSEnvironment(
    # Identity
    account_id="123456789012",
    region="us-east-1",
    profile="production",           # AWS CLI profile
    environment="prod",             # Logical name

    # Naming & Tagging
    naming_prefix="prod",           # Prefix for resource names
    tags={                          # Default tags for all resources
        "Environment": "production",
        "ManagedBy": "glacier",
        "Team": "data-engineering",
        "CostCenter": "engineering",
    },

    # Networking (optional, for Lambda/ECS)
    vpc_id="vpc-123456",
    subnet_ids=["subnet-a", "subnet-b", "subnet-c"],
    security_group_ids=["sg-app", "sg-db"],
)
```

---

## Generic vs Environment-Scoped Resources

You can still use **generic** resources when you don't need multi-account support:

```python
from glacier.storage import ObjectStorage  # Generic
from glacier import compute

# Generic resources (for simple, single-account pipelines)
data = Dataset("data", storage=ObjectStorage())

@pipeline.task(compute=compute.serverless(memory=512))
def process() -> data:
    return fetch()

# Compile to any environment
infra = pipeline.compile(AWSCompiler.from_environment(aws_prod))
```

**When to use which:**

| Scenario | Use |
|----------|-----|
| Single AWS account | Generic resources |
| Dev/staging/prod (different accounts) | Environment-scoped |
| Multi-region | Environment-scoped |
| Cross-account access | Environment-scoped |
| Need account-specific config | Environment-scoped |

---

## Compiler Integration

The compiler uses environment information to generate correct infrastructure:

```python
from glacier_aws import AWSCompiler, AWSEnvironment

# Create environment
aws_prod = AWSEnvironment(
    account_id="123456789012",
    region="us-east-1",
    profile="production",
    vpc_id="vpc-123",
)

# Compiler from environment
compiler = AWSCompiler.from_environment(aws_prod)

# Or pass environment to existing compiler
compiler = AWSCompiler(
    region=aws_prod.region,
    account_id=aws_prod.account_id,
    vpc_config={
        "vpc_id": aws_prod.vpc_id,
        "subnet_ids": aws_prod.subnet_ids,
    },
)

infra = pipeline.compile(compiler)
```

---

## Environment Validation

Environments validate configuration at creation time:

```python
# ✅ Valid
env = AWSEnvironment(
    account_id="123456789012",  # 12 digits
    region="us-east-1",         # Valid AWS region
)

# ❌ Invalid - will raise ValueError
env = AWSEnvironment(
    account_id="123",           # Too short!
    region="invalid-region",    # Not a real region
)
```

---

## Best Practices

### 1. Create Environments Early

```python
# Good: Define all environments upfront
aws_dev = AWSEnvironment(...)
aws_staging = AWSEnvironment(...)
aws_prod = AWSEnvironment(...)

# Then use them throughout
data = Dataset("data", storage=aws_prod.storage.s3(...))
```

### 2. Use Environment Names Consistently

```python
# Good: Environment name matches its purpose
aws_prod = AWSEnvironment(environment="prod", ...)
aws_dev = AWSEnvironment(environment="dev", ...)

# Avoid: Confusing names
aws_prod = AWSEnvironment(environment="my-env-123", ...)  # ❌
```

### 3. Leverage Environment Tags

```python
# Good: Use tags for cost allocation and organization
env = AWSEnvironment(
    tags={
        "Environment": "production",
        "Team": "data-engineering",
        "CostCenter": "eng-001",
        "Application": "analytics",
    }
)
```

### 4. Keep Credentials Out of Code

```python
# Good: Use AWS profiles (credentials in ~/.aws/credentials)
env = AWSEnvironment(
    account_id="123456789012",
    profile="production",  # Reads from AWS config
)

# Bad: Hardcoded credentials
env = AWSEnvironment(
    access_key="AKIAIOSFODNN7EXAMPLE",  # ❌ NEVER DO THIS
    secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
)
```

### 5. Use Separate Accounts for Isolation

```python
# Good: Separate accounts for dev/prod
aws_dev = AWSEnvironment(account_id="111111111111", ...)   # Dev account
aws_prod = AWSEnvironment(account_id="999999999999", ...)  # Prod account

# Acceptable: Same account, different regions
aws_us = AWSEnvironment(account_id="123456", region="us-east-1", ...)
aws_eu = AWSEnvironment(account_id="123456", region="eu-west-1", ...)
```

---

## Migration from Old Approach

If you were using the old direct resource creation:

**Old (before environments):**
```python
from glacier_aws.storage import S3

bucket = S3(bucket="my-data")  # Which account?
```

**New (with environments):**
```python
from glacier_aws import AWSEnvironment

aws_prod = AWSEnvironment(
    account_id="123456789012",
    region="us-east-1",
)

bucket = aws_prod.storage.s3(bucket="my-data")  # Clear!
```

---

## Summary

**Environments solve:**
- ✅ Multi-account deployments
- ✅ Dev/staging/prod separation
- ✅ Multi-region deployments
- ✅ Cross-account resource access
- ✅ Credential management
- ✅ Resource naming conventions
- ✅ Cost allocation via tags
- ✅ Pulumi provider mapping

**Key pattern:**
1. Create environment context
2. Create resources FROM environment
3. Resources carry environment metadata
4. Compiler uses environment to generate correct infrastructure

---

For examples, see:
- [examples/multi_environment_example.py](./examples/multi_environment_example.py)
- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [MULTICLOUD.md](./MULTICLOUD.md)
