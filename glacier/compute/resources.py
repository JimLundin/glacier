"""
Compute Resources: Provider-agnostic execution environments.

These resources define WHERE and HOW tasks execute, but not the
specific cloud provider implementation. The provider is chosen
at compile/execution time.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from dataclasses import dataclass


class ComputeResource(ABC):
    """
    Abstract base class for compute resources.

    Compute resources define execution requirements without
    being tied to a specific provider (AWS, GCP, local, etc.).
    """

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary representation for infrastructure generation.

        Returns:
            Dictionary with resource configuration
        """
        pass

    @abstractmethod
    def get_type(self) -> str:
        """
        Get the resource type identifier.

        Returns:
            Resource type string ('local', 'container', 'serverless', etc.)
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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "local",
            "workers": self.workers,
        }

    def get_type(self) -> str:
        return "local"

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

    env: Optional[Dict[str, str]] = None
    """Environment variables"""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "container",
            "image": self.image,
            "cpu": self.cpu,
            "memory": self.memory,
            "gpu": self.gpu,
            "env": self.env or {},
        }

    def get_type(self) -> str:
        return "container"

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

    runtime: Optional[str] = None
    """Runtime version (e.g., 'python3.11')"""

    env: Optional[Dict[str, str]] = None
    """Environment variables"""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "serverless",
            "memory": self.memory,
            "timeout": self.timeout,
            "runtime": self.runtime,
            "env": self.env or {},
        }

    def get_type(self) -> str:
        return "serverless"

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
    env: Optional[Dict[str, str]] = None,
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
    runtime: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
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
