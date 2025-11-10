"""
Stack: Container for all infrastructure in a Glacier deployment.

A Stack tracks environments, pipelines, and resources across multiple
cloud providers. When deployed, it creates the compute and orchestration
infrastructure needed to run the pipelines.
"""

from typing import Any
from dataclasses import dataclass, field

from glacier.core.environment import Environment, Provider
from glacier.core.pipeline import Pipeline


@dataclass
class Stack:
    """
    Container for all infrastructure in a deployment.

    The Stack is the top-level organizational unit that tracks:
    - Environments (which create infrastructure resources)
    - Pipelines (which define compute logic)
    - Shared resources (databases, secrets, etc.)

    Resources created via environments (object_storage, database, etc.)
    are Pulumi resources created immediately. Stack compilation creates
    the compute infrastructure (Lambda, Cloud Functions) and wiring
    (IAM, triggers, orchestration) needed to run the pipelines.

    Example:
        from glacier import Stack
        from glacier_aws import AWSProvider

        # Create stack
        stack = Stack(name="my-deployment")

        # Add environments (creates infrastructure resources)
        aws_env = stack.environment(
            provider=AWSProvider(account="...", region="us-east-1"),
            name="aws-prod"
        )

        # Resources created immediately (Pulumi resources)
        db = aws_env.database("analytics")
        storage = aws_env.object_storage("raw-data")

        # Add pipelines (defines compute logic)
        pipeline = stack.pipeline(name="etl")

        @pipeline.task()
        def extract() -> raw:
            return data

        # Deploy - creates compute and wiring
        stack.deploy()  # or just run as Pulumi program
    """

    name: str
    """Stack name"""

    _environments: dict[str, Environment] = field(default_factory=dict)
    """Environments in this stack"""

    _pipelines: dict[str, Pipeline] = field(default_factory=dict)
    """Pipelines in this stack"""

    _resources: dict[str, Any] = field(default_factory=dict)
    """Shared resources (databases, secrets, etc.)"""

    def environment(
        self,
        provider: Provider,
        name: str,
        tags: dict[str, str] | None = None
    ) -> Environment:
        """
        Create an environment in this stack.

        Resources created via the environment (object_storage, database, etc.)
        are Pulumi resources created immediately.

        Args:
            provider: Cloud provider implementation
            name: Environment name
            tags: Optional tags for all resources

        Returns:
            Environment instance

        Example:
            aws_env = stack.environment(
                provider=AWSProvider(account="123", region="us-east-1"),
                name="aws-prod"
            )

            # This creates a Pulumi S3 bucket immediately
            bucket = aws_env.object_storage("data")
        """
        env = Environment(provider=provider, name=name, tags=tags)
        self._environments[name] = env
        return env

    def pipeline(self, name: str) -> Pipeline:
        """
        Create a pipeline in this stack.

        Args:
            name: Pipeline name

        Returns:
            Pipeline instance

        Example:
            pipeline = stack.pipeline(name="etl")

            @pipeline.task()
            def extract() -> raw:
                return data
        """
        pipeline = Pipeline(name=name)
        self._pipelines[name] = pipeline
        return pipeline

    def track_resource(self, name: str, resource: Any):
        """
        Track a shared resource in this stack.

        Use this for resources that are shared across pipelines
        (databases, secrets, etc.)

        Args:
            name: Resource identifier
            resource: Pulumi resource object

        Example:
            db = aws_env.database("analytics")
            stack.track_resource("analytics-db", db)
        """
        self._resources[name] = resource

    def compile(self) -> 'CompiledStack':
        """
        Compile the stack to create compute and orchestration infrastructure.

        This creates:
        - Compute resources for tasks (Lambda, Cloud Functions, etc.)
        - IAM policies connecting tasks to storage/databases
        - Orchestration (EventBridge rules, Cloud Scheduler jobs)
        - Monitoring (CloudWatch, Cloud Logging)

        Resources created via environments are already Pulumi resources
        and don't need compilation.

        Returns:
            CompiledStack with all infrastructure

        Example:
            compiled = stack.compile()
            compiled.export_outputs()
        """
        from glacier.compilation.stack_compiler import StackCompiler

        compiler = StackCompiler()
        return compiler.compile(self)

    def list_environments(self) -> list[str]:
        """List all environment names."""
        return list(self._environments.keys())

    def list_pipelines(self) -> list[str]:
        """List all pipeline names."""
        return list(self._pipelines.keys())

    def list_resources(self) -> list[str]:
        """List all tracked resource names."""
        return list(self._resources.keys())

    def get_environment(self, name: str) -> Environment | None:
        """Get environment by name."""
        return self._environments.get(name)

    def get_pipeline(self, name: str) -> Pipeline | None:
        """Get pipeline by name."""
        return self._pipelines.get(name)

    def get_resource(self, name: str) -> Any | None:
        """Get resource by name."""
        return self._resources.get(name)


@dataclass
class CompiledStack:
    """
    A compiled stack with all infrastructure resources.

    Contains:
    - Infrastructure resources (from environments)
    - Compute resources (from compilation)
    - Orchestration resources (from compilation)
    """

    stack_name: str
    """Stack name"""

    resources: dict[str, Any]
    """All Pulumi resources (infrastructure + compute + orchestration)"""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Compilation metadata"""

    def get_resource(self, name: str) -> Any | None:
        """Get a resource by name."""
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
