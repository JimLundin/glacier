"""
PulumiCompiler: Base class for Pulumi-based compilers.

Provides common infrastructure for generating Pulumi programs
from Glacier pipelines.
"""

from abc import abstractmethod
from pathlib import Path
from typing import Any, TYPE_CHECKING
import json
import textwrap

from glacier.compilation.compiler import Compiler, CompiledPipeline, CompilationError

if TYPE_CHECKING:
    from glacier.core.pipeline import Pipeline
    from glacier.core.task import Task
    from glacier.core.dataset import Dataset


class PulumiCompiledPipeline(CompiledPipeline):
    """
    Compiled pipeline with Pulumi-specific export capabilities.
    """

    def __init__(
        self,
        pipeline_name: str,
        provider_name: str,
        resources: dict[str, Any],
        pulumi_program_code: str,
        pulumi_config: dict[str, Any],
        metadata: dict[str, Any] | None = None
    ):
        """
        Initialize Pulumi compiled pipeline.

        Args:
            pipeline_name: Name of the source pipeline
            provider_name: Cloud provider (aws, gcp, azure)
            resources: Dictionary of compiled infrastructure resources
            pulumi_program_code: Generated Python code for __main__.py
            pulumi_config: Configuration for Pulumi.yaml
            metadata: Optional metadata about compilation
        """
        super().__init__(pipeline_name, provider_name, resources, metadata)
        self.pulumi_program_code = pulumi_program_code
        self.pulumi_config = pulumi_config

    def export_pulumi(self, output_dir: str | Path) -> Path:
        """
        Export as Pulumi program.

        Creates:
        - output_dir/__main__.py: Pulumi program
        - output_dir/Pulumi.yaml: Pulumi project configuration
        - output_dir/requirements.txt: Python dependencies

        Args:
            output_dir: Directory to write Pulumi program files

        Returns:
            Path to the generated Pulumi program directory
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Write __main__.py
        main_file = output_path / "__main__.py"
        main_file.write_text(self.pulumi_program_code)

        # Write Pulumi.yaml
        pulumi_yaml = output_path / "Pulumi.yaml"
        pulumi_yaml.write_text(self._generate_pulumi_yaml())

        # Write requirements.txt
        requirements_file = output_path / "requirements.txt"
        requirements_file.write_text(self._generate_requirements())

        return output_path

    def _generate_pulumi_yaml(self) -> str:
        """Generate Pulumi.yaml content."""
        config = {
            "name": self.pulumi_config.get("project_name", self.pipeline_name),
            "runtime": "python",
            "description": self.pulumi_config.get(
                "description",
                f"Glacier pipeline: {self.pipeline_name}"
            ),
        }

        # Add backend configuration if specified
        if "backend" in self.pulumi_config:
            config["backend"] = self.pulumi_config["backend"]

        # Convert to YAML format (simple dict to YAML)
        yaml_lines = []
        for key, value in config.items():
            if isinstance(value, dict):
                yaml_lines.append(f"{key}:")
                for sub_key, sub_value in value.items():
                    yaml_lines.append(f"  {sub_key}: {sub_value}")
            else:
                yaml_lines.append(f"{key}: {value}")

        return "\n".join(yaml_lines) + "\n"

    def _generate_requirements(self) -> str:
        """Generate requirements.txt content."""
        deps = self.pulumi_config.get("dependencies", [])
        return "\n".join(deps) + "\n" if deps else ""


class PulumiCompiler(Compiler):
    """
    Base class for Pulumi-based compilers.

    Provides template methods for generating Pulumi programs from
    Glacier pipelines. Subclasses implement provider-specific logic.
    """

    def __init__(self, region: str | None = None, project_name: str | None = None):
        """
        Initialize Pulumi compiler.

        Args:
            region: Cloud region (e.g., "us-east-1", "us-central1")
            project_name: Optional Pulumi project name override
        """
        self.region = region
        self.project_name = project_name

    def compile(self, pipeline: 'Pipeline') -> PulumiCompiledPipeline:
        """
        Compile a pipeline to Pulumi infrastructure definitions.

        Args:
            pipeline: The pipeline to compile

        Returns:
            PulumiCompiledPipeline with infrastructure definitions

        Raises:
            CompilationError: If compilation fails
        """
        try:
            # Validate pipeline
            pipeline.validate()

            # Collect resources
            resources = {}

            # Compile storage resources (buckets, databases, etc.)
            storage_resources = self._compile_storage(pipeline)
            resources.update(storage_resources)

            # Compile compute resources (Lambda, Cloud Functions, etc.)
            compute_resources = self._compile_compute(pipeline)
            resources.update(compute_resources)

            # Compile scheduling resources (EventBridge, Cloud Scheduler, etc.)
            scheduling_resources = self._compile_scheduling(pipeline)
            resources.update(scheduling_resources)

            # Compile monitoring resources (CloudWatch, Cloud Logging, etc.)
            monitoring_resources = self._compile_monitoring(pipeline)
            resources.update(monitoring_resources)

            # Compile secrets resources (Secrets Manager, Secret Manager, etc.)
            secrets_resources = self._compile_secrets(pipeline)
            resources.update(secrets_resources)

            # Generate Pulumi program code
            program_code = self._generate_pulumi_program(pipeline, resources)

            # Generate Pulumi configuration
            pulumi_config = self._generate_pulumi_config(pipeline)

            return PulumiCompiledPipeline(
                pipeline_name=pipeline.name,
                provider_name=self.get_provider_name(),
                resources=resources,
                pulumi_program_code=program_code,
                pulumi_config=pulumi_config,
                metadata={
                    "region": self.region,
                    "task_count": len(pipeline.tasks),
                    "dataset_count": len(pipeline.datasets),
                }
            )

        except Exception as e:
            raise CompilationError(f"Failed to compile pipeline '{pipeline.name}': {e}") from e

    # =========================================================================
    # Template methods - Override in subclasses
    # =========================================================================

    @abstractmethod
    def _compile_storage(self, pipeline: 'Pipeline') -> dict[str, Any]:
        """
        Compile storage resources for the pipeline.

        Returns:
            Dictionary mapping resource names to Pulumi resource definitions
        """
        pass

    @abstractmethod
    def _compile_compute(self, pipeline: 'Pipeline') -> dict[str, Any]:
        """
        Compile compute resources for the pipeline tasks.

        Returns:
            Dictionary mapping resource names to Pulumi resource definitions
        """
        pass

    @abstractmethod
    def _compile_scheduling(self, pipeline: 'Pipeline') -> dict[str, Any]:
        """
        Compile scheduling resources (cron, events, triggers).

        Returns:
            Dictionary mapping resource names to Pulumi resource definitions
        """
        pass

    @abstractmethod
    def _compile_monitoring(self, pipeline: 'Pipeline') -> dict[str, Any]:
        """
        Compile monitoring resources (logging, metrics, alerts).

        Returns:
            Dictionary mapping resource names to Pulumi resource definitions
        """
        pass

    @abstractmethod
    def _compile_secrets(self, pipeline: 'Pipeline') -> dict[str, Any]:
        """
        Compile secrets resources.

        Returns:
            Dictionary mapping resource names to Pulumi resource definitions
        """
        pass

    @abstractmethod
    def _generate_resource_code(self, resource_name: str, resource_def: Any) -> str:
        """
        Generate Pulumi Python code for a specific resource.

        Args:
            resource_name: Name of the resource
            resource_def: Resource definition

        Returns:
            Python code string that creates the resource
        """
        pass

    def _generate_pulumi_program(self, pipeline: 'Pipeline', resources: dict[str, Any]) -> str:
        """
        Generate complete Pulumi program code (__main__.py).

        Args:
            pipeline: Source pipeline
            resources: Compiled resources

        Returns:
            Python code for __main__.py
        """
        imports = self._generate_imports()
        resource_code = []

        for resource_name, resource_def in resources.items():
            code = self._generate_resource_code(resource_name, resource_def)
            resource_code.append(code)

        exports = self._generate_exports(resources)

        program = f'''"""
Generated Pulumi program for Glacier pipeline: {pipeline.name}

Provider: {self.get_provider_name()}
Generated by: glacier.compilation.PulumiCompiler
"""

{imports}

# Pipeline: {pipeline.name}
# Tasks: {len(pipeline.tasks)}
# Datasets: {len(pipeline.datasets)}

{chr(10).join(resource_code)}

# Exports
{exports}
'''
        return program

    def _generate_imports(self) -> str:
        """
        Generate import statements for Pulumi program.

        Override in subclasses to add provider-specific imports.
        """
        return "import pulumi"

    def _generate_exports(self, resources: dict[str, Any]) -> str:
        """
        Generate Pulumi exports for stack outputs.

        Args:
            resources: Compiled resources

        Returns:
            Python code for pulumi.export() calls
        """
        exports = []
        for resource_name in resources.keys():
            # Convert to valid Python identifier for variable name
            var_name = resource_name.replace("-", "_")
            exports.append(f'pulumi.export("{resource_name}", {var_name}.id)')
        return "\n".join(exports) if exports else "# No exports"

    def _generate_pulumi_config(self, pipeline: 'Pipeline') -> dict[str, Any]:
        """
        Generate Pulumi.yaml configuration.

        Args:
            pipeline: Source pipeline

        Returns:
            Dictionary with Pulumi configuration
        """
        project_name = self.project_name or f"glacier-{pipeline.name}"

        return {
            "project_name": project_name,
            "description": f"Glacier pipeline: {pipeline.name}",
            "dependencies": self._get_pulumi_dependencies(),
        }

    @abstractmethod
    def _get_pulumi_dependencies(self) -> list[str]:
        """
        Get list of Python dependencies for Pulumi program.

        Returns:
            List of pip package requirements
        """
        pass
