"""Map extracted entities to TypeDB queries."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger

from ..extractors.base import ExtractedEntity, ExtractedRelation
from .entity_resolver import ResolvedEntity


class TypeDBMapper:
    """Maps entities and relations to TypeDB insert queries."""

    def __init__(self):
        self.logger = logger.bind(component="typedb_mapper")

    def entity_to_insert(self, entity: ExtractedEntity) -> str:
        """Convert an ExtractedEntity to a TypeDB insert query."""
        entity_type = self._map_entity_type(entity.entity_type)
        attributes = self._build_attributes(entity.data, entity.external_id, entity.source_system)

        return f"""
insert
$e isa {entity_type},
{attributes};
"""

    def resolved_entity_to_insert(self, resolved: ResolvedEntity) -> str:
        """Convert a ResolvedEntity to a TypeDB insert query."""
        entity_type = resolved.entity_type
        data = resolved.merged_data.copy()

        # Add canonical ID as external_id
        data["external_id"] = resolved.canonical_id

        attributes = self._build_attributes(data, resolved.canonical_id, "merged")

        return f"""
insert
$e isa {entity_type},
{attributes};
"""

    def relation_to_insert(self, relation: ExtractedRelation) -> str:
        """Convert an ExtractedRelation to a TypeDB insert query."""
        relation_type = self._map_relation_type(relation.relation_type)

        # Build role players
        from_role, to_role = self._get_relation_roles(relation.relation_type)

        query = f"""
match
$from isa {relation.from_entity_type}, has external_id "{relation.from_entity_id}";
$to isa {relation.to_entity_type}, has external_id "{relation.to_entity_id}";
insert
({from_role}: $from, {to_role}: $to) isa {relation_type}
"""

        # Add attributes if present
        if relation.attributes:
            attrs = []
            for key, value in relation.attributes.items():
                formatted = self._format_value(value)
                if formatted:
                    attrs.append(f"has {key} {formatted}")
            if attrs:
                query += ", " + ", ".join(attrs)

        query += ";"
        return query

    def build_batch_insert(
        self, entities: List[ExtractedEntity], batch_size: int = 50
    ) -> List[str]:
        """Build batched insert queries for multiple entities."""
        queries = []
        current_batch = []

        for entity in entities:
            current_batch.append(self.entity_to_insert(entity))

            if len(current_batch) >= batch_size:
                queries.append("\n".join(current_batch))
                current_batch = []

        if current_batch:
            queries.append("\n".join(current_batch))

        return queries

    def build_upsert(self, entity: ExtractedEntity) -> str:
        """Build an upsert query (update if exists, insert if not)."""
        entity_type = self._map_entity_type(entity.entity_type)
        external_id = entity.external_id

        # Build attribute updates
        updates = []
        for key, value in entity.data.items():
            if key.startswith("_") or key == "external_id":
                continue
            formatted = self._format_value(value)
            if formatted:
                updates.append(f"$e has {key} {formatted}")

        update_str = ", ".join(updates)

        return f"""
match
$e isa {entity_type}, has external_id "{external_id}";
delete
$e has sync_timestamp $old_ts;
insert
$e has sync_timestamp {self._format_value(datetime.now())};
"""

    def _map_entity_type(self, source_type: str) -> str:
        """Map source entity type to TypeDB entity type."""
        mapping = {
            "teacher": "teacher",
            "employee": "teacher",
            "student": "student",
            "room": "room",
            "time_slot": "time-slot",
            "class_assignment": "class-assignment",
            "assignment": "class-assignment",
            "attendance": "attendance",
            "student_attendance": "attendance",
            "coaching_record": "coaching-record",
            "coaching_category": "coaching-category",
            "offense_type": "offense-type",
            "demo_assessment": "demo-assessment",
            "interview_assessment": "interview-assessment",
            "student_report": "student-report",
            "educational_app": "educational-app",
            "app_comment": "app-comment",
            "workflow": "workflow",
            "workflow_run": "workflow-run",
        }
        return mapping.get(source_type, source_type)

    def _map_relation_type(self, source_type: str) -> str:
        """Map source relation type to TypeDB relation type."""
        mapping = {
            "teaching": "teaching",
            "supervision": "supervision",
            "substitution": "substitution",
            "attendance_record": "attendance-record",
            "coaching_session": "coaching-session",
            "offense_classification": "offense-classification",
            "assessment_event": "assessment-event",
            "app_contribution": "app-contribution",
            "app_review": "app-review",
        }
        return mapping.get(source_type, source_type)

    def _get_relation_roles(self, relation_type: str) -> tuple:
        """Get role names for a relation type."""
        roles = {
            "teaching": ("instructor", "learner"),
            "supervision": ("supervisor", "supervisee"),
            "substitution": ("original-teacher", "substitute-teacher"),
            "attendance_record": ("attendee", "record"),
            "coaching_session": ("coach", "coachee"),
            "assessment_event": ("assessor", "subject"),
            "app_contribution": ("contributor", "app"),
            "app_review": ("reviewer", "app"),
        }
        return roles.get(relation_type, ("from", "to"))

    def _build_attributes(
        self, data: Dict[str, Any], external_id: str, source_system: str
    ) -> str:
        """Build attribute list for an entity."""
        attributes = [
            f'has external_id "{external_id}"',
            f'has source_system "{source_system}"',
            f"has sync_timestamp {self._format_value(datetime.now())}",
        ]

        # Map data fields to TypeDB attributes
        field_mapping = {
            "name": "name",
            "first_name": "first_name",
            "last_name": "last_name",
            "english_name": "english_name",
            "email": "email",
            "phone": "phone",
            "gender": "gender",
            "age": "age",
            "photo_url": "photo_url",
            "employee_number": "employee_number",
            "position": "position",
            "department": "department",
            "hire_date": "hire_date",
            "role_start_date": "role_start_date",
            "is_active": "is_active",
            "color_keyword": "color_keyword",
            "student_id": "student_id",
            "grade": "grade",
            "school": "school",
            "student_type": "student_type",
            "weakness_level": "weakness_level",
            "program_start_date": "program_start_date",
            "program_end_date": "program_end_date",
            "notion_id": "notion_id",
            # Scores
            "reading_score": "reading_score",
            "grammar_score": "grammar_score",
            "listening_score": "listening_score",
            "writing_score": "writing_score",
            "vocabulary_score": "vocabulary_score",
            "interview_score": "interview_score",
            "level_test_total": "level_test_total",
            "wpm_score": "wpm_score",
            "pronunciation_score": "pronunciation_score",
            "fluency_score": "fluency_score",
            "comprehension_score": "comprehension_score",
            "insight_score": "insight_score",
            "knowledge_level": "knowledge_level",
            # Schedule
            "date": "date",
            "start_time": "start_time",
            "end_time": "end_time",
            "slot_name": "slot_name",
            "room_name": "room_name",
            # Attendance
            "attendance_status": "attendance_status",
            "minutes_late": "minutes_late",
            "late_reason": "late_reason",
            "absent_reason": "absent_reason",
            "has_undertime": "has_undertime",
            "undertime_minutes": "undertime_minutes",
            # Assessment
            "assessment_type": "assessment_type",
            "assessment_score": "assessment_score",
            "assessment_result": "assessment_result",
            "feedback": "feedback",
            "ai_feedback": "ai_feedback",
            "criteria_json": "criteria_json",
            "met_count": "met_count",
            "needs_improvement_count": "needs_improvement_count",
            "fail_count": "fail_count",
            # Coaching
            "coaching_type": "coaching_type",
            "offense_code": "offense_code",
            "offense_name": "offense_name",
            "offense_severity": "offense_severity",
            "issue_description": "issue_description",
            "expected_improvement": "expected_improvement",
            "improvement_timeline": "improvement_timeline",
            "follow_up_date": "follow_up_date",
            "employee_acknowledged": "employee_acknowledged",
            "employee_refused_sign": "employee_refused_sign",
            # Content
            "title": "title",
            "description": "description",
            "category": "category",
            "notes": "notes",
            "comments": "comments",
            "app_link": "app_link",
            "image_url": "image_url",
            "student_levels": "student_levels",
            "rating": "rating",
            # Timestamps
            "created_at": "created_at",
            "updated_at": "updated_at",
        }

        for source_field, typedb_field in field_mapping.items():
            if source_field in data and data[source_field] is not None:
                formatted = self._format_value(data[source_field])
                if formatted:
                    attributes.append(f"has {typedb_field} {formatted}")

        return ",\n".join(attributes)

    def _format_value(self, value: Any) -> Optional[str]:
        """Format a value for TypeDB query."""
        if value is None:
            return None

        if isinstance(value, bool):
            return "true" if value else "false"

        if isinstance(value, int):
            return str(value)

        if isinstance(value, float):
            return str(value)

        if isinstance(value, datetime):
            return f'{value.strftime("%Y-%m-%dT%H:%M:%S")}'

        if isinstance(value, str):
            # Escape special characters
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
            return f'"{escaped}"'

        if isinstance(value, (list, dict)):
            import json

            escaped = json.dumps(value).replace("\\", "\\\\").replace('"', '\\"')
            return f'"{escaped}"'

        return f'"{str(value)}"'
