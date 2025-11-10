"""
Compiler: Provider-agnostic pipeline compilation to Pulumi resources.

Handles multi-cloud pipelines where different tasks and datasets
may use different cloud providers (AWS, GCP, Azure).
"""

from abc import ABC, abstractmethod
from typing import Any, TYPE_CHECKING
from pathlib import Path

if TYPE_CHECKING:
    from glacier.core.pipeline import Pipeline


class CompiledPipeline:
    """
    Represents a compiled pipeline with Pulumi resources.

    Contains actual Pulumi resource objects that have been registered
    with the Pulumi runtime. Supports multi-cloud pipelines.
    """

    def __init__(
        self,
        pipeline_name: str,
        resources: dict[str, Any],
        metadata: dict[str, Any] | None = None
    ):
        """
        Initialize compiled pipeline.

        Args:
            pipeline_name: Name of the source pipeline
            resources: Dictionary of Pulumi resource objects (multi-cloud)
            metadata: Optional metadata about compilation
        """
        self.pipeline_name = pipeline_name
        self.resources = resources
        self.metadata = metadata or {}

    def get_resource(self, name: str) -> Any:
        """Get a specific Pulumi resource by name."""
        return self.resources.get(name)

    def list_resources(self) -> list[str]:
        """List all resource names."""
        return list(self.resources.keys())

    def get_resources_by_provider(self) -> dict[str, list[str]]:
        """
        Group resources by cloud provider.

        Returns:
            Dictionary mapping provider names to lists of resource names
        """
        by_provider = {}
        for name, resource in self.resources.items():
            provider = self._infer_provider(resource)
            if provider not in by_provider:
                by_provider[provider] = []
            by_provider[provider].append(name)
        return by_provider

    def _infer_provider(self, resource: Any) -> str:
        """Infer provider from Pulumi resource type."""
        resource_type = type(resource).__module__
        if 'pulumi_aws' in resource_type:
            return 'aws'
        elif 'pulumi_gcp' in resource_type:
            return 'gcp'
        elif 'pulumi_azure' in resource_type or 'pulumi_azure_native' in resource_type:
            return 'azure'
        else:
            return 'unknown'

    def export_outputs(self) -> dict[str, Any]:
        """
        Create Pulumi stack outputs for all resources.

        Returns:
            Dictionary of outputs
        """
        try:
            import pulumi
        except ImportError:
            raise ImportError("pulumi required for export_outputs()")

        outputs = {}
        for name, resource in self.resources.items():
            if hasattr(resource, 'id'):
                pulumi.export(name, resource.id)
                outputs[name] = resource.id
            elif hasattr(resource, 'arn'):
                pulumi.export(f"{name}_arn", resource.arn)
                outputs[f"{name}_arn"] = resource.arn

        return outputs


class Compiler(ABC):
    """
    Abstract compiler interface.

    Provider-agnostic compilers implement this interface to transform
    Glacier pipelines into deployable infrastructure across multiple clouds.

    The compiler is responsible for:
    1. Analyzing the pipeline DAG and resources
    2. Determining which provider each resource uses
    3. Creating cloud-specific compute resources (Lambda, Cloud Functions, etc.)
    4. Setting up cross-cloud IAM and networking
    5. Wiring together the infrastructure
    """

    @abstractmethod
    def compile(self, pipeline: 'Pipeline') -> CompiledPipeline:
        """
        Compile a pipeline to infrastructure definitions.

        Args:
            pipeline: The pipeline to compile

        Returns:
            CompiledPipeline with infrastructure definitions

        Raises:
            CompilationError: If compilation fails
        """
        pass


class CompilationError(Exception):
    """Raised when pipeline compilation fails."""
    pass
