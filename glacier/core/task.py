"""
Task decorator and Task class for Glacier pipelines.
"""

import inspect
from functools import wraps
from typing import Callable, Any, get_type_hints, TYPE_CHECKING
from dataclasses import dataclass, field
import polars as pl

if TYPE_CHECKING:
    from glacier.resources.execution import ExecutionResource


@dataclass
class TaskMetadata:
    """Metadata about a task for DAG construction and analysis."""

    name: str
    func: Callable
    depends_on: list["Task"] = field(default_factory=list)
    executor: "ExecutionResource | str | None" = None
    description: str | None = None
    inputs: dict = field(default_factory=dict)
    outputs: dict = field(default_factory=dict)


class Task:
    """
    Represents a computational task in a Glacier pipeline.

    Tasks are nodes in the DAG and represent transformations or operations
    on data. They can depend on other tasks and can be analyzed at compile
    time to understand infrastructure requirements.

    Tasks are created by the @executor.task() decorator and are bound to
    execution resources (not strings).

    Example:
        provider = Provider(config=AwsConfig(region="us-east-1"))
        local_exec = provider.local()

        @local_exec.task()
        def process_data(df: pl.LazyFrame) -> pl.LazyFrame:
            return df.filter(pl.col("value") > 0)
    """

    def __init__(
        self,
        func: Callable,
        name: str | None = None,
        depends_on: list["Task"] | None = None,
        executor: "ExecutionResource | str | None" = None,
        **config: Any,
    ):
        """
        Initialize a Task.

        Args:
            func: The function to wrap
            name: Optional task name (defaults to function name)
            depends_on: List of Task objects this task depends on (NOT strings)
            executor: Execution resource object (preferred) or string (legacy)
            **config: Additional task configuration
        """
        self.func = func
        self.name = name or func.__name__
        self.depends_on = depends_on or []
        self.executor = executor
        self.config = config

        # Store the original function signature for introspection
        self.signature = inspect.signature(func)
        self._type_hints = get_type_hints(func) if hasattr(func, "__annotations__") else {}

        self.metadata = self._extract_metadata()

    def _extract_metadata(self) -> TaskMetadata:
        """Extract metadata from the function for analysis."""
        return TaskMetadata(
            name=self.name,
            func=self.func,
            depends_on=self.depends_on,
            executor=self.executor,
            description=inspect.getdoc(self.func),
            inputs=self._type_hints,
            outputs=self._type_hints.get("return", Any),
        )

    def get_executor_type(self) -> str:
        """
        Get the executor type string.

        Returns:
            Executor type string ("local", "serverless", "cluster", "vm")
        """
        if isinstance(self.executor, str):
            return self.executor
        elif hasattr(self.executor, "get_executor_type"):
            return self.executor.get_executor_type()
        else:
            return "local"

    def __call__(self, *args, **kwargs) -> Any:
        """Execute the task function."""
        return self.func(*args, **kwargs)

    def get_sources(self) -> list:
        """
        Extract sources from the task's signature.

        This is used at compile time to understand what data sources
        this task depends on.
        """
        from glacier.sources.base import Source

        sources = []
        for param_name, param in self.signature.parameters.items():
            # Check if parameter type is a Source subclass
            param_type = self._type_hints.get(param_name)
            if param_type and (
                (inspect.isclass(param_type) and issubclass(param_type, Source))
                or isinstance(param_type, Source)
            ):
                sources.append(param_name)
        return sources

    def get_dependency_names(self) -> list[str]:
        """Get names of tasks this task depends on."""
        return [task.name for task in self.depends_on]

    def __repr__(self) -> str:
        deps = [t.name for t in self.depends_on]
        executor_type = self.get_executor_type()
        return f"Task(name='{self.name}', executor='{executor_type}', depends_on={deps})"


class TaskInstance:
    """
    Executable instance of a task.

    Represents: sources → transform → target

    This is created from TransformStep in the fluent pipeline API.
    """

    def __init__(
        self,
        task: Task,
        sources: dict[str, Any],
        target: Any,
        name: str,
    ):
        """
        Initialize a TaskInstance.

        Args:
            task: Task to execute
            sources: Dictionary mapping parameter names to Bucket sources
            target: Target Bucket to write to
            name: Instance name
        """
        self.task = task
        self.sources = sources
        self.target = target
        self.name = name
        self.dependencies: list["TaskInstance"] = []

    def execute(self, context: Any = None) -> Any:
        """
        Execute this task instance.

        Steps:
        1. Read from source(s)
        2. Execute task function
        3. Write to target

        Args:
            context: Optional execution context

        Returns:
            Result of the task execution
        """
        # Load all sources as LazyFrames
        source_dfs = {
            name: bucket.scan() for name, bucket in self.sources.items()
        }

        # Call task with named arguments
        result = self.task.func(**source_dfs)

        # Write to target
        if result is not None and hasattr(result, "collect"):
            result.collect().write_parquet(self.target.get_uri())

        return result

    def __repr__(self) -> str:
        return f"TaskInstance(name='{self.name}', task='{self.task.name}')"


# Global task decorator has been removed.
# Use execution resource-bound tasks instead: @executor.task()
#
# Example:
#   from glacier import Provider
#   from glacier.config import AwsConfig
#
#   provider = Provider(config=AwsConfig(region="us-east-1"))
#   local_exec = provider.local()
#
#   @local_exec.task()
#   def my_task(source) -> pl.LazyFrame:
#       return source.scan()
