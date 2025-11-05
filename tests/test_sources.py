"""
Tests for Glacier source abstractions.
"""

import pytest
from pathlib import Path
from glacier.sources import S3Source, LocalSource, BucketSource


class TestS3Source:
    """Tests for S3Source."""

    def test_initialization(self):
        """Test S3Source can be initialized."""
        source = S3Source(bucket="test-bucket", path="data/file.parquet", region="us-east-1")

        assert source.bucket == "test-bucket"
        assert source.path == "data/file.parquet"
        assert source.region == "us-east-1"
        assert source.format == "parquet"

    def test_uri_generation(self):
        """Test S3 URI is correctly generated."""
        source = S3Source(bucket="my-bucket", path="folder/data.parquet")

        assert source.get_uri() == "s3://my-bucket/folder/data.parquet"

    def test_metadata(self):
        """Test metadata is correctly generated."""
        source = S3Source(
            bucket="analytics-data", path="sales/2024.parquet", region="us-west-2"
        )

        metadata = source.get_metadata()

        assert metadata.source_type == "s3"
        assert metadata.cloud_provider == "aws"
        assert metadata.region == "us-west-2"
        assert metadata.resource_name == "analytics-data"

    def test_path_normalization(self):
        """Test paths are normalized (leading slashes removed)."""
        source = S3Source(bucket="test", path="/data/file.parquet")

        assert source.path == "data/file.parquet"
        assert source.get_uri() == "s3://test/data/file.parquet"


class TestLocalSource:
    """Tests for LocalSource."""

    def test_initialization(self):
        """Test LocalSource can be initialized."""
        source = LocalSource(bucket="./data", path="sample.parquet")

        assert source.bucket == "./data"
        assert source.path == "sample.parquet"
        assert source.format == "parquet"

    def test_uri_generation(self):
        """Test file:// URI is correctly generated."""
        source = LocalSource(bucket="/tmp/data", path="file.parquet")

        uri = source.get_uri()
        assert uri.startswith("file://")
        assert "file.parquet" in uri

    def test_metadata(self):
        """Test metadata for local sources."""
        source = LocalSource(bucket="./data", path="test.parquet")

        metadata = source.get_metadata()

        assert metadata.source_type == "local"
        assert metadata.cloud_provider is None
        assert metadata.region is None

    def test_file_path_construction(self):
        """Test file path is correctly constructed."""
        source = LocalSource(bucket="./examples/data", path="sample.parquet")

        file_path = source.get_file_path()
        assert isinstance(file_path, Path)
        assert file_path.name == "sample.parquet"


class TestBucketSourceAbstraction:
    """Tests for BucketSource abstraction."""

    def test_format_normalization(self):
        """Test format is normalized to lowercase."""
        source = S3Source(bucket="test", path="data.csv", format="CSV")

        assert source.format == "csv"

    def test_full_path(self):
        """Test full path construction."""
        source = S3Source(bucket="my-bucket", path="data/file.parquet")

        assert source.get_full_path() == "my-bucket/data/file.parquet"
