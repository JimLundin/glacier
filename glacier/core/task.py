"""
Task decorator and Task class for Glacier pipelines.
"""

import inspect
from functools import wraps
from typing import Callable, Any, get_type_hints
from dataclasses import dataclass, field
import polars as pl


@dataclass
class TaskMetadata:
    """Metadata about a task for DAG construction and analysis."""

    name: str
    func: Callable
    depends_on: list["Task"] = field(default_factory=list)
    executor: str | None = None
    description: str | None = None
    inputs: dict = field(default_factory=dict)
    outputs: dict = field(default_factory=dict)


class Task:
    """
    Represents a computational task in a Glacier pipeline.

    Tasks are nodes in the DAG and represent transformations or operations
    on data. They can depend on other tasks and can be analyzed at compile
    time to understand infrastructure requirements.

    Tasks now support:
    - Explicit dependencies (pass Task objects, not strings)
    - Executor specification (local, databricks, dbt, etc.)
    - Type-safe composition
    """

    def __init__(
        self,
        func: Callable,
        name: str | None = None,
        depends_on: list["Task"] | None = None,
        executor: str | None = None,
    ):
        """
        Initialize a Task.

        Args:
            func: The function to wrap
            name: Optional task name (defaults to function name)
            depends_on: List of Task objects this task depends on (NOT strings)
            executor: Execution backend (local, databricks, dbt, spark, etc.)
        """
        self.func = func
        self.name = name or func.__name__
        self.depends_on = depends_on or []
        self.executor = executor or "local"

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
        return f"Task(name='{self.name}', executor='{self.executor}', depends_on={deps})"


# Global task decorator has been removed.
# Use environment-bound tasks instead: @env.task()
#
# Example:
#   from glacier import GlacierEnv
#   env = GlacierEnv(provider=provider, name="production")
#
#   @env.task()
#   def my_task(source) -> pl.LazyFrame:
#       return source.scan()
