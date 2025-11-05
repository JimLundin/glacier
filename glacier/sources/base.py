"""
Base Source abstraction for Glacier.
"""

from abc import ABC, abstractmethod
from typing import Any, TYPE_CHECKING
from pydantic import BaseModel
import polars as pl

if TYPE_CHECKING:
    from glacier.providers.base import Provider


class SourceMetadata(BaseModel):
    """Metadata about a source for infrastructure generation."""

    source_type: str
    cloud_provider: str | None = None
    region: str | None = None
    resource_name: str | None = None
    additional_config: dict[str, Any] = {}

    class Config:
        arbitrary_types_allowed = True


class Source(ABC):
    """
    Base class for all data sources in Glacier.

    Sources represent locations where data can be read from. They:
    1. Provide runtime access to data via scan() and read() methods
    2. Expose metadata for infrastructure-from-code generation
    3. Support different storage backends through adapters
    4. Are created through Provider instances for cloud-agnostic pipelines
    """

    def __init__(
        self,
        name: str | None = None,
        provider: "Provider | None" = None,
    ):
        self.name = name or self._generate_name()
        self.provider = provider
        self._metadata: SourceMetadata | None = None

    @abstractmethod
    def scan(self) -> pl.LazyFrame:
        """
        Return a LazyFrame for reading the source data.

        This is the primary method for integrating sources into pipelines.
        It returns a Polars LazyFrame for optimal performance.
        """
        pass

    def read(self) -> pl.DataFrame:
        """
        Eagerly read the source data into a DataFrame.

        Use this for small datasets or when immediate materialization is needed.
        """
        return self.scan().collect()

    @abstractmethod
    def get_metadata(self) -> SourceMetadata:
        """
        Return metadata about this source for infrastructure generation.

        This is used during the "compile" phase to understand what infrastructure
        is needed (buckets, IAM roles, etc.).
        """
        pass

    @abstractmethod
    def get_uri(self) -> str:
        """
        Return the URI of this source (e.g., s3://bucket/path).
        """
        pass

    def _generate_name(self) -> str:
        """Generate a default name for this source."""
        return f"{self.__class__.__name__}_{id(self)}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}', uri='{self.get_uri()}')"
