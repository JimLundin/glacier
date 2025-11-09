"""
Escape Hatch Design: Pulumi Customization Hooks

Users should NOT need to import Pulumi unless they explicitly want to.
Pulumi is a compilation target, not a runtime dependency.

The escape hatch works via:
1. Post-compilation hooks - modify generated Pulumi resources
2. Pulumi program injection - add custom Pulumi code to exported project
3. Extended configuration - pass advanced config that compiler translates

This keeps Pulumi as an optional, compile-time dependency.
"""

from typing import Callable, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class PulumiCustomization:
    """
    Customization hook for Pulumi resources.

    This allows users to modify generated Pulumi resources without
    importing Pulumi in their pipeline code.

    The customization function receives the generated Pulumi resource
    and can modify it using Pulumi APIs.

    Example:
        def customize_bucket(bucket, context):
            '''
            This function receives a Pulumi S3 bucket and can modify it.
            Pulumi is imported HERE, not in pipeline code.
            '''
            import pulumi_aws as aws

            # Add object lock (not in Glacier abstraction)
            aws.s3.BucketObjectLockConfigurationV2(
                f"{context.resource_name}-lock",
                bucket=bucket.id,
                object_lock_enabled="Enabled",
                rule=aws.s3.BucketObjectLockConfigurationV2RuleArgs(
                    default_retention=...
                ),
            )

            # Add custom encryption
            aws.s3.BucketServerSideEncryptionConfigurationV2(
                f"{context.resource_name}-encryption",
                bucket=bucket.id,
                rules=[...]
            )

            return bucket

        # Apply during compilation
        infra = pipeline.compile(
            compiler,
            customizations={
                "data": customize_bucket,  # Customize specific resource
            }
        )
    """

    resource_name: str
    """Name of the resource to customize"""

    customize_fn: Callable[[Any, 'CustomizationContext'], Any]
    """
    Function that receives Pulumi resource and modifies it.

    Args:
        resource: The generated Pulumi resource
        context: Context with metadata about the resource

    Returns:
        Modified or replacement Pulumi resource
    """

    stage: str = "post_generation"
    """When to apply: 'post_generation' or 'pre_export'"""


@dataclass
class CustomizationContext:
    """
    Context provided to customization functions.

    Contains metadata about the resource being customized.
    """

    resource_name: str
    """Glacier resource name"""

    resource_type: str
    """Resource type (object_storage, database, etc.)"""

    environment: Any
    """Environment this resource belongs to"""

    glacier_config: Dict[str, Any]
    """Original Glacier configuration"""

    pulumi_outputs: Dict[str, Any] = field(default_factory=dict)
    """Pulumi outputs from other resources (for dependencies)"""


class PulumiProgramInjector:
    """
    Allows injecting custom Pulumi code into exported programs.

    This is the alternative escape hatch - instead of modifying
    generated resources, add completely custom Pulumi resources.

    Example:
        # Export pipeline
        infra = pipeline.compile(compiler)
        infra.export_pulumi("./infra")

        # Add custom Pulumi code
        injector = PulumiProgramInjector("./infra")

        injector.add_custom_code('''
# Custom Pulumi resources not in Glacier
import pulumi_aws as aws

# Complex VPC setup
custom_vpc = aws.ec2.Vpc(
    "custom-vpc",
    cidr_block="10.0.0.0/16",
    enable_dns_hostnames=True,
)

# Transit gateway
transit_gw = aws.ec2transitgateway.TransitGateway(
    "transit-gw",
    description="Custom transit gateway",
)

# Export for other resources to reference
pulumi.export("custom_vpc_id", custom_vpc.id)
        ''')

        injector.save()
    """

    def __init__(self, pulumi_project_dir: str):
        """
        Create injector for a Pulumi project.

        Args:
            pulumi_project_dir: Directory containing Pulumi project
        """
        self.project_dir = pulumi_project_dir
        self.custom_code_blocks = []

    def add_custom_code(self, code: str, position: str = "end"):
        """
        Add custom Pulumi code to the program.

        Args:
            code: Python code to add (can import Pulumi)
            position: Where to insert ("start", "end", or "before:<resource_name>")
        """
        self.custom_code_blocks.append({
            "code": code,
            "position": position,
        })

    def save(self):
        """Write custom code to __main__.py"""
        import os

        main_file = os.path.join(self.project_dir, "__main__.py")

        # Read existing content
        with open(main_file, "r") as f:
            content = f.read()

        # Inject custom code
        for block in self.custom_code_blocks:
            if block["position"] == "end":
                content += "\n\n# Custom Pulumi code\n"
                content += block["code"]
            elif block["position"] == "start":
                content = "# Custom Pulumi code\n" + block["code"] + "\n\n" + content

        # Write back
        with open(main_file, "w") as f:
            f.write(content)


# Configuration-based escape hatch (no Pulumi imports needed)

@dataclass
class AdvancedStorageConfig:
    """
    Extended storage configuration that compiler translates to Pulumi.

    Users specify WHAT they want, compiler figures out HOW with Pulumi.

    Example:
        storage = aws_prod.storage.s3(
            bucket="data",
            advanced_config=AdvancedStorageConfig(
                object_lock=ObjectLockConfig(
                    mode="GOVERNANCE",
                    retention_days=365,
                ),
                replication=ReplicationConfig(
                    destination_bucket="dr-bucket",
                    destination_region="us-west-2",
                ),
                lifecycle_tiers=[
                    ("STANDARD", 0),
                    ("STANDARD_IA", 30),
                    ("GLACIER", 90),
                    ("DEEP_ARCHIVE", 365),
                ],
            )
        )

    No Pulumi imports! Compiler translates this to Pulumi resources.
    """

    object_lock: Optional['ObjectLockConfig'] = None
    """Object lock configuration (for compliance)"""

    replication: Optional['ReplicationConfig'] = None
    """Cross-region replication"""

    lifecycle_tiers: Optional[list] = None
    """List of (storage_class, days) tuples"""

    custom_encryption: Optional['EncryptionConfig'] = None
    """Custom encryption settings"""

    access_logging: Optional['LoggingConfig'] = None
    """Access logging configuration"""

    cors: Optional['CORSConfig'] = None
    """CORS configuration"""


@dataclass
class ObjectLockConfig:
    """Object lock configuration (for compliance)"""

    mode: str  # "GOVERNANCE" or "COMPLIANCE"
    retention_days: int


@dataclass
class ReplicationConfig:
    """Cross-region replication configuration"""

    destination_bucket: str
    destination_region: Optional[str] = None
    storage_class: str = "STANDARD_IA"


@dataclass
class EncryptionConfig:
    """Custom encryption configuration"""

    algorithm: str  # "AES256" or "aws:kms"
    kms_key_id: Optional[str] = None
    kms_key_rotation: bool = False


@dataclass
class LoggingConfig:
    """Access logging configuration"""

    target_bucket: str
    target_prefix: str = "logs/"


@dataclass
class CORSConfig:
    """CORS configuration"""

    allowed_origins: list
    allowed_methods: list
    allowed_headers: Optional[list] = None
    max_age_seconds: int = 3000
