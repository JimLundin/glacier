"""
Tests for @task and @pipeline decorators.
"""

import pytest
import polars as pl
from glacier import task, pipeline
from glacier.sources import LocalSource
from glacier.core.task import Task
from glacier.core.pipeline import Pipeline


class TestTaskDecorator:
    """Tests for @task decorator."""

    def test_basic_task(self):
        """Test basic task creation."""

        @task
        def my_task(x: int) -> int:
            return x * 2

        # Check that the task wrapper has the task object attached
        assert hasattr(my_task, "_glacier_task")
        assert isinstance(my_task._glacier_task, Task)

        # Check task properties
        assert my_task._glacier_task.name == "my_task"
        assert my_task._glacier_task.depends_on == []

        # Check that the task is callable
        result = my_task(5)
        assert result == 10

    def test_task_with_name(self):
        """Test task with custom name."""

        @task(name="custom_name")
        def my_task() -> None:
            pass

        assert my_task._glacier_task.name == "custom_name"

    def test_task_with_dependencies(self):
        """Test task with explicit dependencies."""

        @task(depends_on=["task1", "task2"])
        def my_task() -> None:
            pass

        assert my_task._glacier_task.depends_on == ["task1", "task2"]

    def test_task_metadata(self):
        """Test task metadata extraction."""

        @task
        def documented_task() -> pl.LazyFrame:
            """This is a documented task."""
            pass

        metadata = documented_task._glacier_task.metadata

        assert metadata.name == "documented_task"
        assert "documented task" in metadata.description.lower()


class TestPipelineDecorator:
    """Tests for @pipeline decorator."""

    def test_basic_pipeline(self):
        """Test basic pipeline creation."""

        @pipeline
        def my_pipeline():
            return "result"

        # Check that the pipeline wrapper has the pipeline object attached
        assert hasattr(my_pipeline, "_glacier_pipeline")
        assert isinstance(my_pipeline._glacier_pipeline, Pipeline)

        # Check pipeline properties
        assert my_pipeline._glacier_pipeline.name == "my_pipeline"

    def test_pipeline_with_name(self):
        """Test pipeline with custom name."""

        @pipeline(name="custom_pipeline_name")
        def my_pipeline():
            pass

        assert my_pipeline._glacier_pipeline.name == "custom_pipeline_name"

    def test_pipeline_with_description(self):
        """Test pipeline with description."""

        @pipeline(description="This is a test pipeline")
        def my_pipeline():
            pass

        assert my_pipeline._glacier_pipeline.description == "This is a test pipeline"

    def test_pipeline_with_config(self):
        """Test pipeline with configuration."""

        @pipeline(config={"env": "production", "region": "us-east-1"})
        def my_pipeline():
            pass

        config = my_pipeline._glacier_pipeline.config

        assert config["env"] == "production"
        assert config["region"] == "us-east-1"

    def test_pipeline_has_run_method(self):
        """Test that pipeline has run method."""

        @pipeline
        def my_pipeline():
            return "result"

        assert hasattr(my_pipeline, "run")
        assert callable(my_pipeline.run)


class TestPipelineExecution:
    """Tests for pipeline execution."""

    def test_simple_pipeline_execution(self):
        """Test executing a simple pipeline."""

        @task
        def add_one(x: int) -> int:
            return x + 1

        @task
        def multiply_two(x: int) -> int:
            return x * 2

        @pipeline
        def math_pipeline():
            result = add_one(5)
            result = multiply_two(result)
            return result

        # Execute the pipeline
        result = math_pipeline._glacier_pipeline.func()

        assert result == 12  # (5 + 1) * 2
