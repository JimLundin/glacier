"""
AWS Compiler: Compiles Glacier pipelines to AWS infrastructure using Pulumi.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import os

from glacier.compilation import Compiler, CompiledPipeline, CompilationContext
from glacier.storage.resources import ObjectStorage, Database, Cache, Queue
from glacier.compute.resources import Serverless, Container, Local


class AWSCompiler(Compiler):
    """
    AWS-specific compiler that generates Pulumi code for AWS infrastructure.
    """

    def __init__(
        self,
        region: str = "us-east-1",
        account_id: Optional[str] = None,
        naming_prefix: str = "",
        tags: Optional[Dict[str, str]] = None,
        defaults: Optional[Dict[str, Any]] = None,
        vpc_config: Optional[Dict[str, Any]] = None,
        iam_config: Optional[Dict[str, Any]] = None,
    ):
        """
        Create an AWS compiler.

        Args:
            region: AWS region
            account_id: AWS account ID
            naming_prefix: Prefix for all resource names
            tags: Tags to apply to all resources
            defaults: Default configurations for resources
            vpc_config: VPC configuration for Lambda functions
            iam_config: IAM configuration (roles, permissions boundary, etc.)
        """
        self.context = CompilationContext(
            provider="aws",
            region=region,
            project_id=account_id,
            naming_prefix=naming_prefix,
            tags=tags or {},
            defaults=defaults or {},
            vpc_config=vpc_config,
            iam_config=iam_config,
        )

    def get_context(self) -> CompilationContext:
        """Get compilation context"""
        return self.context

    def compile(self, pipeline) -> 'AWSCompiledPipeline':
        """
        Compile pipeline to AWS infrastructure.
        """
        # Collect all resources from the pipeline
        storage_resources = []
        compute_resources = []
        iam_policies = []

        for task in pipeline._tasks:
            # Validate and collect compute resources
            if task.compute:
                self.validate_resource(task.compute)
                compute_resources.append({
                    "task": task,
                    "compute": task.compute,
                })

            # Collect storage resources from datasets
            for dataset in task.outputs + [inp.dataset for inp in task.inputs]:
                if dataset.storage and dataset.storage not in [s["storage"] for s in storage_resources]:
                    self.validate_resource(dataset.storage)
                    storage_resources.append({
                        "dataset": dataset,
                        "storage": dataset.storage,
                    })

        # Generate IAM policies based on task→dataset relationships
        iam_policies = self._generate_iam_policies(pipeline)

        return AWSCompiledPipeline(
            pipeline=pipeline,
            context=self.context,
            storage_resources=storage_resources,
            compute_resources=compute_resources,
            iam_policies=iam_policies,
        )

    def validate_resource(self, resource: Any) -> None:
        """Validate resource compatibility with AWS"""
        if isinstance(resource, Serverless):
            # Validate AWS Lambda limits
            if resource.timeout > 900:
                raise ValueError(
                    f"AWS Lambda max timeout is 900s, got {resource.timeout}. "
                    f"Use Container resource for longer execution."
                )
            if resource.memory > 10240:
                raise ValueError(
                    f"AWS Lambda max memory is 10240MB, got {resource.memory}."
                )
            if resource.memory < 128:
                raise ValueError(
                    f"AWS Lambda min memory is 128MB, got {resource.memory}."
                )

        elif isinstance(resource, Container):
            # Container resources are flexible on AWS (ECS/Fargate)
            pass

        elif isinstance(resource, Local):
            raise ValueError(
                "Local compute cannot be compiled to AWS infrastructure. "
                "Use Serverless or Container resources instead."
            )

        elif isinstance(resource, (ObjectStorage, Database, Cache, Queue)):
            # Validate provider hints
            hints = resource.provider_hints
            if "aws_storage_class" in hints:
                valid_classes = [
                    "STANDARD", "REDUCED_REDUNDANCY", "STANDARD_IA",
                    "ONEZONE_IA", "INTELLIGENT_TIERING", "GLACIER",
                    "DEEP_ARCHIVE", "GLACIER_IR"
                ]
                if hints["aws_storage_class"] not in valid_classes:
                    raise ValueError(
                        f"Invalid AWS storage class: {hints['aws_storage_class']}. "
                        f"Valid options: {', '.join(valid_classes)}"
                    )

    def get_capabilities(self) -> Dict[str, Any]:
        """Get AWS capabilities"""
        return {
            "serverless": {
                "service": "lambda",
                "max_timeout": 900,
                "max_memory": 10240,
                "min_memory": 128,
                "supports_gpu": False,
                "cold_start": "~1s",
            },
            "container": {
                "services": ["ecs", "fargate"],
                "max_timeout": None,
                "supports_gpu": True,
            },
            "object_storage": {
                "service": "s3",
                "storage_classes": [
                    "STANDARD", "STANDARD_IA", "ONEZONE_IA",
                    "INTELLIGENT_TIERING", "GLACIER", "DEEP_ARCHIVE"
                ],
                "max_object_size": "5TB",
            },
            "database": {
                "service": "rds",
                "engines": ["postgres", "mysql", "mariadb", "oracle", "sqlserver"],
            },
            "cache": {
                "service": "elasticache",
                "engines": ["redis", "memcached"],
            },
            "queue": {
                "service": "sqs",
                "supports_fifo": True,
            },
        }

    def _generate_iam_policies(self, pipeline) -> List[Dict[str, Any]]:
        """Generate IAM policies based on task dependencies"""
        policies = []

        for task in pipeline._tasks:
            role_name = self.context.generate_name(task.name, "execution-role")

            statements = []

            # Input datasets → read permissions
            for input_param in task.inputs:
                dataset = input_param.dataset
                if dataset.storage and isinstance(dataset.storage, ObjectStorage):
                    bucket_name = (
                        self._get_storage_name(dataset.storage) or
                        self.context.generate_name(dataset.name, "bucket")
                    )
                    statements.append({
                        "effect": "Allow",
                        "actions": ["s3:GetObject", "s3:ListBucket"],
                        "resources": [
                            f"arn:aws:s3:::{bucket_name}",
                            f"arn:aws:s3:::{bucket_name}/*",
                        ],
                    })

            # Output datasets → write permissions
            for output_dataset in task.outputs:
                if output_dataset.storage and isinstance(output_dataset.storage, ObjectStorage):
                    bucket_name = (
                        self._get_storage_name(output_dataset.storage) or
                        self.context.generate_name(output_dataset.name, "bucket")
                    )
                    statements.append({
                        "effect": "Allow",
                        "actions": ["s3:PutObject", "s3:PutObjectAcl"],
                        "resources": [f"arn:aws:s3:::{bucket_name}/*"],
                    })

            policies.append({
                "task_name": task.name,
                "role_name": role_name,
                "statements": statements,
            })

        return policies


class AWSCompiledPipeline(CompiledPipeline):
    """
    AWS-compiled pipeline using Pulumi.
    """

    def __init__(
        self,
        pipeline,
        context: CompilationContext,
        storage_resources: List[Dict],
        compute_resources: List[Dict],
        iam_policies: List[Dict],
    ):
        self.pipeline = pipeline
        self.context = context
        self.storage_resources = storage_resources
        self.compute_resources = compute_resources
        self.iam_policies = iam_policies

    def export_pulumi(self, output_dir: str, project_name: Optional[str] = None) -> None:
        """
        Export as Pulumi project.
        """
        project_name = project_name or self.pipeline.name

        # Create output directory
        os.makedirs(output_dir, exist_ok=True)

        # Generate Pulumi.yaml
        pulumi_yaml = self._generate_pulumi_yaml(project_name)
        with open(os.path.join(output_dir, "Pulumi.yaml"), "w") as f:
            f.write(pulumi_yaml)

        # Generate __main__.py
        main_py = self._generate_main_py()
        with open(os.path.join(output_dir, "__main__.py"), "w") as f:
            f.write(main_py)

        # Generate requirements.txt
        requirements = self._generate_requirements()
        with open(os.path.join(output_dir, "requirements.txt"), "w") as f:
            f.write(requirements)

        # Generate README
        readme = self._generate_readme(project_name)
        with open(os.path.join(output_dir, "README.md"), "w") as f:
            f.write(readme)

    def _generate_pulumi_yaml(self, project_name: str) -> str:
        """Generate Pulumi.yaml configuration"""
        return f"""name: {project_name}
runtime: python
description: Glacier pipeline compiled to AWS infrastructure

config:
  aws:region:
    value: {self.context.region}
"""

    def _generate_main_py(self) -> str:
        """Generate __main__.py with Pulumi resources"""
        lines = [
            '"""',
            f'Pulumi infrastructure for {self.pipeline.name} pipeline.',
            '',
            'Generated by Glacier AWS Compiler.',
            '"""',
            '',
            'import pulumi',
            'import pulumi_aws as aws',
            'import json',
            '',
            '# Configuration',
            f"pipeline_name = '{self.pipeline.name}'",
            f"region = '{self.context.region}'",
            f"naming_prefix = '{self.context.naming_prefix}'",
            f"tags = {self.context.tags}",
            '',
            '# Storage Resources',
        ]

        # Generate S3 buckets
        bucket_map = {}
        for storage_res in self.storage_resources:
            dataset = storage_res["dataset"]
            storage = storage_res["storage"]

            if isinstance(storage, ObjectStorage):
                bucket_var = dataset.name.replace("-", "_")
                bucket_name = (
                    self._get_storage_name(storage) or
                    self.context.generate_name(dataset.name, "bucket")
                )
                bucket_map[dataset.name] = bucket_var

                lines.append(f"# Bucket for {dataset.name}")
                lines.append(f"{bucket_var} = aws.s3.BucketV2(")
                lines.append(f"    '{bucket_var}',")
                lines.append(f"    bucket='{bucket_name}',")
                lines.append(f"    tags={{**tags, 'Dataset': '{dataset.name}'}},")
                lines.append(")")
                lines.append("")

                if storage.versioning:
                    lines.append(f"{bucket_var}_versioning = aws.s3.BucketVersioningV2(")
                    lines.append(f"    '{bucket_var}_versioning',")
                    lines.append(f"    bucket={bucket_var}.id,")
                    lines.append("    versioning_configuration=aws.s3.BucketVersioningV2VersioningConfigurationArgs(")
                    lines.append("        status='Enabled',")
                    lines.append("    ),")
                    lines.append(")")
                    lines.append("")

        lines.append("# IAM Roles and Policies")

        # Generate IAM roles
        for policy in self.iam_policies:
            role_var = policy["task_name"].replace("-", "_") + "_role"
            role_name = policy["role_name"]

            lines.append(f"# Role for {policy['task_name']}")
            lines.append(f"{role_var} = aws.iam.Role(")
            lines.append(f"    '{role_var}',")
            lines.append(f"    name='{role_name}',")
            lines.append("    assume_role_policy=json.dumps({")
            lines.append("        'Version': '2012-10-17',")
            lines.append("        'Statement': [{")
            lines.append("            'Effect': 'Allow',")
            lines.append("            'Principal': {'Service': 'lambda.amazonaws.com'},")
            lines.append("            'Action': 'sts:AssumeRole',")
            lines.append("        }],")
            lines.append("    }),")
            lines.append(f"    tags={{**tags, 'Task': '{policy['task_name']}'}},")
            lines.append(")")

            if policy["statements"]:
                policy_var = role_var + "_policy"
                lines.append(f"{policy_var} = aws.iam.RolePolicy(")
                lines.append(f"    '{policy_var}',")
                lines.append(f"    role={role_var}.id,")
                lines.append("    policy=json.dumps({")
                lines.append("        'Version': '2012-10-17',")
                lines.append("        'Statement': [")
                for stmt in policy["statements"]:
                    lines.append("            {")
                    lines.append(f"                'Effect': '{stmt['effect']}',")
                    lines.append(f"                'Action': {stmt['actions']},")
                    lines.append(f"                'Resource': {stmt['resources']},")
                    lines.append("            },")
                lines.append("        ],")
                lines.append("    }),")
                lines.append(")")

            lines.append("")

        lines.append("# Compute Resources (Lambda Functions)")

        # Generate Lambda functions
        for compute_res in self.compute_resources:
            task = compute_res["task"]
            compute = compute_res["compute"]

            if isinstance(compute, Serverless):
                func_var = task.name.replace("-", "_")
                func_name = self.context.generate_name(task.name)
                role_var = func_var + "_role"

                lines.append(f"# Lambda function for {task.name}")
                lines.append(f"# TODO: Package and upload function code for {task.name}")
                lines.append(f"# {func_var} = aws.lambda_.Function(")
                lines.append(f"#     '{func_var}',")
                lines.append(f"#     function_name='{func_name}',")
                lines.append(f"#     role={role_var}.arn,")
                lines.append(f"#     runtime='{compute.runtime or 'python3.11'}',")
                lines.append(f"#     handler='handler.main',")
                lines.append(f"#     memory_size={compute.memory},")
                lines.append(f"#     timeout={compute.timeout},")
                lines.append("#     code=pulumi.FileArchive('./functions/{}'),".format(task.name))
                lines.append(f"#     tags={{**tags, 'Task': '{task.name}'}},")
                lines.append("# )")
                lines.append("")

        lines.append("# Exports")
        lines.append("pulumi.export('pipeline_name', pipeline_name)")
        for storage_res in self.storage_resources:
            dataset = storage_res["dataset"]
            if isinstance(storage_res["storage"], ObjectStorage):
                bucket_var = bucket_map[dataset.name]
                lines.append(f"pulumi.export('{dataset.name}_bucket', {bucket_var}.bucket)")

        return "\n".join(lines)

    def _generate_requirements(self) -> str:
        """Generate requirements.txt"""
        return """pulumi>=3.0.0
pulumi-aws>=6.0.0
"""

    def _generate_readme(self, project_name: str) -> str:
        """Generate README"""
        return f"""# {project_name}

Pulumi infrastructure for the `{self.pipeline.name}` Glacier pipeline.

## Generated Resources

### Storage
{self._format_storage_list()}

### Compute
{self._format_compute_list()}

## Deployment

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure AWS credentials:
   ```bash
   export AWS_ACCESS_KEY_ID=xxx
   export AWS_SECRET_ACCESS_KEY=xxx
   export AWS_REGION={self.context.region}
   ```

3. Deploy with Pulumi:
   ```bash
   pulumi up
   ```

## Next Steps

1. Package Lambda function code in `./functions/` directory
2. Uncomment Lambda function resources in `__main__.py`
3. Configure any additional environment variables or VPC settings

---

Generated by Glacier AWS Compiler
"""

    def _get_storage_name(self, storage) -> Optional[str]:
        """Get the name of a storage resource"""
        # For AWS-specific resources
        if hasattr(storage, 'bucket'):
            return storage.bucket
        elif hasattr(storage, 'instance_identifier'):
            return storage.instance_identifier
        elif hasattr(storage, 'table_name'):
            return storage.table_name
        # For generic resources
        elif hasattr(storage, 'resource_name'):
            return storage.resource_name
        return None

    def _format_storage_list(self) -> str:
        """Format storage resources for README"""
        lines = []
        for res in self.storage_resources:
            dataset = res["dataset"]
            storage = res["storage"]
            bucket_name = (
                self._get_storage_name(storage) or
                self.context.generate_name(dataset.name, "bucket")
            )
            lines.append(f"- **{dataset.name}**: S3 bucket `{bucket_name}`")
        return "\n".join(lines) if lines else "None"

    def _format_compute_list(self) -> str:
        """Format compute resources for README"""
        lines = []
        for res in self.compute_resources:
            task = res["task"]
            compute = res["compute"]
            if isinstance(compute, Serverless):
                func_name = self.context.generate_name(task.name)
                lines.append(
                    f"- **{task.name}**: Lambda function `{func_name}` "
                    f"({compute.memory}MB, {compute.timeout}s timeout)"
                )
        return "\n".join(lines) if lines else "None"

    def to_dict(self) -> Dict[str, Any]:
        """Export as dictionary"""
        return {
            "provider": "aws",
            "pipeline": self.pipeline.name,
            "region": self.context.region,
            "storage_resources": [
                {
                    "dataset": res["dataset"].name,
                    "storage": res["storage"].to_dict(),
                }
                for res in self.storage_resources
            ],
            "compute_resources": [
                {
                    "task": res["task"].name,
                    "compute": res["compute"].to_dict(),
                }
                for res in self.compute_resources
            ],
            "iam_policies": self.iam_policies,
        }

    def get_resources(self) -> Dict[str, Any]:
        """Get all resources"""
        return {
            "storage": self.storage_resources,
            "compute": self.compute_resources,
            "iam": self.iam_policies,
        }

    def get_outputs(self) -> Dict[str, Any]:
        """Get pipeline outputs"""
        outputs = {
            "pipeline_name": self.pipeline.name,
            "region": self.context.region,
        }

        for res in self.storage_resources:
            dataset = res["dataset"]
            storage = res["storage"]
            if isinstance(storage, ObjectStorage):
                bucket_name = (
                    self._get_storage_name(storage) or
                    self.context.generate_name(dataset.name, "bucket")
                )
                outputs[f"{dataset.name}_bucket"] = bucket_name

        return outputs
