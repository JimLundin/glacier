"""
Compiler: Abstract interface for pipeline compilation.

Compilers are provider-specific plugins that transform abstract
Glacier pipelines into concrete infrastructure definitions.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, TYPE_CHECKING
from dataclasses import dataclass, field

if TYPE_CHECKING:
    from glacier.core.pipeline import Pipeline


@dataclass
class CompilationContext:
    """
    Context provided during compilation.

    This contains provider-specific configuration and defaults
    that the compiler uses to generate infrastructure.
    """

    provider: str
    """Provider name: 'aws', 'gcp', 'azure', etc."""

    region: str
    """Primary region/location for resources"""

    project_id: Optional[str] = None
    """Project/account ID (required for some providers)"""

    naming_prefix: str = ""
    """Prefix for generated resource names"""

    tags: Dict[str, str] = field(default_factory=dict)
    """Tags/labels to apply to all resources"""

    defaults: Dict[str, Any] = field(default_factory=dict)
    """Provider-specific defaults for resources"""

    vpc_config: Optional[Dict[str, Any]] = None
    """VPC/network configuration"""

    iam_config: Optional[Dict[str, Any]] = None
    """IAM/permissions configuration"""

    def generate_name(self, base_name: str, resource_type: str = "") -> str:
        """
        Generate a resource name following naming conventions.

        Args:
            base_name: Base name for the resource
            resource_type: Optional resource type suffix

        Returns:
            Generated resource name
        """
        parts = [p for p in [self.naming_prefix, base_name, resource_type] if p]
        return "-".join(parts)


class Compiler(ABC):
    """
    Abstract compiler interface.

    Provider-specific compilers implement this interface to transform
    Glacier pipelines into infrastructure-as-code using Pulumi.

    The compiler is responsible for:
    1. Validating resource compatibility with the target provider
    2. Mapping abstract resources to provider-specific resources
    3. Generating IAM/permissions policies
    4. Generating networking configuration
    5. Producing Pulumi code
    """

    @abstractmethod
    def compile(self, pipeline: 'Pipeline') -> 'CompiledPipeline':
        """
        Compile a pipeline to infrastructure definition.

        Args:
            pipeline: The pipeline to compile

        Returns:
            Compiled pipeline with Pulumi resources

        Raises:
            ValueError: If pipeline contains incompatible resources
        """
        pass

    @abstractmethod
    def validate_resource(self, resource: Any) -> None:
        """
        Validate that a resource is compatible with this provider.

        Args:
            resource: Storage or compute resource to validate

        Raises:
            ValueError: If resource is incompatible with this provider
        """
        pass

    @abstractmethod
    def get_capabilities(self) -> Dict[str, Any]:
        """
        Get provider capabilities and limitations.

        Returns:
            Dictionary describing provider capabilities

        Example:
            {
                "serverless": {
                    "max_timeout": 900,
                    "max_memory": 10240,
                    "supports_gpu": False
                },
                "object_storage": {
                    "service": "s3",
                    "storage_classes": ["STANDARD", "GLACIER"]
                }
            }
        """
        pass

    @abstractmethod
    def get_context(self) -> CompilationContext:
        """
        Get the compilation context for this compiler.

        Returns:
            Compilation context
        """
        pass


class CompiledPipeline(ABC):
    """
    Abstract compiled pipeline.

    Represents a pipeline that has been compiled to infrastructure-as-code.
    Provider-specific implementations generate Pulumi code.
    """

    @abstractmethod
    def export_pulumi(self, output_dir: str, project_name: Optional[str] = None) -> None:
        """
        Export as Pulumi project.

        Generates a complete Pulumi project structure with:
        - __main__.py with resource definitions
        - Pulumi.yaml with project configuration
        - requirements.txt with dependencies

        Args:
            output_dir: Directory to write Pulumi project
            project_name: Optional project name (defaults to pipeline name)
        """
        pass

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """
        Export as dictionary.

        Returns:
            Dictionary representation of compiled infrastructure
        """
        pass

    @abstractmethod
    def get_resources(self) -> Dict[str, Any]:
        """
        Get all Pulumi resources.

        Returns:
            Dictionary mapping resource names to Pulumi resource objects
        """
        pass

    @abstractmethod
    def get_outputs(self) -> Dict[str, Any]:
        """
        Get pipeline outputs.

        Returns:
            Dictionary of output values (e.g., bucket ARNs, function names)
        """
        pass
