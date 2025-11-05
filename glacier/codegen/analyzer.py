"""
Pipeline analyzer for extracting tasks, dependencies, and sources.
"""

import ast
import inspect
from typing import Any, Dict, List, Set
from pathlib import Path
from glacier.core.dag import DAG
from glacier.core.task import Task
from glacier.sources.base import Source


class PipelineAnalyzer:
    """
    Analyzes Glacier pipelines to extract:
    1. Task dependencies and build DAG
    2. Data sources and their metadata
    3. Infrastructure requirements

    This enables "Infrastructure from Code" by introspecting the pipeline
    definition and understanding what resources are needed.
    """

    def __init__(self, pipeline):
        self.pipeline = pipeline
        self.dag = DAG()
        self.sources: List[Source] = []
        self.tasks: Dict[str, Task] = {}

    def analyze(self, **kwargs) -> Dict[str, Any]:
        """
        Perform complete analysis of the pipeline.

        Returns:
            Dictionary containing DAG, sources, tasks, and infrastructure metadata
        """
        # Execute the pipeline in analysis mode to capture tasks and sources
        self._trace_pipeline_execution()

        # Build the DAG from discovered tasks
        self._build_dag()

        # Extract infrastructure requirements
        infra_requirements = self._extract_infrastructure_requirements()

        return {
            "dag": self.dag,
            "tasks": self.tasks,
            "sources": self.sources,
            "infrastructure": infra_requirements,
            "execution_order": self.dag.topological_sort() if len(self.dag.nodes) > 0 else [],
            "execution_levels": self.dag.get_execution_levels() if len(self.dag.nodes) > 0 else [],
        }

    def _trace_pipeline_execution(self) -> None:
        """
        Trace the pipeline execution to discover tasks and sources.

        This works by:
        1. Inspecting the pipeline function's source code
        2. Extracting variable assignments and function calls
        3. Identifying tasks and sources used
        """
        # Get the pipeline function
        func = self.pipeline.func

        # Try to get the source code
        try:
            source = inspect.getsource(func)
            tree = ast.parse(source)

            # Visit the AST to find task calls and source instantiations
            visitor = PipelineVisitor()
            visitor.visit(tree)

            # Store discovered information
            self.pipeline.tasks = visitor.tasks
            self.tasks = {task.name: task for task in visitor.tasks}

        except (OSError, TypeError):
            # If we can't get source (e.g., interactive mode), try to execute and capture
            self._execute_and_capture()

    def _execute_and_capture(self) -> None:
        """
        Execute the pipeline in a controlled environment to capture tasks and sources.

        This is a fallback when static analysis isn't possible.
        """
        # TODO: Implement execution tracing
        # For now, this is a placeholder
        pass

    def _build_dag(self) -> None:
        """Build the DAG from discovered tasks."""
        # Add all tasks as nodes
        for task_name, task in self.tasks.items():
            self.dag.add_node(
                name=task_name,
                task=task,
                metadata={"sources": task.get_sources()},
            )

        # Add edges based on explicit dependencies
        for task_name, task in self.tasks.items():
            for dependency in task.depends_on:
                if dependency in self.tasks:
                    self.dag.add_edge(dependency, task_name)

        # TODO: Infer additional dependencies from data flow
        # For example, if task B takes the output of task A as input,
        # we should add an edge from A to B

    def _extract_infrastructure_requirements(self) -> Dict[str, Any]:
        """
        Extract infrastructure requirements from sources and tasks.

        Returns:
            Dictionary describing needed cloud resources
        """
        requirements = {
            "storage": [],
            "compute": [],
            "iam": [],
            "networking": [],
        }

        # Extract storage requirements from sources
        for source in self.sources:
            metadata = source.get_metadata()

            if metadata.source_type == "s3":
                requirements["storage"].append(
                    {
                        "type": "s3_bucket",
                        "name": metadata.resource_name,
                        "region": metadata.region,
                        "access": "read",
                    }
                )
                requirements["iam"].append(
                    {
                        "type": "s3_read_policy",
                        "bucket": metadata.resource_name,
                    }
                )

            elif metadata.source_type == "local":
                requirements["storage"].append(
                    {
                        "type": "local_filesystem",
                        "path": metadata.resource_name,
                    }
                )

        return requirements


class PipelineVisitor(ast.NodeVisitor):
    """
    AST visitor for extracting tasks and sources from pipeline code.
    """

    def __init__(self):
        self.tasks: List[Task] = []
        self.sources: List[Any] = []
        self.task_calls: List[str] = []

    def visit_Call(self, node: ast.Call) -> None:
        """Visit function call nodes to identify task calls."""
        # Check if this is a call to a function that might be a task
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            self.task_calls.append(func_name)

        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        """Visit assignment nodes to identify source instantiations."""
        # Check if the right-hand side is a source instantiation
        if isinstance(node.value, ast.Call):
            if isinstance(node.value.func, ast.Name):
                class_name = node.value.func.id
                # Check if this looks like a Source class (ends with "Source")
                if class_name.endswith("Source"):
                    # Extract variable name
                    if isinstance(node.targets[0], ast.Name):
                        var_name = node.targets[0].id
                        # TODO: Store source information

        self.generic_visit(node)
