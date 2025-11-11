"""
Multi-cloud Pulumi Compiler.

Creates Pulumi resources for pipelines that span multiple cloud providers.
Tasks and datasets can use different providers (AWS, GCP, Azure) within
the same pipeline.
"""

from typing import TYPE_CHECKING

try:
    import pulumi
except ImportError:
    raise ImportError(
        "pulumi required for PulumiCompiler. "
        "Install with: pip install pulumi"
    )

from glacier.compilation.compiler import Compiler, CompiledPipeline, CompilationError

if TYPE_CHECKING:
    from glacier.core.dataset import Dataset
    from glacier.core.pipeline import Pipeline
    from glacier.core.task import Task


class PulumiCompiler(Compiler):
    """
    Multi-cloud aware Pulumi compiler.

    Inspects tasks and datasets to determine which provider they use,
    then creates the appropriate Pulumi resources for each provider.

    Example:
        # Pipeline with AWS and GCP resources
        aws_env = Environment(provider=AWSProvider(...), name="aws")
        gcp_env = Environment(provider=GCPProvider(...), name="gcp")

        # S3 storage
        s3_storage = aws_env.object_storage("raw-data")
        raw = Dataset("raw", storage=s3_storage)

        # GCS storage
        gcs_storage = gcp_env.object_storage("processed")
        processed = Dataset("processed", storage=gcs_storage)

        # Task on AWS
        @pipeline.task(environment=aws_env)
        def extract() -> raw:
            return data

        # Task on GCP
        @pipeline.task(environment=gcp_env)
        def process(data: raw) -> processed:
            return transformed

        # Compile - creates resources in both clouds
        compiler = PulumiCompiler()
        compiled = pipeline.compile(compiler)
    """

    def compile(self, pipeline: 'Pipeline') -> CompiledPipeline:
        """
        Compile a multi-cloud pipeline to Pulumi resources.

        Args:
            pipeline: The pipeline to compile

        Returns:
            CompiledPipeline with resources from all providers

        Raises:
            CompilationError: If compilation fails
        """
        try:
            # Validate pipeline
            pipeline.validate()

            resources = {}

            # Storage resources are already created via Environment.object_storage()
            # They're attached to datasets and are already Pulumi resources
            # We just need to track them
            for dataset in pipeline.datasets:
                if hasattr(dataset, 'storage') and dataset.storage is not None:
                    storage_name = f"{pipeline.name}-{dataset.name}-storage"
                    resources[storage_name] = dataset.storage

            # For each task, create compute resources based on the task's environment
            for task in pipeline.tasks:
                task_resources = self._compile_task(pipeline, task)
                resources.update(task_resources)

            return CompiledPipeline(
                pipeline_name=pipeline.name,
                resources=resources,
                metadata={
                    "task_count": len(pipeline.tasks),
                    "dataset_count": len(pipeline.datasets),
                    "providers": list(set(
                        self._infer_provider(r) for r in resources.values()
                    ))
                }
            )

        except Exception as e:
            raise CompilationError(f"Failed to compile pipeline '{pipeline.name}': {e}") from e

    def _compile_task(self, pipeline: 'Pipeline', task: 'Task') -> dict[str, pulumi.Resource]:
        """
        Compile a single task to Pulumi resources.

        Determines which provider the task uses and creates appropriate
        compute resources (Lambda, Cloud Functions, etc.)

        Args:
            pipeline: Source pipeline
            task: Task to compile

        Returns:
            Dictionary of Pulumi resources for this task
        """
        resources: dict[str, pulumi.Resource] = {}

        # Get the task's environment (which contains the provider)
        environment = task.config.get('environment')
        if environment is None:
            # Fall back to default environment
            from glacier.defaults import get_default_environment
            try:
                environment = get_default_environment()
            except ImportError:
                raise CompilationError(
                    f"Task '{task.name}' must specify an environment. "
                    f"Use @pipeline.task(environment=env) or install glacier-local "
                    f"for default local environment."
                )

        provider = environment.provider
        provider_name = provider.get_provider_name()

        # Determine compute config
        compute_config = getattr(task, 'compute', None)
        memory = 512
        timeout = 300

        if compute_config:
            if hasattr(compute_config, 'memory'):
                memory = compute_config.memory
            if hasattr(compute_config, 'timeout'):
                timeout = compute_config.timeout

        # Create compute resources based on provider
        if provider_name == 'aws':
            task_resources = self._compile_aws_task(
                pipeline, task, provider, memory, timeout
            )
        elif provider_name == 'gcp':
            task_resources = self._compile_gcp_task(
                pipeline, task, provider, memory, timeout
            )
        elif provider_name == 'azure':
            task_resources = self._compile_azure_task(
                pipeline, task, provider, memory, timeout
            )
        else:
            raise CompilationError(f"Unsupported provider: {provider_name}")

        resources.update(task_resources)

        return resources

    def _compile_aws_task(
        self,
        pipeline: 'Pipeline',
        task: 'Task',
        provider,
        memory: int,
        timeout: int
    ) -> dict[str, pulumi.Resource]:
        """Create AWS Lambda resources for a task."""
        try:
            import pulumi_aws as aws
        except ImportError:
            raise CompilationError(
                "pulumi-aws required for AWS tasks. "
                "Install with: pip install pulumi-aws"
            )

        resources: dict[str, pulumi.Resource] = {}
        function_name = f"{pipeline.name}-{task.name}".replace("_", "-")

        # Create IAM role
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

        # Create IAM policy
        policy_name = f"{function_name}-policy"
        policy = aws.iam.RolePolicy(
            policy_name,
            role=role.name,
            policy=pulumi.Output.from_input({
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": ["s3:*", "storage.googleapis.com:*"],  # Cross-cloud access
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
            runtime="python3.11",
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

        # Create CloudWatch log group
        log_group_name = f"{function_name}-logs"
        log_group = aws.cloudwatch.LogGroup(
            log_group_name,
            name=f"/aws/lambda/{function_name}",
            retention_in_days=30
        )
        resources[log_group_name] = log_group

        return resources

    def _compile_gcp_task(
        self,
        pipeline: 'Pipeline',
        task: 'Task',
        provider,
        memory: int,
        timeout: int
    ) -> dict[str, pulumi.Resource]:
        """Create GCP Cloud Function resources for a task."""
        try:
            import pulumi_gcp as gcp
        except ImportError:
            raise CompilationError(
                "pulumi-gcp required for GCP tasks. "
                "Install with: pip install pulumi-gcp"
            )

        resources: dict[str, pulumi.Resource] = {}
        function_name = f"{pipeline.name}-{task.name}".replace("_", "-")

        # Create Cloud Function
        function = gcp.cloudfunctions.Function(
            function_name,
            name=function_name,
            runtime="python311",
            entry_point=task.name,
            available_memory_mb=memory,
            timeout=timeout,
            source_archive_bucket="<bucket>",  # TODO: needs actual bucket
            source_archive_object=f"{task.name}.zip",
            trigger_http=True,
        )
        resources[function_name] = function

        return resources

    def _compile_azure_task(
        self,
        pipeline: 'Pipeline',
        task: 'Task',
        provider,
        memory: int,
        timeout: int
    ) -> dict[str, pulumi.Resource]:
        """Create Azure Function resources for a task."""
        try:
            import pulumi_azure_native as azure
        except ImportError:
            raise CompilationError(
                "pulumi-azure-native required for Azure tasks. "
                "Install with: pip install pulumi-azure-native"
            )

        resources: dict[str, pulumi.Resource] = {}
        function_name = f"{pipeline.name}-{task.name}".replace("_", "-")

        # Azure Function implementation would go here
        # This is a placeholder
        raise CompilationError("Azure Functions not yet implemented")

    def _infer_provider(self, resource: pulumi.Resource) -> str:
        """Infer provider from Pulumi resource type."""
        resource_type = type(resource).__module__
        if 'pulumi_aws' in resource_type:
            return 'aws'
        elif 'pulumi_gcp' in resource_type:
            return 'gcp'
        elif 'pulumi_azure' in resource_type or 'pulumi_azure_native' in resource_type:
            return 'azure'
        else:
            return 'unknown'
