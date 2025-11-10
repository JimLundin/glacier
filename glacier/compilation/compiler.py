"""
Compiler: Provider-agnostic pipeline compilation to Pulumi resources.

Handles multi-cloud pipelines where different tasks and datasets
may use different cloud providers (AWS, GCP, Azure).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from glacier.core.pipeline import Pipeline


@dataclass
class CompiledPipeline:
    """
    Represents a compiled pipeline with Pulumi resources.

    Contains actual Pulumi resource objects that have been registered
    with the Pulumi runtime. Supports multi-cloud pipelines.
    """

    pipeline_name: str
    resources: dict[str, object]
    metadata: dict[str, int | str] = field(default_factory=dict)

    def get_resource(self, name: str) -> object | None:
        """Get a specific Pulumi resource by name."""
        return self.resources.get(name)

    def get_resources_by_provider(self) -> dict[str, list[str]]:
        """Group resources by cloud provider."""
        by_provider: dict[str, list[str]] = {}
        for name, resource in self.resources.items():
            provider = self._infer_provider(resource)
            if provider not in by_provider:
                by_provider[provider] = []
            by_provider[provider].append(name)
        return by_provider

    def _infer_provider(self, resource: object) -> str:
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

    def export_outputs(self) -> dict[str, object]:
        """Create Pulumi stack outputs for all resources."""
        try:
            import pulumi
        except ImportError:
            raise ImportError("pulumi required for export_outputs()")

        outputs: dict[str, object] = {}
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
    """

    @abstractmethod
    def compile(self, pipeline: Pipeline) -> CompiledPipeline:
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
