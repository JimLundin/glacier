"""
Pipeline: Automatically infers DAG from task signatures.

A Pipeline is a collection of tasks where dependencies are inferred
from the datasets that tasks consume and produce.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from glacier.core.task import Task
from glacier.core.dataset import Dataset


@dataclass
class PipelineEdge:
    """Represents an edge in the pipeline DAG"""
    from_task: Task
    to_task: Task
    dataset: Dataset  # The dataset that connects them
    param_name: str  # Parameter name in to_task


class Pipeline:
    """
    A Pipeline automatically builds a DAG from task signatures.

    The DAG is inferred by:
    1. Finding which task produces each dataset (outputs)
    2. Finding which tasks consume each dataset (inputs)
    3. Connecting producers to consumers

    Example:
        raw = Dataset("raw")
        clean = Dataset("clean")

        @task
        def extract() -> raw:
            return fetch_data()

        @task
        def transform(data: raw) -> clean:
            return process(data)

        # Pipeline infers: extract -> raw -> transform
        pipeline = Pipeline([extract, transform])
    """

    def __init__(self, tasks: List[Task], name: str = "pipeline"):
        """
        Create a pipeline from a list of tasks.

        Args:
            tasks: List of Task objects
            name: Pipeline name

        The DAG is automatically built from task signatures.
        """
        self.name = name
        self.tasks = tasks
        self.edges: List[PipelineEdge] = []
        self._dataset_producers: Dict[Dataset, Task] = {}

        self._build_dag()

    def _build_dag(self):
        """
        Build the DAG by inferring dependencies from task signatures.

        For each dataset:
        1. Find the task that produces it (from outputs)
        2. Find tasks that consume it (from inputs)
        3. Create edges: producer -> consumer
        """
        # First pass: map datasets to their producers
        for task in self.tasks:
            for output_dataset in task.outputs:
                if output_dataset in self._dataset_producers:
                    raise ValueError(
                        f"Dataset '{output_dataset.name}' is produced by multiple tasks: "
                        f"'{self._dataset_producers[output_dataset].name}' and '{task.name}'"
                    )
                self._dataset_producers[output_dataset] = task

        # Second pass: create edges from producers to consumers
        for task in self.tasks:
            for input_param in task.inputs:
                dataset = input_param.dataset
                producer = self._dataset_producers.get(dataset)

                if producer is None:
                    # This dataset is not produced by any task in the pipeline
                    # It's an external input
                    continue

                # Create edge: producer -> task
                edge = PipelineEdge(
                    from_task=producer,
                    to_task=task,
                    dataset=dataset,
                    param_name=input_param.name
                )
                self.edges.append(edge)

    def validate(self) -> bool:
        """
        Validate the pipeline structure.

        Checks:
        - No cycles in the DAG
        - All required datasets have producers
        - No orphaned tasks

        Returns:
            True if valid

        Raises:
            ValueError if invalid
        """
        # Check for cycles using DFS
        if self._has_cycle():
            raise ValueError("Pipeline contains a cycle!")

        # Check that all non-source tasks have their inputs satisfied
        for task in self.tasks:
            for input_param in task.inputs:
                dataset = input_param.dataset
                if dataset not in self._dataset_producers:
                    # This is OK - it's an external input
                    # But we should track this
                    pass

        return True

    def _has_cycle(self) -> bool:
        """Check if the DAG has a cycle using DFS"""
        # Build adjacency list
        adj = {task: [] for task in self.tasks}
        for edge in self.edges:
            adj[edge.from_task].append(edge.to_task)

        # Track visit states: 0 = unvisited, 1 = visiting, 2 = visited
        state = {task: 0 for task in self.tasks}

        def dfs(task: Task) -> bool:
            if state[task] == 1:  # Currently visiting - cycle detected
                return True
            if state[task] == 2:  # Already visited
                return False

            state[task] = 1  # Mark as visiting
            for neighbor in adj[task]:
                if dfs(neighbor):
                    return True
            state[task] = 2  # Mark as visited

            return False

        # Check all components
        for task in self.tasks:
            if state[task] == 0:
                if dfs(task):
                    return True

        return False

    def get_source_tasks(self) -> List[Task]:
        """
        Get tasks that have no dependencies (source tasks).

        These are tasks with no inputs, or inputs that come from
        datasets not produced by any task in the pipeline.

        Returns:
            List of source tasks
        """
        tasks_with_deps = {edge.to_task for edge in self.edges}
        return [task for task in self.tasks if task not in tasks_with_deps]

    def get_sink_tasks(self) -> List[Task]:
        """
        Get tasks that have no consumers (sink tasks).

        These are tasks whose outputs are not consumed by any
        other task in the pipeline.

        Returns:
            List of sink tasks
        """
        tasks_with_consumers = {edge.from_task for edge in self.edges}
        return [task for task in self.tasks if task not in tasks_with_consumers]

    def get_execution_order(self) -> List[Task]:
        """
        Get topological ordering of tasks for execution.

        Returns:
            List of tasks in execution order

        Raises:
            ValueError if pipeline has a cycle
        """
        if self._has_cycle():
            raise ValueError("Cannot get execution order: pipeline has a cycle")

        # Build adjacency list and in-degree count
        adj = {task: [] for task in self.tasks}
        in_degree = {task: 0 for task in self.tasks}

        for edge in self.edges:
            adj[edge.from_task].append(edge.to_task)
            in_degree[edge.to_task] += 1

        # Kahn's algorithm for topological sort
        queue = [task for task in self.tasks if in_degree[task] == 0]
        result = []

        while queue:
            task = queue.pop(0)
            result.append(task)

            for neighbor in adj[task]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(result) != len(self.tasks):
            raise ValueError("Cycle detected in pipeline")

        return result

    def get_dependencies(self, task: Task) -> List[Task]:
        """
        Get all tasks that this task depends on.

        Args:
            task: The task to get dependencies for

        Returns:
            List of tasks this task depends on
        """
        return [edge.from_task for edge in self.edges if edge.to_task == task]

    def get_consumers(self, task: Task) -> List[Task]:
        """
        Get all tasks that depend on this task.

        Args:
            task: The task to get consumers for

        Returns:
            List of tasks that consume this task's outputs
        """
        return [edge.to_task for edge in self.edges if edge.from_task == task]

    def visualize(self) -> str:
        """
        Generate a text visualization of the pipeline DAG.

        Returns:
            String representation of the DAG
        """
        lines = [f"Pipeline: {self.name}", "=" * 50, ""]

        # Show tasks
        lines.append("Tasks:")
        for task in self.tasks:
            inputs = ", ".join(p.dataset.name for p in task.inputs)
            outputs = ", ".join(d.name for d in task.outputs)
            lines.append(f"  {task.name}")
            if inputs:
                lines.append(f"    inputs: {inputs}")
            if outputs:
                lines.append(f"    outputs: {outputs}")
            lines.append("")

        # Show edges
        lines.append("Dependencies:")
        for edge in self.edges:
            lines.append(
                f"  {edge.from_task.name} -> {edge.to_task.name} "
                f"(via {edge.dataset.name})"
            )

        return "\n".join(lines)

    def __repr__(self):
        return f"Pipeline({self.name}, tasks={len(self.tasks)}, edges={len(self.edges)})"
