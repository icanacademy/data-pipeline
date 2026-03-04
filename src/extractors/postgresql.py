"""PostgreSQL extractor for scheduling database."""

import json
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional

import psycopg2
from psycopg2.extras import RealDictCursor

from ..config import settings
from .base import (
    BaseExtractor,
    ExtractedEntity,
    ExtractedRelation,
    ExtractionResult,
)


class PostgreSQLExtractor(BaseExtractor):
    """Extract data from PostgreSQL scheduling database."""

    def __init__(self):
        super().__init__("postgres")
        self.conn = None
        self.cursor = None

    def connect(self) -> bool:
        """Connect to PostgreSQL database."""
        try:
            self.conn = psycopg2.connect(
                host=settings.postgres_host,
                port=settings.postgres_port,
                user=settings.postgres_user,
                password=settings.postgres_password,
                database=settings.postgres_database,
            )
            self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)
            self.logger.info("Connected to PostgreSQL")
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to PostgreSQL: {e}")
            return False

    def disconnect(self) -> None:
        """Close PostgreSQL connection."""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        self.logger.info("Disconnected from PostgreSQL")

    def extract_all(self) -> ExtractionResult:
        """Extract all data from scheduling database."""
        start_time = datetime.now()
        result = ExtractionResult(source_system=self.source_name)

        try:
            if not self.connect():
                result.errors.append("Failed to connect to PostgreSQL")
                return result

            # Extract entities
            entities = []
            relations = []

            # Teachers
            teachers = list(self._extract_teachers())
            entities.extend(teachers)
            self.logger.info(f"Extracted {len(teachers)} teachers")

            # Students
            students = list(self._extract_students())
            entities.extend(students)
            self.logger.info(f"Extracted {len(students)} students")

            # Rooms
            rooms = list(self._extract_rooms())
            entities.extend(rooms)
            self.logger.info(f"Extracted {len(rooms)} rooms")

            # Time Slots
            time_slots = list(self._extract_time_slots())
            entities.extend(time_slots)
            self.logger.info(f"Extracted {len(time_slots)} time slots")

            # Assignments and relations
            assignments, assignment_relations = self._extract_assignments()
            entities.extend(assignments)
            relations.extend(assignment_relations)
            self.logger.info(
                f"Extracted {len(assignments)} assignments with {len(assignment_relations)} relations"
            )

            # Attendance
            attendance = list(self._extract_attendance())
            entities.extend(attendance)
            self.logger.info(f"Extracted {len(attendance)} attendance records")

            result.entities = entities
            result.relations = relations
            result.record_count = len(entities) + len(relations)

        except Exception as e:
            self.logger.error(f"Extraction failed: {e}")
            result.errors.append(str(e))
        finally:
            self.disconnect()

        result.duration_seconds = (datetime.now() - start_time).total_seconds()
        return result

    def extract_incremental(
        self, since: Optional[datetime] = None
    ) -> ExtractionResult:
        """Extract data changed since timestamp."""
        if since is None:
            return self.extract_all()

        start_time = datetime.now()
        result = ExtractionResult(source_system=self.source_name)

        try:
            if not self.connect():
                result.errors.append("Failed to connect to PostgreSQL")
                return result

            entities = []
            relations = []

            # Get updated teachers
            self.cursor.execute(
                "SELECT * FROM teachers WHERE updated_at > %s", (since,)
            )
            for row in self.cursor.fetchall():
                entities.append(self._row_to_teacher(dict(row)))

            # Get updated students
            self.cursor.execute(
                "SELECT * FROM students WHERE updated_at > %s", (since,)
            )
            for row in self.cursor.fetchall():
                entities.append(self._row_to_student(dict(row)))

            # Get updated assignments
            self.cursor.execute(
                "SELECT * FROM assignments WHERE updated_at > %s", (since,)
            )
            for row in self.cursor.fetchall():
                assignment = self._row_to_assignment(dict(row))
                entities.append(assignment)
                # Get related teachers and students
                rels = self._get_assignment_relations(row["id"])
                relations.extend(rels)

            result.entities = entities
            result.relations = relations
            result.record_count = len(entities) + len(relations)

        except Exception as e:
            self.logger.error(f"Incremental extraction failed: {e}")
            result.errors.append(str(e))
        finally:
            self.disconnect()

        result.duration_seconds = (datetime.now() - start_time).total_seconds()
        return result

    def _extract_teachers(self) -> Generator[ExtractedEntity, None, None]:
        """Extract all teachers."""
        self.cursor.execute("SELECT * FROM teachers")
        for row in self.cursor.fetchall():
            yield self._row_to_teacher(dict(row))

    def _row_to_teacher(self, row: Dict[str, Any]) -> ExtractedEntity:
        """Convert teacher row to ExtractedEntity."""
        availability = row.get("availability", [])
        if isinstance(availability, str):
            availability = json.loads(availability)

        return ExtractedEntity(
            source_system=self.source_name,
            entity_type="teacher",
            external_id=self._create_external_id("teacher", row["id"]),
            data={
                "name": row.get("name"),
                "availability": availability,
                "color_keyword": row.get("color_keyword"),
                "is_active": self._safe_bool(row.get("is_active", True)),
                "date": str(row.get("date")) if row.get("date") else None,
                "created_at": self._safe_datetime(row.get("created_at")),
                "updated_at": self._safe_datetime(row.get("updated_at")),
            },
            raw_record=row,
        )

    def _extract_students(self) -> Generator[ExtractedEntity, None, None]:
        """Extract all students."""
        self.cursor.execute("SELECT * FROM students")
        for row in self.cursor.fetchall():
            yield self._row_to_student(dict(row))

    def _row_to_student(self, row: Dict[str, Any]) -> ExtractedEntity:
        """Convert student row to ExtractedEntity."""
        availability = row.get("availability", [])
        if isinstance(availability, str):
            availability = json.loads(availability)

        return ExtractedEntity(
            source_system=self.source_name,
            entity_type="student",
            external_id=self._create_external_id("student", row["id"]),
            data={
                "name": row.get("name"),
                "english_name": row.get("english_name"),
                "student_id": row.get("student_id"),
                "availability": availability,
                "color_keyword": row.get("color_keyword"),
                "weakness_level": row.get("weakness_level"),
                "teacher_notes": row.get("teacher_notes"),
                "is_active": self._safe_bool(row.get("is_active", True)),
                "school": row.get("school"),
                "grade": row.get("grade"),
                "gender": row.get("gender"),
                "student_type": row.get("student_type"),
                "program_start_date": self._safe_datetime(
                    row.get("program_start_date")
                ),
                "program_end_date": self._safe_datetime(row.get("program_end_date")),
                # Scores
                "reading_score": row.get("reading_score"),
                "grammar_score": row.get("grammar_score"),
                "listening_score": row.get("listening_score"),
                "writing_score": row.get("writing_score"),
                "vocabulary_score": row.get("vocabulary_score"),
                "interview_score": row.get("interview_score"),
                "level_test_total": row.get("level_test_total"),
                "wpm_initial": row.get("wpm_initial"),
                "gbwt_initial": row.get("gbwt_initial"),
                "reading_level_initial": row.get("reading_level_initial"),
                "created_at": self._safe_datetime(row.get("created_at")),
                "updated_at": self._safe_datetime(row.get("updated_at")),
            },
            raw_record=row,
        )

    def _extract_rooms(self) -> Generator[ExtractedEntity, None, None]:
        """Extract all rooms."""
        self.cursor.execute("SELECT * FROM rooms")
        for row in self.cursor.fetchall():
            yield ExtractedEntity(
                source_system=self.source_name,
                entity_type="room",
                external_id=self._create_external_id("room", row["id"]),
                data={
                    "room_name": row.get("name"),
                    "is_active": self._safe_bool(row.get("is_active", True)),
                },
                raw_record=dict(row),
            )

    def _extract_time_slots(self) -> Generator[ExtractedEntity, None, None]:
        """Extract all time slots."""
        self.cursor.execute("SELECT * FROM time_slots")
        for row in self.cursor.fetchall():
            yield ExtractedEntity(
                source_system=self.source_name,
                entity_type="time_slot",
                external_id=self._create_external_id("time_slot", row["id"]),
                data={
                    "slot_name": row.get("name"),
                    "start_time": row.get("start_time"),
                    "end_time": row.get("end_time"),
                },
                raw_record=dict(row),
            )

    def _extract_assignments(
        self,
    ) -> tuple[List[ExtractedEntity], List[ExtractedRelation]]:
        """Extract assignments and their relations to teachers/students."""
        entities = []
        relations = []

        self.cursor.execute("SELECT * FROM assignments WHERE is_active = true")
        assignments = self.cursor.fetchall()

        for row in assignments:
            assignment_id = row["id"]
            external_id = self._create_external_id("assignment", assignment_id)

            # Create assignment entity
            entities.append(
                ExtractedEntity(
                    source_system=self.source_name,
                    entity_type="class_assignment",
                    external_id=external_id,
                    data={
                        "date": str(row.get("date")) if row.get("date") else None,
                        "time_slot_id": row.get("time_slot_id"),
                        "room_id": row.get("room_id"),
                        "notes": row.get("notes"),
                        "is_active": self._safe_bool(row.get("is_active", True)),
                        "created_at": self._safe_datetime(row.get("created_at")),
                        "updated_at": self._safe_datetime(row.get("updated_at")),
                    },
                    raw_record=dict(row),
                )
            )

            # Get relations
            relations.extend(self._get_assignment_relations(assignment_id))

        return entities, relations

    def _get_assignment_relations(
        self, assignment_id: int
    ) -> List[ExtractedRelation]:
        """Get teacher and student relations for an assignment."""
        relations = []
        assignment_external_id = self._create_external_id("assignment", assignment_id)

        # Get teachers for this assignment
        self.cursor.execute(
            "SELECT teacher_id FROM assignment_teachers WHERE assignment_id = %s",
            (assignment_id,),
        )
        for row in self.cursor.fetchall():
            teacher_external_id = self._create_external_id("teacher", row["teacher_id"])
            relations.append(
                ExtractedRelation(
                    source_system=self.source_name,
                    relation_type="teaching",
                    from_entity_id=teacher_external_id,
                    to_entity_id=assignment_external_id,
                    from_entity_type="teacher",
                    to_entity_type="class_assignment",
                    attributes={"role": "instructor"},
                )
            )

        # Get students for this assignment
        self.cursor.execute(
            "SELECT student_id FROM assignment_students WHERE assignment_id = %s",
            (assignment_id,),
        )
        for row in self.cursor.fetchall():
            student_external_id = self._create_external_id("student", row["student_id"])
            relations.append(
                ExtractedRelation(
                    source_system=self.source_name,
                    relation_type="teaching",
                    from_entity_id=student_external_id,
                    to_entity_id=assignment_external_id,
                    from_entity_type="student",
                    to_entity_type="class_assignment",
                    attributes={"role": "learner"},
                )
            )

        return relations

    def _extract_attendance(self) -> Generator[ExtractedEntity, None, None]:
        """Extract teacher attendance records."""
        self.cursor.execute("SELECT * FROM teacher_attendance")
        for row in self.cursor.fetchall():
            yield ExtractedEntity(
                source_system=self.source_name,
                entity_type="attendance",
                external_id=self._create_external_id("attendance", row["id"]),
                data={
                    "teacher_id": self._create_external_id(
                        "teacher", row.get("teacher_id")
                    )
                    if row.get("teacher_id")
                    else None,
                    "date": str(row.get("date")) if row.get("date") else None,
                    "attendance_status": row.get("status"),
                    "notes": row.get("notes"),
                },
                raw_record=dict(row),
            )
