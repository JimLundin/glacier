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
    Represents a compiled pipeline ready for deployment.

    Contains infrastructure definitions and deployment artifacts
    generated from a Glacier pipeline.
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
            resources: Dictionary of compiled infrastructure resources
            metadata: Optional metadata about compilation
        """
        self.pipeline_name = pipeline_name
        self.provider_name = provider_name
        self.resources = resources
        self.metadata = metadata or {}

    def export_pulumi(self, output_dir: str | Path) -> Path:
        """
        Export as Pulumi program.

        Args:
            output_dir: Directory to write Pulumi program files

        Returns:
            Path to the generated Pulumi program directory
        """
        raise NotImplementedError("Subclass must implement export_pulumi()")

    def get_resource(self, name: str) -> Any:
        """Get a specific compiled resource by name."""
        return self.resources.get(name)

    def list_resources(self) -> list[str]:
        """List all compiled resource names."""
        return list(self.resources.keys())


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
