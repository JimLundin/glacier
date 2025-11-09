"""
Monitoring and observability for pipeline execution.

Provides provider-agnostic logging, metrics, and alerting.
"""

from glacier.monitoring.resources import (
    MonitoringConfig,
    NotificationChannel,
    LoggingConfig,
    MetricsConfig,
    monitoring,
    notify_email,
    notify_slack,
    notify_webhook,
)

__all__ = [
    "MonitoringConfig",
    "NotificationChannel",
    "LoggingConfig",
    "MetricsConfig",
    "monitoring",
    "notify_email",
    "notify_slack",
    "notify_webhook",
]
