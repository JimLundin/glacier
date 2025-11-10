"""
Deployment CLI for Glacier pipelines.

Provides commands for compiling and deploying pipelines to cloud infrastructure.
"""

import sys
import subprocess
from pathlib import Path
from typing import Any


class DeploymentError(Exception):
    """Raised when deployment fails."""
    pass


class DeploymentCLI:
    """
    CLI interface for pipeline deployment.

    Provides commands for:
    - Compiling pipelines to Pulumi programs
    - Running Pulumi preview/up/destroy
    - Managing deployment lifecycle
    """

    def __init__(self, verbose: bool = True):
        """
        Initialize deployment CLI.

        Args:
            verbose: Print detailed output
        """
        self.verbose = verbose

    def compile_pipeline(
        self,
        pipeline: Any,
        compiler: Any,
        output_dir: str | Path
    ) -> Path:
        """
        Compile pipeline to Pulumi program.

        Args:
            pipeline: Glacier pipeline to compile
            compiler: Provider-specific compiler
            output_dir: Directory to write Pulumi program

        Returns:
            Path to generated Pulumi program directory

        Raises:
            DeploymentError: If compilation fails
        """
        try:
            if self.verbose:
                print(f"Compiling pipeline '{pipeline.name}'...")
                print(f"  Provider: {compiler.get_provider_name()}")
                print(f"  Output: {output_dir}")

            # Compile pipeline
            compiled = pipeline.compile(compiler)

            if self.verbose:
                print(f"  Compiled {len(compiled.resources)} resources")

            # Export Pulumi program
            exported_path = compiled.export_pulumi(output_dir)

            if self.verbose:
                print(f"✓ Compilation successful")
                print(f"  Generated: {exported_path}")

            return exported_path

        except Exception as e:
            raise DeploymentError(f"Compilation failed: {e}") from e

    def pulumi_preview(
        self,
        pulumi_dir: str | Path,
        stack: str | None = None
    ) -> subprocess.CompletedProcess:
        """
        Run 'pulumi preview' to preview infrastructure changes.

        Args:
            pulumi_dir: Directory containing Pulumi program
            stack: Optional stack name

        Returns:
            CompletedProcess with preview results

        Raises:
            DeploymentError: If preview fails
        """
        return self._run_pulumi_command(
            "preview",
            pulumi_dir,
            stack,
            description="Previewing infrastructure changes"
        )

    def pulumi_up(
        self,
        pulumi_dir: str | Path,
        stack: str | None = None,
        yes: bool = False
    ) -> subprocess.CompletedProcess:
        """
        Run 'pulumi up' to deploy infrastructure.

        Args:
            pulumi_dir: Directory containing Pulumi program
            stack: Optional stack name
            yes: Skip confirmation prompt

        Returns:
            CompletedProcess with deployment results

        Raises:
            DeploymentError: If deployment fails
        """
        extra_args = ["--yes"] if yes else []
        return self._run_pulumi_command(
            "up",
            pulumi_dir,
            stack,
            extra_args=extra_args,
            description="Deploying infrastructure"
        )

    def pulumi_destroy(
        self,
        pulumi_dir: str | Path,
        stack: str | None = None,
        yes: bool = False
    ) -> subprocess.CompletedProcess:
        """
        Run 'pulumi destroy' to tear down infrastructure.

        Args:
            pulumi_dir: Directory containing Pulumi program
            stack: Optional stack name
            yes: Skip confirmation prompt

        Returns:
            CompletedProcess with destroy results

        Raises:
            DeploymentError: If destroy fails
        """
        extra_args = ["--yes"] if yes else []
        return self._run_pulumi_command(
            "destroy",
            pulumi_dir,
            stack,
            extra_args=extra_args,
            description="Destroying infrastructure"
        )

    def pulumi_stack_output(
        self,
        pulumi_dir: str | Path,
        stack: str | None = None
    ) -> dict[str, Any]:
        """
        Get stack outputs as dictionary.

        Args:
            pulumi_dir: Directory containing Pulumi program
            stack: Optional stack name

        Returns:
            Dictionary of stack outputs

        Raises:
            DeploymentError: If getting outputs fails
        """
        result = self._run_pulumi_command(
            "stack output --json",
            pulumi_dir,
            stack,
            description="Getting stack outputs"
        )

        try:
            import json
            return json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise DeploymentError(f"Failed to parse stack outputs: {e}") from e

    def _run_pulumi_command(
        self,
        command: str,
        pulumi_dir: str | Path,
        stack: str | None = None,
        extra_args: list[str] | None = None,
        description: str | None = None
    ) -> subprocess.CompletedProcess:
        """
        Run a Pulumi CLI command.

        Args:
            command: Pulumi command to run
            pulumi_dir: Directory containing Pulumi program
            stack: Optional stack name
            extra_args: Optional extra arguments
            description: Optional description for verbose output

        Returns:
            CompletedProcess with command results

        Raises:
            DeploymentError: If command fails
        """
        pulumi_path = Path(pulumi_dir)
        if not pulumi_path.exists():
            raise DeploymentError(f"Pulumi directory not found: {pulumi_dir}")

        # Build command
        cmd = ["pulumi", command]
        if stack:
            cmd.extend(["--stack", stack])
        if extra_args:
            cmd.extend(extra_args)

        if self.verbose and description:
            print(f"{description}...")
            print(f"  Command: {' '.join(cmd)}")
            print(f"  Directory: {pulumi_path}")

        try:
            result = subprocess.run(
                cmd,
                cwd=pulumi_path,
                check=True,
                capture_output=True,
                text=True
            )

            if self.verbose:
                print("✓ Command completed successfully")
                if result.stdout:
                    print(result.stdout)

            return result

        except subprocess.CalledProcessError as e:
            error_msg = f"Pulumi command failed: {' '.join(cmd)}"
            if e.stderr:
                error_msg += f"\n{e.stderr}"
            raise DeploymentError(error_msg) from e

    def deploy_pipeline(
        self,
        pipeline: Any,
        compiler: Any,
        output_dir: str | Path,
        stack: str = "dev",
        auto_approve: bool = False
    ) -> dict[str, Any]:
        """
        One-command deployment: compile and deploy pipeline.

        Args:
            pipeline: Glacier pipeline to deploy
            compiler: Provider-specific compiler
            output_dir: Directory to write Pulumi program
            stack: Stack name
            auto_approve: Skip confirmation prompt

        Returns:
            Dictionary of stack outputs

        Raises:
            DeploymentError: If deployment fails
        """
        # Step 1: Compile
        exported_path = self.compile_pipeline(pipeline, compiler, output_dir)

        # Step 2: Preview
        if self.verbose:
            print()
            print("=" * 70)
            print("PREVIEW")
            print("=" * 70)
        self.pulumi_preview(exported_path, stack)

        # Step 3: Deploy
        if self.verbose:
            print()
            print("=" * 70)
            print("DEPLOY")
            print("=" * 70)
        self.pulumi_up(exported_path, stack, yes=auto_approve)

        # Step 4: Get outputs
        if self.verbose:
            print()
            print("=" * 70)
            print("OUTPUTS")
            print("=" * 70)
        outputs = self.pulumi_stack_output(exported_path, stack)

        if self.verbose:
            print("Stack outputs:")
            for key, value in outputs.items():
                print(f"  {key}: {value}")

        return outputs


# Convenience functions
def compile_pipeline(pipeline: Any, compiler: Any, output_dir: str | Path) -> Path:
    """
    Compile pipeline to Pulumi program.

    Args:
        pipeline: Glacier pipeline to compile
        compiler: Provider-specific compiler
        output_dir: Directory to write Pulumi program

    Returns:
        Path to generated Pulumi program directory
    """
    cli = DeploymentCLI()
    return cli.compile_pipeline(pipeline, compiler, output_dir)


def deploy_pipeline(
    pipeline: Any,
    compiler: Any,
    output_dir: str | Path,
    stack: str = "dev",
    auto_approve: bool = False
) -> dict[str, Any]:
    """
    Compile and deploy pipeline in one command.

    Args:
        pipeline: Glacier pipeline to deploy
        compiler: Provider-specific compiler
        output_dir: Directory to write Pulumi program
        stack: Stack name
        auto_approve: Skip confirmation prompt

    Returns:
        Dictionary of stack outputs
    """
    cli = DeploymentCLI()
    return cli.deploy_pipeline(pipeline, compiler, output_dir, stack, auto_approve)
