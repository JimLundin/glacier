"""
AWS-specific compute resources.

These are explicit AWS resources for when you need AWS-specific features
or want to deploy to AWS specifically.
"""

from typing import Optional, Dict, Any, List
from glacier.compute.resources import ComputeResource


class Lambda(ComputeResource):
    """
    AWS Lambda function (provider-specific).

    Use this when:
    - You specifically want AWS Lambda
    - You need AWS-specific features (layers, reserved concurrency, etc.)
    - You're building a multi-cloud pipeline with AWS compute

    For provider-agnostic serverless, use Serverless from glacier.compute
    """

    def __init__(
        self,
        memory: int = 512,
        timeout: int = 300,
        runtime: str = "python3.11",
        layers: Optional[List[str]] = None,
        reserved_concurrency: Optional[int] = None,
        environment: Optional[Dict[str, str]] = None,
        vpc_config: Optional[Dict[str, Any]] = None,
    ):
        """
        Create a Lambda function resource.

        Args:
            memory: Memory in MB (128-10240)
            timeout: Timeout in seconds (1-900)
            runtime: Lambda runtime
            layers: Lambda layer ARNs
            reserved_concurrency: Reserved concurrent executions
            environment: Environment variables
            vpc_config: VPC configuration
        """
        self.memory = memory
        self.timeout = timeout
        self.runtime = runtime
        self.layers = layers or []
        self.reserved_concurrency = reserved_concurrency
        self.environment = environment or {}
        self.vpc_config = vpc_config

    def get_type(self) -> str:
        return "serverless"

    def get_provider(self) -> Optional[str]:
        return "aws"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "serverless",
            "provider": "aws",
            "service": "lambda",
            "config": {
                "memory": self.memory,
                "timeout": self.timeout,
                "runtime": self.runtime,
                "layers": self.layers,
                "reserved_concurrency": self.reserved_concurrency,
                "environment": self.environment,
                "vpc_config": self.vpc_config,
            }
        }

    def __repr__(self):
        return f"Lambda(memory={self.memory}MB, timeout={self.timeout}s)"
