"""Base extractor class for all data sources."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional

from loguru import logger
from pydantic import BaseModel


class ExtractedEntity(BaseModel):
    """Represents an extracted entity from a data source."""

    source_system: str
    entity_type: str
    external_id: str
    data: Dict[str, Any]
    extracted_at: datetime = datetime.now()
    raw_record: Optional[Dict[str, Any]] = None


class ExtractedRelation(BaseModel):
    """Represents an extracted relation between entities."""

    source_system: str
    relation_type: str
    from_entity_id: str
    to_entity_id: str
    from_entity_type: str
    to_entity_type: str
    attributes: Dict[str, Any] = {}
    extracted_at: datetime = datetime.now()


class ExtractionResult(BaseModel):
    """Result of an extraction operation."""

    source_system: str
    entities: List[ExtractedEntity] = []
    relations: List[ExtractedRelation] = []
    extracted_at: datetime = datetime.now()
    duration_seconds: float = 0.0
    record_count: int = 0
    errors: List[str] = []


class BaseExtractor(ABC):
    """Abstract base class for all data extractors."""

    def __init__(self, source_name: str):
        self.source_name = source_name
        self.logger = logger.bind(extractor=source_name)

    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to the data source."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection to the data source."""
        pass

    @abstractmethod
    def extract_all(self) -> ExtractionResult:
        """Extract all data from the source."""
        pass

    @abstractmethod
    def extract_incremental(
        self, since: Optional[datetime] = None
    ) -> ExtractionResult:
        """Extract only data changed since the given timestamp."""
        pass

    def extract_entities(
        self, entity_type: str, limit: Optional[int] = None
    ) -> Generator[ExtractedEntity, None, None]:
        """Generator to extract entities of a specific type."""
        raise NotImplementedError(
            f"extract_entities not implemented for {self.source_name}"
        )

    def healthcheck(self) -> bool:
        """Check if the data source is accessible."""
        try:
            connected = self.connect()
            if connected:
                self.disconnect()
            return connected
        except Exception as e:
            self.logger.error(f"Healthcheck failed: {e}")
            return False

    def _create_external_id(self, entity_type: str, source_id: Any) -> str:
        """Create a unique external ID for an entity."""
        return f"{self.source_name}_{entity_type}_{source_id}"

    def _safe_datetime(self, value: Any) -> Optional[datetime]:
        """Safely convert a value to datetime."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            for fmt in [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%S.%f",
            ]:
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue
        return None

    def _safe_bool(self, value: Any) -> bool:
        """Safely convert a value to boolean."""
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value != 0
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes", "on")
        return bool(value)
