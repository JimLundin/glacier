"""
Stack: Container for all infrastructure in a Glacier deployment.

A Stack tracks environments, pipelines, and resources across multiple
cloud providers. When deployed, it creates the compute and orchestration
infrastructure needed to run the pipelines.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, TypedDict

from glacier.core.environment import Environment, Provider
from glacier.core.pipeline import Pipeline

if TYPE_CHECKING:
    import pulumi


class StackMetadata(TypedDict, total=False):
    """Metadata about stack compilation."""
    environment_count: int
    pipeline_count: int
    resource_count: int


@dataclass
class Stack:
    """
    Container for all infrastructure in a deployment.

    The Stack is the compilation unit that tracks:
    - Environments (which create infrastructure resources)
    - Pipelines (which define compute logic)
    - Shared resources (databases, secrets, etc.)
    """

    name: str
    _environments: dict[str, Environment] = field(default_factory=dict, init=False)
    _pipelines: dict[str, Pipeline] = field(default_factory=dict, init=False)
    _resources: dict[str, pulumi.Resource] = field(default_factory=dict, init=False)

    def environment(
        self,
        provider: Provider,
        name: str,
        tags: dict[str, str] | None = None
    ) -> Environment:
        """Create an environment in this stack."""
        env = Environment(provider=provider, name=name, tags=tags)
        self._environments[name] = env
        return env

    def pipeline(self, name: str) -> Pipeline:
        """Create a pipeline in this stack."""
        pipeline = Pipeline(name=name)
        self._pipelines[name] = pipeline
        return pipeline

    def track_resource(self, name: str, resource: pulumi.Resource):
        """Track a shared resource in this stack."""
        self._resources[name] = resource

    def compile(self) -> CompiledStack:
        """
        Compile the stack to create compute and orchestration infrastructure.

        This creates:
        - Compute resources for tasks (Lambda, Cloud Functions, etc.)
        - IAM policies connecting tasks to storage/databases
        - Orchestration (EventBridge rules, Cloud Scheduler jobs)
        - Monitoring (CloudWatch, Cloud Logging)
        """
        from glacier.compilation.stack_compiler import StackCompiler

        compiler = StackCompiler()
        return compiler.compile(self)

    def get_environment(self, name: str) -> Environment | None:
        """Get environment by name."""
        return self._environments.get(name)

    def get_pipeline(self, name: str) -> Pipeline | None:
        """Get pipeline by name."""
        return self._pipelines.get(name)

    def get_resource(self, name: str) -> pulumi.Resource | None:
        """Get resource by name."""
        return self._resources.get(name)


@dataclass
class CompiledStack:
    """A compiled stack with all infrastructure resources."""

    stack_name: str
    resources: dict[str, pulumi.Resource]
    metadata: StackMetadata = field(default_factory=dict)

    def get_resource(self, name: str) -> pulumi.Resource | None:
        """Get a resource by name."""
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

    def _infer_provider(self, resource: pulumi.Resource) -> str:
        """Infer provider from Pulumi resource type."""
        resource_type = type(resource).__module__
        if 'pulumi_aws' in resource_type:
            return 'aws'
        elif 'pulumi_gcp' in resource_type:
            return 'gcp'
        elif 'pulumi_azure' in resource_type or 'pulumi_azure_native' in resource_type:
            return 'azure'
        return 'unknown'

    def export_outputs(self) -> dict[str, pulumi.Output]:
        """Create Pulumi stack outputs for all resources."""
        import pulumi

        outputs: dict[str, pulumi.Output] = {}
        for name, resource in self.resources.items():
            if hasattr(resource, 'id'):
                pulumi.export(name, resource.id)
                outputs[name] = resource.id
            elif hasattr(resource, 'arn'):
                pulumi.export(f"{name}_arn", resource.arn)
                outputs[f"{name}_arn"] = resource.arn

        return outputs
