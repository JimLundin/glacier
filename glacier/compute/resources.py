"""
Compute Resources: Provider-agnostic execution environments.

These resources define WHERE and HOW tasks execute, but not the
specific cloud provider implementation. The provider is chosen
at compile/execution time.
"""

from abc import ABC
from dataclasses import dataclass


class ComputeResource(ABC):
    """
    Abstract base class for compute resources.

    Compute resources define execution requirements without
    being tied to a specific provider (AWS, GCP, local, etc.).
    """
    pass


@dataclass
class Local(ComputeResource):
    """
    Run tasks in local processes.

    Good for:
    - Development and testing
    - Small-scale pipelines
    - Pipelines that run on a single machine
    """

    workers: int = 1
    """Number of parallel workers"""

    def __repr__(self):
        return f"Local(workers={self.workers})"


@dataclass
class Container(ComputeResource):
    """
    Run tasks in containers (provider-agnostic).

    Maps to:
    - Docker locally
    - Kubernetes in cloud
    - ECS on AWS
    - Cloud Run on GCP
    - Container Instances on Azure
    """

    image: str
    """Container image to use"""

    cpu: float = 1.0
    """CPU cores (can be fractional)"""

    memory: int = 512
    """Memory in MB"""

    gpu: int = 0
    """Number of GPUs"""

    env: dict[str, str] | None = None
    """Environment variables"""

    def __repr__(self):
        return f"Container(image={self.image}, cpu={self.cpu}, memory={self.memory})"


@dataclass
class Serverless(ComputeResource):
    """
    Run tasks in serverless functions (provider-agnostic).

    Maps to:
    - AWS Lambda
    - Google Cloud Functions
    - Azure Functions
    - Local function execution (for development)
    """

    memory: int = 512
    """Memory in MB"""

    timeout: int = 300
    """Timeout in seconds"""

    runtime: str | None = None
    """Runtime version (e.g., 'python3.11')"""

    env: dict[str, str] | None = None
    """Environment variables"""

    def __repr__(self):
        return f"Serverless(memory={self.memory}, timeout={self.timeout})"


# Convenience factory functions
def local(workers: int = 1) -> Local:
    """
    Create a local compute resource.

    Args:
        workers: Number of parallel workers

    Returns:
        Local compute resource
    """
    return Local(workers=workers)


def container(
    image: str,
    cpu: float = 1.0,
    memory: int = 512,
    gpu: int = 0,
    env: dict[str, str] | None = None,
) -> Container:
    """
    Create a container compute resource.

    Args:
        image: Container image to use
        cpu: CPU cores (can be fractional)
        memory: Memory in MB
        gpu: Number of GPUs
        env: Environment variables

    Returns:
        Container compute resource
    """
    return Container(image=image, cpu=cpu, memory=memory, gpu=gpu, env=env)


def serverless(
    memory: int = 512,
    timeout: int = 300,
    runtime: str | None = None,
    env: dict[str, str] | None = None,
) -> Serverless:
    """
    Create a serverless compute resource.

    Args:
        memory: Memory in MB
        timeout: Timeout in seconds
        runtime: Runtime version (e.g., 'python3.11')
        env: Environment variables

    Returns:
        Serverless compute resource
    """
    return Serverless(memory=memory, timeout=timeout, runtime=runtime, env=env)
