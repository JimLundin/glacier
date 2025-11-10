"""
Stack Compiler: Compiles entire stacks including all environments and pipelines.

Creates compute and orchestration infrastructure for pipelines,
using infrastructure resources already created via environments.
"""

from typing import TYPE_CHECKING

try:
    import pulumi
except ImportError:
    raise ImportError(
        "pulumi required for StackCompiler. "
        "Install with: pip install pulumi"
    )

from glacier.compilation.compiler import CompilationError

if TYPE_CHECKING:
    from glacier.core.environment import Environment
    from glacier.core.pipeline import Pipeline
    from glacier.core.stack import CompiledStack, Stack
    from glacier.core.task import Task


class StackCompiler:
    """
    Compiles entire stacks to Pulumi infrastructure.

    The StackCompiler:
    1. Collects infrastructure resources from environments (already Pulumi resources)
    2. For each pipeline, creates compute resources for tasks
    3. Creates IAM policies connecting tasks to resources
    4. Creates orchestration (EventBridge, Cloud Scheduler, etc.)

    This is provider-agnostic - it handles multi-cloud stacks naturally.
    """

    def compile(self, stack: 'Stack') -> 'CompiledStack':
        """
        Compile a stack to create compute and orchestration infrastructure.

        Args:
            stack: The stack to compile

        Returns:
            CompiledStack with all infrastructure

        Raises:
            CompilationError: If compilation fails
        """
        try:
            from glacier.core.stack import CompiledStack

            resources = {}

            # Step 1: Collect infrastructure resources from environments
            # These are already Pulumi resources created via env.object_storage(), etc.
            infra_resources = self._collect_infrastructure_resources(stack)
            resources.update(infra_resources)

            # Step 2: Collect tracked shared resources
            resources.update(stack._resources)

            # Step 3: Collect storage resources from datasets
            dataset_resources = self._collect_dataset_resources(stack)
            resources.update(dataset_resources)

            # Step 4: For each pipeline, create compute resources for tasks
            for pipeline_name, pipeline in stack._pipelines.items():
                pipeline_resources = self._compile_pipeline(stack, pipeline)
                resources.update(pipeline_resources)

            return CompiledStack(
                stack_name=stack.name,
                resources=resources,
                metadata={
                    "environment_count": len(stack._environments),
                    "pipeline_count": len(stack._pipelines),
                    "resource_count": len(resources),
                }
            )

        except Exception as e:
            raise CompilationError(f"Failed to compile stack '{stack.name}': {e}") from e

    def _collect_infrastructure_resources(self, stack: 'Stack') -> dict[str, pulumi.Resource]:
        """
        Collect infrastructure resources from environments.

        These resources are already created as Pulumi resources when
        env.object_storage(), env.database(), etc. were called.

        We don't recreate them - we just collect references.
        """
        resources: dict[str, pulumi.Resource] = {}

        # Note: Infrastructure resources are already created and registered
        # with Pulumi. We don't need to do anything here - they're already
        # in the Pulumi stack.

        # This method is a placeholder to show the architecture.
        # In practice, Pulumi automatically tracks all resources created.

        return resources

    def _collect_dataset_resources(self, stack: 'Stack') -> dict[str, pulumi.Resource]:
        """
        Collect storage resources attached to datasets.

        Datasets may have storage (S3 buckets, GCS buckets, etc.) that
        were created via environments. We collect references to them.
        """
        resources: dict[str, pulumi.Resource] = {}

        for pipeline_name, pipeline in stack._pipelines.items():
            for dataset in pipeline.datasets:
                if hasattr(dataset, 'storage') and dataset.storage is not None:
                    storage_name = f"{pipeline_name}-{dataset.name}-storage"
                    resources[storage_name] = dataset.storage

        return resources

    def _compile_pipeline(self, stack: 'Stack', pipeline: 'Pipeline') -> dict[str, pulumi.Resource]:
        """
        Create compute and orchestration resources for a pipeline.

        For each task:
        1. Determine which environment/provider it uses
        2. Create compute resources (Lambda, Cloud Functions, etc.)
        3. Create IAM policies for accessing resources
        4. Create orchestration (triggers, schedules)

        Args:
            stack: Parent stack
            pipeline: Pipeline to compile

        Returns:
            Dictionary of Pulumi resources
        """
        resources: dict[str, pulumi.Resource] = {}

        # Validate pipeline
        pipeline.validate()

        # Compile each task
        for task in pipeline.tasks:
            task_resources = self._compile_task(stack, pipeline, task)
            resources.update(task_resources)

        return resources

    def _compile_task(
        self,
        stack: 'Stack',
        pipeline: 'Pipeline',
        task: 'Task'
    ) -> dict[str, pulumi.Resource]:
        """
        Create compute resources for a single task.

        Determines which environment/provider the task uses and creates
        appropriate compute resources.

        Args:
            stack: Parent stack
            pipeline: Parent pipeline
            task: Task to compile

        Returns:
            Dictionary of Pulumi resources
        """
        resources: dict[str, pulumi.Resource] = {}

        # Get the task's environment
        environment = getattr(task, 'environment', None)
        if environment is None:
            # Try to infer environment from task's datasets
            environment = self._infer_task_environment(stack, task)

        if environment is None:
            raise CompilationError(
                f"Task '{task.name}' in pipeline '{pipeline.name}' must specify "
                f"an environment or have datasets with storage"
            )

        provider = environment.provider
        provider_name = provider.get_provider_name()

        # Get compute config
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
                stack, pipeline, task, provider, memory, timeout
            )
        elif provider_name == 'gcp':
            task_resources = self._compile_gcp_task(
                stack, pipeline, task, provider, memory, timeout
            )
        elif provider_name == 'azure':
            task_resources = self._compile_azure_task(
                stack, pipeline, task, provider, memory, timeout
            )
        else:
            raise CompilationError(f"Unsupported provider: {provider_name}")

        resources.update(task_resources)

        return resources

    def _infer_task_environment(self, stack: 'Stack', task: 'Task') -> 'Environment | None':
        """
        Try to infer task environment from its input/output datasets.

        If datasets have storage, we can determine which environment they
        came from.
        """
        # Look at output datasets first (task produces these)
        for output_dataset in task.outputs:
            if hasattr(output_dataset, 'storage') and output_dataset.storage is not None:
                # Find which environment created this storage
                for env in stack._environments.values():
                    # Storage was created via this environment
                    # (in practice, we'd need to track this explicitly)
                    return env

        # Look at input datasets
        for input_param in task.inputs:
            dataset = input_param.dataset
            if hasattr(dataset, 'storage') and dataset.storage is not None:
                for env in stack._environments.values():
                    return env

        return None

    def _compile_aws_task(
        self,
        stack: 'Stack',
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

        # Create IAM policy with broad permissions for multi-cloud access
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
            runtime="python3.11",
            memory_size=memory,
            timeout=timeout,
            role=role.arn,
            code=pulumi.FileArchive(f"./.glacier/compiled/{task.name}"),
            tags={
                "task": task.name,
                "pipeline": pipeline.name,
                "stack": stack.name,
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
        stack: 'Stack',
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

        # GCP Cloud Function implementation would go here
        # This is a placeholder
        raise CompilationError("GCP Cloud Functions not yet fully implemented")

    def _compile_azure_task(
        self,
        stack: 'Stack',
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
