# Glacier Design Document V3

## Executive Summary

Glacier is a cloud-agnostic data pipeline library that uses **dependency injection** and **registry patterns** to achieve true cloud portability without inheritance hierarchies. The core design principle is: **one Provider class, one Bucket class, one Serverless class** - cloud-specific behavior is achieved through configuration, not subclassing.

## Design Philosophy

### Core Principles

1. **Composition Over Inheritance**: Use configuration and dependency injection rather than class hierarchies
2. **Registry Pattern**: Provider acts as a factory/registry for creating resources
3. **Dependency Injection**: Resources receive their dependencies (Provider, Configs) explicitly
4. **Unified Resource Model**: Single classes (Bucket, Serverless) work across all clouds
5. **Configuration-Based Polymorphism**: Cloud-specific behavior via config objects, not subclasses
6. **Execution as Resources**: Execution environments are first-class resources attached to the provider

### What This Means

```python
# ❌ WRONG: Provider subclasses
provider = AWSProvider(region="us-east-1")  # No!
bucket = S3Bucket(...)  # No!

# ✅ RIGHT: Single Provider, configured with cloud-specific config
from glacier import Provider
from glacier.config import AwsConfig, S3Config

provider = Provider(config=AwsConfig(region="us-east-1"))
bucket = provider.bucket("my-data", config=S3Config(versioning=True))
```

## Architecture Overview

### Component Hierarchy

```
Provider (single class)
├── Config: AwsConfig | AzureConfig | GcpConfig | LocalConfig
├── Registry Methods: bucket(), serverless(), executor()
└── Resources (created via registry)
    ├── Bucket (single class)
    │   └── Config: S3Config | BlobConfig | GcsConfig
    ├── Serverless (single class)
    │   └── Config: LambdaConfig | AzureFunctionConfig | CloudFunctionConfig
    └── Executor (single class)
        └── Config: DatabricksConfig | GlueConfig | DataprocConfig | SynapseConfig
```

### Key Design Elements

1. **Single Provider Class**: One `Provider` class that adapts to any cloud via configuration
2. **Provider as Registry**: `provider.bucket()`, `provider.serverless()`, `provider.executor()` are factory methods
3. **Resource Polymorphism**: Resources (Bucket, Serverless, Executor) are cloud-agnostic
4. **Config-Based Behavior**: Cloud-specific behavior injected via config objects
5. **Adapter Pattern**: Internal adapters handle cloud-specific implementation details
6. **Core Principle**: **Only configs can be platform-specific, never resources**

### The Golden Rule

**"We abstract away the infrastructure with an escape hatch via the config option"**

This means:
- ✅ `Bucket` (generic) + `S3Config` (specific) = abstraction + escape hatch
- ✅ `Executor` (generic) + `DatabricksConfig` (specific) = abstraction + escape hatch
- ❌ `S3Bucket` (specific class) = no abstraction, defeats the purpose
- ❌ `DatabricksExecutor` (specific class) = no abstraction, defeats the purpose

You get:
- **Abstraction**: Generic resources work across all platforms
- **Escape Hatch**: Platform-specific configs when you need them
- **Best of both worlds**: Cloud-agnostic code with platform-specific optimizations

## Core Components

### 1. Provider Object

The Provider is the central orchestrator. It:
- Acts as a **registry/factory** for creating resources
- Injects itself into resources (**dependency injection**)
- Maintains cloud-specific configuration
- Creates appropriate adapters for resources

```python
class Provider:
    """
    Single provider class that works with any cloud.

    The provider acts as a registry/factory for creating resources.
    It injects itself into resources, enabling them to access
    cloud-specific adapters and configuration.
    """

    def __init__(
        self,
        config: AwsConfig | AzureConfig | GcpConfig | LocalConfig,
        tags: dict[str, str] | None = None
    ):
        """
        Initialize provider with cloud-specific configuration.

        Args:
            config: Cloud-specific configuration object
            tags: Default tags to apply to all resources
        """
        self.config = config
        self.tags = tags or {}

        # Registry of created resources (for tracking)
        self._resources: list[Resource] = []

        # Adapter registry (maps resource types to adapter classes)
        self._adapter_registry = self._build_adapter_registry()

    def bucket(
        self,
        bucket_name: str,
        path: str = "",
        format: str = "parquet",
        config: S3Config | BlobConfig | GcsConfig | None = None,
        name: str | None = None,
    ) -> Bucket:
        """
        Create a Bucket resource.

        This is a registry/factory method that creates a generic Bucket
        and injects the provider into it.

        Args:
            bucket_name: Name of the bucket
            path: Path within bucket
            format: Data format
            config: Cloud-specific bucket configuration
            name: Optional resource name

        Returns:
            Bucket instance with provider injected
        """
        bucket = Bucket(
            bucket_name=bucket_name,
            path=path,
            format=format,
            provider=self,  # Dependency injection!
            config=config,
            name=name,
        )
        self._resources.append(bucket)
        return bucket

    def serverless(
        self,
        function_name: str,
        handler: Callable | str,
        runtime: str = "python3.11",
        config: LambdaConfig | AzureFunctionConfig | CloudFunctionConfig | None = None,
        name: str | None = None,
    ) -> Serverless:
        """
        Create a Serverless execution resource.

        Args:
            function_name: Name of the function
            handler: Handler function or path
            runtime: Runtime environment
            config: Cloud-specific serverless configuration
            name: Optional resource name

        Returns:
            Serverless instance with provider injected
        """
        serverless = Serverless(
            function_name=function_name,
            handler=handler,
            runtime=runtime,
            provider=self,  # Dependency injection!
            config=config,
            name=name,
        )
        self._resources.append(serverless)
        return serverless

    def executor(
        self,
        name: str,
        config: DatabricksConfig | GlueConfig | DataprocConfig | SynapseConfig | None = None,
        runtime: str | None = None,
    ) -> Executor:
        """
        Create an Executor resource.

        Executors are generic execution environments. The actual platform
        (Databricks, Glue, Dataproc, etc.) is determined by the config.

        This follows the same pattern as Bucket - one resource type,
        cloud-specific behavior via config.

        Args:
            name: Name of the executor/cluster/job
            config: Platform-specific configuration (DatabricksConfig, GlueConfig, etc.)
            runtime: Optional runtime specification
            name: Optional resource name

        Returns:
            Executor instance with provider injected

        Examples:
            # Databricks executor
            executor = provider.executor(
                "analytics-cluster",
                config=DatabricksConfig(instance_type="m5.xlarge", num_workers=4)
            )

            # AWS Glue executor
            executor = provider.executor(
                "etl-job",
                config=GlueConfig(worker_type="G.1X", num_workers=5)
            )

            # GCP Dataproc executor
            executor = provider.executor(
                "spark-cluster",
                config=DataprocConfig(machine_type="n1-standard-4")
            )
        """
        executor = Executor(
            name=name,
            provider=self,  # Dependency injection!
            config=config,
            runtime=runtime,
        )
        self._resources.append(executor)
        return executor

    def _build_adapter_registry(self) -> dict[type, type]:
        """
        Build the adapter registry based on provider config.

        This maps resource types to their cloud-specific adapter classes.

        NOTE: Executor adapters are selected based on the Executor's config,
        not the Provider's config, since executors can be cross-cloud
        (e.g., Databricks on AWS or Azure).
        """
        if isinstance(self.config, AwsConfig):
            from glacier.adapters.aws import (
                S3BucketAdapter,
                LambdaAdapter,
            )
            return {
                Bucket: S3BucketAdapter,
                Serverless: LambdaAdapter,
            }
        elif isinstance(self.config, AzureConfig):
            from glacier.adapters.azure import (
                BlobStorageAdapter,
                AzureFunctionAdapter,
            )
            return {
                Bucket: BlobStorageAdapter,
                Serverless: AzureFunctionAdapter,
            }
        elif isinstance(self.config, GcpConfig):
            from glacier.adapters.gcp import (
                GcsAdapter,
                CloudFunctionAdapter,
            )
            return {
                Bucket: GcsAdapter,
                Serverless: CloudFunctionAdapter,
            }
        else:  # LocalConfig
            from glacier.adapters.local import (
                LocalBucketAdapter,
                LocalServerlessAdapter,
            )
            return {
                Bucket: LocalBucketAdapter,
                Serverless: LocalServerlessAdapter,
            }

    def get_adapter(self, resource: Resource) -> Adapter:
        """
        Get the appropriate adapter for a resource.

        This is called by resources to get their cloud-specific adapter.

        For most resources (Bucket, Serverless), the adapter is determined
        by the Provider's config. For Executor, the adapter is determined
        by the Executor's config, allowing cross-cloud executors.

        Args:
            resource: The resource needing an adapter

        Returns:
            Cloud-specific adapter instance
        """
        # Special case: Executor adapter is determined by executor config
        if isinstance(resource, Executor):
            return self._get_executor_adapter(resource)

        # Standard case: adapter determined by provider config
        resource_type = type(resource)
        adapter_class = self._adapter_registry.get(resource_type)
        if adapter_class is None:
            raise ValueError(
                f"No adapter registered for {resource_type.__name__} "
                f"with {type(self.config).__name__}"
            )
        return adapter_class(resource, self)

    def _get_executor_adapter(self, executor: Executor) -> Adapter:
        """
        Get adapter for an Executor based on its config.

        Executor adapters are determined by the executor's config type,
        not the provider's config. This allows using Databricks on AWS,
        Azure, or standalone.
        """
        from glacier.config import (
            DatabricksConfig,
            GlueConfig,
            DataprocConfig,
            SynapseConfig,
        )

        if isinstance(executor.config, DatabricksConfig):
            from glacier.adapters.databricks import DatabricksAdapter
            return DatabricksAdapter(executor, self)
        elif isinstance(executor.config, GlueConfig):
            from glacier.adapters.aws import GlueAdapter
            return GlueAdapter(executor, self)
        elif isinstance(executor.config, DataprocConfig):
            from glacier.adapters.gcp import DataprocAdapter
            return DataprocAdapter(executor, self)
        elif isinstance(executor.config, SynapseConfig):
            from glacier.adapters.azure import SynapseAdapter
            return SynapseAdapter(executor, self)
        else:
            # Default to local execution if no config provided
            from glacier.adapters.local import LocalExecutorAdapter
            return LocalExecutorAdapter(executor, self)

    def get_resources(self) -> list[Resource]:
        """Get all resources created by this provider."""
        return self._resources.copy()

    @classmethod
    def from_env(cls) -> Provider:
        """
        Create a provider from environment variables.

        Detects cloud provider from environment and loads appropriate config.
        """
        # Detect cloud from environment
        if os.getenv("AWS_REGION"):
            config = AwsConfig.from_env()
        elif os.getenv("AZURE_RESOURCE_GROUP"):
            config = AzureConfig.from_env()
        elif os.getenv("GCP_PROJECT"):
            config = GcpConfig.from_env()
        else:
            config = LocalConfig.from_env()

        return cls(config=config)
```

### 2. Configuration Objects

Configuration objects encapsulate cloud-specific settings. They are **data classes**, not behavior classes.

```python
class AwsConfig(BaseModel):
    """
    AWS provider configuration.

    This is a data class - it holds configuration, not behavior.
    """
    region: str
    profile: str | None = None
    account_id: str | None = None
    role_arn: str | None = None
    session_token: str | None = None

    @classmethod
    def from_env(cls) -> AwsConfig:
        """Load from environment variables."""
        return cls(
            region=os.getenv("AWS_REGION", "us-east-1"),
            profile=os.getenv("AWS_PROFILE"),
            account_id=os.getenv("AWS_ACCOUNT_ID"),
            role_arn=os.getenv("AWS_ROLE_ARN"),
        )


class S3Config(BaseModel):
    """
    S3-specific bucket configuration.

    Passed to Bucket when using AWS provider.
    """
    versioning: bool = False
    lifecycle_rules: list[dict] | None = None
    encryption: str = "AES256"
    public_access_block: bool = True
    cors: list[dict] | None = None


class BlobConfig(BaseModel):
    """
    Azure Blob Storage configuration.

    Passed to Bucket when using Azure provider.
    """
    tier: str = "Hot"  # Hot, Cool, Archive
    replication: str = "LRS"  # LRS, GRS, RA-GRS
    encryption_scope: str | None = None
    soft_delete_retention_days: int = 7


class GcsConfig(BaseModel):
    """
    Google Cloud Storage configuration.

    Passed to Bucket when using GCP provider.
    """
    storage_class: str = "STANDARD"
    versioning: bool = False
    lifecycle_rules: list[dict] | None = None
    uniform_bucket_level_access: bool = True
```

### 3. Resource Objects

Resources are **cloud-agnostic** objects that represent infrastructure components. They receive the Provider via dependency injection and use it to access cloud-specific adapters.

```python
class Resource(ABC):
    """
    Base class for all resources.

    Resources are cloud-agnostic objects that receive a Provider
    via dependency injection.
    """

    def __init__(
        self,
        provider: Provider,
        config: Any | None = None,
        name: str | None = None,
    ):
        """
        Initialize resource.

        Args:
            provider: Provider instance (injected)
            config: Cloud-specific configuration
            name: Optional resource name
        """
        self.provider = provider
        self.config = config
        self.name = name or self._generate_name()

        # Lazy-initialized adapter
        self._adapter: Adapter | None = None

    def _get_adapter(self) -> Adapter:
        """
        Get the cloud-specific adapter.

        Adapters are created lazily and cached.
        """
        if self._adapter is None:
            self._adapter = self.provider.get_adapter(self)
        return self._adapter

    @abstractmethod
    def _generate_name(self) -> str:
        """Generate a default name for this resource."""
        pass


class Bucket(Resource):
    """
    Generic bucket abstraction.

    Works with S3, Azure Blob Storage, GCS, or local filesystem.
    Cloud-specific behavior is handled by adapters.
    """

    def __init__(
        self,
        bucket_name: str,
        path: str = "",
        format: str = "parquet",
        provider: Provider | None = None,
        config: S3Config | BlobConfig | GcsConfig | None = None,
        name: str | None = None,
    ):
        """
        Initialize bucket.

        Note: Users should use provider.bucket() instead of direct instantiation.

        Args:
            bucket_name: Name of bucket/container
            path: Path within bucket
            format: Data format
            provider: Provider instance (injected)
            config: Cloud-specific bucket config
            name: Optional resource name
        """
        if provider is None:
            raise ValueError(
                "Bucket must be created via Provider.bucket(). "
                "Do not instantiate directly."
            )

        super().__init__(provider, config, name)
        self.bucket_name = bucket_name
        self.path = path.lstrip("/")
        self.format = format.lower()

    def scan(self) -> pl.LazyFrame:
        """
        Scan data from bucket.

        Returns:
            Polars LazyFrame
        """
        adapter = self._get_adapter()
        return adapter.scan()

    def write(self, data: pl.DataFrame | pl.LazyFrame) -> None:
        """
        Write data to bucket.

        Args:
            data: Polars DataFrame or LazyFrame
        """
        adapter = self._get_adapter()
        adapter.write(data)

    def exists(self) -> bool:
        """Check if bucket/path exists."""
        adapter = self._get_adapter()
        return adapter.exists()

    def get_uri(self) -> str:
        """
        Get cloud-specific URI.

        Returns:
            - AWS: s3://bucket/path
            - Azure: abfs://container@account.dfs.core.windows.net/path
            - GCS: gs://bucket/path
            - Local: file:///path
        """
        adapter = self._get_adapter()
        return adapter.get_uri()

    def _generate_name(self) -> str:
        """Generate default name."""
        return f"{self.bucket_name}_{self.path.replace('/', '_')}"


class Serverless(Resource):
    """
    Generic serverless execution environment.

    Works with AWS Lambda, Azure Functions, Google Cloud Functions,
    or local execution.
    """

    def __init__(
        self,
        function_name: str,
        handler: Callable | str,
        runtime: str = "python3.11",
        provider: Provider | None = None,
        config: LambdaConfig | AzureFunctionConfig | CloudFunctionConfig | None = None,
        name: str | None = None,
    ):
        """
        Initialize serverless function.

        Args:
            function_name: Function name
            handler: Handler function or path
            runtime: Runtime environment
            provider: Provider instance (injected)
            config: Cloud-specific serverless config
            name: Optional resource name
        """
        if provider is None:
            raise ValueError(
                "Serverless must be created via Provider.serverless(). "
                "Do not instantiate directly."
            )

        super().__init__(provider, config, name)
        self.function_name = function_name
        self.handler = handler
        self.runtime = runtime

    def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Invoke the serverless function.

        Args:
            payload: Input payload

        Returns:
            Function response
        """
        adapter = self._get_adapter()
        return adapter.invoke(payload)

    def deploy(self) -> None:
        """Deploy the function."""
        adapter = self._get_adapter()
        adapter.deploy()

    def _generate_name(self) -> str:
        """Generate default name."""
        return self.function_name


class Executor(Resource):
    """
    Generic executor abstraction.

    Executors are first-class resources, just like storage (Bucket) and
    compute (Serverless). The actual platform (Databricks, Glue, Dataproc,
    Synapse) is determined by the config, not by the class.

    This follows the core principle: only configs are platform-specific,
    resources are abstract.

    Examples:
        # Databricks executor (can run on AWS, Azure, or GCP)
        executor = provider.executor(
            "analytics-cluster",
            config=DatabricksConfig(...)
        )

        # AWS Glue executor
        executor = provider.executor(
            "etl-job",
            config=GlueConfig(...)
        )

        # GCP Dataproc executor
        executor = provider.executor(
            "spark-cluster",
            config=DataprocConfig(...)
        )
    """

    def __init__(
        self,
        name: str,
        provider: Provider | None = None,
        config: DatabricksConfig | GlueConfig | DataprocConfig | SynapseConfig | None = None,
        runtime: str | None = None,
    ):
        """
        Initialize executor.

        Args:
            name: Name of the executor/cluster/job
            provider: Provider instance (injected)
            config: Platform-specific executor config
            runtime: Optional runtime specification
        """
        if provider is None:
            raise ValueError(
                "Executor must be created via Provider.executor(). "
                "Do not instantiate directly."
            )

        super().__init__(provider, config, name)
        self.runtime = runtime

    def submit_job(self, job_definition: dict[str, Any]) -> str:
        """
        Submit a job to the executor.

        The actual implementation depends on the executor config:
        - DatabricksConfig: submits to Databricks jobs API
        - GlueConfig: submits to AWS Glue
        - DataprocConfig: submits to GCP Dataproc
        - etc.

        Args:
            job_definition: Job configuration

        Returns:
            Job ID
        """
        adapter = self._get_adapter()
        return adapter.submit_job(job_definition)

    def get_job_status(self, job_id: str) -> str:
        """
        Get job status.

        Args:
            job_id: Job identifier

        Returns:
            Job status (PENDING, RUNNING, SUCCEEDED, FAILED)
        """
        adapter = self._get_adapter()
        return adapter.get_job_status(job_id)

    def cancel_job(self, job_id: str) -> None:
        """
        Cancel a running job.

        Args:
            job_id: Job identifier
        """
        adapter = self._get_adapter()
        adapter.cancel_job(job_id)

    def _generate_name(self) -> str:
        """Generate default name."""
        # Use the config type to generate a descriptive name
        config_type = type(self.config).__name__ if self.config else "local"
        return f"{config_type.lower().replace('config', '')}_{self.name}"
```

### 4. Adapter Pattern

Adapters handle cloud-specific implementation details. They are **internal** - users never interact with them directly.

```python
class Adapter(ABC):
    """
    Base adapter class.

    Adapters handle cloud-specific implementation details.
    They are internal - users never see them.
    """

    def __init__(self, resource: Resource, provider: Provider):
        """
        Initialize adapter.

        Args:
            resource: The resource this adapter serves
            provider: The provider (for accessing config)
        """
        self.resource = resource
        self.provider = provider


class S3BucketAdapter(Adapter):
    """S3-specific bucket adapter."""

    def scan(self) -> pl.LazyFrame:
        """Scan from S3 using Polars."""
        uri = self.get_uri()

        # Get S3-specific config if provided
        config = self.resource.config
        storage_options = {}
        if isinstance(self.provider.config, AwsConfig):
            storage_options["region"] = self.provider.config.region
            if self.provider.config.profile:
                storage_options["profile"] = self.provider.config.profile

        # Use Polars to scan from S3
        if self.resource.format == "parquet":
            return pl.scan_parquet(uri, storage_options=storage_options)
        elif self.resource.format == "csv":
            return pl.scan_csv(uri, storage_options=storage_options)
        else:
            raise ValueError(f"Unsupported format: {self.resource.format}")

    def write(self, data: pl.DataFrame | pl.LazyFrame) -> None:
        """Write to S3."""
        uri = self.get_uri()
        if isinstance(data, pl.LazyFrame):
            data = data.collect()

        # Write using Polars
        if self.resource.format == "parquet":
            data.write_parquet(uri)
        elif self.resource.format == "csv":
            data.write_csv(uri)
        else:
            raise ValueError(f"Unsupported format: {self.resource.format}")

    def exists(self) -> bool:
        """Check if S3 object exists."""
        # Use boto3 to check existence
        import boto3
        s3 = boto3.client("s3", region_name=self.provider.config.region)
        try:
            s3.head_object(Bucket=self.resource.bucket_name, Key=self.resource.path)
            return True
        except:
            return False

    def get_uri(self) -> str:
        """Get S3 URI."""
        return f"s3://{self.resource.bucket_name}/{self.resource.path}"
```

## Usage Examples

### Example 1: Basic Cloud-Agnostic Pipeline

```python
from glacier import Provider, pipeline, task
from glacier.config import AwsConfig, S3Config
import polars as pl

# Create provider with AWS config
provider = Provider(config=AwsConfig(region="us-east-1"))

# Create bucket resource via registry
raw_data = provider.bucket(
    bucket_name="my-data-lake",
    path="raw/sales.parquet",
    config=S3Config(versioning=True),
)

output_bucket = provider.bucket(
    bucket_name="my-data-lake",
    path="processed/sales.parquet",
)

@task
def load_data(source):
    return source.scan()

@task(depends_on=[load_data])
def clean_data(df: pl.LazyFrame) -> pl.LazyFrame:
    return df.filter(pl.col("amount") > 0)

@task(depends_on=[clean_data])
def save_data(df: pl.LazyFrame, destination):
    destination.write(df)

@pipeline(name="sales_pipeline")
def sales_pipeline():
    df = load_data(raw_data)
    cleaned = clean_data(df)
    save_data(cleaned, output_bucket)

# Run pipeline
sales_pipeline.run()
```

### Example 2: Switch Clouds by Changing Config

```python
from glacier import Provider
from glacier.config import AwsConfig, AzureConfig, GcpConfig

# Development: Local
dev_provider = Provider(config=LocalConfig(base_path="./data"))

# Staging: AWS
staging_provider = Provider(config=AwsConfig(
    region="us-west-2",
    profile="staging",
))

# Production: Azure
prod_provider = Provider(config=AzureConfig(
    resource_group="prod-data-rg",
    location="eastus",
    subscription_id="xxx",
))

# GCP Alternative
gcp_provider = Provider(config=GcpConfig(
    project="my-project",
    region="us-central1",
))

# Same bucket creation code works with any provider!
def create_pipeline(provider: Provider):
    data = provider.bucket("data-lake", path="input.parquet")
    output = provider.bucket("data-lake", path="output.parquet")

    # ... define pipeline ...
    return pipeline

# Works with any provider!
dev_pipeline = create_pipeline(dev_provider)
staging_pipeline = create_pipeline(staging_provider)
prod_pipeline = create_pipeline(prod_provider)
```

### Example 3: Executors as Resources

```python
from glacier import Provider
from glacier.config import AwsConfig, DatabricksConfig, GlueConfig

provider = Provider(config=AwsConfig(region="us-east-1"))

# Storage resources
data_source = provider.bucket("raw-data", path="sales.parquet")
output = provider.bucket("processed-data", path="aggregated.parquet")

# Executor resources - note the consistent pattern!
# Just like Bucket is generic with S3Config, Executor is generic with DatabricksConfig

databricks_executor = provider.executor(
    name="analytics-cluster",
    config=DatabricksConfig(
        instance_type="m5.xlarge",
        num_workers=4,
        spark_version="13.3.x-scala2.12",
    ),
)

glue_executor = provider.executor(
    name="etl-job",
    config=GlueConfig(
        worker_type="G.1X",
        num_workers=5,
        glue_version="4.0",
    ),
)

# Tasks can specify executors
@task(executor=databricks_executor)
def heavy_transform(df: pl.LazyFrame) -> pl.LazyFrame:
    # Runs on Databricks
    return df.with_columns([
        pl.col("revenue").rolling_mean(window_size=7)
    ])

@task(executor=glue_executor, depends_on=[heavy_transform])
def save_results(df: pl.LazyFrame):
    # Runs on AWS Glue
    output.write(df)
```

### Example 4: Cross-Cloud Executors (Databricks)

One powerful aspect of this design: executors like Databricks can run on any cloud!

```python
from glacier import Provider
from glacier.config import AwsConfig, AzureConfig, DatabricksConfig

# Databricks on AWS
aws_provider = Provider(config=AwsConfig(region="us-east-1"))
databricks_on_aws = aws_provider.executor(
    name="analytics-cluster",
    config=DatabricksConfig(
        instance_type="m5.xlarge",  # AWS instance type
        num_workers=4,
    ),
)

# Same Databricks config, different cloud!
azure_provider = Provider(config=AzureConfig(
    resource_group="prod-rg",
    location="eastus",
))
databricks_on_azure = azure_provider.executor(
    name="analytics-cluster",
    config=DatabricksConfig(
        instance_type="Standard_D4s_v3",  # Azure instance type
        num_workers=4,
    ),
)

# The executor config (DatabricksConfig) determines the platform
# The provider config determines where it runs
# This separation is powerful!
```

### Example 5: Provider-Specific Config for Optimization

```python
from glacier import Provider
from glacier.config import AwsConfig, S3Config

provider = Provider(config=AwsConfig(region="us-east-1"))

# High-performance bucket with S3-specific optimizations
high_perf_bucket = provider.bucket(
    bucket_name="analytics-data",
    path="hot-data/",
    config=S3Config(
        versioning=False,  # Disable versioning for performance
        encryption="aws:kms",  # Use KMS encryption
        lifecycle_rules=[
            {
                "id": "archive-old-data",
                "transition": {"days": 30, "storage_class": "GLACIER"},
            }
        ],
    ),
)

# Cost-optimized bucket
cold_storage = provider.bucket(
    bucket_name="analytics-data",
    path="archive/",
    config=S3Config(
        lifecycle_rules=[
            {
                "id": "immediate-archive",
                "transition": {"days": 0, "storage_class": "DEEP_ARCHIVE"},
            }
        ],
    ),
)
```

## Key Design Decisions

### Decision 1: Single Provider Class

**Rationale**: A single Provider class configured with cloud-specific config objects is more flexible than a hierarchy of provider subclasses.

**Benefits**:
- Easier to extend to new clouds
- No multiple inheritance issues
- Clear separation of configuration and behavior
- Easier to test and mock
- More functional programming style

**Trade-offs**:
- Must use runtime type checking (isinstance) instead of compile-time
- Adapter registry pattern adds some complexity

### Decision 2: Provider as Registry/Factory

**Rationale**: `provider.bucket()` serves as both a registry and factory, creating resources and injecting dependencies.

**Benefits**:
- Clear, discoverable API
- Ensures all resources have proper provider reference
- Enables resource tracking for infrastructure generation
- Natural namespace for resource types

### Decision 3: No Resource Subclasses

**Rationale**: Having `Bucket` instead of `S3Bucket`, `AzureBlobBucket`, etc. maintains cloud-agnostic code.

**Benefits**:
- Pipeline code truly cloud-agnostic
- No need to change imports when switching clouds
- Forces proper abstraction
- Simpler mental model

**Trade-offs**:
- Need adapter pattern for cloud-specific behavior
- Some cloud-specific features might be harder to expose

### Decision 4: Config Objects for Cloud-Specific Behavior

**Rationale**: Configuration objects (S3Config, BlobConfig) provide cloud-specific customization without breaking abstraction.

**Benefits**:
- Optional: can use defaults for generic use cases
- Explicit: cloud-specific features are clearly marked
- Type-safe: configs are validated by Pydantic
- Composable: can mix generic and specific configs

### Decision 5: Executors as Resources with Config-Based Dispatch

**Rationale**: Treating executors (Databricks, Glue, etc.) as first-class resources with config-based adapter selection allows cross-cloud executors.

**Key Insight**: Unlike Bucket and Serverless (where the adapter is determined by the Provider's config), Executor adapters are determined by the Executor's config. This enables Databricks to run on AWS, Azure, or GCP with the same Executor class.

**Benefits**:
- Consistent API: same pattern as storage resources
- Cross-cloud executors: Databricks on any cloud
- Better tracking: can analyze all resources used
- Infrastructure generation: can generate execution env configs
- Flexibility: can have multiple executors per provider
- Separation of concerns: provider config = where, executor config = what

### Decision 6: Dependency Injection Throughout

**Rationale**: Explicit dependency injection (passing provider to resources) makes dependencies clear and testable.

**Benefits**:
- Testability: easy to mock providers and resources
- Clarity: dependencies are explicit
- Flexibility: can swap implementations easily
- No global state or singletons

## Extension Points

### Adding a New Cloud Provider

To add a new cloud provider:

1. Create config class:
```python
class NewCloudConfig(BaseModel):
    region: str
    api_key: str
```

2. Create adapters:
```python
class NewCloudBucketAdapter(Adapter):
    def scan(self) -> pl.LazyFrame:
        # Implement cloud-specific scan
        pass
```

3. Update Provider adapter registry:
```python
def _build_adapter_registry(self):
    if isinstance(self.config, NewCloudConfig):
        return {
            Bucket: NewCloudBucketAdapter,
            Serverless: NewCloudServerlessAdapter,
        }
```

That's it! No need to create provider subclasses.

### Adding a New Resource Type

To add a new resource type (e.g., Database):

1. Create resource class:
```python
class Database(Resource):
    def __init__(self, db_name: str, provider: Provider, config=None):
        super().__init__(provider, config)
        self.db_name = db_name
```

2. Add registry method to Provider:
```python
def database(self, db_name: str, config=None) -> Database:
    db = Database(db_name, provider=self, config=config)
    self._resources.append(db)
    return db
```

3. Create adapters for each cloud:
```python
class RdsDatabaseAdapter(Adapter): ...
class AzureSqlAdapter(Adapter): ...
class CloudSqlAdapter(Adapter): ...
```

4. Register adapters in adapter registry.

### Adding a New Executor Config

To add support for a new executor platform:

```python
# 1. Create the config class
class EmrConfig(BaseModel):
    """Amazon EMR configuration."""
    instance_type: str
    num_instances: int
    emr_release: str = "emr-6.10.0"

# 2. Create the adapter
class EmrAdapter(Adapter):
    """Adapter for Amazon EMR."""
    def submit_job(self, job_definition: dict) -> str:
        # EMR-specific job submission
        pass

    def get_job_status(self, job_id: str) -> str:
        # EMR-specific status check
        pass

# 3. Register in Provider._get_executor_adapter()
# Add to the method:
elif isinstance(executor.config, EmrConfig):
    from glacier.adapters.aws import EmrAdapter
    return EmrAdapter(executor, self)

# That's it! No need to create new resource classes
```

## Comparison with Alternative Approaches

### Approach 1: Provider Inheritance (Current)

```python
# ❌ Current approach
provider = AWSProvider(region="us-east-1")  # Subclass
source = provider.bucket_source("data")  # Returns generic source
```

**Issues**:
- Provider hierarchy (AWSProvider, AzureProvider, etc.)
- Must create subclass for each cloud
- Configuration mixed with behavior

### Approach 2: Resource Inheritance

```python
# ❌ Resource inheritance approach
from glacier.resources.aws import S3Bucket
bucket = S3Bucket("my-bucket")  # Cloud-specific class
```

**Issues**:
- Pipeline code is not cloud-agnostic
- Must change imports when switching clouds
- Defeats the purpose of abstraction

### Approach 3: Factory Functions

```python
# ❌ Factory function approach
from glacier import create_bucket
bucket = create_bucket("s3", bucket="data", region="us-east-1")
```

**Issues**:
- String-based dispatch is error-prone
- No type safety
- Hard to track resources
- No clear namespace

### Approach 4: Proposed Design (V3)

```python
# ✅ Proposed design
provider = Provider(config=AwsConfig(region="us-east-1"))
bucket = provider.bucket("data", config=S3Config(versioning=True))
```

**Advantages**:
- Single Provider class
- Cloud-agnostic resources
- Configuration-based polymorphism
- Registry pattern for discoverability
- Dependency injection for testability
- Resources include execution environments

## Implementation Roadmap

### Phase 1: Core Refactoring
1. Create new Provider class (single, no subclasses)
2. Update Bucket to work with new Provider
3. Implement adapter registry pattern
4. Create AwsConfig, AzureConfig, GcpConfig, LocalConfig
5. Update adapters to use new pattern

### Phase 2: Resource Config System
1. Create S3Config, BlobConfig, GcsConfig
2. Create LambdaConfig, AzureFunctionConfig, CloudFunctionConfig
3. Update resources to accept config objects
4. Update adapters to use configs

### Phase 3: Execution Environments
1. Create ExecutionEnvironment resource
2. Add DatabricksConfig, GlueConfig, DataprocConfig
3. Implement execution environment adapters
4. Integrate with task executor system

### Phase 4: Examples and Documentation
1. Update all examples to use new design
2. Write migration guide from V2 to V3
3. Update README and documentation
4. Create comprehensive tutorials

### Phase 5: Infrastructure Generation
1. Update Terraform generator to work with new Provider
2. Generate configs for execution environments
3. Optimize infrastructure generation

## Testing Strategy

### Unit Tests
- Test Provider resource creation
- Test adapter selection logic
- Test each adapter independently
- Test config validation

### Integration Tests
- Test Provider with real cloud resources (sandboxed)
- Test resource operations (read/write)
- Test cross-cloud compatibility

### Example Tests
```python
def test_provider_bucket_creation():
    """Test that Provider creates Bucket with proper injection."""
    config = AwsConfig(region="us-east-1")
    provider = Provider(config=config)

    bucket = provider.bucket("test-bucket", path="data.parquet")

    assert isinstance(bucket, Bucket)
    assert bucket.provider is provider
    assert bucket in provider.get_resources()

def test_bucket_uses_correct_adapter():
    """Test that Bucket uses correct adapter based on provider config."""
    aws_provider = Provider(config=AwsConfig(region="us-east-1"))
    azure_provider = Provider(config=AzureConfig(resource_group="rg"))

    aws_bucket = aws_provider.bucket("test")
    azure_bucket = azure_provider.bucket("test")

    assert isinstance(aws_bucket._get_adapter(), S3BucketAdapter)
    assert isinstance(azure_bucket._get_adapter(), BlobStorageAdapter)

def test_config_optional():
    """Test that resource-specific config is optional."""
    provider = Provider(config=AwsConfig(region="us-east-1"))

    # Should work without config
    bucket = provider.bucket("test-bucket")
    assert bucket.config is None

    # Should work with config
    bucket_with_config = provider.bucket(
        "test-bucket",
        config=S3Config(versioning=True)
    )
    assert bucket_with_config.config.versioning is True
```

## Migration from V2

### V2 Code
```python
from glacier.providers import AWSProvider

provider = AWSProvider(region="us-east-1")
source = provider.bucket_source("my-data", path="file.parquet")
```

### V3 Code
```python
from glacier import Provider
from glacier.config import AwsConfig

provider = Provider(config=AwsConfig(region="us-east-1"))
bucket = provider.bucket("my-data", path="file.parquet")
```

### Breaking Changes
1. `AWSProvider` → `Provider(config=AwsConfig(...))`
2. `bucket_source()` → `bucket()` (more semantic)
3. Resources created directly need provider passed in

### Migration Script
We should provide a codemod or script to automate migration:

```python
# migration_script.py
# Automatically convert V2 to V3 code
```

## Conclusion

This design achieves true cloud-agnosticism through:

1. **Single Provider class** configured with cloud-specific configs
2. **Registry pattern** for resource creation (`provider.bucket()`)
3. **Dependency injection** of provider into resources
4. **Unified resource model** - single Bucket, Serverless, ExecutionEnvironment classes
5. **Configuration-based polymorphism** - behavior via configs, not subclasses
6. **Execution environments as resources** - consistent treatment of compute and storage

The result is a library where:
- Pipeline code is truly cloud-agnostic
- Adding new clouds requires minimal changes
- Resources are first-class citizens
- Dependencies are explicit
- Testing is straightforward
- Infrastructure generation is consistent

This architecture provides maximum flexibility while maintaining simplicity and type safety.
