"""
Pulumi Escape Hatch: Use raw Pulumi resources directly.

This module provides wrappers that allow users to pass Pulumi resources
directly into Glacier pipelines when they need full Pulumi power.

The pattern: Simple abstractions for common cases, full Pulumi for edge cases.
"""

from typing import Any, Optional, Dict
from glacier.storage.resources import StorageResource
from glacier.compute.resources import ComputeResource


class PulumiResource:
    """
    Wrapper for raw Pulumi resources.

    This is the escape hatch - when Glacier's abstractions aren't enough,
    drop down to raw Pulumi.

    Example:
        import pulumi_aws as aws

        # Raw Pulumi resource
        pulumi_bucket = aws.s3.BucketV2(
            "my-bucket",
            bucket="my-complex-bucket",
            # Use any Pulumi feature!
            server_side_encryption_configuration=aws.s3.BucketServerSideEncryptionConfigurationArgs(
                rule=aws.s3.BucketServerSideEncryptionConfigurationRuleArgs(
                    apply_server_side_encryption_by_default=aws.s3.BucketServerSideEncryptionConfigurationRuleApplyServerSideEncryptionByDefaultArgs(
                        sse_algorithm="aws:kms",
                        kms_master_key_id=key.arn,
                    ),
                ),
            ),
        )

        # Use in Glacier
        data = Dataset("data", storage=PulumiResource(pulumi_bucket, provider="aws"))
    """

    def __init__(self, pulumi_resource: Any, provider: str, resource_type: str = "custom"):
        """
        Wrap a Pulumi resource for use in Glacier.

        Args:
            pulumi_resource: The Pulumi resource object
            provider: Provider name ("aws", "gcp", "azure")
            resource_type: Generic type hint ("object_storage", "database", etc.)
        """
        self.pulumi_resource = pulumi_resource
        self.provider = provider
        self.resource_type = resource_type

    def __repr__(self):
        return f"PulumiResource({type(self.pulumi_resource).__name__}, provider={self.provider})"


class PulumiStorageResource(StorageResource):
    """
    Storage resource that wraps a Pulumi resource.

    This allows using raw Pulumi resources as Glacier storage.
    """

    def __init__(
        self,
        pulumi_resource: Any,
        provider: str,
        storage_type: str = "object_storage",
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Create a storage resource from a Pulumi resource.

        Args:
            pulumi_resource: The Pulumi resource (e.g., aws.s3.BucketV2)
            provider: Provider name ("aws", "gcp", "azure")
            storage_type: Storage type ("object_storage", "database", etc.)
            metadata: Optional metadata about the resource
        """
        self.pulumi_resource = pulumi_resource
        self.provider_name = provider
        self.storage_type = storage_type
        self.metadata = metadata or {}

    def get_type(self) -> str:
        return self.storage_type

    def get_provider(self) -> Optional[str]:
        return self.provider_name

    def supports_provider(self, provider: str) -> bool:
        return provider == self.provider_name

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.storage_type,
            "provider": self.provider_name,
            "pulumi_resource": {
                "type": type(self.pulumi_resource).__name__,
                "name": getattr(self.pulumi_resource, "_name", "unknown"),
            },
            "metadata": self.metadata,
        }

    def __repr__(self):
        return f"PulumiStorage({type(self.pulumi_resource).__name__}, {self.provider_name})"


class PulumiComputeResource(ComputeResource):
    """
    Compute resource that wraps a Pulumi resource.

    This allows using raw Pulumi resources as Glacier compute.
    """

    def __init__(
        self,
        pulumi_resource: Any,
        provider: str,
        compute_type: str = "custom",
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Create a compute resource from a Pulumi resource.

        Args:
            pulumi_resource: The Pulumi resource (e.g., aws.lambda_.Function)
            provider: Provider name ("aws", "gcp", "azure")
            compute_type: Compute type ("serverless", "container", etc.)
            metadata: Optional metadata about the resource
        """
        self.pulumi_resource = pulumi_resource
        self.provider_name = provider
        self.compute_type = compute_type
        self.metadata = metadata or {}

    def get_type(self) -> str:
        return self.compute_type

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.compute_type,
            "provider": self.provider_name,
            "pulumi_resource": {
                "type": type(self.pulumi_resource).__name__,
                "name": getattr(self.pulumi_resource, "_name", "unknown"),
            },
            "metadata": self.metadata,
        }

    def __repr__(self):
        return f"PulumiCompute({type(self.pulumi_resource).__name__}, {self.provider_name})"


# Convenience functions for common Pulumi resources

def pulumi_s3_bucket(bucket: Any) -> PulumiStorageResource:
    """
    Wrap a Pulumi S3 bucket for use in Glacier.

    Args:
        bucket: pulumi_aws.s3.BucketV2 instance

    Returns:
        PulumiStorageResource wrapping the bucket
    """
    return PulumiStorageResource(
        pulumi_resource=bucket,
        provider="aws",
        storage_type="object_storage",
        metadata={"service": "s3"}
    )


def pulumi_gcs_bucket(bucket: Any) -> PulumiStorageResource:
    """
    Wrap a Pulumi GCS bucket for use in Glacier.

    Args:
        bucket: pulumi_gcp.storage.Bucket instance

    Returns:
        PulumiStorageResource wrapping the bucket
    """
    return PulumiStorageResource(
        pulumi_resource=bucket,
        provider="gcp",
        storage_type="object_storage",
        metadata={"service": "gcs"}
    )


def pulumi_lambda(function: Any) -> PulumiComputeResource:
    """
    Wrap a Pulumi Lambda function for use in Glacier.

    Args:
        function: pulumi_aws.lambda_.Function instance

    Returns:
        PulumiComputeResource wrapping the function
    """
    return PulumiComputeResource(
        pulumi_resource=function,
        provider="aws",
        compute_type="serverless",
        metadata={"service": "lambda"}
    )


def pulumi_cloud_function(function: Any) -> PulumiComputeResource:
    """
    Wrap a Pulumi Cloud Function for use in Glacier.

    Args:
        function: pulumi_gcp.cloudfunctions.Function instance

    Returns:
        PulumiComputeResource wrapping the function
    """
    return PulumiComputeResource(
        pulumi_resource=function,
        provider="gcp",
        compute_type="serverless",
        metadata={"service": "cloud_functions"}
    )
