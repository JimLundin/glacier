"""
Monitoring Resources: Provider-agnostic observability configuration.

These resources define logging, metrics, and alerting without being tied
to a specific provider implementation.
"""

from typing import Any, Literal
from dataclasses import dataclass, field


@dataclass
class LoggingConfig:
    """
    Configuration for structured logging.

    Maps to:
    - CloudWatch Logs on AWS
    - Cloud Logging on GCP
    - Azure Monitor Logs on Azure
    - Python logging locally
    """

    enabled: bool = True
    """Whether logging is enabled"""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    """Minimum log level to capture"""

    retention_days: int = 30
    """How long to retain logs"""

    structured: bool = True
    """Use structured (JSON) logging"""

    include_context: bool = True
    """Include task/pipeline context in logs"""

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "level": self.level,
            "retention_days": self.retention_days,
            "structured": self.structured,
            "include_context": self.include_context,
        }

    def __repr__(self):
        return f"LoggingConfig(level={self.level}, retention={self.retention_days}d)"


@dataclass
class MetricsConfig:
    """
    Configuration for metrics collection.

    Maps to:
    - CloudWatch Metrics on AWS
    - Cloud Monitoring on GCP
    - Azure Monitor Metrics on Azure
    - Prometheus/StatsD locally

    Automatically tracks:
    - Task execution duration
    - Success/failure rates
    - Data volumes processed
    - Resource utilization
    """

    enabled: bool = True
    """Whether metrics collection is enabled"""

    track_duration: bool = True
    """Track task execution time"""

    track_success_rate: bool = True
    """Track success/failure rates"""

    track_data_volume: bool = True
    """Track data size processed"""

    track_resource_usage: bool = False
    """Track CPU/memory usage (may have performance impact)"""

    custom_metrics: dict[str, str] | None = None
    """Custom metric definitions"""

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "track_duration": self.track_duration,
            "track_success_rate": self.track_success_rate,
            "track_data_volume": self.track_data_volume,
            "track_resource_usage": self.track_resource_usage,
            "custom_metrics": self.custom_metrics or {},
        }

    def __repr__(self):
        metrics = []
        if self.track_duration:
            metrics.append("duration")
        if self.track_success_rate:
            metrics.append("success_rate")
        if self.track_data_volume:
            metrics.append("data_volume")
        return f"MetricsConfig({', '.join(metrics)})"


@dataclass
class NotificationChannel:
    """
    Channel for sending alerts and notifications.

    Maps to:
    - SNS/SES on AWS
    - Pub/Sub on GCP
    - Azure Monitor action groups on Azure
    - SMTP/webhooks locally

    Supports multiple notification types:
    - Email
    - Slack
    - PagerDuty
    - Custom webhooks
    """

    type: Literal["email", "slack", "pagerduty", "sns", "webhook", "custom"]
    """Type of notification channel"""

    destination: str
    """Where to send notifications (email, webhook URL, SNS ARN, etc.)"""

    name: str | None = None
    """Optional name for this channel"""

    enabled: bool = True
    """Whether this channel is active"""

    notify_on_failure: bool = True
    """Send notifications on task failures"""

    notify_on_success: bool = False
    """Send notifications on successful completion"""

    notify_on_start: bool = False
    """Send notifications when tasks start"""

    metadata: dict[str, Any] | None = None
    """Additional provider-specific metadata"""

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "destination": self.destination,
            "name": self.name,
            "enabled": self.enabled,
            "notify_on_failure": self.notify_on_failure,
            "notify_on_success": self.notify_on_success,
            "notify_on_start": self.notify_on_start,
            "metadata": self.metadata or {},
        }

    def __repr__(self):
        name_str = f"{self.name}: " if self.name else ""
        return f"NotificationChannel({name_str}{self.type} -> {self.destination})"


@dataclass
class MonitoringConfig:
    """
    Complete monitoring configuration for pipelines and tasks.

    Combines logging, metrics, and alerting into a single configuration
    that can be applied at pipeline or task level.

    Maps to:
    - CloudWatch (Logs + Metrics + Alarms) on AWS
    - Cloud Monitoring + Cloud Logging on GCP
    - Azure Monitor on Azure
    - Python logging + Prometheus locally
    """

    logging: LoggingConfig = field(default_factory=LoggingConfig)
    """Logging configuration"""

    metrics: MetricsConfig = field(default_factory=MetricsConfig)
    """Metrics configuration"""

    notifications: list[NotificationChannel] = field(default_factory=list)
    """Notification channels for alerts"""

    alert_on_failure: bool = True
    """Send alerts when tasks fail"""

    alert_on_slow_execution: bool = False
    """Send alerts when tasks exceed expected duration"""

    slow_threshold_multiplier: float = 2.0
    """Multiplier for slow execution alerts (2.0 = alert if 2x baseline)"""

    enable_tracing: bool = False
    """Enable distributed tracing (may have performance impact)"""

    def add_notification(self, channel: NotificationChannel) -> "MonitoringConfig":
        """
        Add a notification channel.

        Args:
            channel: Notification channel to add

        Returns:
            Self for chaining
        """
        self.notifications.append(channel)
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "logging": self.logging.to_dict(),
            "metrics": self.metrics.to_dict(),
            "notifications": [n.to_dict() for n in self.notifications],
            "alert_on_failure": self.alert_on_failure,
            "alert_on_slow_execution": self.alert_on_slow_execution,
            "slow_threshold_multiplier": self.slow_threshold_multiplier,
            "enable_tracing": self.enable_tracing,
        }

    def __repr__(self):
        components = []
        if self.logging.enabled:
            components.append(f"logging({self.logging.level})")
        if self.metrics.enabled:
            components.append("metrics")
        if self.notifications:
            components.append(f"{len(self.notifications)} channels")
        return f"MonitoringConfig({', '.join(components)})"


# Convenience factory functions
def monitoring(
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO",
    log_retention_days: int = 30,
    enable_metrics: bool = True,
    alert_on_failure: bool = True,
    notifications: list[NotificationChannel] | None = None,
) -> MonitoringConfig:
    """
    Create a monitoring configuration with common defaults.

    Args:
        log_level: Minimum log level to capture
        log_retention_days: How long to retain logs
        enable_metrics: Whether to collect metrics
        alert_on_failure: Send alerts on task failures
        notifications: List of notification channels

    Returns:
        MonitoringConfig

    Example:
        # Simple monitoring with email alerts
        config = monitoring(
            log_level="INFO",
            notifications=[notify_email("alerts@example.com")]
        )

        # Apply to pipeline
        pipeline = Pipeline(name="etl", monitoring=config)

        # Or apply to specific task
        @pipeline.task(monitoring=monitoring(log_level="DEBUG"))
        def debug_task() -> data:
            ...
    """
    return MonitoringConfig(
        logging=LoggingConfig(level=log_level, retention_days=log_retention_days),
        metrics=MetricsConfig(enabled=enable_metrics),
        notifications=notifications or [],
        alert_on_failure=alert_on_failure,
    )


def notify_email(
    email: str,
    name: str | None = None,
    notify_on_success: bool = False,
    notify_on_failure: bool = True,
) -> NotificationChannel:
    """
    Create an email notification channel.

    Args:
        email: Email address to send notifications to
        name: Optional name for this channel
        notify_on_success: Send notifications on success
        notify_on_failure: Send notifications on failure

    Returns:
        NotificationChannel configured for email

    Example:
        channel = notify_email("alerts@example.com", name="Team Alerts")
    """
    return NotificationChannel(
        type="email",
        destination=email,
        name=name,
        notify_on_success=notify_on_success,
        notify_on_failure=notify_on_failure,
    )


def notify_slack(
    webhook_url: str,
    name: str | None = None,
    notify_on_success: bool = False,
    notify_on_failure: bool = True,
) -> NotificationChannel:
    """
    Create a Slack notification channel.

    Args:
        webhook_url: Slack webhook URL
        name: Optional name for this channel
        notify_on_success: Send notifications on success
        notify_on_failure: Send notifications on failure

    Returns:
        NotificationChannel configured for Slack

    Example:
        channel = notify_slack(
            "https://hooks.slack.com/services/...",
            name="Engineering Channel"
        )
    """
    return NotificationChannel(
        type="slack",
        destination=webhook_url,
        name=name,
        notify_on_success=notify_on_success,
        notify_on_failure=notify_on_failure,
    )


def notify_webhook(
    url: str,
    name: str | None = None,
    notify_on_success: bool = False,
    notify_on_failure: bool = True,
    metadata: dict[str, Any] | None = None,
) -> NotificationChannel:
    """
    Create a custom webhook notification channel.

    Args:
        url: Webhook URL to POST notifications to
        name: Optional name for this channel
        notify_on_success: Send notifications on success
        notify_on_failure: Send notifications on failure
        metadata: Additional metadata (headers, auth, etc.)

    Returns:
        NotificationChannel configured for webhook

    Example:
        channel = notify_webhook(
            "https://api.example.com/alerts",
            name="Custom System",
            metadata={"auth_token": "secret"}
        )
    """
    return NotificationChannel(
        type="webhook",
        destination=url,
        name=name,
        notify_on_success=notify_on_success,
        notify_on_failure=notify_on_failure,
        metadata=metadata,
    )
