"""
Local Executor: Runs Glacier pipelines locally.
"""

from typing import Any, Dict
from glacier.execution import Executor


class LocalExecutor(Executor):
    """
    Local executor for running pipelines on the local machine.

    This executor runs tasks sequentially in topological order,
    passing data between tasks in memory.
    """

    def __init__(self):
        """Create a local executor"""
        self.execution_status = {
            "state": "initialized",
            "tasks": {},
        }

    def execute(self, pipeline) -> Dict[str, Any]:
        """
        Execute pipeline locally.

        Args:
            pipeline: Pipeline to execute

        Returns:
            Dictionary mapping dataset names to their values
        """
        self.execution_status["state"] = "running"

        # Get execution order
        execution_order = pipeline.get_execution_order()

        # Track materialized datasets
        dataset_values = {}

        # Execute tasks in order
        for task in execution_order:
            task_name = task.name
            self.execution_status["tasks"][task_name] = "running"

            try:
                # Prepare arguments from input datasets
                kwargs = {}
                for input_param in task.inputs:
                    dataset = input_param.dataset
                    if dataset.name in dataset_values:
                        kwargs[input_param.name] = dataset_values[dataset.name]
                    elif dataset.is_materialized:
                        kwargs[input_param.name] = dataset.get_value()
                    else:
                        raise RuntimeError(
                            f"Dataset '{dataset.name}' required by task '{task_name}' "
                            f"has not been materialized"
                        )

                # Execute task
                result = task.fn(**kwargs)

                # Store result in output datasets
                if len(task.outputs) == 1:
                    # Single output
                    output_dataset = task.outputs[0]
                    output_dataset.set_value(result)
                    dataset_values[output_dataset.name] = result
                elif len(task.outputs) > 1:
                    # Multiple outputs - expect tuple/list
                    if not isinstance(result, (tuple, list)):
                        raise RuntimeError(
                            f"Task '{task_name}' has {len(task.outputs)} outputs "
                            f"but returned {type(result).__name__}"
                        )
                    if len(result) != len(task.outputs):
                        raise RuntimeError(
                            f"Task '{task_name}' has {len(task.outputs)} outputs "
                            f"but returned {len(result)} values"
                        )
                    for output_dataset, value in zip(task.outputs, result):
                        output_dataset.set_value(value)
                        dataset_values[output_dataset.name] = value

                self.execution_status["tasks"][task_name] = "completed"

            except Exception as e:
                self.execution_status["tasks"][task_name] = "failed"
                self.execution_status["state"] = "failed"
                self.execution_status["error"] = str(e)
                raise RuntimeError(f"Task '{task_name}' failed: {e}") from e

        self.execution_status["state"] = "completed"
        return dataset_values

    def get_status(self) -> Dict[str, Any]:
        """Get execution status"""
        return self.execution_status
