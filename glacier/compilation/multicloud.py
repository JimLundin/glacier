"""
Multi-Cloud Compiler: Handles pipelines with resources across multiple providers.

This compiler detects which providers are in use and delegates to
provider-specific compilers accordingly.
"""

from typing import Dict, Any, Optional, List, Set
from collections import defaultdict
from dataclasses import dataclass

from glacier.compilation.compiler import Compiler, CompiledPipeline, CompilationContext


@dataclass
class CrossProviderTransfer:
    """Represents data transfer between different cloud providers"""
    from_provider: str
    to_provider: str
    dataset_name: str
    from_task: str
    to_task: str
    estimated_cost_factor: float = 1.0  # Relative to same-provider transfer


class MultiCloudCompiler(Compiler):
    """
    Multi-cloud compiler that handles pipelines with mixed providers.

    This compiler:
    1. Detects which providers are in use
    2. Delegates to provider-specific compilers
    3. Handles cross-provider data transfer
    4. Generates infrastructure for each provider

    Example:
        from glacier_aws import AWSCompiler
        from glacier_gcp import GCPCompiler

        compiler = MultiCloudCompiler(
            providers={
                "aws": AWSCompiler(region="us-east-1"),
                "gcp": GCPCompiler(project="my-project"),
            },
            default_provider="aws",  # For generic resources
        )

        infra = pipeline.compile(compiler)
    """

    def __init__(
        self,
        providers: Dict[str, Compiler],
        default_provider: Optional[str] = None,
        enable_cross_cloud_warnings: bool = True,
    ):
        """
        Create a multi-cloud compiler.

        Args:
            providers: Mapping of provider names to their compilers
            default_provider: Default provider for generic resources (if not specified, uses first provider)
            enable_cross_cloud_warnings: Warn about cross-cloud data transfers
        """
        if not providers:
            raise ValueError("At least one provider compiler must be specified")

        self.providers = providers
        self.default_provider = default_provider or list(providers.keys())[0]
        self.enable_cross_cloud_warnings = enable_cross_cloud_warnings

        if self.default_provider not in self.providers:
            raise ValueError(
                f"Default provider '{self.default_provider}' not in providers list"
            )

    def get_context(self) -> CompilationContext:
        """Get context from default provider"""
        return self.providers[self.default_provider].get_context()

    def compile(self, pipeline) -> 'MultiCloudCompiledPipeline':
        """
        Compile pipeline with multi-cloud support.

        1. Analyze which providers are needed
        2. Detect cross-provider data transfers
        3. Delegate to provider-specific compilers
        4. Combine results
        """
        # Analyze pipeline to determine provider usage
        analysis = self._analyze_pipeline(pipeline)

        # Warn about cross-provider transfers
        if self.enable_cross_cloud_warnings and analysis.cross_provider_transfers:
            self._warn_cross_provider_transfers(analysis.cross_provider_transfers)

        # Compile for each provider
        provider_infrastructures = {}
        for provider_name in analysis.providers_used:
            if provider_name not in self.providers:
                raise ValueError(
                    f"Pipeline uses provider '{provider_name}' but no compiler provided. "
                    f"Add {provider_name} to providers dict."
                )

            compiler = self.providers[provider_name]

            # Filter pipeline to only resources for this provider
            filtered_resources = self._filter_resources_for_provider(
                pipeline, provider_name, analysis
            )

            # Compile with provider-specific compiler
            # (This might need to be a partial compile - just the resources for this provider)
            provider_infra = compiler.compile(pipeline)
            provider_infrastructures[provider_name] = provider_infra

        return MultiCloudCompiledPipeline(
            pipeline=pipeline,
            provider_infrastructures=provider_infrastructures,
            analysis=analysis,
            default_provider=self.default_provider,
        )

    def _analyze_pipeline(self, pipeline) -> 'PipelineAnalysis':
        """
        Analyze pipeline to determine provider usage.

        Returns which providers are used and where cross-provider
        transfers occur.
        """
        providers_used = set()
        resource_providers = {}  # resource -> provider
        cross_provider_transfers = []

        # Analyze storage resources
        for task in pipeline._tasks:
            # Check task compute resource
            if task.compute:
                provider = task.compute.get_provider()
                if provider:
                    providers_used.add(provider)
                    resource_providers[f"task:{task.name}"] = provider
                else:
                    # Generic resource - use default
                    providers_used.add(self.default_provider)
                    resource_providers[f"task:{task.name}"] = self.default_provider

            # Check datasets
            for dataset in task.outputs + [inp.dataset for inp in task.inputs]:
                if dataset.storage:
                    provider = dataset.storage.get_provider()
                    if provider:
                        providers_used.add(provider)
                        resource_providers[f"dataset:{dataset.name}"] = provider
                    else:
                        # Generic resource - use default
                        providers_used.add(self.default_provider)
                        resource_providers[f"dataset:{dataset.name}"] = self.default_provider

        # Detect cross-provider transfers
        for task in pipeline._tasks:
            task_provider = resource_providers.get(f"task:{task.name}")

            # Check if task reads from different provider
            for input_param in task.inputs:
                dataset = input_param.dataset
                dataset_provider = resource_providers.get(f"dataset:{dataset.name}")

                if dataset_provider and task_provider and dataset_provider != task_provider:
                    # Find producer task
                    producer_task = None
                    for t in pipeline._tasks:
                        if dataset in t.outputs:
                            producer_task = t
                            break

                    cross_provider_transfers.append(
                        CrossProviderTransfer(
                            from_provider=dataset_provider,
                            to_provider=task_provider,
                            dataset_name=dataset.name,
                            from_task=producer_task.name if producer_task else "external",
                            to_task=task.name,
                            estimated_cost_factor=5.0,  # Cross-cloud egress is ~5x more expensive
                        )
                    )

        return PipelineAnalysis(
            providers_used=providers_used,
            resource_providers=resource_providers,
            cross_provider_transfers=cross_provider_transfers,
        )

    def _filter_resources_for_provider(
        self, pipeline, provider_name: str, analysis: 'PipelineAnalysis'
    ) -> Dict[str, Any]:
        """Filter pipeline resources to only those for a specific provider"""
        # This is a helper for future optimization
        # For now, we pass the whole pipeline to each compiler
        # and let them handle their own resources
        return {}

    def _warn_cross_provider_transfers(self, transfers: List[CrossProviderTransfer]):
        """Warn user about cross-provider data transfers"""
        if not transfers:
            return

        print("\n" + "=" * 70)
        print("⚠️  CROSS-PROVIDER DATA TRANSFERS DETECTED")
        print("=" * 70)
        print()
        print("The following data transfers cross cloud provider boundaries:")
        print()

        for transfer in transfers:
            print(f"  • {transfer.dataset_name}")
            print(f"    {transfer.from_task} ({transfer.from_provider}) → {transfer.to_task} ({transfer.to_provider})")
            print(f"    Estimated cost: ~{transfer.estimated_cost_factor}x normal transfer")
            print()

        print("Recommendations:")
        print("  1. Consider co-locating compute and storage in the same provider")
        print("  2. Use intermediate storage to batch transfers")
        print("  3. Compress data before transfer")
        print("  4. Monitor egress costs carefully")
        print()
        print("=" * 70)
        print()

    def validate_resource(self, resource: Any) -> None:
        """Validate resource against appropriate provider"""
        provider = resource.get_provider()

        if provider:
            # Provider-specific resource
            if provider not in self.providers:
                raise ValueError(
                    f"Resource requires provider '{provider}' but no compiler provided"
                )
            self.providers[provider].validate_resource(resource)
        else:
            # Generic resource - validate against default provider
            self.providers[self.default_provider].validate_resource(resource)

    def get_capabilities(self) -> Dict[str, Any]:
        """Get combined capabilities from all providers"""
        capabilities = {}
        for provider_name, compiler in self.providers.items():
            capabilities[provider_name] = compiler.get_capabilities()
        return capabilities


@dataclass
class PipelineAnalysis:
    """Analysis results from examining a pipeline"""
    providers_used: Set[str]
    resource_providers: Dict[str, str]  # resource_id -> provider
    cross_provider_transfers: List[CrossProviderTransfer]


class MultiCloudCompiledPipeline(CompiledPipeline):
    """
    Multi-cloud compiled pipeline.

    Contains infrastructure for multiple providers.
    """

    def __init__(
        self,
        pipeline,
        provider_infrastructures: Dict[str, CompiledPipeline],
        analysis: PipelineAnalysis,
        default_provider: str,
    ):
        self.pipeline = pipeline
        self.provider_infrastructures = provider_infrastructures
        self.analysis = analysis
        self.default_provider = default_provider

    def export_pulumi(self, output_dir: str, project_name: Optional[str] = None) -> None:
        """
        Export as Pulumi projects (one per provider).

        Creates subdirectories for each provider:
        - output_dir/aws/
        - output_dir/gcp/
        - output_dir/azure/
        """
        import os

        project_name = project_name or self.pipeline.name

        for provider_name, infra in self.provider_infrastructures.items():
            provider_dir = os.path.join(output_dir, provider_name)
            infra.export_pulumi(provider_dir, f"{project_name}-{provider_name}")

        # Create root README
        readme_path = os.path.join(output_dir, "README.md")
        with open(readme_path, "w") as f:
            f.write(self._generate_root_readme(project_name))

    def _generate_root_readme(self, project_name: str) -> str:
        """Generate README for multi-cloud deployment"""
        providers_list = ", ".join(self.analysis.providers_used)

        content = [
            f"# {project_name}",
            "",
            "Multi-cloud Glacier pipeline deployment.",
            "",
            f"**Providers used:** {providers_list}",
            "",
            "## Structure",
            "",
        ]

        for provider in self.analysis.providers_used:
            content.append(f"- `{provider}/` - {provider.upper()} infrastructure")

        content.extend([
            "",
            "## Deployment",
            "",
            "Deploy each provider separately:",
            "",
        ])

        for provider in self.analysis.providers_used:
            content.extend([
                f"### {provider.upper()}",
                "",
                "```bash",
                f"cd {provider}",
                "pulumi up",
                "cd ..",
                "```",
                "",
            ])

        if self.analysis.cross_provider_transfers:
            content.extend([
                "## Cross-Provider Data Transfers",
                "",
                "⚠️ This pipeline transfers data between cloud providers:",
                "",
            ])

            for transfer in self.analysis.cross_provider_transfers:
                content.append(
                    f"- **{transfer.dataset_name}**: "
                    f"{transfer.from_provider} → {transfer.to_provider} "
                    f"({transfer.from_task} → {transfer.to_task})"
                )

            content.extend([
                "",
                "**Note:** Cross-provider transfers may incur significant egress costs.",
                "",
            ])

        return "\n".join(content)

    def to_dict(self) -> Dict[str, Any]:
        """Export as dictionary"""
        return {
            "pipeline": self.pipeline.name,
            "providers": list(self.analysis.providers_used),
            "default_provider": self.default_provider,
            "cross_provider_transfers": [
                {
                    "dataset": t.dataset_name,
                    "from_provider": t.from_provider,
                    "to_provider": t.to_provider,
                    "from_task": t.from_task,
                    "to_task": t.to_task,
                }
                for t in self.analysis.cross_provider_transfers
            ],
            "infrastructures": {
                provider: infra.to_dict()
                for provider, infra in self.provider_infrastructures.items()
            },
        }

    def get_resources(self) -> Dict[str, Any]:
        """Get all resources grouped by provider"""
        return {
            provider: infra.get_resources()
            for provider, infra in self.provider_infrastructures.items()
        }

    def get_outputs(self) -> Dict[str, Any]:
        """Get outputs from all providers"""
        outputs = {}
        for provider, infra in self.provider_infrastructures.items():
            provider_outputs = infra.get_outputs()
            outputs[provider] = provider_outputs
        return outputs
