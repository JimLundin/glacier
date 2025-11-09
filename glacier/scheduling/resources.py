"""
Scheduling Resources: Provider-agnostic task scheduling and triggers.

These resources define WHEN tasks should execute, without being tied
to a specific provider implementation.
"""

from abc import ABC, abstractmethod
from typing import Any, Literal
from dataclasses import dataclass


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

    Triggers tasks when events occur (file uploads, queue messages, etc.)
    """

    event_source: str
    """Source of events (storage bucket, queue, topic, etc.)"""

    event_type: Literal[
        "object_created",
        "object_deleted",
        "queue_message",
        "topic_message",
        "webhook",
        "custom",
    ] = "object_created"
    """Type of event to trigger on"""

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
        return {
            "type": "event",
            "event_source": self.event_source,
            "event_type": self.event_type,
            "filter_pattern": self.filter_pattern,
            "enabled": self.enabled,
            "description": self.description,
        }

    def __repr__(self):
        filter_str = f", filter={self.filter_pattern}" if self.filter_pattern else ""
        return f"EventTrigger({self.event_type} from {self.event_source}{filter_str})"


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


def on_event(
    source: str,
    event_type: Literal[
        "object_created",
        "object_deleted",
        "queue_message",
        "topic_message",
        "webhook",
        "custom",
    ] = "object_created",
    filter_pattern: str | None = None,
    enabled: bool = True,
    description: str | None = None,
) -> EventTrigger:
    """
    Create an event-based trigger.

    Args:
        source: Event source (bucket name, queue name, topic name, etc.)
        event_type: Type of event to trigger on
        filter_pattern: Optional filter pattern (e.g., '*.csv')
        enabled: Whether the trigger is active
        description: Optional description

    Returns:
        EventTrigger resource

    Example:
        # Trigger when CSV files are uploaded
        @pipeline.task(schedule=on_event(
            source="raw-data-bucket",
            event_type="object_created",
            filter_pattern="*.csv"
        ))
        def process_new_file(file_path: str) -> processed:
            ...

        # Trigger on queue messages
        @pipeline.task(schedule=on_event(
            source="work-queue",
            event_type="queue_message"
        ))
        def handle_message(message: dict) -> result:
            ...
    """
    return EventTrigger(
        event_source=source,
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
