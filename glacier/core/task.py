"""
Task decorator and Task class for Glacier pipelines.
"""

import inspect
from functools import wraps
from typing import Callable, Any, Optional, List, get_type_hints
from dataclasses import dataclass, field
import polars as pl


@dataclass
class TaskMetadata:
    """Metadata about a task for DAG construction and analysis."""

    name: str
    func: Callable
    depends_on: List[str] = field(default_factory=list)
    description: Optional[str] = None
    inputs: dict = field(default_factory=dict)
    outputs: dict = field(default_factory=dict)


class Task:
    """
    Represents a computational task in a Glacier pipeline.

    Tasks are nodes in the DAG and represent transformations or operations
    on data. They can depend on other tasks and can be analyzed at compile
    time to understand infrastructure requirements.
    """

    def __init__(
        self,
        func: Callable,
        name: Optional[str] = None,
        depends_on: Optional[List[str]] = None,
    ):
        self.func = func
        self.name = name or func.__name__
        self.depends_on = depends_on or []
        self.metadata = self._extract_metadata()

        # Store the original function signature for introspection
        self.signature = inspect.signature(func)
        self._type_hints = get_type_hints(func) if hasattr(func, "__annotations__") else {}

    def _extract_metadata(self) -> TaskMetadata:
        """Extract metadata from the function for analysis."""
        return TaskMetadata(
            name=self.name,
            func=self.func,
            depends_on=self.depends_on,
            description=inspect.getdoc(self.func),
            inputs=self._type_hints,
            outputs=self._type_hints.get("return", Any),
        )

    def __call__(self, *args, **kwargs) -> Any:
        """Execute the task function."""
        return self.func(*args, **kwargs)

    def get_sources(self) -> List:
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

    def __repr__(self) -> str:
        return f"Task(name='{self.name}', depends_on={self.depends_on})"


def task(
    func: Optional[Callable] = None,
    *,
    name: Optional[str] = None,
    depends_on: Optional[List[str]] = None,
) -> Callable:
    """
    Decorator to mark a function as a Glacier task.

    Tasks are the building blocks of pipelines. They represent transformations
    or operations that can be composed into a DAG.

    Args:
        func: The function to wrap (automatically provided when used as @task)
        name: Optional name for the task (defaults to function name)
        depends_on: Optional list of task names this task depends on

    Example:
        @task
        def load_data(source: S3Source) -> pl.LazyFrame:
            return source.scan()

        @task(name="clean", depends_on=["load_data"])
        def clean_data(df: pl.LazyFrame) -> pl.LazyFrame:
            return df.filter(pl.col("value").is_not_null())
    """

    def decorator(f: Callable) -> Task:
        task_obj = Task(f, name=name, depends_on=depends_on)

        @wraps(f)
        def wrapper(*args, **kwargs):
            # In analysis mode, we might want to capture calls without executing
            # For now, just execute normally
            return task_obj(*args, **kwargs)

        # Attach the Task object to the wrapper for introspection
        wrapper._glacier_task = task_obj  # type: ignore
        wrapper.task = task_obj  # type: ignore

        return wrapper

    # Support both @task and @task(...) syntax
    if func is None:
        return decorator
    else:
        return decorator(func)
