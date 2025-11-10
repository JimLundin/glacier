"""
AWS Compiler: Converts Glacier pipelines to AWS Pulumi resources.

Creates actual Pulumi resource objects for deploying pipelines on AWS:
- Lambda functions for tasks
- S3 buckets for datasets
- EventBridge rules for scheduling
- CloudWatch for monitoring
- Secrets Manager for secrets
"""

from typing import Any, TYPE_CHECKING

try:
    import pulumi
    import pulumi_aws as aws
except ImportError:
    raise ImportError(
        "pulumi and pulumi_aws required for AWSCompiler. "
        "Install with: pip install pulumi pulumi-aws"
    )

from glacier.compilation.compiler import Compiler, CompiledPipeline, CompilationError

if TYPE_CHECKING:
    from glacier.core.pipeline import Pipeline
    from glacier.core.task import Task
    from glacier.core.dataset import Dataset


class AWSCompiler(Compiler):
    """
    Compiles Glacier pipelines to AWS infrastructure via Pulumi.

    Creates actual Pulumi resource objects that are registered with
    the Pulumi runtime.
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
            project_name: Optional project name
            lambda_runtime: Lambda runtime version
            lambda_memory: Default Lambda memory in MB
            lambda_timeout: Default Lambda timeout in seconds
        """
        self.account = account
        self.region = region
        self.project_name = project_name
        self.lambda_runtime = lambda_runtime
        self.lambda_memory = lambda_memory
        self.lambda_timeout = lambda_timeout

    def get_provider_name(self) -> str:
        return "aws"

    def compile(self, pipeline: 'Pipeline') -> CompiledPipeline:
        """
        Compile a pipeline to AWS Pulumi resources.

        Args:
            pipeline: The pipeline to compile

        Returns:
            CompiledPipeline with actual Pulumi resource objects

        Raises:
            CompilationError: If compilation fails
        """
        try:
            # Validate pipeline
            pipeline.validate()

            # Create resources
            resources = {}

            # Compile storage resources (S3 buckets)
            storage_resources = self._compile_storage(pipeline)
            resources.update(storage_resources)

            # Compile compute resources (Lambda functions)
            compute_resources = self._compile_compute(pipeline, storage_resources)
            resources.update(compute_resources)

            # Compile scheduling resources (EventBridge rules)
            scheduling_resources = self._compile_scheduling(pipeline, compute_resources)
            resources.update(scheduling_resources)

            # Compile monitoring resources (CloudWatch)
            monitoring_resources = self._compile_monitoring(pipeline, compute_resources)
            resources.update(monitoring_resources)

            # Compile secrets resources (Secrets Manager)
            secrets_resources = self._compile_secrets(pipeline)
            resources.update(secrets_resources)

            return CompiledPipeline(
                pipeline_name=pipeline.name,
                resources=resources,
                metadata={
                    "region": self.region,
                    "account": self.account,
                    "task_count": len(pipeline.tasks),
                    "dataset_count": len(pipeline.datasets),
                }
            )

        except Exception as e:
            raise CompilationError(f"Failed to compile pipeline '{pipeline.name}': {e}") from e

    def _compile_storage(self, pipeline: 'Pipeline') -> dict[str, Any]:
        """
        Create S3 buckets for datasets with storage configuration.

        Returns:
            Dictionary mapping resource names to Pulumi S3 bucket objects
        """
        resources = {}

        for dataset in pipeline.datasets:
            # Check if dataset has storage configuration
            if hasattr(dataset, 'storage') and dataset.storage is not None:
                bucket_name = self._get_bucket_name(pipeline, dataset)

                # Create actual S3 bucket resource
                bucket = aws.s3.BucketV2(
                    bucket_name,
                    bucket=bucket_name,
                    tags={
                        "dataset": dataset.name,
                        "pipeline": pipeline.name,
                    }
                )

                resources[bucket_name] = bucket

        return resources

    def _compile_compute(self, pipeline: 'Pipeline', storage_resources: dict[str, Any]) -> dict[str, Any]:
        """
        Create Lambda functions for tasks.

        Args:
            pipeline: Source pipeline
            storage_resources: Storage resources created earlier

        Returns:
            Dictionary mapping resource names to Pulumi Lambda and IAM objects
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

            # Create IAM role for Lambda
            role_name = f"{function_name}-role"
            role = aws.iam.Role(
                role_name,
                name=role_name,
                assume_role_policy=pulumi.Output.from_input({
                    "Version": "2012-10-17",
                    "Statement": [{
                        "Effect": "Allow",
                        "Principal": {"Service": "lambda.amazonaws.com"},
                        "Action": "sts:AssumeRole"
                    }]
                }).apply(lambda policy: pulumi.Output.json_dumps(policy))
            )
            resources[role_name] = role

            # Create IAM policy for Lambda to access S3 and CloudWatch
            policy_name = f"{function_name}-policy"
            policy = aws.iam.RolePolicy(
                policy_name,
                role=role.name,
                policy=pulumi.Output.from_input({
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Action": ["s3:*"],
                            "Resource": "*"
                        },
                        {
                            "Effect": "Allow",
                            "Action": ["logs:*"],
                            "Resource": "*"
                        }
                    ]
                }).apply(lambda policy: pulumi.Output.json_dumps(policy))
            )
            resources[policy_name] = policy

            # Create Lambda function
            function = aws.lambda_.Function(
                function_name,
                name=function_name,
                handler=f"{task.name}.handler",
                runtime=self.lambda_runtime,
                memory_size=memory,
                timeout=timeout,
                role=role.arn,
                code=pulumi.FileArchive(f"./.glacier/compiled/{task.name}"),
                tags={
                    "task": task.name,
                    "pipeline": pipeline.name,
                }
            )
            resources[function_name] = function

        return resources

    def _compile_scheduling(self, pipeline: 'Pipeline', compute_resources: dict[str, Any]) -> dict[str, Any]:
        """
        Create EventBridge rules for scheduled tasks.

        Args:
            pipeline: Source pipeline
            compute_resources: Compute resources (Lambda functions)

        Returns:
            Dictionary mapping resource names to Pulumi EventBridge objects
        """
        resources = {}

        for task in pipeline.tasks:
            schedule = getattr(task, 'schedule', None)
            if schedule is None:
                continue

            function_name = self._get_function_name(pipeline, task)
            function = compute_resources.get(function_name)
            if function is None:
                continue

            rule_name = self._get_rule_name(pipeline, task)
            schedule_type = type(schedule).__name__

            # Create EventBridge rule
            if schedule_type == "CronSchedule":
                # Cron-based schedule
                rule = aws.cloudwatch.EventRule(
                    rule_name,
                    name=rule_name,
                    schedule_expression=f"cron({schedule.expression})",
                    tags={
                        "task": task.name,
                        "pipeline": pipeline.name,
                    }
                )
            elif schedule_type == "EventTrigger":
                # Event-based trigger (S3 upload, etc.)
                rule = aws.cloudwatch.EventRule(
                    rule_name,
                    name=rule_name,
                    event_pattern=pulumi.Output.from_input({
                        "source": ["aws.s3"],
                        "detail-type": ["Object Created"]
                    }).apply(lambda pattern: pulumi.Output.json_dumps(pattern)),
                    tags={
                        "task": task.name,
                        "pipeline": pipeline.name,
                    }
                )
            else:
                continue

            resources[rule_name] = rule

            # Create EventBridge target
            target_name = f"{rule_name}-target"
            target = aws.cloudwatch.EventTarget(
                target_name,
                rule=rule.name,
                arn=function.arn
            )
            resources[target_name] = target

            # Create Lambda permission for EventBridge
            permission_name = f"{function_name}-eventbridge-permission"
            permission = aws.lambda_.Permission(
                permission_name,
                action="lambda:InvokeFunction",
                function=function.name,
                principal="events.amazonaws.com",
                source_arn=rule.arn
            )
            resources[permission_name] = permission

        return resources

    def _compile_monitoring(self, pipeline: 'Pipeline', compute_resources: dict[str, Any]) -> dict[str, Any]:
        """
        Create CloudWatch log groups and alarms for monitoring.

        Args:
            pipeline: Source pipeline
            compute_resources: Compute resources (Lambda functions)

        Returns:
            Dictionary mapping resource names to Pulumi CloudWatch objects
        """
        resources = {}

        # Check for pipeline-level monitoring config
        monitoring_config = getattr(pipeline, 'monitoring', None)

        for task in pipeline.tasks:
            function_name = self._get_function_name(pipeline, task)
            function = compute_resources.get(function_name)
            if function is None:
                continue

            # CloudWatch log group for Lambda
            log_group_name = f"{function_name}-logs"
            retention_days = 30  # Default

            if monitoring_config and hasattr(monitoring_config, 'log_retention_days'):
                retention_days = monitoring_config.log_retention_days

            log_group = aws.cloudwatch.LogGroup(
                log_group_name,
                name=f"/aws/lambda/{function_name}",
                retention_in_days=retention_days
            )
            resources[log_group_name] = log_group

            # CloudWatch alarm for Lambda errors
            if monitoring_config and getattr(monitoring_config, 'alert_on_failure', False):
                alarm_name = f"{function_name}-errors-alarm"

                # Create SNS topic for notifications if configured
                sns_topic = None
                if hasattr(monitoring_config, 'notifications') and monitoring_config.notifications:
                    topic_name = f"{pipeline.name}-alerts"
                    if topic_name not in resources:
                        sns_topic = aws.sns.Topic(
                            topic_name,
                            name=topic_name
                        )
                        resources[topic_name] = sns_topic
                    else:
                        sns_topic = resources[topic_name]

                alarm_actions = [sns_topic.arn] if sns_topic else []

                alarm = aws.cloudwatch.MetricAlarm(
                    alarm_name,
                    name=alarm_name,
                    comparison_operator="GreaterThanThreshold",
                    evaluation_periods=1,
                    metric_name="Errors",
                    namespace="AWS/Lambda",
                    period=300,
                    statistic="Sum",
                    threshold=1,
                    alarm_actions=alarm_actions,
                    dimensions={
                        "FunctionName": function.name
                    }
                )
                resources[alarm_name] = alarm

        return resources

    def _compile_secrets(self, pipeline: 'Pipeline') -> dict[str, Any]:
        """
        Create Secrets Manager secrets.

        Args:
            pipeline: Source pipeline

        Returns:
            Dictionary mapping resource names to Pulumi Secrets Manager objects
        """
        resources = {}

        # Check if pipeline uses any secrets
        # This would be populated if Environment.secret() was called
        # For now, we'll create a placeholder for future implementation

        return resources

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
