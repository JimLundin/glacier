"""
Scheduling Resources: Provider-agnostic task scheduling and triggers.

These resources define WHEN tasks should execute, without being tied
to a specific provider implementation.
"""

from abc import ABC, abstractmethod
from typing import Any, Literal, Annotated, get_origin, get_args
from dataclasses import dataclass, field

# Import Dataset at runtime for trigger_datasets
# No circular dependency: scheduling -> dataset is one-way
from glacier.core.dataset import Dataset


def _extract_dataset_from_annotation(annotation: Any) -> Dataset | None:
    """
    Extract a Dataset instance from an Annotated type annotation.

    Expects: Annotated[Dataset, instance]

    Args:
        annotation: The type annotation or Dataset instance to inspect

    Returns:
        Dataset instance if found, None otherwise
    """
    # If it's already a Dataset instance, return it directly
    if isinstance(annotation, Dataset):
        return annotation

    # Check if this is an Annotated type
    if get_origin(annotation) is Annotated:
        # Extract metadata from Annotated
        args = get_args(annotation)
        # args[0] is the actual type (Dataset class)
        # args[1:] is the metadata tuple (should contain the instance)
        if len(args) > 1:
            # Search metadata for Dataset instances
            for metadata_item in args[1:]:
                if isinstance(metadata_item, Dataset):
                    return metadata_item

    return None


class ScheduleResource(ABC):
    """
    Abstract base class for scheduling resources.

    Schedule resources define when and how tasks should be triggered
    without being tied to a specific provider (EventBridge, Cloud
    Scheduler, cron, etc.).
    """

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """
        Convert to dictionary representation for infrastructure generation.

        Returns:
            Dictionary with resource configuration
        """
        pass

    @abstractmethod
    def get_type(self) -> str:
        """
        Get the resource type identifier.

        Returns:
            Resource type string ('cron', 'event', 'manual', etc.)
        """
        pass

    @abstractmethod
    def supports_provider(self, provider: str) -> bool:
        """
        Check if this resource can be compiled to the given provider.

        Args:
            provider: Provider name ('aws', 'gcp', 'azure', 'local')

        Returns:
            True if this resource supports the provider
        """
        pass


@dataclass
class CronSchedule(ScheduleResource):
    """
    Time-based scheduling using cron expressions.

    Maps to:
    - AWS EventBridge scheduled rules
    - GCP Cloud Scheduler
    - Azure Logic Apps recurrence
    - APScheduler/cron locally

    Standard cron format: "minute hour day month weekday"
    Examples:
    - "0 2 * * *" - Daily at 2:00 AM
    - "0 */4 * * *" - Every 4 hours
    - "0 9 * * 1-5" - Weekdays at 9:00 AM
    """

    cron_expression: str
    """Cron expression defining the schedule"""

    timezone: str = "UTC"
    """Timezone for schedule evaluation"""

    enabled: bool = True
    """Whether the schedule is active"""

    description: str | None = None
    """Optional description of the schedule"""

    def get_type(self) -> str:
        return "cron"

    def supports_provider(self, provider: str) -> bool:
        """Cron schedules are supported by all providers"""
        return provider in ["aws", "gcp", "azure", "local"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "cron",
            "cron_expression": self.cron_expression,
            "timezone": self.timezone,
            "enabled": self.enabled,
            "description": self.description,
        }

    def __repr__(self):
        status = "enabled" if self.enabled else "disabled"
        return f"CronSchedule({self.cron_expression}, {status})"


@dataclass
class EventTrigger(ScheduleResource):
    """
    Event-based trigger for reactive pipelines.

    Maps to:
    - AWS EventBridge events, S3 notifications
    - GCP Pub/Sub, Cloud Storage triggers
    - Azure Event Grid
    - File watchers locally

    Triggers tasks when specific Dataset(s) are updated.
    If no datasets specified, triggers on ANY input dataset update.
    """

    trigger_datasets: list[Dataset] = field(default_factory=list)
    """
    Dataset(s) that trigger this task when updated.
    Empty list = trigger on ANY input dataset update (default behavior).
    """

    event_type: Literal["created", "modified", "deleted"] = "created"
    """Type of change to trigger on"""

    filter_pattern: str | None = None
    """Optional filter pattern (e.g., '*.csv' for files)"""

    enabled: bool = True
    """Whether the trigger is active"""

    description: str | None = None
    """Optional description of the trigger"""

    def get_type(self) -> str:
        return "event"

    def supports_provider(self, provider: str) -> bool:
        """Event triggers are supported by all providers"""
        return provider in ["aws", "gcp", "azure", "local"]

    def to_dict(self) -> dict[str, Any]:
        # Serialize datasets by name for infrastructure generation
        dataset_names = [ds.name for ds in self.trigger_datasets]
        return {
            "type": "event",
            "trigger_datasets": dataset_names,
            "event_type": self.event_type,
            "filter_pattern": self.filter_pattern,
            "enabled": self.enabled,
            "description": self.description,
        }

    def __repr__(self):
        if self.trigger_datasets:
            datasets_str = ", ".join(ds.name for ds in self.trigger_datasets)
            filter_str = f", filter={self.filter_pattern}" if self.filter_pattern else ""
            return f"EventTrigger(on={datasets_str}{filter_str})"
        else:
            return "EventTrigger(on=any input)"


@dataclass
class ManualTrigger(ScheduleResource):
    """
    Manual trigger for on-demand execution.

    Represents tasks that are triggered manually via:
    - API calls
    - CLI commands
    - UI buttons
    - Other tasks in the pipeline

    This is the default if no schedule is specified.
    """

    description: str | None = None
    """Optional description"""

    def get_type(self) -> str:
        return "manual"

    def supports_provider(self, provider: str) -> bool:
        """Manual triggers are supported by all providers"""
        return provider in ["aws", "gcp", "azure", "local"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "manual",
            "description": self.description,
        }

    def __repr__(self):
        return "ManualTrigger()"


# Convenience factory functions
def cron(
    expression: str,
    timezone: str = "UTC",
    enabled: bool = True,
    description: str | None = None,
) -> CronSchedule:
    """
    Create a cron-based schedule.

    Args:
        expression: Cron expression (e.g., "0 2 * * *" for daily at 2am)
        timezone: Timezone for schedule evaluation
        enabled: Whether the schedule is active
        description: Optional description

    Returns:
        CronSchedule resource

    Example:
        # Run every day at 2 AM UTC
        @pipeline.task(schedule=cron("0 2 * * *"))
        def daily_sync() -> data:
            ...

        # Run every 4 hours
        @pipeline.task(schedule=cron("0 */4 * * *"))
        def frequent_update() -> data:
            ...

        # Run on weekdays at 9 AM Eastern
        @pipeline.task(schedule=cron("0 9 * * 1-5", timezone="America/New_York"))
        def business_hours_task() -> data:
            ...
    """
    return CronSchedule(
        cron_expression=expression,
        timezone=timezone,
        enabled=enabled,
        description=description,
    )


def on_update(
    datasets: Dataset | list[Dataset] | None = None,
    event_type: Literal["created", "modified", "deleted"] = "created",
    filter_pattern: str | None = None,
    enabled: bool = True,
    description: str | None = None,
) -> EventTrigger:
    """
    Create an event-based trigger on Dataset updates.

    Args:
        datasets: Dataset(s) to watch for updates. None or empty = trigger on ANY input dataset
        event_type: Type of change to trigger on (created, modified, deleted)
        filter_pattern: Optional filter pattern (e.g., '*.csv' for files)
        enabled: Whether the trigger is active
        description: Optional description

    Returns:
        EventTrigger resource

    Example:
        # Trigger when specific dataset updates
        raw_data = Dataset(name="raw_data", storage=...)
        reference_data = Dataset(name="reference_data", storage=...)

        @pipeline.task(schedule=on_update(raw_data, filter_pattern="*.csv"))
        def process(data: raw_data, ref: reference_data) -> output:
            # Triggers when raw_data updates, not when reference_data updates
            ...

        # Trigger on multiple datasets
        @pipeline.task(schedule=on_update([raw_data, api_data]))
        def merge(data1: raw_data, data2: api_data, data3: static_data) -> output:
            # Triggers when EITHER raw_data OR api_data updates
            # static_data changes don't trigger this
            ...

        # Trigger on ANY input dataset update (default)
        @pipeline.task(schedule=on_update())
        def process_any(data1: raw_data, data2: api_data) -> output:
            # Triggers when ANY input dataset updates
            ...
    """
    # Normalize to list and extract Dataset instances from Annotated types
    if datasets is None:
        dataset_list = []
    elif isinstance(datasets, list):
        dataset_list = datasets
    else:
        dataset_list = [datasets]

    # Extract actual Dataset instances from Annotated types
    extracted_datasets = []
    for ds in dataset_list:
        extracted = _extract_dataset_from_annotation(ds)
        if extracted is not None:
            extracted_datasets.append(extracted)

    return EventTrigger(
        trigger_datasets=extracted_datasets,
        event_type=event_type,
        filter_pattern=filter_pattern,
        enabled=enabled,
        description=description,
    )


def manual(description: str | None = None) -> ManualTrigger:
    """
    Create a manual trigger (default).

    Args:
        description: Optional description

    Returns:
        ManualTrigger resource

    Example:
        # Explicit manual trigger
        @pipeline.task(schedule=manual("Run via API"))
        def on_demand_task() -> data:
            ...

        # Or just omit schedule parameter (defaults to manual)
        @pipeline.task()
        def another_task() -> data:
            ...
    """
    return ManualTrigger(description=description)
