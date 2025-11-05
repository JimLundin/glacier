"""
Tests for cloud-agnostic resource abstractions.

These tests verify that the provider factory pattern works correctly
and that Bucket and Serverless resources are truly cloud-agnostic.
"""

import pytest
from glacier.providers import AWSProvider, AzureProvider, GCPProvider, LocalProvider
from glacier.resources import Bucket, Serverless
from glacier.config import S3Config, AzureBlobConfig, GCSConfig, LambdaConfig


class TestProviderFactoryPattern:
    """Test that providers correctly create cloud-agnostic resources."""

    def test_aws_provider_creates_generic_bucket(self):
        """AWS provider should create generic Bucket, not S3Source."""
        provider = AWSProvider(region="us-east-1")
        bucket = provider.bucket("my-bucket", path="data.parquet")

        assert isinstance(bucket, Bucket)
        assert bucket.bucket_name == "my-bucket"
        assert bucket.path == "data.parquet"
        assert bucket.provider == provider

    def test_azure_provider_creates_generic_bucket(self):
        """Azure provider should create generic Bucket."""
        provider = AzureProvider(resource_group="my-rg", location="eastus")
        bucket = provider.bucket("my-container", path="data.parquet")

        assert isinstance(bucket, Bucket)
        assert bucket.bucket_name == "my-container"
        assert bucket.provider == provider

    def test_gcp_provider_creates_generic_bucket(self):
        """GCP provider should create generic Bucket."""
        provider = GCPProvider(project_id="my-project", region="us-central1")
        bucket = provider.bucket("my-bucket", path="data.parquet")

        assert isinstance(bucket, Bucket)
        assert bucket.bucket_name == "my-bucket"
        assert bucket.provider == provider

    def test_local_provider_creates_generic_bucket(self):
        """Local provider should create generic Bucket."""
        provider = LocalProvider(base_path="./data")
        bucket = provider.bucket("my-dir", path="data.parquet")

        assert isinstance(bucket, Bucket)
        assert bucket.bucket_name == "my-dir"
        assert bucket.provider == provider

    def test_bucket_with_provider_specific_config(self):
        """Test passing provider-specific config to bucket."""
        provider = AWSProvider(region="us-east-1")
        config = S3Config(
            versioning=True,
            encryption="AES256",
            storage_class="INTELLIGENT_TIERING",
        )
        bucket = provider.bucket(
            "my-bucket", path="data.parquet", config=config
        )

        assert isinstance(bucket, Bucket)
        assert bucket.config == config
        assert bucket.config.versioning is True
        assert bucket.config.encryption == "AES256"

    def test_aws_provider_creates_serverless(self):
        """AWS provider should create generic Serverless."""
        provider = AWSProvider(region="us-east-1")
        func = provider.serverless("my-function", runtime="python3.11")

        assert isinstance(func, Serverless)
        assert func.function_name == "my-function"
        assert func.runtime == "python3.11"
        assert func.provider == provider

    def test_serverless_with_provider_specific_config(self):
        """Test passing provider-specific config to serverless."""
        provider = AWSProvider(region="us-east-1")
        config = LambdaConfig(memory=1024, timeout=300)
        func = provider.serverless(
            "my-function", runtime="python3.11", config=config
        )

        assert isinstance(func, Serverless)
        assert func.config == config
        assert func.config.memory == 1024
        assert func.config.timeout == 300


class TestBucketCloudAgnostic:
    """Test that Bucket works the same across all providers."""

    @pytest.fixture
    def providers(self):
        """Create all providers for testing."""
        return {
            "aws": AWSProvider(region="us-east-1"),
            "azure": AzureProvider(resource_group="my-rg", location="eastus"),
            "gcp": GCPProvider(project_id="my-project", region="us-central1"),
            "local": LocalProvider(base_path="./data"),
        }

    def test_bucket_interface_consistent_across_providers(self, providers):
        """All providers should create Buckets with the same interface."""
        for provider_name, provider in providers.items():
            bucket = provider.bucket("test-bucket", path="data.parquet")

            # All should be Bucket instances
            assert isinstance(bucket, Bucket)

            # All should have the same attributes
            assert hasattr(bucket, "bucket_name")
            assert hasattr(bucket, "path")
            assert hasattr(bucket, "format")
            assert hasattr(bucket, "provider")

            # All should have the same methods
            assert hasattr(bucket, "scan")
            assert hasattr(bucket, "read")
            assert hasattr(bucket, "get_uri")
            assert hasattr(bucket, "get_metadata")

    def test_bucket_path_normalization_consistent(self, providers):
        """Path normalization should work the same across all providers."""
        for provider in providers.values():
            bucket = provider.bucket("test", path="/leading/slash/path.parquet")

            # Leading slash should be removed
            assert bucket.path == "leading/slash/path.parquet"

    def test_bucket_format_normalization_consistent(self, providers):
        """Format normalization should work the same across all providers."""
        for provider in providers.values():
            bucket = provider.bucket("test", path="data.CSV", format="CSV")

            # Format should be lowercase
            assert bucket.format == "csv"


class TestBucketAdapters:
    """Test that bucket adapters are correctly selected."""

    def test_aws_bucket_uses_s3_adapter(self):
        """AWS buckets should use S3BucketAdapter."""
        provider = AWSProvider(region="us-east-1")
        bucket = provider.bucket("test", path="data.parquet")

        # Get adapter (triggers lazy initialization)
        adapter = bucket._get_adapter()

        from glacier.adapters.bucket import S3BucketAdapter

        assert isinstance(adapter, S3BucketAdapter)

    def test_azure_bucket_uses_blob_adapter(self):
        """Azure buckets should use AzureBlobAdapter."""
        provider = AzureProvider(resource_group="my-rg", location="eastus")
        bucket = provider.bucket("test", path="data.parquet")

        adapter = bucket._get_adapter()

        from glacier.adapters.bucket import AzureBlobAdapter

        assert isinstance(adapter, AzureBlobAdapter)

    def test_gcp_bucket_uses_gcs_adapter(self):
        """GCP buckets should use GCSBucketAdapter."""
        provider = GCPProvider(project_id="my-project")
        bucket = provider.bucket("test", path="data.parquet")

        adapter = bucket._get_adapter()

        from glacier.adapters.bucket import GCSBucketAdapter

        assert isinstance(adapter, GCSBucketAdapter)

    def test_local_bucket_uses_local_adapter(self):
        """Local buckets should use LocalBucketAdapter."""
        provider = LocalProvider()
        bucket = provider.bucket("test", path="data.parquet")

        adapter = bucket._get_adapter()

        from glacier.adapters.bucket import LocalBucketAdapter

        assert isinstance(adapter, LocalBucketAdapter)


class TestBucketURIs:
    """Test that bucket URIs are correctly generated."""

    def test_s3_uri(self):
        """Test S3 URI generation."""
        provider = AWSProvider(region="us-east-1")
        bucket = provider.bucket("my-bucket", path="data/file.parquet")

        assert bucket.get_uri() == "s3://my-bucket/data/file.parquet"

    def test_gcs_uri(self):
        """Test GCS URI generation."""
        provider = GCPProvider(project_id="my-project")
        bucket = provider.bucket("my-bucket", path="data/file.parquet")

        assert bucket.get_uri() == "gs://my-bucket/data/file.parquet"

    def test_local_uri(self):
        """Test local filesystem path generation."""
        provider = LocalProvider(base_path="./data")
        bucket = provider.bucket("my-dir", path="file.parquet")

        uri = bucket.get_uri()
        # Should be a file path (not necessarily with file:// prefix)
        assert "file.parquet" in uri


class TestProviderSpecificConfigs:
    """Test provider-specific configuration classes."""

    def test_s3_config(self):
        """Test S3Config with all options."""
        config = S3Config(
            versioning=True,
            encryption="AES256",
            storage_class="GLACIER",
            acceleration=True,
        )

        assert config.versioning is True
        assert config.encryption == "AES256"
        assert config.storage_class == "GLACIER"
        assert config.acceleration is True

    def test_azure_blob_config(self):
        """Test AzureBlobConfig with all options."""
        config = AzureBlobConfig(
            tier="Cool",
            replication_type="GRS",
            versioning=True,
        )

        assert config.tier == "Cool"
        assert config.replication_type == "GRS"
        assert config.versioning is True

    def test_gcs_config(self):
        """Test GCSConfig with all options."""
        config = GCSConfig(
            storage_class="NEARLINE",
            versioning=True,
            uniform_bucket_level_access=True,
        )

        assert config.storage_class == "NEARLINE"
        assert config.versioning is True
        assert config.uniform_bucket_level_access is True

    def test_lambda_config(self):
        """Test LambdaConfig with all options."""
        config = LambdaConfig(
            memory=1024,
            timeout=300,
            runtime="python3.11",
            architecture="arm64",
        )

        assert config.memory == 1024
        assert config.timeout == 300
        assert config.runtime == "python3.11"
        assert config.architecture == "arm64"
