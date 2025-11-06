"""
Pipeline decorator and Pipeline class for Glacier.
"""

import inspect
from functools import wraps
from typing import Callable, Any, Optional, Dict, List, TYPE_CHECKING
from dataclasses import dataclass, field

if TYPE_CHECKING:
    from glacier.core.task import Task
    from glacier.resources.bucket import Bucket


@dataclass
class PipelineMetadata:
    """Metadata about a pipeline for DAG construction and infrastructure generation."""

    name: str
    description: Optional[str] = None
    tasks: List["Task"] = field(default_factory=list)
    sources: List[Any] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TransformStep:
    """
    A complete step in the pipeline: sources → task → target.

    This represents one transformation in the pipeline, including:
    - Source bucket(s) to read from
    - Task to execute
    - Target bucket to write to
    """

    sources: Dict[str, "Bucket"]
    task: "Task"
    target: "Bucket"

    def to_task_instance(self):
        """Convert to TaskInstance for execution."""
        from glacier.core.task import TaskInstance

        return TaskInstance(
            task=self.task,
            sources=self.sources,
            target=self.target,
            name=self.task.name,
        )


@dataclass
class PendingStep:
    """
    A transformation awaiting .to() to complete.

    This represents an incomplete step that has sources and task,
    but needs a target bucket to be complete.
    """

    sources: Dict[str, "Bucket"]
    task: "Task"


class Pipeline:
    """
    Represents a data pipeline in Glacier.

    Pipelines can be created in two ways:
    1. Using the fluent API (NEW, PREFERRED):
       pipeline = (
           Pipeline(name="etl")
           .source(raw_data)
           .transform(clean)
           .to(output)
       )

    2. Using the decorator pattern (for function-based pipelines):
       @pipeline(name="etl")
       def my_pipeline():
           data = extract(source)
           return data

    The fluent API is recommended for new code as it provides better
    structure for code generation and infrastructure analysis.
    """

    def __init__(
        self,
        func: Optional[Callable] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize a Pipeline.

        Args:
            func: Optional function for decorator-based pipelines
            name: Pipeline name (required for fluent API)
            description: Optional description
            config: Optional configuration

        Example (Fluent API):
            pipeline = Pipeline(name="etl").source(raw).transform(clean).to(output)

        Example (Decorator):
            @pipeline(name="etl")
            def my_pipeline():
                return process(data)
        """
        self.func = func
        self.name = name or (func.__name__ if func else "unnamed_pipeline")
        self.description = description or (inspect.getdoc(func) if func else None)
        self.config = config or {}

        # For fluent API
        self._steps: List[TransformStep] = []
        self._current_sources: Optional[Dict[str, "Bucket"]] = None
        self._pending_step: Optional[PendingStep] = None

        # For decorator-based pipelines
        self.tasks: List["Task"] = []
        self.sources: List[Any] = []
        self._analyzed = False

    def __call__(self, *args, **kwargs) -> Any:
        """Execute the pipeline (for decorator-based pipelines)."""
        if self.func is None:
            raise ValueError("Cannot call Pipeline without a function. Use fluent API methods instead.")
        return self.func(*args, **kwargs)

    def source(self, bucket: "Bucket") -> "Pipeline":
        """
        Add a single source to the pipeline (fluent API).

        Args:
            bucket: Source bucket to read from

        Returns:
            Self (for chaining)

        Example:
            pipeline = Pipeline(name="etl").source(raw_data)
        """
        self._current_sources = {"df": bucket}  # Default param name
        return self

    def sources(self, **buckets: "Bucket") -> "Pipeline":
        """
        Add multiple sources to the pipeline (fluent API, for joins).

        Args:
            **buckets: Named source buckets (names must match task parameters)

        Returns:
            Self (for chaining)

        Example:
            pipeline = Pipeline(name="join").sources(
                sales_df=sales,
                customers_df=customers
            )
        """
        self._current_sources = buckets
        return self

    def transform(self, task: "Task") -> "Pipeline":
        """
        Apply a transformation (fluent API).

        Args:
            task: Task to execute

        Returns:
            Self (for chaining)

        Example:
            pipeline.transform(clean_data)

        Note:
            Must be followed by .to() to complete the step.
        """
        if self._current_sources is None:
            raise ValueError("Must call .source() or .sources() before .transform()")

        # Validate task signature matches sources
        sig = inspect.signature(task.func)
        task_params = set(sig.parameters.keys())
        source_names = set(self._current_sources.keys())

        if task_params != source_names:
            raise ValueError(
                f"Task parameters {task_params} do not match sources {source_names}. "
                f"Task function signature must match the source names provided."
            )

        # Create pending step (needs .to() to complete)
        self._pending_step = PendingStep(
            sources=self._current_sources, task=task
        )
        self._current_sources = None  # Must call .to() next
        return self

    def to(self, bucket: "Bucket") -> "Pipeline":
        """
        Write transform output to a bucket (fluent API).

        Args:
            bucket: Target bucket to write to

        Returns:
            Self (for chaining)

        Example:
            pipeline.to(output_bucket)

        Note:
            Completes the step started by .transform().
            Can be followed by another .transform() to continue the chain.
        """
        if self._pending_step is None:
            raise ValueError("Must call .transform() before .to()")

        # Complete the step
        step = TransformStep(
            sources=self._pending_step.sources,
            task=self._pending_step.task,
            target=bucket,
        )
        self._steps.append(step)
        self._pending_step = None

        # Set target as source for next transform
        self._current_sources = {"df": bucket}

        return self

    def to_dag(self):
        """
        Build DAG from pipeline steps (fluent API).

        Returns:
            DAG object

        Example:
            dag = pipeline.to_dag()

        Raises:
            ValueError: If pipeline has incomplete steps or no steps
        """
        if self._pending_step is not None:
            raise ValueError(
                "Pipeline has incomplete step. Use .to() to complete it."
            )

        if not self._steps:
            raise ValueError("Pipeline has no steps")

        from glacier.core.dag import DAG

        # Build TaskInstances
        instances = []
        for step in self._steps:
            instance = step.to_task_instance()
            instances.append(instance)

        # Build DAG from instances
        dag = DAG()
        for i, instance in enumerate(instances):
            dag.add_node(instance.name, instance.task, instance.task.metadata)

            # Add dependency on previous step
            if i > 0:
                dag.add_edge(instances[i - 1].name, instance.name)

        return dag

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
        steps_count = len(self._steps) if self._steps else len(self.tasks)
        return f"Pipeline(name='{self.name}', steps={steps_count})"


def pipeline(
    name: Optional[str] = None,
    description: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Callable:
    """
    Global pipeline decorator for creating pipelines from functions.

    This decorator creates a Pipeline object from a function that defines
    task dependencies and data flow.

    Args:
        name: Pipeline name (defaults to function name)
        description: Optional description
        config: Optional configuration

    Returns:
        Decorator function

    Example:
        from glacier import Provider, pipeline
        import polars as pl

        provider = Provider(config=AwsConfig(region="us-east-1"))
        local_exec = provider.local()
        data_source = provider.bucket(bucket="data", path="input.parquet")

        @local_exec.task()
        def load(source) -> pl.LazyFrame:
            return source.scan()

        @local_exec.task()
        def transform(df: pl.LazyFrame) -> pl.LazyFrame:
            return df.filter(pl.col("value") > 0)

        @pipeline(name="etl")
        def etl_pipeline():
            data = load(data_source)
            result = transform(data)
            return result

        # Execute
        result = etl_pipeline.run(mode="local")
    """

    def decorator(func: Callable) -> Pipeline:
        return Pipeline(
            func=func,
            name=name or func.__name__,
            description=description,
            config=config,
        )

    return decorator
