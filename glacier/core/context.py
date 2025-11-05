"""
Execution context for Glacier pipelines.
"""

from typing import Any, Dict, Optional
from dataclasses import dataclass, field
from enum import Enum


class ExecutionMode(Enum):
    """Execution modes for Glacier pipelines."""

    LOCAL = "local"
    ANALYZE = "analyze"
    GENERATE = "generate"
    DEPLOY = "deploy"


@dataclass
class GlacierContext:
    """
    Context manager for pipeline execution.

    Tracks execution state, mode, and configuration across pipeline runs.
    """

    mode: ExecutionMode = ExecutionMode.LOCAL
    config: Dict[str, Any] = field(default_factory=dict)
    environment: str = "development"
    debug: bool = False

    # Tracks captured sources and tasks during analysis
    _captured_sources: list = field(default_factory=list)
    _captured_tasks: list = field(default_factory=list)

    def capture_source(self, source: Any) -> None:
        """Capture a source for analysis."""
        if source not in self._captured_sources:
            self._captured_sources.append(source)

    def capture_task(self, task: Any) -> None:
        """Capture a task for analysis."""
        if task not in self._captured_tasks:
            self._captured_tasks.append(task)

    def get_captured_sources(self) -> list:
        """Get all captured sources."""
        return self._captured_sources.copy()

    def get_captured_tasks(self) -> list:
        """Get all captured tasks."""
        return self._captured_tasks.copy()

    def reset(self) -> None:
        """Reset the context."""
        self._captured_sources.clear()
        self._captured_tasks.clear()


# Global context instance
_context: Optional[GlacierContext] = None


def get_context() -> GlacierContext:
    """Get the current Glacier context."""
    global _context
    if _context is None:
        _context = GlacierContext()
    return _context


def set_context(context: GlacierContext) -> None:
    """Set the global Glacier context."""
    global _context
    _context = context


def reset_context() -> None:
    """Reset the global context."""
    global _context
    _context = GlacierContext()
