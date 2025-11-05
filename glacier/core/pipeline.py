"""
Pipeline decorator and Pipeline class for Glacier.
"""

import inspect
from functools import wraps
from typing import Callable, Any, Optional, Dict, List
from dataclasses import dataclass, field
from glacier.core.task import Task


@dataclass
class PipelineMetadata:
    """Metadata about a pipeline for DAG construction and infrastructure generation."""

    name: str
    description: Optional[str] = None
    tasks: List[Task] = field(default_factory=list)
    sources: List[Any] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)


class Pipeline:
    """
    Represents a data pipeline in Glacier.

    Pipelines orchestrate tasks and manage dependencies. They can be:
    1. Executed locally for testing
    2. Analyzed to generate DAGs
    3. Compiled to generate infrastructure code
    """

    def __init__(
        self,
        func: Callable,
        name: Optional[str] = None,
        description: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.func = func
        self.name = name or func.__name__
        self.description = description or inspect.getdoc(func)
        self.config = config or {}

        # Tracks tasks and sources discovered during analysis
        self.tasks: List[Task] = []
        self.sources: List[Any] = []
        self._analyzed = False

    def __call__(self, *args, **kwargs) -> Any:
        """Execute the pipeline."""
        return self.func(*args, **kwargs)

    def run(self, mode: str = "local", **kwargs) -> Any:
        """
        Run the pipeline in the specified mode.

        Args:
            mode: Execution mode ('local', 'analyze', 'generate')
            **kwargs: Additional arguments passed to the execution engine

        Returns:
            Result of the pipeline execution (mode-dependent)
        """
        if mode == "local":
            return self._run_local(**kwargs)
        elif mode == "analyze":
            return self._analyze(**kwargs)
        elif mode == "generate":
            return self._generate_infrastructure(**kwargs)
        else:
            raise ValueError(f"Unknown execution mode: {mode}")

    def _run_local(self, **kwargs) -> Any:
        """Execute the pipeline locally."""
        from glacier.runtime.local import LocalExecutor

        executor = LocalExecutor(self)
        return executor.execute(**kwargs)

    def _analyze(self, **kwargs) -> Dict[str, Any]:
        """Analyze the pipeline to build DAG and extract metadata."""
        from glacier.codegen.analyzer import PipelineAnalyzer

        analyzer = PipelineAnalyzer(self)
        return analyzer.analyze(**kwargs)

    def _generate_infrastructure(self, output_dir: str = "./infra", **kwargs) -> Dict[str, Any]:
        """Generate infrastructure code from the pipeline."""
        from glacier.codegen.terraform import TerraformGenerator

        # First analyze to get metadata
        analysis = self._analyze(**kwargs)

        # Then generate infrastructure
        generator = TerraformGenerator(self, analysis)
        return generator.generate(output_dir=output_dir)

    def get_metadata(self) -> PipelineMetadata:
        """Get metadata about this pipeline."""
        return PipelineMetadata(
            name=self.name,
            description=self.description,
            tasks=self.tasks,
            sources=self.sources,
            config=self.config,
        )

    def __repr__(self) -> str:
        return f"Pipeline(name='{self.name}', tasks={len(self.tasks)})"


# Global pipeline decorator has been removed.
# Use environment-bound pipelines instead: @env.pipeline()
#
# Example:
#   from glacier import GlacierEnv
#   env = GlacierEnv(provider=provider, name="production")
#
#   @env.pipeline(name="my_pipeline")
#   def my_pipeline():
#       source = env.provider.bucket("data", path="input.parquet")
#       df = load_data(source)
#       return df
