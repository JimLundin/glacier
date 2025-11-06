"""
Execution resource classes for binding tasks to execution environments.

Execution resources represent WHERE CODE RUNS (local, serverless, cluster, VM).
They are first-class objects created by the Provider.
"""

from typing import Any, TYPE_CHECKING, Callable, Optional
from abc import ABC, abstractmethod
from functools import wraps

if TYPE_CHECKING:
    from glacier.providers.provider import Provider
    from glacier.config.serverless import ServerlessConfig
    from glacier.core.task import Task


class ExecutionResource(ABC):
    """
    Base class for execution resources.

    Execution resources represent where code runs (local, serverless, cluster, VM).
    They provide a .task() decorator to bind tasks to the execution environment.
    """

    def __init__(
        self,
        provider: "Provider",
        name: str | None = None,
        config: Any | None = None,
    ):
        """
        Initialize execution resource.

        Args:
            provider: Provider that created this resource
            name: Optional name for this execution resource
            config: Optional resource-specific configuration
        """
        self.provider = provider
        self.name = name
        self.config = config

    def task(
        self,
        name: str | None = None,
        **kwargs: Any,
    ) -> Callable:
        """
        Decorator to bind a task to this execution resource.

        Args:
            name: Optional task name (defaults to function name)
            **kwargs: Additional task configuration

        Returns:
            Decorator function

        Example:
            provider = Provider(config=AwsConfig(region="us-east-1"))
            local_exec = provider.local()

            @local_exec.task()
            def process_data(df: pl.LazyFrame) -> pl.LazyFrame:
                return df.filter(pl.col("value") > 0)
        """

        def decorator(func: Callable) -> "Task":
            from glacier.core.task import Task

            task_name = name or func.__name__

            # Create Task object bound to this executor
            task = Task(
                func=func,
                name=task_name,
                executor=self,  # Pass the resource object, not a string
                **kwargs,
            )

            return task

        return decorator

    @abstractmethod
    def get_executor_type(self) -> str:
        """
        Get the executor type identifier.

        Returns:
            Executor type string ("local", "serverless", "cluster", "vm")
        """
        pass

    @abstractmethod
    def get_metadata(self) -> dict[str, Any]:
        """
        Get metadata for infrastructure generation.

        Returns:
            Metadata dictionary
        """
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}')"


class LocalExecutor(ExecutionResource):
    """
    Local execution resource.

    Runs tasks in the local Python process. Useful for:
    - Testing and development
    - Lightweight transformations
    - Coordinating other tasks

    Example:
        provider = Provider(config=AwsConfig(region="us-east-1"))
        local_exec = provider.local()

        @local_exec.task()
        def load_data(source):
            return source.scan()
    """

    def __init__(
        self,
        provider: "Provider",
        name: str | None = None,
        config: Any | None = None,
    ):
        super().__init__(provider=provider, name=name or "local", config=config)

    def get_executor_type(self) -> str:
        return "local"

    def get_metadata(self) -> dict[str, Any]:
        return {
            "executor_type": "local",
            "provider": self.provider.get_provider_type(),
            "description": "Local Python process execution",
        }


class ServerlessExecutor(ExecutionResource):
    """
    Serverless execution resource.

    Runs tasks in serverless functions (Lambda, Cloud Functions, Azure Functions).
    The actual backend is determined by the provider config.

    Example:
        provider = Provider(config=AwsConfig(region="us-east-1"))
        lambda_exec = provider.serverless(
            config=LambdaConfig(memory=1024, timeout=300)
        )

        @lambda_exec.task()
        def transform(df: pl.LazyFrame) -> pl.LazyFrame:
            return df.filter(pl.col("value") > 0)
    """

    def __init__(
        self,
        provider: "Provider",
        name: str | None = None,
        config: "ServerlessConfig | None" = None,
    ):
        super().__init__(
            provider=provider, name=name or "serverless", config=config
        )

    def get_executor_type(self) -> str:
        return "serverless"

    def get_metadata(self) -> dict[str, Any]:
        provider_type = self.provider.get_provider_type()

        # Determine serverless backend based on provider
        backend_map = {
            "aws": "AWS Lambda",
            "azure": "Azure Functions",
            "gcp": "Cloud Functions",
            "local": "Local Serverless Emulator",
        }

        metadata = {
            "executor_type": "serverless",
            "provider": provider_type,
            "backend": backend_map.get(provider_type, "Unknown"),
            "description": f"Serverless function execution on {backend_map.get(provider_type)}",
        }

        # Add config-specific metadata
        if self.config:
            if hasattr(self.config, "memory"):
                metadata["memory"] = self.config.memory
            if hasattr(self.config, "timeout"):
                metadata["timeout"] = self.config.timeout
            if hasattr(self.config, "runtime"):
                metadata["runtime"] = self.config.runtime

        return metadata


class ClusterExecutor(ExecutionResource):
    """
    Cluster execution resource.

    Runs tasks on distributed compute clusters (Databricks, EMR, Dataproc, Spark).
    The actual backend is determined by the provider config.

    Example:
        provider = Provider(config=AwsConfig(region="us-east-1"))
        databricks_exec = provider.cluster(
            config=DatabricksConfig(
                cluster_id="cluster-123",
                instance_type="i3.xlarge",
                num_workers=4
            )
        )

        @databricks_exec.task()
        def ml_inference(df: pl.LazyFrame) -> pl.LazyFrame:
            return df.with_columns(pl.lit(0.85).alias("prediction"))
    """

    def __init__(
        self,
        provider: "Provider",
        name: str | None = None,
        config: Any | None = None,
    ):
        super().__init__(provider=provider, name=name or "cluster", config=config)

    def get_executor_type(self) -> str:
        return "cluster"

    def get_metadata(self) -> dict[str, Any]:
        provider_type = self.provider.get_provider_type()

        # Determine cluster backend based on provider and config
        backend = "Spark Cluster"
        if self.config:
            config_name = self.config.__class__.__name__
            if "Databricks" in config_name:
                backend = "Databricks"
            elif "EMR" in config_name:
                backend = "AWS EMR"
            elif "Dataproc" in config_name:
                backend = "GCP Dataproc"

        metadata = {
            "executor_type": "cluster",
            "provider": provider_type,
            "backend": backend,
            "description": f"Cluster execution on {backend}",
        }

        # Add config-specific metadata
        if self.config:
            if hasattr(self.config, "cluster_id"):
                metadata["cluster_id"] = self.config.cluster_id
            if hasattr(self.config, "num_workers"):
                metadata["num_workers"] = self.config.num_workers
            if hasattr(self.config, "instance_type"):
                metadata["instance_type"] = self.config.instance_type

        return metadata


class VMExecutor(ExecutionResource):
    """
    VM execution resource.

    Runs tasks on virtual machines (EC2, Compute Engine, Azure VM).
    The actual backend is determined by the provider config.

    Example:
        provider = Provider(config=AwsConfig(region="us-east-1"))
        ec2_exec = provider.vm(
            config=EC2Config(
                instance_type="t3.large",
                ami="ami-12345"
            )
        )

        @ec2_exec.task()
        def batch_process(df: pl.LazyFrame) -> pl.LazyFrame:
            return df.filter(pl.col("value") > 0)
    """

    def __init__(
        self,
        provider: "Provider",
        name: str | None = None,
        config: Any | None = None,
    ):
        super().__init__(provider=provider, name=name or "vm", config=config)

    def get_executor_type(self) -> str:
        return "vm"

    def get_metadata(self) -> dict[str, Any]:
        provider_type = self.provider.get_provider_type()

        # Determine VM backend based on provider
        backend_map = {
            "aws": "AWS EC2",
            "azure": "Azure VM",
            "gcp": "GCP Compute Engine",
            "local": "Local Process",
        }

        metadata = {
            "executor_type": "vm",
            "provider": provider_type,
            "backend": backend_map.get(provider_type, "Unknown"),
            "description": f"VM execution on {backend_map.get(provider_type)}",
        }

        # Add config-specific metadata
        if self.config:
            if hasattr(self.config, "instance_type"):
                metadata["instance_type"] = self.config.instance_type
            if hasattr(self.config, "ami"):
                metadata["ami"] = self.config.ami

        return metadata
