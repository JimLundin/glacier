"""
Local executor for running Glacier pipelines on a single machine.
"""

from typing import Any, Dict, Optional
import time
from glacier.core.context import GlacierContext, ExecutionMode


class LocalExecutor:
    """
    Executes Glacier pipelines locally in the current Python process.

    This is primarily used for:
    1. Development and testing
    2. Small-scale data processing
    3. Debugging pipeline logic before deployment
    """

    def __init__(self, pipeline, context: Optional[GlacierContext] = None):
        self.pipeline = pipeline
        self.context = context or GlacierContext(mode=ExecutionMode.LOCAL)

    def execute(self, **kwargs) -> Any:
        """
        Execute the pipeline locally.

        This runs the pipeline function directly, allowing Polars' lazy
        evaluation to optimize the execution plan.

        Args:
            **kwargs: Arguments passed to the pipeline function

        Returns:
            The result of the pipeline execution
        """
        start_time = time.time()

        try:
            # Execute the pipeline function
            result = self.pipeline.func(**kwargs)

            execution_time = time.time() - start_time

            if self.context.debug:
                print(f"Pipeline '{self.pipeline.name}' completed in {execution_time:.2f}s")

            return result

        except Exception as e:
            execution_time = time.time() - start_time
            print(f"Pipeline '{self.pipeline.name}' failed after {execution_time:.2f}s")
            raise

    def execute_with_dag(self, dag, task_results: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute the pipeline using DAG-based task ordering.

        This allows for:
        1. Proper dependency resolution
        2. Potential parallelization of independent tasks
        3. Fine-grained error handling per task

        Args:
            dag: The DAG representing task dependencies
            task_results: Optional pre-computed task results

        Returns:
            Dictionary mapping task names to their results
        """
        results = task_results or {}

        # Get execution order from topological sort
        execution_order = dag.topological_sort()

        for task_name in execution_order:
            if task_name in results:
                # Task already executed (pre-computed)
                continue

            node = dag.nodes[task_name]
            task = node.task

            if self.context.debug:
                print(f"Executing task: {task_name}")

            # Get results of dependent tasks
            dependency_results = {
                dep: results[dep] for dep in node.dependencies if dep in results
            }

            try:
                # Execute the task
                # TODO: Pass dependency results to task
                result = task()
                results[task_name] = result

            except Exception as e:
                print(f"Task '{task_name}' failed: {e}")
                raise

        return results

    def validate(self) -> bool:
        """
        Validate the pipeline without executing it.

        Checks:
        1. All tasks are properly defined
        2. Dependencies exist
        3. No circular dependencies

        Returns:
            True if validation passes, False otherwise
        """
        try:
            # Analyze the pipeline to build DAG
            from glacier.codegen.analyzer import PipelineAnalyzer

            analyzer = PipelineAnalyzer(self.pipeline)
            analysis = analyzer.analyze()

            # Check for cycles
            cycles = analysis["dag"].detect_cycles()
            if cycles:
                print(f"Validation failed: Circular dependency detected: {cycles}")
                return False

            # TODO: Add more validation checks
            # - Verify all source files exist (for local sources)
            # - Check task signatures are compatible
            # - Validate data types match between tasks

            return True

        except Exception as e:
            print(f"Validation failed: {e}")
            return False
