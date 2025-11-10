"""
Compiler: Abstract interface for pipeline compilation.

Compilers are provider-specific plugins that transform Glacier pipelines
into deployable infrastructure definitions (Pulumi, Terraform, etc.).
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
    with the Pulumi runtime.
    """

    def __init__(
        self,
        pipeline_name: str,
        provider_name: str,
        resources: dict[str, Any],
        metadata: dict[str, Any] | None = None
    ):
        """
        Initialize compiled pipeline.

        Args:
            pipeline_name: Name of the source pipeline
            provider_name: Cloud provider (aws, gcp, azure)
            resources: Dictionary of Pulumi resource objects
            metadata: Optional metadata about compilation
        """
        self.pipeline_name = pipeline_name
        self.provider_name = provider_name
        self.resources = resources
        self.metadata = metadata or {}

    def get_resource(self, name: str) -> Any:
        """Get a specific Pulumi resource by name."""
        return self.resources.get(name)

    def list_resources(self) -> list[str]:
        """List all resource names."""
        return list(self.resources.keys())

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

    Provider-specific compilers implement this interface to transform
    Glacier pipelines into deployable infrastructure.

    The compiler is responsible for:
    1. Analyzing the pipeline DAG and resources
    2. Generating cloud-specific infrastructure definitions
    3. Configuring networking, IAM, and security
    4. Creating deployment artifacts (Pulumi programs, etc.)
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

    @abstractmethod
    def get_provider_name(self) -> str:
        """
        Get the provider name for this compiler.

        Returns:
            Provider name (e.g., "aws", "gcp", "azure")
        """
        pass


class CompilationError(Exception):
    """Raised when pipeline compilation fails."""
    pass
