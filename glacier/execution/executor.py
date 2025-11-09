"""
Executor: Abstract interface for pipeline execution.

Executors are provider-specific plugins that run pipelines
in different environments (local, AWS, GCP, Azure, etc.).
"""

from abc import ABC, abstractmethod
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from glacier.core.pipeline import Pipeline


class Executor(ABC):
    """
    Abstract executor interface.

    Provider-specific executors implement this interface to run
    Glacier pipelines in different environments.

    The executor is responsible for:
    1. Orchestrating task execution in topological order
    2. Managing data flow between tasks
    3. Handling failures and retries
    4. Collecting execution metrics
    """

    @abstractmethod
    def execute(self, pipeline: 'Pipeline') -> Any:
        """
        Execute a pipeline.

        Args:
            pipeline: The pipeline to execute

        Returns:
            Execution result (executor-specific)

        Raises:
            ExecutionError: If pipeline execution fails
        """
        pass

    @abstractmethod
    def get_status(self) -> dict[str, Any]:
        """
        Get execution status.

        Returns:
            Dictionary with execution status information
        """
        pass
