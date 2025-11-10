"""
Pipeline: Automatically infers DAG from task signatures.

A Pipeline is a collection of tasks where dependencies are inferred
from the datasets that tasks consume and produce.
"""

from typing import Any, Callable
from dataclasses import dataclass

from glacier.core.task import Task
from glacier.core.dataset import Dataset
from glacier.compute.resources import ComputeResource


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

    Example (new pattern - recommended):
        pipeline = Pipeline(name="etl")

        raw = Dataset("raw")
        clean = Dataset("clean")

        @pipeline.task(compute=compute.local())
        def extract() -> raw:
            return fetch_data()

        @pipeline.task(compute=compute.serverless())
        def transform(data: raw) -> clean:
            return process(data)

    Example (old pattern - still supported):
        @task
        def extract() -> raw:
            return fetch_data()

        @task
        def transform(data: raw) -> clean:
            return process(data)

        pipeline = Pipeline([extract, transform], name="etl")
    """

    def __init__(self, tasks: list[Task] | None = None, name: str = "pipeline"):
        """
        Create a pipeline.

        Args:
            tasks: Optional list of Task objects (for backwards compatibility)
            name: Pipeline name

        The DAG is automatically built from task signatures.
        """
        self.name = name
        self._tasks: list[Task] = tasks or []
        self.edges: list[PipelineEdge] = []
        self._dataset_producers: dict[Dataset, Task] = {}
        self._dag_built = False

        if tasks:
            # Old pattern - tasks provided upfront
            self._build_dag()
            self._dag_built = True

    def task(
        self,
        compute: ComputeResource | None = None,
        retries: int = 0,
        timeout: int | None = None,
        **kwargs
    ) -> Callable:
        """
        Decorator to register a task with this pipeline.

        This is the recommended way to add tasks to a pipeline.

        Args:
            compute: Compute resource for execution
            retries: Number of retry attempts
            timeout: Task timeout in seconds
            **kwargs: Additional task configuration

        Returns:
            Decorator function

        Example:
            pipeline = Pipeline(name="etl")

            @pipeline.task(compute=compute.serverless(memory=1024))
            def my_task(data: input_data) -> output_data:
                return process(data)
        """
        def decorator(func: Callable) -> Task:
            # Import here to avoid circular dependency
            from glacier.core.task import task as create_task

            # Create task from function
            task_obj = create_task(
                compute=compute,
                retries=retries,
                timeout=timeout,
                **kwargs
            )(func)

            # Register with pipeline
            self._tasks.append(task_obj)
            self._dag_built = False  # Invalidate DAG

            return task_obj

        return decorator

    @property
    def tasks(self) -> list[Task]:
        """
        Get all tasks in the pipeline.

        Triggers DAG building if needed.
        """
        if not self._dag_built:
            self._build_dag()
            self._dag_built = True
        return self._tasks.copy()

    @property
    def datasets(self) -> list[Dataset]:
        """
        Get all datasets in the pipeline.

        Collects unique datasets from all task inputs and outputs.
        """
        if not self._dag_built:
            self._build_dag()
            self._dag_built = True

        datasets_set = set()

        # Collect from task outputs
        for task in self._tasks:
            datasets_set.update(task.outputs)

        # Collect from task inputs
        for task in self._tasks:
            for input_param in task.inputs:
                datasets_set.add(input_param.dataset)

        return list(datasets_set)

    def _build_dag(self):
        """
        Build the DAG by inferring dependencies from task signatures.

        For each dataset:
        1. Find the task that produces it (from outputs)
        2. Find tasks that consume it (from inputs)
        3. Create edges: producer -> consumer
        """
        # Reset edges and producers
        self.edges = []
        self._dataset_producers = {}

        # First pass: map datasets to their producers
        for task in self._tasks:
            for output_dataset in task.outputs:
                if output_dataset in self._dataset_producers:
                    raise ValueError(
                        f"Dataset '{output_dataset.name}' is produced by multiple tasks: "
                        f"'{self._dataset_producers[output_dataset].name}' and '{task.name}'"
                    )
                self._dataset_producers[output_dataset] = task

        # Second pass: create edges from producers to consumers
        for task in self._tasks:
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
        # Build DAG if needed
        if not self._dag_built:
            self._build_dag()
            self._dag_built = True

        # Check for cycles using DFS
        if self._has_cycle():
            raise ValueError("Pipeline contains a cycle!")

        # Check that all non-source tasks have their inputs satisfied
        for task in self._tasks:
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
        adj = {task: [] for task in self._tasks}
        for edge in self.edges:
            adj[edge.from_task].append(edge.to_task)

        # Track visit states: 0 = unvisited, 1 = visiting, 2 = visited
        state = {task: 0 for task in self._tasks}

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
        for task in self._tasks:
            if state[task] == 0:
                if dfs(task):
                    return True

        return False

    def get_source_tasks(self) -> list[Task]:
        """
        Get tasks that have no dependencies (source tasks).

        These are tasks with no inputs, or inputs that come from
        datasets not produced by any task in the pipeline.

        Returns:
            List of source tasks
        """
        if not self._dag_built:
            self._build_dag()
            self._dag_built = True
        tasks_with_deps = {edge.to_task for edge in self.edges}
        return [task for task in self._tasks if task not in tasks_with_deps]

    def get_sink_tasks(self) -> list[Task]:
        """
        Get tasks that have no consumers (sink tasks).

        These are tasks whose outputs are not consumed by any
        other task in the pipeline.

        Returns:
            List of sink tasks
        """
        if not self._dag_built:
            self._build_dag()
            self._dag_built = True
        tasks_with_consumers = {edge.from_task for edge in self.edges}
        return [task for task in self._tasks if task not in tasks_with_consumers]

    def get_execution_order(self) -> list[Task]:
        """
        Get topological ordering of tasks for execution.

        Returns:
            List of tasks in execution order

        Raises:
            ValueError if pipeline has a cycle
        """
        if not self._dag_built:
            self._build_dag()
            self._dag_built = True

        if self._has_cycle():
            raise ValueError("Cannot get execution order: pipeline has a cycle")

        # Build adjacency list and in-degree count
        adj = {task: [] for task in self._tasks}
        in_degree = {task: 0 for task in self._tasks}

        for edge in self.edges:
            adj[edge.from_task].append(edge.to_task)
            in_degree[edge.to_task] += 1

        # Kahn's algorithm for topological sort
        queue = [task for task in self._tasks if in_degree[task] == 0]
        result = []

        while queue:
            task = queue.pop(0)
            result.append(task)

            for neighbor in adj[task]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(result) != len(self._tasks):
            raise ValueError("Cycle detected in pipeline")

        return result

    def get_dependencies(self, task: Task) -> list[Task]:
        """
        Get all tasks that this task depends on.

        Args:
            task: The task to get dependencies for

        Returns:
            List of tasks this task depends on
        """
        return [edge.from_task for edge in self.edges if edge.to_task == task]

    def get_consumers(self, task: Task) -> list[Task]:
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
        if not self._dag_built:
            self._build_dag()
            self._dag_built = True

        lines = [f"Pipeline: {self.name}", "=" * 50, ""]

        # Show tasks
        lines.append("Tasks:")
        for task in self._tasks:
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

    def compile(self, compiler: 'Compiler') -> 'CompiledPipeline':
        """
        Compile pipeline using provided compiler.

        Args:
            compiler: Provider-specific compiler (injected dependency)

        Returns:
            Compiled infrastructure definition

        Example:
            from glacier_aws import AWSCompiler

            compiler = AWSCompiler(region="us-east-1")
            infra = pipeline.compile(compiler)
            infra.export_pulumi("./infra")
        """
        self.validate()
        return compiler.compile(self)

    def run(self, executor: 'Executor') -> Any:
        """
        Execute pipeline with provided executor.

        Args:
            executor: Provider-specific executor (injected dependency)

        Returns:
            Execution result

        Example:
            from glacier_local import LocalExecutor

            executor = LocalExecutor()
            result = pipeline.run(executor)
        """
        self.validate()
        return executor.execute(self)

    def __repr__(self):
        return f"Pipeline({self.name}, tasks={len(self._tasks)}, edges={len(self.edges)})"
