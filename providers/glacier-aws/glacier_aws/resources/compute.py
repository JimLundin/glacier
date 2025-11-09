"""
AWS Compute Resources: Environment-scoped compute.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from glacier.compute.resources import ComputeResource


@dataclass
class LambdaResource(ComputeResource):
    """
    Lambda function bound to an AWS environment.

    This resource knows which AWS account and region it belongs to.
    """

    environment: 'AWSEnvironment'
    """AWS environment this resource belongs to"""

    memory: int = 512
    """Memory in MB"""

    timeout: int = 300
    """Timeout in seconds"""

    runtime: str = "python3.11"
    """Lambda runtime"""

    layers: List[str] = field(default_factory=list)
    """Lambda layer ARNs"""

    reserved_concurrency: Optional[int] = None
    """Reserved concurrent executions"""

    environment_vars: Dict[str, str] = field(default_factory=dict)
    """Environment variables"""

    def get_type(self) -> str:
        return "serverless"

    def get_provider(self) -> str:
        return "aws"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "serverless",
            "provider": "aws",
            "service": "lambda",
            "environment": {
                "account_id": self.environment.account_id,
                "region": self.environment.region,
                "environment": self.environment.environment,
            },
            "config": {
                "memory": self.memory,
                "timeout": self.timeout,
                "runtime": self.runtime,
                "layers": self.layers,
                "reserved_concurrency": self.reserved_concurrency,
                "environment_vars": self.environment_vars,
            }
        }

    def __repr__(self):
        return (
            f"Lambda(memory={self.memory}MB, "
            f"account={self.environment.account_id}, "
            f"region={self.environment.region})"
        )


@dataclass
class ECSResource(ComputeResource):
    """ECS task bound to an AWS environment"""

    environment: 'AWSEnvironment'
    image: str
    cpu: int = 256
    memory: int = 512
    environment_vars: Dict[str, str] = field(default_factory=dict)

    def get_type(self) -> str:
        return "container"

    def get_provider(self) -> str:
        return "aws"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "container",
            "provider": "aws",
            "service": "ecs",
            "environment": {
                "account_id": self.environment.account_id,
                "region": self.environment.region,
            },
            "config": {
                "image": self.image,
                "cpu": self.cpu,
                "memory": self.memory,
                "environment_vars": self.environment_vars,
            }
        }
