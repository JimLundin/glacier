"""
AWS Compiler: Converts Glacier pipelines to AWS Pulumi resources.

Generates infrastructure definitions for deploying pipelines on AWS:
- Lambda functions for tasks
- S3 buckets for datasets
- EventBridge rules for scheduling
- CloudWatch for monitoring
- Secrets Manager for secrets
"""

from typing import Any, TYPE_CHECKING
from glacier.compilation.pulumi_compiler import PulumiCompiler, CompilationError

if TYPE_CHECKING:
    from glacier.core.pipeline import Pipeline
    from glacier.core.task import Task
    from glacier.core.dataset import Dataset


class AWSCompiler(PulumiCompiler):
    """
    Compiles Glacier pipelines to AWS infrastructure via Pulumi.
    """

    def __init__(
        self,
        account: str,
        region: str = "us-east-1",
        project_name: str | None = None,
        lambda_runtime: str = "python3.11",
        lambda_memory: int = 512,
        lambda_timeout: int = 300,
    ):
        """
        Initialize AWS compiler.

        Args:
            account: AWS account ID
            region: AWS region
            project_name: Optional Pulumi project name override
            lambda_runtime: Lambda runtime version
            lambda_memory: Default Lambda memory in MB
            lambda_timeout: Default Lambda timeout in seconds
        """
        super().__init__(region=region, project_name=project_name)
        self.account = account
        self.lambda_runtime = lambda_runtime
        self.lambda_memory = lambda_memory
        self.lambda_timeout = lambda_timeout

    def get_provider_name(self) -> str:
        return "aws"

    def _compile_storage(self, pipeline: 'Pipeline') -> dict[str, Any]:
        """
        Compile storage resources (S3 buckets) for datasets.

        Creates an S3 bucket for each dataset that has storage configured.
        """
        resources = {}

        for dataset in pipeline.datasets:
            # Check if dataset has storage configuration
            if hasattr(dataset, 'storage') and dataset.storage is not None:
                bucket_name = self._get_bucket_name(pipeline, dataset)
                resources[bucket_name] = {
                    "type": "s3_bucket",
                    "dataset": dataset.name,
                    "bucket_name": bucket_name,
                    "storage_config": dataset.storage,
                }

        return resources

    def _compile_compute(self, pipeline: 'Pipeline') -> dict[str, Any]:
        """
        Compile compute resources (Lambda functions) for tasks.

        Creates a Lambda function for each task in the pipeline.
        """
        resources = {}

        for task in pipeline.tasks:
            function_name = self._get_function_name(pipeline, task)

            # Extract compute configuration from task
            compute_config = getattr(task, 'compute', None)
            memory = self.lambda_memory
            timeout = self.lambda_timeout

            # Override with task-specific config if provided
            if compute_config:
                if hasattr(compute_config, 'memory'):
                    memory = compute_config.memory
                if hasattr(compute_config, 'timeout'):
                    timeout = compute_config.timeout

            resources[function_name] = {
                "type": "lambda_function",
                "task": task.name,
                "function_name": function_name,
                "handler": f"{task.name}.handler",
                "runtime": self.lambda_runtime,
                "memory": memory,
                "timeout": timeout,
                "code_path": f"./.glacier/compiled/{task.name}",
                "inputs": [ds.name for ds in task.inputs],
                "outputs": [ds.name for ds in task.outputs],
            }

            # Create IAM role for Lambda
            role_name = f"{function_name}-role"
            resources[role_name] = {
                "type": "iam_role",
                "function": function_name,
                "role_name": role_name,
            }

            # Attach policies for S3 access
            policy_name = f"{function_name}-policy"
            resources[policy_name] = {
                "type": "iam_role_policy",
                "role": role_name,
                "policy_name": policy_name,
            }

        return resources

    def _compile_scheduling(self, pipeline: 'Pipeline') -> dict[str, Any]:
        """
        Compile scheduling resources (EventBridge rules) for scheduled tasks.

        Creates EventBridge rules for tasks with cron or event-based schedules.
        """
        resources = {}

        for task in pipeline.tasks:
            schedule = getattr(task, 'schedule', None)
            if schedule is None:
                continue

            rule_name = self._get_rule_name(pipeline, task)
            function_name = self._get_function_name(pipeline, task)

            # Determine schedule type
            schedule_type = type(schedule).__name__

            if schedule_type == "CronSchedule":
                # Cron-based schedule
                resources[rule_name] = {
                    "type": "eventbridge_cron_rule",
                    "task": task.name,
                    "rule_name": rule_name,
                    "function": function_name,
                    "cron_expression": schedule.expression,
                }
            elif schedule_type == "EventTrigger":
                # Event-based trigger (S3 upload, etc.)
                resources[rule_name] = {
                    "type": "eventbridge_event_rule",
                    "task": task.name,
                    "rule_name": rule_name,
                    "function": function_name,
                    "trigger_datasets": [ds.name for ds in schedule.datasets],
                    "filter_pattern": getattr(schedule, 'filter_pattern', None),
                }

            # Create Lambda permission for EventBridge
            permission_name = f"{function_name}-eventbridge-permission"
            resources[permission_name] = {
                "type": "lambda_permission",
                "function": function_name,
                "permission_name": permission_name,
                "principal": "events.amazonaws.com",
                "source_arn": f"rule:{rule_name}",
            }

            # Create EventBridge target
            target_name = f"{rule_name}-target"
            resources[target_name] = {
                "type": "eventbridge_target",
                "rule": rule_name,
                "target_name": target_name,
                "function": function_name,
            }

        return resources

    def _compile_monitoring(self, pipeline: 'Pipeline') -> dict[str, Any]:
        """
        Compile monitoring resources (CloudWatch logs, metrics, alarms).
        """
        resources = {}

        # Check for pipeline-level monitoring config
        monitoring_config = getattr(pipeline, 'monitoring', None)

        for task in pipeline.tasks:
            function_name = self._get_function_name(pipeline, task)

            # CloudWatch log group for Lambda
            log_group_name = f"{function_name}-logs"
            retention_days = 30  # Default

            if monitoring_config and hasattr(monitoring_config, 'log_retention_days'):
                retention_days = monitoring_config.log_retention_days

            resources[log_group_name] = {
                "type": "cloudwatch_log_group",
                "function": function_name,
                "log_group_name": f"/aws/lambda/{function_name}",
                "retention_days": retention_days,
            }

            # CloudWatch alarm for Lambda errors
            if monitoring_config and getattr(monitoring_config, 'alert_on_failure', False):
                alarm_name = f"{function_name}-errors-alarm"
                resources[alarm_name] = {
                    "type": "cloudwatch_alarm",
                    "function": function_name,
                    "alarm_name": alarm_name,
                    "metric_name": "Errors",
                    "threshold": 1,
                }

                # SNS topic for notifications
                if hasattr(monitoring_config, 'notifications') and monitoring_config.notifications:
                    topic_name = f"{pipeline.name}-alerts"
                    if topic_name not in resources:
                        resources[topic_name] = {
                            "type": "sns_topic",
                            "topic_name": topic_name,
                            "notifications": monitoring_config.notifications,
                        }

                    # Subscribe alarm to SNS topic
                    resources[alarm_name]["sns_topic"] = topic_name

        return resources

    def _compile_secrets(self, pipeline: 'Pipeline') -> dict[str, Any]:
        """
        Compile secrets resources (Secrets Manager secrets).
        """
        resources = {}

        # Check if pipeline uses any secrets
        # This would be populated if Environment.secret() was called
        # For now, we'll create a placeholder for future implementation

        return resources

    def _to_python_identifier(self, name: str) -> str:
        """Convert a resource name to a valid Python identifier."""
        return name.replace("-", "_")

    def _generate_resource_code(self, resource_name: str, resource_def: dict) -> str:
        """
        Generate Pulumi Python code for a specific AWS resource.
        """
        resource_type = resource_def["type"]

        if resource_type == "s3_bucket":
            return self._generate_s3_bucket_code(resource_name, resource_def)
        elif resource_type == "lambda_function":
            return self._generate_lambda_function_code(resource_name, resource_def)
        elif resource_type == "iam_role":
            return self._generate_iam_role_code(resource_name, resource_def)
        elif resource_type == "iam_role_policy":
            return self._generate_iam_policy_code(resource_name, resource_def)
        elif resource_type == "eventbridge_cron_rule":
            return self._generate_eventbridge_cron_code(resource_name, resource_def)
        elif resource_type == "eventbridge_event_rule":
            return self._generate_eventbridge_event_code(resource_name, resource_def)
        elif resource_type == "eventbridge_target":
            return self._generate_eventbridge_target_code(resource_name, resource_def)
        elif resource_type == "lambda_permission":
            return self._generate_lambda_permission_code(resource_name, resource_def)
        elif resource_type == "cloudwatch_log_group":
            return self._generate_cloudwatch_log_group_code(resource_name, resource_def)
        elif resource_type == "cloudwatch_alarm":
            return self._generate_cloudwatch_alarm_code(resource_name, resource_def)
        elif resource_type == "sns_topic":
            return self._generate_sns_topic_code(resource_name, resource_def)
        else:
            return f"# Unknown resource type: {resource_type}"

    def _generate_s3_bucket_code(self, name: str, resource_def: dict) -> str:
        var_name = self._to_python_identifier(name)
        bucket_name = resource_def["bucket_name"]
        return f'''
# S3 Bucket for dataset: {resource_def["dataset"]}
{var_name} = aws.s3.BucketV2(
    "{name}",
    bucket="{bucket_name}",
    tags={{"dataset": "{resource_def["dataset"]}"}}
)
'''

    def _generate_lambda_function_code(self, name: str, resource_def: dict) -> str:
        var_name = self._to_python_identifier(name)
        function_name = resource_def["function_name"]
        role_name = self._to_python_identifier(resource_def["function_name"] + "-role")
        return f'''
# Lambda function for task: {resource_def["task"]}
{var_name} = aws.lambda_.Function(
    "{name}",
    name="{function_name}",
    handler="{resource_def["handler"]}",
    runtime="{resource_def["runtime"]}",
    memory_size={resource_def["memory"]},
    timeout={resource_def["timeout"]},
    role={role_name}.arn,
    code=pulumi.FileArchive("{resource_def["code_path"]}"),
    tags={{"task": "{resource_def["task"]}"}}
)
'''

    def _generate_iam_role_code(self, name: str, resource_def: dict) -> str:
        var_name = self._to_python_identifier(name)
        role_name = resource_def["role_name"]
        return f'''
# IAM role for Lambda function
{var_name} = aws.iam.Role(
    "{name}",
    name="{role_name}",
    assume_role_policy="""{{
        "Version": "2012-10-17",
        "Statement": [{{
            "Effect": "Allow",
            "Principal": {{"Service": "lambda.amazonaws.com"}},
            "Action": "sts:AssumeRole"
        }}]
    }}"""
)
'''

    def _generate_iam_policy_code(self, name: str, resource_def: dict) -> str:
        var_name = self._to_python_identifier(name)
        role_name = self._to_python_identifier(resource_def["role"])
        return f'''
# IAM policy for Lambda function
{var_name} = aws.iam.RolePolicy(
    "{name}",
    role={role_name}.name,
    policy="""{{
        "Version": "2012-10-17",
        "Statement": [
            {{
                "Effect": "Allow",
                "Action": ["s3:*"],
                "Resource": "*"
            }},
            {{
                "Effect": "Allow",
                "Action": ["logs:*"],
                "Resource": "*"
            }}
        ]
    }}"""
)
'''

    def _generate_eventbridge_cron_code(self, name: str, resource_def: dict) -> str:
        var_name = self._to_python_identifier(name)
        rule_name = resource_def["rule_name"]
        return f'''
# EventBridge cron rule for task: {resource_def["task"]}
{var_name} = aws.cloudwatch.EventRule(
    "{name}",
    name="{rule_name}",
    schedule_expression="cron({resource_def["cron_expression"]})",
    tags={{"task": "{resource_def["task"]}"}}
)
'''

    def _generate_eventbridge_event_code(self, name: str, resource_def: dict) -> str:
        var_name = self._to_python_identifier(name)
        rule_name = resource_def["rule_name"]
        return f'''
# EventBridge event rule for task: {resource_def["task"]}
{var_name} = aws.cloudwatch.EventRule(
    "{name}",
    name="{rule_name}",
    event_pattern="""{{
        "source": ["aws.s3"],
        "detail-type": ["Object Created"]
    }}""",
    tags={{"task": "{resource_def["task"]}"}}
)
'''

    def _generate_eventbridge_target_code(self, name: str, resource_def: dict) -> str:
        var_name = self._to_python_identifier(name)
        rule_name = self._to_python_identifier(resource_def["rule"])
        function_name = self._to_python_identifier(resource_def["function"])
        return f'''
# EventBridge target
{var_name} = aws.cloudwatch.EventTarget(
    "{name}",
    rule={rule_name}.name,
    arn={function_name}.arn
)
'''

    def _generate_lambda_permission_code(self, name: str, resource_def: dict) -> str:
        var_name = self._to_python_identifier(name)
        function_name = self._to_python_identifier(resource_def["function"])
        return f'''
# Lambda permission for EventBridge
{var_name} = aws.lambda_.Permission(
    "{name}",
    action="lambda:InvokeFunction",
    function={function_name}.name,
    principal="{resource_def["principal"]}"
)
'''

    def _generate_cloudwatch_log_group_code(self, name: str, resource_def: dict) -> str:
        var_name = self._to_python_identifier(name)
        log_group_name = resource_def["log_group_name"]
        return f'''
# CloudWatch log group for Lambda
{var_name} = aws.cloudwatch.LogGroup(
    "{name}",
    name="{log_group_name}",
    retention_in_days={resource_def["retention_days"]}
)
'''

    def _generate_cloudwatch_alarm_code(self, name: str, resource_def: dict) -> str:
        var_name = self._to_python_identifier(name)
        alarm_name = resource_def["alarm_name"]
        function_name = self._to_python_identifier(resource_def["function"])
        sns_topic = resource_def.get("sns_topic")
        sns_topic_var = self._to_python_identifier(sns_topic) if sns_topic else None
        alarm_actions = f"[{sns_topic_var}.arn]" if sns_topic_var else "[]"
        return f'''
# CloudWatch alarm for Lambda errors
{var_name} = aws.cloudwatch.MetricAlarm(
    "{name}",
    name="{alarm_name}",
    comparison_operator="GreaterThanThreshold",
    evaluation_periods=1,
    metric_name="{resource_def["metric_name"]}",
    namespace="AWS/Lambda",
    period=300,
    statistic="Sum",
    threshold={resource_def["threshold"]},
    alarm_actions={alarm_actions},
    dimensions={{"FunctionName": {function_name}.name}}
)
'''

    def _generate_sns_topic_code(self, name: str, resource_def: dict) -> str:
        var_name = self._to_python_identifier(name)
        topic_name = resource_def["topic_name"]
        return f'''
# SNS topic for alerts
{var_name} = aws.sns.Topic(
    "{name}",
    name="{topic_name}"
)
'''

    def _generate_imports(self) -> str:
        """Generate import statements for AWS Pulumi program."""
        return """import pulumi
import pulumi_aws as aws"""

    def _get_pulumi_dependencies(self) -> list[str]:
        """Get list of Python dependencies for AWS Pulumi program."""
        return [
            "pulumi>=3.0.0",
            "pulumi-aws>=6.0.0",
        ]

    # Helper methods for resource naming
    def _get_bucket_name(self, pipeline: 'Pipeline', dataset: 'Dataset') -> str:
        """Generate S3 bucket name for dataset."""
        return f"{pipeline.name}-{dataset.name}".replace("_", "-")

    def _get_function_name(self, pipeline: 'Pipeline', task: 'Task') -> str:
        """Generate Lambda function name for task."""
        return f"{pipeline.name}-{task.name}".replace("_", "-")

    def _get_rule_name(self, pipeline: 'Pipeline', task: 'Task') -> str:
        """Generate EventBridge rule name for task."""
        return f"{pipeline.name}-{task.name}-rule".replace("_", "-")
