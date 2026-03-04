"""JSON extractor for face attendance app."""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from ..config import settings
from .base import (
    BaseExtractor,
    ExtractedEntity,
    ExtractionResult,
)


class FaceAttendanceExtractor(BaseExtractor):
    """Extract from face attendance JSON files."""

    def __init__(self):
        super().__init__("face_attendance")
        self.users_path = settings.face_attendance_users_json
        self.attendance_path = settings.face_attendance_records_json

    def connect(self) -> bool:
        """Check if JSON files exist."""
        if not self.users_path.exists():
            self.logger.warning(f"Users file not found: {self.users_path}")
        if not self.attendance_path.exists():
            self.logger.warning(f"Attendance file not found: {self.attendance_path}")
        return self.users_path.exists() or self.attendance_path.exists()

    def disconnect(self) -> None:
        """No connection to close for JSON files."""
        pass

    def extract_all(self) -> ExtractionResult:
        """Extract all face attendance data."""
        start_time = datetime.now()
        result = ExtractionResult(source_system=self.source_name)

        try:
            if not self.connect():
                result.errors.append("No JSON files found")
                return result

            entities = []

            # Extract users (face encodings)
            if self.users_path.exists():
                with open(self.users_path, "r") as f:
                    users = json.load(f)

                for idx, user in enumerate(users):
                    entity = ExtractedEntity(
                        source_system=self.source_name,
                        entity_type="face_user",
                        external_id=self._create_external_id("user", idx),
                        data={
                            "name": user.get("name"),
                            "has_encoding": bool(user.get("encoding")),
                        },
                        raw_record={"name": user.get("name")},  # Don't store encoding
                    )
                    entities.append(entity)

            # Extract attendance records
            if self.attendance_path.exists():
                with open(self.attendance_path, "r") as f:
                    records = json.load(f)

                for idx, record in enumerate(records):
                    entity = ExtractedEntity(
                        source_system=self.source_name,
                        entity_type="face_attendance",
                        external_id=self._create_external_id("attendance", idx),
                        data={
                            "name": record.get("name"),
                            "timestamp": record.get("timestamp"),
                            "confidence": record.get("confidence"),
                            "date": record.get("timestamp", "")[:10] if record.get("timestamp") else None,
                        },
                        raw_record=record,
                    )
                    entities.append(entity)

            result.entities = entities
            result.record_count = len(entities)

        except Exception as e:
            self.logger.error(f"Extraction failed: {e}")
            result.errors.append(str(e))

        result.duration_seconds = (datetime.now() - start_time).total_seconds()
        return result

    def extract_incremental(self, since: Optional[datetime] = None) -> ExtractionResult:
        """Extract incremental data."""
        # JSON files don't support incremental, do full sync
        return self.extract_all()
