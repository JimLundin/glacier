"""
Task: Functions decorated with @task become pipeline tasks.

Tasks are the logic units in a pipeline. They:
- Take datasets as inputs (via function parameters)
- Produce datasets as outputs (via return type)
- Declare execution context (via decorator parameters)
"""

import inspect
from typing import Callable, List, Optional, Any, get_type_hints, get_origin, get_args
from dataclasses import dataclass

from glacier.core.dataset import Dataset


class Task:
    """
    A Task wraps a user function and extracts metadata from its signature.

    The function signature declares:
    - Input datasets (parameter type annotations)
    - Output datasets (return type annotation)

    The decorator declares:
    - Execution context (compute, retries, timeout, etc.)
    """

    def __init__(self, fn: Callable, **config):
        """
        Create a task from a function.

        Args:
            fn: The function to wrap
            **config: Execution configuration (compute, retries, timeout, etc.)
        """
        self.fn = fn
        self.name = fn.__name__
        self.config = config

        # Extract signature information
        self.signature = inspect.signature(fn)
        self._extract_datasets()

    def _extract_datasets(self):
        """
        Extract input and output datasets from function signature.

        Looks at type annotations to find Dataset instances.
        """
        self.inputs: List[DatasetParameter] = []
        self.outputs: List[Dataset] = []

        # Get type hints
        try:
            hints = get_type_hints(self.fn)
        except Exception:
            # If we can't get hints, try manual inspection
            hints = {}
            for param_name, param in self.signature.parameters.items():
                if param.annotation != inspect.Parameter.empty:
                    hints[param_name] = param.annotation

        # Extract input datasets from parameters
        for param_name, param in self.signature.parameters.items():
            if param_name == 'self' or param_name == 'ctx':
                # Skip 'self' for methods and 'ctx' for context
                continue

            annotation = hints.get(param_name)
            if annotation and isinstance(annotation, Dataset):
                self.inputs.append(DatasetParameter(
                    name=param_name,
                    dataset=annotation
                ))

        # Extract output datasets from return annotation
        return_annotation = hints.get('return')
        if return_annotation:
            if isinstance(return_annotation, Dataset):
                # Single output
                self.outputs.append(return_annotation)
            elif get_origin(return_annotation) is tuple:
                # Multiple outputs: Tuple[dataset_a, dataset_b]
                args = get_args(return_annotation)
                for arg in args:
                    if isinstance(arg, Dataset):
                        self.outputs.append(arg)

    def __repr__(self):
        inputs_str = ", ".join(f"{p.name}: {p.dataset.name}" for p in self.inputs)
        outputs_str = ", ".join(d.name for d in self.outputs)
        return f"Task({self.name}, inputs=[{inputs_str}], outputs=[{outputs_str}])"

    def execute(self, **input_datasets) -> Any:
        """
        Execute this task with the given input datasets.

        Args:
            **input_datasets: Mapping of parameter names to dataset values

        Returns:
            The output dataset value(s)
        """
        # Prepare arguments for the function
        kwargs = {}
        for param in self.inputs:
            if param.name in input_datasets:
                kwargs[param.name] = input_datasets[param.name]
            else:
                raise ValueError(
                    f"Task '{self.name}' requires input '{param.name}' "
                    f"(dataset '{param.dataset.name}') but it was not provided"
                )

        # Execute the function
        return self.fn(**kwargs)

    def get_compute(self):
        """Get the compute resource for this task"""
        return self.config.get('compute')


@dataclass
class DatasetParameter:
    """Represents a dataset input parameter to a task"""
    name: str  # Parameter name
    dataset: Dataset  # The dataset instance


def task(fn: Optional[Callable] = None, **config) -> Task:
    """
    Decorator to mark a function as a pipeline task.

    The function signature declares data dependencies:
    - Parameters typed with Dataset instances are inputs
    - Return type with Dataset instance(s) are outputs

    The decorator can specify execution configuration:
    - compute: Compute resource to use
    - retries: Retry configuration
    - timeout: Execution timeout
    - etc.

    Example:
        raw_data = Dataset("raw_data")
        clean_data = Dataset("clean_data")

        @task(compute=compute.local())
        def clean(input: raw_data) -> clean_data:
            return process(input)

    Args:
        fn: The function to decorate (when used without arguments)
        **config: Execution configuration

    Returns:
        Task instance wrapping the function
    """
    if fn is None:
        # Called with arguments: @task(compute=...)
        return lambda f: Task(f, **config)
    else:
        # Called without arguments: @task
        return Task(fn, **config)
