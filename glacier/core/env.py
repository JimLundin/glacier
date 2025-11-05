"""
Environment-based design for Glacier pipelines.

GlacierEnv is the central orchestrator that manages providers, resources,
tasks, and pipelines in a dependency-injection pattern.
"""

from typing import Any, Callable
from functools import wraps
import inspect


class GlacierEnv:
    """
    Central orchestrator for Glacier pipelines using dependency injection.

    The GlacierEnv class manages:
    - Provider configuration and lifecycle
    - Resource registry (named resources that can be retrieved)
    - Task binding (@env.task())
    - Pipeline binding (@env.pipeline())
    - Execution context

    This enables the environment-first pattern where configuration
    flows explicitly through the system:
        Provider → Environment → Resources/Tasks → Pipeline

    Example:
        from glacier import GlacierEnv
        from glacier.providers import AWSProvider
        from glacier.config import AwsConfig
        import polars as pl

        # 1. Create provider with config
        provider = AWSProvider(config=AwsConfig(region="us-east-1"))

        # 2. Create environment
        env = GlacierEnv(provider=provider, name="production")

        # 3. Define tasks bound to environment
        @env.task()
        def extract(source) -> pl.LazyFrame:
            return source.scan()

        @env.task()
        def transform(df: pl.LazyFrame) -> pl.LazyFrame:
            return df.filter(pl.col("amount") > 0)

        # 4. Define pipeline
        @env.pipeline()
        def my_pipeline():
            source = env.provider.bucket("data", path="sales.parquet")
            df = extract(source)
            result = transform(df)
            return result

        # 5. Execute
        result = my_pipeline.run(mode="local")
    """

    def __init__(
        self,
        provider: Any,
        name: str = "default",
        debug: bool = False,
        resources: dict[str, Any] | None = None,
    ):
        """
        Initialize a Glacier environment.

        Args:
            provider: Cloud provider (AWSProvider, GCPProvider, AzureProvider, LocalProvider)
            name: Environment name (e.g., "development", "staging", "production")
            debug: Enable debug mode
            resources: Optional dict of pre-registered resources
        """
        self.provider = provider
        self.name = name
        self.debug = debug
        self._resources: dict[str, Any] = resources or {}
        self._tasks: list = []
        self._pipelines: list = []

    def register(self, name: str, resource: Any) -> None:
        """
        Register a named resource in the environment registry.

        This allows tasks and pipelines to retrieve resources by name,
        enabling centralized resource management.

        Args:
            name: Resource name (string identifier)
            resource: Resource object (Bucket, Serverless, etc.)

        Example:
            env.register("sales_data", provider.bucket("sales", path="data.parquet"))
            env.register("customer_data", provider.bucket("customers", path="data.parquet"))

            @env.task()
            def load_sales() -> pl.LazyFrame:
                source = env.get("sales_data")
                return source.scan()
        """
        self._resources[name] = resource

    def get(self, name: str) -> Any:
        """
        Retrieve a named resource from the environment registry.

        Args:
            name: Resource name

        Returns:
            The registered resource

        Raises:
            KeyError: If resource not found

        Example:
            sales_bucket = env.get("sales_data")
            df = sales_bucket.scan()
        """
        if name not in self._resources:
            raise KeyError(
                f"Resource '{name}' not found in environment '{self.name}'. "
                f"Available resources: {list(self._resources.keys())}"
            )
        return self._resources[name]

    def list_resources(self) -> list[str]:
        """Get list of registered resource names."""
        return list(self._resources.keys())

    def task(
        self,
        func: Callable | None = None,
        *,
        name: str | None = None,
        depends_on: list | None = None,
        executor: str | None = None,
        timeout: int | None = None,
        retries: int | None = None,
        retry_delay: int | None = None,
        cache: bool | None = None,
        tags: dict[str, str] | None = None,
    ) -> Callable:
        """
        Decorator to bind a task to this environment.

        Tasks bound to an environment have explicit dependencies and
        can access the environment's provider and resources.

        Args:
            func: The function to wrap (automatically provided)
            name: Optional task name
            depends_on: List of Task objects this depends on
            executor: Execution backend (local, databricks, dbt, etc.)
            timeout: Task timeout in seconds
            retries: Number of retries on failure
            retry_delay: Delay between retries in seconds
            cache: Enable result caching
            tags: Task-specific tags

        Example:
            @env.task()
            def extract(source) -> pl.LazyFrame:
                return source.scan()

            @env.task(executor="databricks", timeout=600, retries=3)
            def heavy_transform(df: pl.LazyFrame) -> pl.LazyFrame:
                # Runs on Databricks with 600s timeout and 3 retries
                return df.filter(pl.col("value") > 100)
        """
        from glacier.core.task import Task

        def decorator(f: Callable) -> Callable:
            task_obj = Task(
                f,
                name=name,
                depends_on=depends_on or [],
                executor=executor or "local",
            )
            # Attach environment to task
            task_obj.env = self

            # Store task-level configuration
            task_obj.timeout = timeout
            task_obj.retries = retries
            task_obj.retry_delay = retry_delay
            task_obj.cache = cache
            task_obj.tags = tags or {}

            @wraps(f)
            def wrapper(*args, **kwargs):
                return task_obj(*args, **kwargs)

            # Attach task object for introspection
            wrapper._glacier_task = task_obj
            wrapper.task = task_obj
            wrapper.env = self

            # Track task in environment
            self._tasks.append(task_obj)

            return wrapper

        # Support both @env.task and @env.task(...) syntax
        if func is None:
            return decorator
        else:
            return decorator(func)

    def pipeline(
        self,
        func: Callable | None = None,
        *,
        name: str | None = None,
        description: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> Callable:
        """
        Decorator to bind a pipeline to this environment.

        Pipelines bound to an environment have access to the environment's
        provider and resources.

        Args:
            func: The function to wrap (automatically provided)
            name: Optional pipeline name
            description: Optional description
            config: Optional configuration dict

        Example:
            @env.pipeline(name="sales_analysis")
            def sales_pipeline():
                # Access provider via env.provider
                source = env.provider.bucket("sales", path="data.parquet")

                # Access registered resources via env.get()
                config = env.get("config")

                # Call environment-bound tasks
                df = extract(source)
                result = transform(df)
                return result

            # Execute
            result = sales_pipeline.run(mode="local")
        """
        from glacier.core.pipeline import Pipeline

        def decorator(f: Callable) -> Callable:
            pipeline_obj = Pipeline(
                f,
                name=name,
                description=description or inspect.getdoc(f),
                config=config or {},
            )
            # Attach environment to pipeline
            pipeline_obj.env = self

            @wraps(f)
            def wrapper(*args, **kwargs):
                if not args and not kwargs:
                    return pipeline_obj
                return pipeline_obj(*args, **kwargs)

            # Attach pipeline object for introspection
            wrapper._glacier_pipeline = pipeline_obj
            wrapper.pipeline = pipeline_obj
            wrapper.env = self

            # Expose run method
            wrapper.run = pipeline_obj.run
            wrapper.get_metadata = pipeline_obj.get_metadata

            # Track pipeline in environment
            self._pipelines.append(pipeline_obj)

            return wrapper

        # Support both @env.pipeline and @env.pipeline(...) syntax
        if func is None:
            return decorator
        else:
            return decorator(func)

    def bind(self, task_or_pipeline):
        """
        Bind an unbound task or pipeline to this environment.

        This enables the deferred binding pattern where you define
        tasks/pipelines first and bind them to environments later.

        Args:
            task_or_pipeline: Task or Pipeline to bind

        Returns:
            Environment-bound version of the task/pipeline

        Example:
            from glacier import task

            # Define unbound task
            @task
            def my_task(source):
                return source.scan()

            # Bind to different environments
            dev_env = GlacierEnv(provider=LocalProvider(...))
            prod_env = GlacierEnv(provider=AWSProvider(...))

            dev_task = dev_env.bind(my_task)
            prod_task = prod_env.bind(my_task)
        """
        # Check if it's a task
        if hasattr(task_or_pipeline, "_glacier_task"):
            task_obj = task_or_pipeline._glacier_task
            task_obj.env = self
            self._tasks.append(task_obj)
            return task_or_pipeline

        # Check if it's a pipeline
        if hasattr(task_or_pipeline, "_glacier_pipeline"):
            pipeline_obj = task_or_pipeline._glacier_pipeline
            pipeline_obj.env = self
            self._pipelines.append(pipeline_obj)
            return task_or_pipeline

        raise TypeError(
            f"Cannot bind {type(task_or_pipeline)}. "
            "Expected a task or pipeline decorated function."
        )

    @classmethod
    def from_provider(
        cls,
        provider_type: str,
        config: Any,
        name: str = "default",
        **kwargs,
    ) -> "GlacierEnv":
        """
        Create environment from provider type and config.

        This is a convenience factory method for creating environments
        without explicitly instantiating providers.

        Args:
            provider_type: Provider type ("aws", "gcp", "azure", "local")
            config: Provider config object (AwsConfig, GcpConfig, etc.)
            name: Environment name
            **kwargs: Additional arguments

        Returns:
            GlacierEnv instance

        Example:
            from glacier.config import AwsConfig

            env = GlacierEnv.from_provider(
                provider_type="aws",
                config=AwsConfig(region="us-east-1"),
                name="production"
            )
        """
        from glacier.providers import (
            AWSProvider,
            GCPProvider,
            AzureProvider,
            LocalProvider,
        )

        provider_map = {
            "aws": AWSProvider,
            "gcp": GCPProvider,
            "azure": AzureProvider,
            "local": LocalProvider,
        }

        if provider_type not in provider_map:
            raise ValueError(
                f"Unknown provider type: {provider_type}. "
                f"Available: {list(provider_map.keys())}"
            )

        provider_class = provider_map[provider_type]
        provider = provider_class(config=config, **kwargs)

        return cls(provider=provider, name=name, **kwargs)

    @classmethod
    def from_env(cls, name: str = "default", **kwargs) -> "GlacierEnv":
        """
        Create environment from environment variables.

        Reads GLACIER_PROVIDER, AWS_REGION, GCP_PROJECT_ID, etc.
        from environment variables to configure the provider.

        Args:
            name: Environment name
            **kwargs: Additional arguments

        Returns:
            GlacierEnv instance

        Example:
            # With GLACIER_PROVIDER=aws and AWS_REGION=us-east-1 set
            env = GlacierEnv.from_env()
        """
        import os

        provider_type = os.getenv("GLACIER_PROVIDER", "local").lower()

        from glacier.providers import (
            AWSProvider,
            GCPProvider,
            AzureProvider,
            LocalProvider,
        )

        provider_map = {
            "aws": AWSProvider,
            "gcp": GCPProvider,
            "azure": AzureProvider,
            "local": LocalProvider,
        }

        if provider_type not in provider_map:
            raise ValueError(
                f"Unknown GLACIER_PROVIDER: {provider_type}. "
                f"Available: {list(provider_map.keys())}"
            )

        provider_class = provider_map[provider_type]
        provider = provider_class.from_env(**kwargs)

        return cls(provider=provider, name=name, **kwargs)

    def get_state(self) -> dict[str, Any]:
        """
        Get environment state including all resources, tasks, and pipelines.

        Returns:
            Dict with environment state

        Example:
            state = env.get_state()
            print(f"Resources: {state['resources']}")
            print(f"Tasks: {state['tasks']}")
        """
        return {
            "name": self.name,
            "provider_type": self.provider.get_provider_type(),
            "resources": list(self._resources.keys()),
            "tasks": [task.name for task in self._tasks],
            "pipelines": [pipeline.name for pipeline in self._pipelines],
            "debug": self.debug,
        }

    def __repr__(self) -> str:
        return (
            f"GlacierEnv(name='{self.name}', "
            f"provider={self.provider.get_provider_type()}, "
            f"resources={len(self._resources)}, "
            f"tasks={len(self._tasks)}, "
            f"pipelines={len(self._pipelines)})"
        )
