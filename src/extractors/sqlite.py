"""SQLite extractor for various local databases."""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from ..config import settings
from .base import (
    BaseExtractor,
    ExtractedEntity,
    ExtractedRelation,
    ExtractionResult,
)


class SQLiteExtractor(BaseExtractor):
    """Extract data from SQLite databases."""

    def __init__(self, db_path: Path, source_name: str):
        super().__init__(source_name)
        self.db_path = db_path
        self.conn = None

    def connect(self) -> bool:
        """Connect to SQLite database."""
        try:
            if not self.db_path.exists():
                self.logger.error(f"Database file not found: {self.db_path}")
                return False
            self.conn = sqlite3.connect(str(self.db_path))
            self.conn.row_factory = sqlite3.Row
            self.logger.info(f"Connected to SQLite: {self.db_path}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to SQLite: {e}")
            return False

    def disconnect(self) -> None:
        """Close SQLite connection."""
        if self.conn:
            self.conn.close()
            self.logger.info(f"Disconnected from SQLite: {self.db_path}")

    def extract_all(self) -> ExtractionResult:
        """Extract all data - to be overridden by specific extractors."""
        raise NotImplementedError("Use specific SQLite extractor subclass")

    def extract_incremental(
        self, since: Optional[datetime] = None
    ) -> ExtractionResult:
        """Extract incremental data."""
        # Most SQLite DBs don't have good timestamp tracking, do full sync
        return self.extract_all()

    def _execute_query(self, query: str, params: tuple = ()) -> List[Dict]:
        """Execute query and return results as list of dicts."""
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


class TeacherAttendanceExtractor(SQLiteExtractor):
    """Extract from teacher attendance database."""

    def __init__(self):
        super().__init__(settings.sqlite_attendance_db, "teacher_attendance")

    def extract_all(self) -> ExtractionResult:
        """Extract all teacher attendance data."""
        start_time = datetime.now()
        result = ExtractionResult(source_system=self.source_name)

        try:
            if not self.connect():
                result.errors.append("Failed to connect")
                return result

            entities = []
            relations = []

            # Extract attendance records
            rows = self._execute_query("SELECT * FROM attendance")
            for row in rows:
                entity = ExtractedEntity(
                    source_system=self.source_name,
                    entity_type="attendance",
                    external_id=self._create_external_id("attendance", row["id"]),
                    data={
                        "teacher_name": row.get("teacher_name"),
                        "teacher_id": row.get("teacher_id"),
                        "date": row.get("date"),
                        "attendance_status": row.get("status"),
                        "start_time": row.get("start_time"),
                        "end_time": row.get("end_time"),
                        "late_reason": row.get("late_reason"),
                        "absent_reason": row.get("absent_reason"),
                        "minutes_late": row.get("minutes_late"),
                        "has_undertime": self._safe_bool(row.get("has_undertime")),
                        "undertime_minutes": row.get("undertime_minutes"),
                        "undertime_reason": row.get("undertime_reason"),
                        "is_active": self._safe_bool(row.get("is_active", True)),
                    },
                    raw_record=row,
                )
                entities.append(entity)

            # Extract class assignments (substitutions, etc.)
            rows = self._execute_query("SELECT * FROM class_assignments")
            for row in rows:
                entity = ExtractedEntity(
                    source_system=self.source_name,
                    entity_type="class_assignment_detail",
                    external_id=self._create_external_id("class_detail", row["id"]),
                    data={
                        "attendance_id": row.get("attendance_id"),
                        "class_slot": row.get("class_slot"),
                        "substitute_teacher_id": row.get("substitute_teacher_id"),
                        "substitute_teacher_name": row.get("substitute_teacher_name"),
                        "no_class": self._safe_bool(row.get("no_class")),
                        "online_class": self._safe_bool(row.get("online_class")),
                        "assignment_type": row.get("assignment_type"),
                    },
                    raw_record=row,
                )
                entities.append(entity)

                # Create substitution relation if applicable
                if row.get("substitute_teacher_id"):
                    relations.append(
                        ExtractedRelation(
                            source_system=self.source_name,
                            relation_type="substitution",
                            from_entity_id=self._create_external_id(
                                "attendance", row["attendance_id"]
                            ),
                            to_entity_id=f"substitute_{row['substitute_teacher_id']}",
                            from_entity_type="attendance",
                            to_entity_type="teacher",
                            attributes={
                                "class_slot": row.get("class_slot"),
                                "assignment_type": row.get("assignment_type"),
                            },
                        )
                    )

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


class StudentAttendanceExtractor(SQLiteExtractor):
    """Extract from student attendance database."""

    def __init__(self):
        super().__init__(settings.sqlite_student_attendance_db, "student_attendance")

    def extract_all(self) -> ExtractionResult:
        """Extract all student attendance data."""
        start_time = datetime.now()
        result = ExtractionResult(source_system=self.source_name)

        try:
            if not self.connect():
                result.errors.append("Failed to connect")
                return result

            entities = []

            rows = self._execute_query("SELECT * FROM attendance")
            for row in rows:
                entity = ExtractedEntity(
                    source_system=self.source_name,
                    entity_type="student_attendance",
                    external_id=self._create_external_id("attendance", row["id"]),
                    data={
                        "student_name": row.get("student_name"),
                        "student_id": row.get("student_id"),
                        "date": row.get("date"),
                        "attendance_status": row.get("status"),
                        "start_time": row.get("start_time"),
                        "end_time": row.get("end_time"),
                        "late_reason": row.get("late_reason"),
                        "absent_reason": row.get("absent_reason"),
                        "minutes_late": row.get("minutes_late"),
                        "has_undertime": self._safe_bool(row.get("has_undertime")),
                        "undertime_minutes": row.get("undertime_minutes"),
                        "undertime_reason": row.get("undertime_reason"),
                        "is_active": self._safe_bool(row.get("is_active", True)),
                    },
                    raw_record=row,
                )
                entities.append(entity)

            result.entities = entities
            result.record_count = len(entities)

        except Exception as e:
            self.logger.error(f"Extraction failed: {e}")
            result.errors.append(str(e))
        finally:
            self.disconnect()

        result.duration_seconds = (datetime.now() - start_time).total_seconds()
        return result


class CoachingExtractor(SQLiteExtractor):
    """Extract from coaching/HR database."""

    def __init__(self):
        super().__init__(settings.sqlite_coaching_db, "coaching")

    def extract_all(self) -> ExtractionResult:
        """Extract all coaching data."""
        start_time = datetime.now()
        result = ExtractionResult(source_system=self.source_name)

        try:
            if not self.connect():
                result.errors.append("Failed to connect")
                return result

            entities = []
            relations = []

            # Extract employees
            rows = self._execute_query("SELECT * FROM employees")
            for row in rows:
                entity = ExtractedEntity(
                    source_system=self.source_name,
                    entity_type="employee",
                    external_id=self._create_external_id("employee", row["id"]),
                    data={
                        "employee_number": row.get("employee_number"),
                        "first_name": row.get("first_name"),
                        "last_name": row.get("last_name"),
                        "name": f"{row.get('first_name', '')} {row.get('last_name', '')}".strip(),
                        "email": row.get("email"),
                        "phone": row.get("phone"),
                        "position": row.get("position"),
                        "department": row.get("department"),
                        "hire_date": row.get("hire_date"),
                        "role_start_date": row.get("role_start_date"),
                        "supervisor_id": row.get("supervisor_id"),
                        "status": row.get("status"),
                        "photo_url": row.get("photo_url"),
                        "notion_id": row.get("notion_id"),
                        "is_active": row.get("status") == "active",
                    },
                    raw_record=row,
                )
                entities.append(entity)

                # Create supervision relation
                if row.get("supervisor_id"):
                    relations.append(
                        ExtractedRelation(
                            source_system=self.source_name,
                            relation_type="supervision",
                            from_entity_id=self._create_external_id(
                                "employee", row["supervisor_id"]
                            ),
                            to_entity_id=self._create_external_id(
                                "employee", row["id"]
                            ),
                            from_entity_type="employee",
                            to_entity_type="employee",
                            attributes={"role": "supervisor"},
                        )
                    )

            # Extract coaching categories
            rows = self._execute_query("SELECT * FROM coaching_categories")
            for row in rows:
                entity = ExtractedEntity(
                    source_system=self.source_name,
                    entity_type="coaching_category",
                    external_id=self._create_external_id("category", row["id"]),
                    data={
                        "name": row.get("name"),
                        "description": row.get("description"),
                        "is_active": self._safe_bool(row.get("is_active", True)),
                    },
                    raw_record=row,
                )
                entities.append(entity)

            # Extract offense types
            rows = self._execute_query("SELECT * FROM offense_types")
            for row in rows:
                entity = ExtractedEntity(
                    source_system=self.source_name,
                    entity_type="offense_type",
                    external_id=self._create_external_id("offense", row["id"]),
                    data={
                        "offense_code": row.get("code"),
                        "offense_name": row.get("name"),
                        "description": row.get("description"),
                        "offense_severity": row.get("severity"),
                        "category_id": row.get("category_id"),
                        "is_active": self._safe_bool(row.get("is_active", True)),
                    },
                    raw_record=row,
                )
                entities.append(entity)

                # Category relation
                if row.get("category_id"):
                    relations.append(
                        ExtractedRelation(
                            source_system=self.source_name,
                            relation_type="offense_classification",
                            from_entity_id=self._create_external_id(
                                "category", row["category_id"]
                            ),
                            to_entity_id=self._create_external_id(
                                "offense", row["id"]
                            ),
                            from_entity_type="coaching_category",
                            to_entity_type="offense_type",
                        )
                    )

            # Extract coaching records
            rows = self._execute_query("SELECT * FROM coaching_records")
            for row in rows:
                entity = ExtractedEntity(
                    source_system=self.source_name,
                    entity_type="coaching_record",
                    external_id=self._create_external_id("record", row["id"]),
                    data={
                        "employee_id": row.get("employee_id"),
                        "supervisor_id": row.get("supervisor_id"),
                        "coaching_type": row.get("coaching_type"),
                        "category_id": row.get("category_id"),
                        "offense_id": row.get("offense_id"),
                        "date": row.get("coaching_date"),
                        "start_time": row.get("coaching_time"),
                        "issue_description": row.get("issue_description"),
                        "expected_improvement": row.get("expected_improvement"),
                        "improvement_timeline": row.get("improvement_timeline"),
                        "follow_up_date": row.get("follow_up_date"),
                        "employee_acknowledged": self._safe_bool(
                            row.get("employee_acknowledged")
                        ),
                        "employee_refused_sign": self._safe_bool(
                            row.get("employee_refused_to_sign")
                        ),
                        "comments": row.get("employee_comments"),
                    },
                    raw_record=row,
                )
                entities.append(entity)

                # Create coaching session relations
                if row.get("employee_id"):
                    relations.append(
                        ExtractedRelation(
                            source_system=self.source_name,
                            relation_type="coaching_session",
                            from_entity_id=self._create_external_id(
                                "employee", row["supervisor_id"]
                            )
                            if row.get("supervisor_id")
                            else "unknown_supervisor",
                            to_entity_id=self._create_external_id(
                                "employee", row["employee_id"]
                            ),
                            from_entity_type="employee",
                            to_entity_type="employee",
                            attributes={
                                "session_id": self._create_external_id(
                                    "record", row["id"]
                                ),
                                "coaching_type": row.get("coaching_type"),
                            },
                        )
                    )

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


class DemoAssessmentExtractor(SQLiteExtractor):
    """Extract from demo assessment database."""

    def __init__(self):
        super().__init__(settings.sqlite_demo_assessment_db, "demo_assessment")

    def extract_all(self) -> ExtractionResult:
        """Extract all demo assessments."""
        start_time = datetime.now()
        result = ExtractionResult(source_system=self.source_name)

        try:
            if not self.connect():
                result.errors.append("Failed to connect")
                return result

            entities = []

            rows = self._execute_query("SELECT * FROM assessments")
            for row in rows:
                entity = ExtractedEntity(
                    source_system=self.source_name,
                    entity_type="demo_assessment",
                    external_id=self._create_external_id("demo", row["id"]),
                    data={
                        "applicant_name": row.get("applicant_name"),
                        "date": row.get("demo_date"),
                        "assessor_name": row.get("assessor_name"),
                        "title": row.get("topic"),
                        "student_levels": row.get("level_targeted"),
                        "assessment_score": row.get("assessment_score"),
                        "criteria_json": row.get("criteria"),
                        "feedback": row.get("additional_comments"),
                        "assessment_result": row.get("final_result"),
                        "met_count": row.get("met_total"),
                        "needs_improvement_count": row.get("ni_total"),
                        "fail_count": row.get("fail_total"),
                        "ai_feedback": row.get("ai_feedback"),
                    },
                    raw_record=row,
                )
                entities.append(entity)

            result.entities = entities
            result.record_count = len(entities)

        except Exception as e:
            self.logger.error(f"Extraction failed: {e}")
            result.errors.append(str(e))
        finally:
            self.disconnect()

        result.duration_seconds = (datetime.now() - start_time).total_seconds()
        return result


class InterviewExtractor(SQLiteExtractor):
    """Extract from interview database."""

    def __init__(self):
        super().__init__(settings.sqlite_interviews_db, "interviews")

    def extract_all(self) -> ExtractionResult:
        """Extract all interview assessments."""
        start_time = datetime.now()
        result = ExtractionResult(source_system=self.source_name)

        try:
            if not self.connect():
                result.errors.append("Failed to connect")
                return result

            entities = []

            rows = self._execute_query("SELECT * FROM interviews")
            for row in rows:
                entity = ExtractedEntity(
                    source_system=self.source_name,
                    entity_type="interview_assessment",
                    external_id=self._create_external_id("interview", row["id"]),
                    data={
                        "student_name": row.get("student_name"),
                        "student_id": row.get("student_id"),
                        "assessment_type": row.get("interview_type"),
                        "date": row.get("date"),
                        "assessor_name": row.get("interviewer"),
                        "grade": row.get("grade"),
                        "gender": row.get("gender"),
                        "age": row.get("age"),
                        "pronunciation_score": row.get("pronunciation"),
                        "fluency_score": row.get("fluency"),
                        "comprehension_score": row.get("comprehension"),
                        "insight_score": row.get("insight"),
                        "vocabulary_score": row.get("vocab"),
                        "knowledge_level": row.get("knowledge_level"),
                        "feedback": row.get("report_text"),
                    },
                    raw_record=row,
                )
                entities.append(entity)

            result.entities = entities
            result.record_count = len(entities)

        except Exception as e:
            self.logger.error(f"Extraction failed: {e}")
            result.errors.append(str(e))
        finally:
            self.disconnect()

        result.duration_seconds = (datetime.now() - start_time).total_seconds()
        return result


class StudentReportExtractor(SQLiteExtractor):
    """Extract from student reports database."""

    def __init__(self):
        super().__init__(settings.sqlite_reports_db, "student_reports")

    def extract_all(self) -> ExtractionResult:
        """Extract all student reports."""
        start_time = datetime.now()
        result = ExtractionResult(source_system=self.source_name)

        try:
            if not self.connect():
                result.errors.append("Failed to connect")
                return result

            entities = []

            rows = self._execute_query("SELECT * FROM student_reports")
            for row in rows:
                entity = ExtractedEntity(
                    source_system=self.source_name,
                    entity_type="student_report",
                    external_id=self._create_external_id("report", row["id"]),
                    data={
                        "student_name": row.get("student_name"),
                        "student_id": row.get("student_id"),
                        "date": row.get("report_date"),
                        "grade": row.get("grade"),
                        "category": row.get("subject"),
                        "attendance_status": row.get("attendance"),
                        "notes": f"Homework: {row.get('homework')}, Participation: {row.get('participation')}, Behavior: {row.get('behavior')}. {row.get('notes', '')}",
                    },
                    raw_record=row,
                )
                entities.append(entity)

            result.entities = entities
            result.record_count = len(entities)

        except Exception as e:
            self.logger.error(f"Extraction failed: {e}")
            result.errors.append(str(e))
        finally:
            self.disconnect()

        result.duration_seconds = (datetime.now() - start_time).total_seconds()
        return result


class MarketplaceExtractor(SQLiteExtractor):
    """Extract from app marketplace database."""

    def __init__(self):
        super().__init__(settings.sqlite_marketplace_db, "marketplace")

    def extract_all(self) -> ExtractionResult:
        """Extract all marketplace data."""
        start_time = datetime.now()
        result = ExtractionResult(source_system=self.source_name)

        try:
            if not self.connect():
                result.errors.append("Failed to connect")
                return result

            entities = []
            relations = []

            # Extract apps
            rows = self._execute_query("SELECT * FROM apps")
            for row in rows:
                # Calculate average rating
                rating_rows = self._execute_query(
                    "SELECT AVG(rating) as avg_rating FROM ratings WHERE app_id = ?",
                    (row["id"],),
                )
                avg_rating = (
                    rating_rows[0]["avg_rating"] if rating_rows else None
                )

                entity = ExtractedEntity(
                    source_system=self.source_name,
                    entity_type="educational_app",
                    external_id=self._create_external_id("app", row["id"]),
                    data={
                        "title": row.get("title"),
                        "description": row.get("description"),
                        "category": row.get("category"),
                        "student_levels": row.get("student_levels"),
                        "app_link": row.get("app_link"),
                        "image_url": row.get("image_url"),
                        "teacher_name": row.get("teacher_name"),
                        "rating": avg_rating,
                    },
                    raw_record=row,
                )
                entities.append(entity)

            # Extract comments
            rows = self._execute_query("SELECT * FROM comments")
            for row in rows:
                entity = ExtractedEntity(
                    source_system=self.source_name,
                    entity_type="app_comment",
                    external_id=self._create_external_id("comment", row["id"]),
                    data={
                        "app_id": row.get("app_id"),
                        "teacher_name": row.get("teacher_name"),
                        "comments": row.get("comment"),
                    },
                    raw_record=row,
                )
                entities.append(entity)

            result.entities = entities
            result.relations = relations
            result.record_count = len(entities)

        except Exception as e:
            self.logger.error(f"Extraction failed: {e}")
            result.errors.append(str(e))
        finally:
            self.disconnect()

        result.duration_seconds = (datetime.now() - start_time).total_seconds()
        return result


class StudentAnalyticsExtractor(SQLiteExtractor):
    """Extract from unified ontology student analytics database."""

    def __init__(self):
        super().__init__(settings.sqlite_student_analytics_db, "student_analytics")

    def extract_all(self) -> ExtractionResult:
        """Extract all student analytics data."""
        start_time = datetime.now()
        result = ExtractionResult(source_system=self.source_name)

        try:
            if not self.connect():
                result.errors.append("Failed to connect")
                return result

            entities = []
            relations = []

            # Extract students
            rows = self._execute_query("SELECT * FROM students")
            for row in rows:
                entity = ExtractedEntity(
                    source_system=self.source_name,
                    entity_type="student",
                    external_id=self._create_external_id("student", row["id"]),
                    data={
                        "student_id": row.get("student_id"),
                        "first_name": row.get("first_name"),
                        "last_name": row.get("last_name"),
                        "name": f"{row.get('first_name', '')} {row.get('last_name', '')}".strip(),
                        "email": row.get("email"),
                        "grade": row.get("grade_level"),
                    },
                    raw_record=row,
                )
                entities.append(entity)

            # Extract assessments
            rows = self._execute_query("SELECT * FROM assessments")
            for row in rows:
                entity = ExtractedEntity(
                    source_system=self.source_name,
                    entity_type="assessment",
                    external_id=self._create_external_id("assessment", row["id"]),
                    data={
                        "student_id": row.get("student_id"),
                        "assessment_type": row.get("assessment_type"),
                        "date": row.get("assessment_date"),
                        "assessment_score": row.get("score"),
                        "max_score": row.get("max_score"),
                        "feedback": row.get("feedback"),
                    },
                    raw_record=row,
                )
                entities.append(entity)

            # Extract skill progressions
            rows = self._execute_query("SELECT * FROM skill_progressions")
            for row in rows:
                entity = ExtractedEntity(
                    source_system=self.source_name,
                    entity_type="skill_progress",
                    external_id=self._create_external_id("skill", row["id"]),
                    data={
                        "student_id": row.get("student_id"),
                        "skill_name": row.get("skill_name"),
                        "proficiency_level": row.get("proficiency_level"),
                        "date": row.get("recorded_at"),
                    },
                    raw_record=row,
                )
                entities.append(entity)

            # Extract insights
            rows = self._execute_query("SELECT * FROM insights")
            for row in rows:
                entity = ExtractedEntity(
                    source_system=self.source_name,
                    entity_type="student_insight",
                    external_id=self._create_external_id("insight", row["id"]),
                    data={
                        "student_id": row.get("student_id"),
                        "insight_type": row.get("insight_type"),
                        "insight_text": row.get("insight_text"),
                        "confidence_score": row.get("confidence_score"),
                        "date": row.get("generated_at"),
                    },
                    raw_record=row,
                )
                entities.append(entity)

            result.entities = entities
            result.relations = relations
            result.record_count = len(entities)

        except Exception as e:
            self.logger.error(f"Extraction failed: {e}")
            result.errors.append(str(e))
        finally:
            self.disconnect()

        result.duration_seconds = (datetime.now() - start_time).total_seconds()
        return result


class IcanClassesExtractor(SQLiteExtractor):
    """Extract from ICAN classes database."""

    def __init__(self):
        super().__init__(settings.sqlite_ican_classes_db, "ican_classes")

    def extract_all(self) -> ExtractionResult:
        """Extract all classes data."""
        start_time = datetime.now()
        result = ExtractionResult(source_system=self.source_name)

        try:
            if not self.connect():
                result.errors.append("Failed to connect")
                return result

            entities = []
            relations = []

            # Extract class categories
            rows = self._execute_query("SELECT * FROM class_categories")
            for row in rows:
                entity = ExtractedEntity(
                    source_system=self.source_name,
                    entity_type="class_category",
                    external_id=self._create_external_id("category", row["id"]),
                    data={
                        "name": row.get("name"),
                        "description": row.get("description"),
                    },
                    raw_record=row,
                )
                entities.append(entity)

            # Extract classes
            rows = self._execute_query("SELECT * FROM classes")
            for row in rows:
                entity = ExtractedEntity(
                    source_system=self.source_name,
                    entity_type="ican_class",
                    external_id=self._create_external_id("class", row["id"]),
                    data={
                        "title": row.get("name"),
                        "description": row.get("description"),
                        "category_id": row.get("category_id"),
                        "min_grade": row.get("min_grade_level"),
                        "max_grade": row.get("max_grade_level"),
                        "difficulty_level": row.get("difficulty_level"),
                        "duration_weeks": row.get("duration_weeks"),
                        "skills_focus": row.get("skills_focus"),
                        "learning_objectives": row.get("learning_objectives"),
                        "materials_needed": row.get("materials_needed"),
                        "is_active": self._safe_bool(row.get("is_active", True)),
                    },
                    raw_record=row,
                )
                entities.append(entity)

            # Extract learning paths
            rows = self._execute_query("SELECT * FROM learning_paths")
            for row in rows:
                entity = ExtractedEntity(
                    source_system=self.source_name,
                    entity_type="learning_path",
                    external_id=self._create_external_id("path", row["id"]),
                    data={
                        "title": row.get("name"),
                        "description": row.get("description"),
                        "target_audience": row.get("target_audience"),
                        "estimated_duration": row.get("estimated_duration"),
                    },
                    raw_record=row,
                )
                entities.append(entity)

            result.entities = entities
            result.relations = relations
            result.record_count = len(entities)

        except Exception as e:
            self.logger.error(f"Extraction failed: {e}")
            result.errors.append(str(e))
        finally:
            self.disconnect()

        result.duration_seconds = (datetime.now() - start_time).total_seconds()
        return result


class BooksLibraryExtractor(SQLiteExtractor):
    """Extract from books library database."""

    def __init__(self):
        super().__init__(settings.sqlite_books_library_db, "books_library")

    def extract_all(self) -> ExtractionResult:
        """Extract all library data."""
        start_time = datetime.now()
        result = ExtractionResult(source_system=self.source_name)

        try:
            if not self.connect():
                result.errors.append("Failed to connect")
                return result

            entities = []
            relations = []

            # Extract books
            rows = self._execute_query("SELECT * FROM books")
            for row in rows:
                entity = ExtractedEntity(
                    source_system=self.source_name,
                    entity_type="book",
                    external_id=self._create_external_id("book", row["id"]),
                    data={
                        "title": row.get("title"),
                        "subtitle": row.get("subtitle"),
                        "isbn": row.get("isbn_13") or row.get("isbn_10"),
                        "publisher": row.get("publisher"),
                        "publication_date": row.get("publication_date"),
                        "language": row.get("language"),
                        "page_count": row.get("page_count"),
                        "description": row.get("description"),
                        "reading_level": row.get("reading_level"),
                        "age_rating": row.get("age_rating"),
                        "location_code": row.get("location_code"),
                        "status": row.get("status"),
                        "total_checkouts": row.get("total_checkouts"),
                        "average_rating": row.get("average_rating"),
                    },
                    raw_record=row,
                )
                entities.append(entity)

            # Extract authors
            rows = self._execute_query("SELECT * FROM authors")
            for row in rows:
                entity = ExtractedEntity(
                    source_system=self.source_name,
                    entity_type="author",
                    external_id=self._create_external_id("author", row["id"]),
                    data={
                        "name": row.get("name"),
                        "biography": row.get("biography"),
                    },
                    raw_record=row,
                )
                entities.append(entity)

            # Extract collections
            rows = self._execute_query("SELECT * FROM collections")
            for row in rows:
                entity = ExtractedEntity(
                    source_system=self.source_name,
                    entity_type="book_collection",
                    external_id=self._create_external_id("collection", row["id"]),
                    data={
                        "name": row.get("name"),
                        "description": row.get("description"),
                    },
                    raw_record=row,
                )
                entities.append(entity)

            result.entities = entities
            result.relations = relations
            result.record_count = len(entities)

        except Exception as e:
            self.logger.error(f"Extraction failed: {e}")
            result.errors.append(str(e))
        finally:
            self.disconnect()

        result.duration_seconds = (datetime.now() - start_time).total_seconds()
        return result


class EduspaceExtractor(SQLiteExtractor):
    """Extract from ICANX Academy / Eduspace database."""

    def __init__(self):
        super().__init__(settings.sqlite_eduspace_db, "eduspace")

    def extract_all(self) -> ExtractionResult:
        """Extract all eduspace data."""
        start_time = datetime.now()
        result = ExtractionResult(source_system=self.source_name)

        try:
            if not self.connect():
                result.errors.append("Failed to connect")
                return result

            entities = []

            # Extract programs
            rows = self._execute_query("SELECT * FROM programs")
            for row in rows:
                entity = ExtractedEntity(
                    source_system=self.source_name,
                    entity_type="program",
                    external_id=self._create_external_id("program", row["id"]),
                    data={
                        "title": row.get("title"),
                        "category": row.get("category"),
                        "duration": row.get("duration"),
                        "level": row.get("level"),
                        "description": row.get("description"),
                        "price": row.get("price"),
                        "featured": self._safe_bool(row.get("featured")),
                    },
                    raw_record=row,
                )
                entities.append(entity)

            # Extract demo classes
            rows = self._execute_query("SELECT * FROM demo_classes")
            for row in rows:
                entity = ExtractedEntity(
                    source_system=self.source_name,
                    entity_type="demo_class",
                    external_id=self._create_external_id("demo_class", row["id"]),
                    data={
                        "title": row.get("title"),
                        "description": row.get("description"),
                        "schedule": row.get("schedule"),
                        "teacher": row.get("teacher"),
                    },
                    raw_record=row,
                )
                entities.append(entity)

            # Extract testimonials
            rows = self._execute_query("SELECT * FROM testimonials")
            for row in rows:
                entity = ExtractedEntity(
                    source_system=self.source_name,
                    entity_type="testimonial",
                    external_id=self._create_external_id("testimonial", row["id"]),
                    data={
                        "name": row.get("name"),
                        "role": row.get("role"),
                        "content": row.get("content"),
                        "rating": row.get("rating"),
                    },
                    raw_record=row,
                )
                entities.append(entity)

            result.entities = entities
            result.record_count = len(entities)

        except Exception as e:
            self.logger.error(f"Extraction failed: {e}")
            result.errors.append(str(e))
        finally:
            self.disconnect()

        result.duration_seconds = (datetime.now() - start_time).total_seconds()
        return result
