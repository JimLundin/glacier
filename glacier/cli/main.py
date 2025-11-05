"""
Glacier CLI - Command-line interface for managing data pipelines.
"""

import click
import sys
import importlib.util
from pathlib import Path
from typing import Any


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """
    Glacier - Code-centric data pipeline library with infrastructure-from-code generation.

    Define your pipelines in Python and let Glacier handle the infrastructure.
    """
    pass


@cli.command()
@click.argument("pipeline_file", type=click.Path(exists=True))
@click.option(
    "--pipeline-name",
    "-p",
    help="Name of the pipeline function to run (if multiple in file)",
)
@click.option("--debug", is_flag=True, help="Enable debug output")
def run(pipeline_file: str, pipeline_name: str, debug: bool):
    """
    Run a pipeline locally.

    Execute a Glacier pipeline in the current Python process for testing
    and development.

    Example:
        glacier run my_pipeline.py
        glacier run pipelines/etl.py --pipeline-name my_etl
    """
    click.echo(f"Running pipeline from: {pipeline_file}")

    # Load the pipeline module
    pipeline = _load_pipeline(pipeline_file, pipeline_name)

    if pipeline is None:
        click.echo("Error: Could not find pipeline in file", err=True)
        sys.exit(1)

    # Execute the pipeline
    try:
        if debug:
            click.echo(f"Executing pipeline: {pipeline.name}")

        result = pipeline.run(mode="local")

        click.echo(f"✓ Pipeline '{pipeline.name}' completed successfully")

        # If result is a LazyFrame, show info
        if hasattr(result, "collect"):
            click.echo("\nResult is a LazyFrame. Use .collect() to materialize.")
        elif hasattr(result, "shape"):
            click.echo(f"\nResult shape: {result.shape}")

    except Exception as e:
        click.echo(f"✗ Pipeline failed: {e}", err=True)
        if debug:
            import traceback

            traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.argument("pipeline_file", type=click.Path(exists=True))
@click.option(
    "--output",
    "-o",
    default="./infra",
    help="Output directory for generated infrastructure",
)
@click.option(
    "--pipeline-name",
    "-p",
    help="Name of the pipeline function (if multiple in file)",
)
@click.option("--format", type=click.Choice(["terraform", "json"]), default="terraform")
def generate(pipeline_file: str, output: str, pipeline_name: str, format: str):
    """
    Generate infrastructure code from a pipeline.

    Analyze the pipeline and generate Terraform (or other IaC) configuration
    for the required cloud resources.

    Example:
        glacier generate my_pipeline.py
        glacier generate my_pipeline.py --output ./infrastructure
        glacier generate my_pipeline.py --format json
    """
    click.echo(f"Analyzing pipeline from: {pipeline_file}")

    # Load the pipeline module
    pipeline = _load_pipeline(pipeline_file, pipeline_name)

    if pipeline is None:
        click.echo("Error: Could not find pipeline in file", err=True)
        sys.exit(1)

    try:
        click.echo(f"Generating {format} infrastructure code...")

        # Generate infrastructure
        result = pipeline.run(mode="generate", output_dir=output)

        click.echo(f"\n✓ Infrastructure generated successfully")
        click.echo(f"  Output directory: {result['output_dir']}")
        click.echo(f"  Files generated: {len(result['files'])}")

        for file in result["files"]:
            click.echo(f"    - {file}")

        # Show resource summary
        resources = result.get("resources", {})
        total = resources.get("total", 0)

        if total > 0:
            click.echo(f"\n  Resources: {total} total")
            for resource_type, count in resources.items():
                if resource_type != "total" and count > 0:
                    click.echo(f"    - {resource_type}: {count}")

        click.echo(f"\nNext steps:")
        click.echo(f"  1. Review the generated files in {output}/")
        click.echo(f"  2. cd {output}")
        click.echo(f"  3. terraform init")
        click.echo(f"  4. terraform plan")
        click.echo(f"  5. terraform apply")

    except Exception as e:
        click.echo(f"✗ Generation failed: {e}", err=True)
        import traceback

        traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.argument("pipeline_file", type=click.Path(exists=True))
@click.option(
    "--pipeline-name",
    "-p",
    help="Name of the pipeline function (if multiple in file)",
)
@click.option("--format", type=click.Choice(["text", "json", "mermaid"]), default="text")
def analyze(pipeline_file: str, pipeline_name: str, format: str):
    """
    Analyze a pipeline and display its structure.

    Show the DAG, tasks, dependencies, and sources without executing
    or generating infrastructure.

    Example:
        glacier analyze my_pipeline.py
        glacier analyze my_pipeline.py --format json
        glacier analyze my_pipeline.py --format mermaid
    """
    click.echo(f"Analyzing pipeline from: {pipeline_file}")

    # Load the pipeline module
    pipeline = _load_pipeline(pipeline_file, pipeline_name)

    if pipeline is None:
        click.echo("Error: Could not find pipeline in file", err=True)
        sys.exit(1)

    try:
        # Analyze the pipeline
        analysis = pipeline.run(mode="analyze")

        if format == "json":
            import json

            # Convert to JSON-serializable format
            output = {
                "pipeline": pipeline.name,
                "tasks": list(analysis["tasks"].keys()),
                "sources": [str(s) for s in analysis["sources"]],
                "execution_order": analysis["execution_order"],
                "dag": analysis["dag"].to_dict(),
            }
            click.echo(json.dumps(output, indent=2))

        elif format == "mermaid":
            # Generate Mermaid diagram
            click.echo("```mermaid")
            click.echo("graph TD")
            dag = analysis["dag"]
            for node_name, node in dag.nodes.items():
                for dep in node.dependencies:
                    click.echo(f"  {dep} --> {node_name}")
            click.echo("```")

        else:  # text format
            click.echo(f"\n Pipeline: {pipeline.name}")
            click.echo(f"{'=' * 50}")

            click.echo(f"\n Tasks: {len(analysis['tasks'])}")
            for task_name in analysis["tasks"].keys():
                click.echo(f"  - {task_name}")

            click.echo(f"\n Sources: {len(analysis['sources'])}")
            for source in analysis["sources"]:
                click.echo(f"  - {source}")

            if analysis["execution_order"]:
                click.echo(f"\n Execution Order:")
                for i, task in enumerate(analysis["execution_order"], 1):
                    click.echo(f"  {i}. {task}")

            if analysis.get("infrastructure"):
                infra = analysis["infrastructure"]
                click.echo(f"\n Infrastructure Requirements:")
                for category, items in infra.items():
                    if items:
                        click.echo(f"  {category}: {len(items)}")

    except Exception as e:
        click.echo(f"✗ Analysis failed: {e}", err=True)
        import traceback

        traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.argument("pipeline_file", type=click.Path(exists=True))
@click.option(
    "--pipeline-name",
    "-p",
    help="Name of the pipeline function (if multiple in file)",
)
def validate(pipeline_file: str, pipeline_name: str):
    """
    Validate a pipeline without executing it.

    Check for common issues like circular dependencies, missing tasks,
    and invalid configurations.

    Example:
        glacier validate my_pipeline.py
    """
    click.echo(f"Validating pipeline from: {pipeline_file}")

    # Load the pipeline module
    pipeline = _load_pipeline(pipeline_file, pipeline_name)

    if pipeline is None:
        click.echo("Error: Could not find pipeline in file", err=True)
        sys.exit(1)

    try:
        from glacier.runtime.local import LocalExecutor

        executor = LocalExecutor(pipeline)

        if executor.validate():
            click.echo(f"✓ Pipeline '{pipeline.name}' is valid")
        else:
            click.echo(f"✗ Pipeline '{pipeline.name}' has validation errors", err=True)
            sys.exit(1)

    except Exception as e:
        click.echo(f"✗ Validation failed: {e}", err=True)
        sys.exit(1)


def _load_pipeline(pipeline_file: str, pipeline_name: str = None) -> Any:
    """
    Load a pipeline from a Python file.

    Args:
        pipeline_file: Path to the Python file
        pipeline_name: Optional name of the pipeline function

    Returns:
        The pipeline object or None if not found
    """
    # Load the module
    spec = importlib.util.spec_from_file_location("pipeline_module", pipeline_file)
    module = importlib.util.module_from_spec(spec)
    sys.modules["pipeline_module"] = module
    spec.loader.exec_module(module)

    # Find the pipeline
    pipeline = None

    if pipeline_name:
        # Look for specific pipeline by name
        if hasattr(module, pipeline_name):
            obj = getattr(module, pipeline_name)
            if hasattr(obj, "_glacier_pipeline"):
                pipeline = obj._glacier_pipeline
    else:
        # Find the first pipeline in the module
        for attr_name in dir(module):
            obj = getattr(module, attr_name)
            if hasattr(obj, "_glacier_pipeline"):
                pipeline = obj._glacier_pipeline
                break

    return pipeline


if __name__ == "__main__":
    cli()
