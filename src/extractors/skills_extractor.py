"""Skills Taxonomy extractor for ontology data."""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List

from ..config import settings
from .base import (
    BaseExtractor,
    ExtractedEntity,
    ExtractedRelation,
    ExtractionResult,
)


class SkillsExtractor(BaseExtractor):
    """Extract data from the Skills Taxonomy database."""

    def __init__(self):
        super().__init__("skills_taxonomy")
        self.db_path = settings.sqlite_skills_db
        self.conn = None

    def connect(self) -> bool:
        """Connect to the skills database."""
        try:
            if not self.db_path.exists():
                self.logger.warning(f"Skills database not found: {self.db_path}")
                return False
            self.conn = sqlite3.connect(str(self.db_path))
            self.conn.row_factory = sqlite3.Row
            self.logger.info(f"Connected to Skills DB: {self.db_path}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to Skills DB: {e}")
            return False

    def disconnect(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.logger.info("Disconnected from Skills DB")

    def _execute_query(self, query: str, params: tuple = ()) -> List[dict]:
        """Execute query and return results as list of dicts."""
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def extract_all(self) -> ExtractionResult:
        """Extract all skills taxonomy data."""
        start_time = datetime.now()
        result = ExtractionResult(source_system=self.source_name)

        try:
            if not self.connect():
                result.errors.append("Failed to connect to skills database")
                return result

            entities = []
            relations = []

            # === Extract Skill Domains ===
            rows = self._execute_query("SELECT * FROM skill_domains WHERE is_active = 1")
            for row in rows:
                entity = ExtractedEntity(
                    source_system=self.source_name,
                    entity_type="skill_domain",
                    external_id=self._create_external_id("domain", row["id"]),
                    data={
                        "code": row.get("code"),
                        "name": row.get("name"),
                        "description": row.get("description"),
                        "color_keyword": row.get("color"),
                        "sort_order": row.get("sort_order"),
                    },
                    raw_record=row,
                )
                entities.append(entity)

            # === Extract Skill Categories ===
            rows = self._execute_query("""
                SELECT c.*, d.code as domain_code
                FROM skill_categories c
                JOIN skill_domains d ON c.domain_id = d.id
                WHERE c.is_active = 1
            """)
            for row in rows:
                entity = ExtractedEntity(
                    source_system=self.source_name,
                    entity_type="skill_category",
                    external_id=self._create_external_id("category", row["id"]),
                    data={
                        "code": row.get("code"),
                        "name": row.get("name"),
                        "description": row.get("description"),
                        "domain_code": row.get("domain_code"),
                        "color_keyword": row.get("color"),
                        "sort_order": row.get("sort_order"),
                    },
                    raw_record=row,
                )
                entities.append(entity)

                # Create domain-category relation
                relations.append(
                    ExtractedRelation(
                        source_system=self.source_name,
                        relation_type="skill_classification",
                        from_entity_id=self._create_external_id("domain", row["domain_id"]),
                        to_entity_id=self._create_external_id("category", row["id"]),
                        from_entity_type="skill_domain",
                        to_entity_type="skill_category",
                    )
                )

            # === Extract Skills ===
            rows = self._execute_query("""
                SELECT s.*, c.code as category_code, d.code as domain_code
                FROM skills s
                JOIN skill_categories c ON s.category_id = c.id
                JOIN skill_domains d ON c.domain_id = d.id
                WHERE s.is_active = 1
            """)
            for row in rows:
                entity = ExtractedEntity(
                    source_system=self.source_name,
                    entity_type="skill",
                    external_id=self._create_external_id("skill", row["id"]),
                    data={
                        "skill_code": row.get("code"),
                        "skill_name": row.get("name"),
                        "description": row.get("description"),
                        "category_code": row.get("category_code"),
                        "domain_code": row.get("domain_code"),
                        "target_age_min": row.get("target_age_min"),
                        "target_age_max": row.get("target_age_max"),
                        "target_grade_min": row.get("target_grade_min"),
                        "target_grade_max": row.get("target_grade_max"),
                        "lexile_level": row.get("lexile_level"),
                        "cefr_level": row.get("cefr_level"),
                        "estimated_hours": row.get("estimated_hours"),
                        "is_core_skill": self._safe_bool(row.get("is_core_skill")),
                        "sort_order": row.get("sort_order"),
                    },
                    raw_record=row,
                )
                entities.append(entity)

                # Create category-skill relation
                relations.append(
                    ExtractedRelation(
                        source_system=self.source_name,
                        relation_type="skill_classification",
                        from_entity_id=self._create_external_id("category", row["category_id"]),
                        to_entity_id=self._create_external_id("skill", row["id"]),
                        from_entity_type="skill_category",
                        to_entity_type="skill",
                    )
                )

            # === Extract Competency Levels ===
            rows = self._execute_query("SELECT * FROM competency_levels ORDER BY level_number")
            for row in rows:
                entity = ExtractedEntity(
                    source_system=self.source_name,
                    entity_type="competency_level",
                    external_id=self._create_external_id("level", row["id"]),
                    data={
                        "code": row.get("code"),
                        "name": row.get("name"),
                        "description": row.get("description"),
                        "level_number": row.get("level_number"),
                        "mastery_threshold": row.get("mastery_threshold"),
                        "color_keyword": row.get("color"),
                    },
                    raw_record=row,
                )
                entities.append(entity)

            # === Extract Skill Prerequisites ===
            rows = self._execute_query("""
                SELECT p.*, s1.code as skill_code, s2.code as prereq_code
                FROM skill_prerequisites p
                JOIN skills s1 ON p.skill_id = s1.id
                JOIN skills s2 ON p.prerequisite_skill_id = s2.id
            """)
            for row in rows:
                relations.append(
                    ExtractedRelation(
                        source_system=self.source_name,
                        relation_type="skill_prerequisite",
                        from_entity_id=self._create_external_id("skill", row["prerequisite_skill_id"]),
                        to_entity_id=self._create_external_id("skill", row["skill_id"]),
                        from_entity_type="skill",
                        to_entity_type="skill",
                        attributes={
                            "is_required": self._safe_bool(row.get("is_required")),
                            "description": row.get("description"),
                        },
                    )
                )

            # === Extract Achievements ===
            rows = self._execute_query("SELECT * FROM achievements WHERE is_active = 1")
            for row in rows:
                entity = ExtractedEntity(
                    source_system=self.source_name,
                    entity_type="achievement",
                    external_id=self._create_external_id("achievement", row["id"]),
                    data={
                        "code": row.get("code"),
                        "badge_name": row.get("name"),
                        "description": row.get("description"),
                        "category": row.get("category"),
                        "requirement_type": row.get("requirement_type"),
                        "requirement_value": row.get("requirement_value"),
                        "points": row.get("points"),
                        "image_url": row.get("icon"),
                        "color_keyword": row.get("color"),
                    },
                    raw_record=row,
                )
                entities.append(entity)

            # === Extract Student Skill Progress ===
            rows = self._execute_query("""
                SELECT p.*, s.code as skill_code, s.name as skill_name,
                       l.code as level_code, l.name as level_name
                FROM student_skill_progress p
                JOIN skills s ON p.skill_id = s.id
                LEFT JOIN competency_levels l ON p.current_level_id = l.id
            """)
            for row in rows:
                entity = ExtractedEntity(
                    source_system=self.source_name,
                    entity_type="skill_progress",
                    external_id=self._create_external_id("progress", row["id"]),
                    data={
                        "student_id": row.get("student_id"),
                        "student_name": row.get("student_name"),
                        "skill_code": row.get("skill_code"),
                        "skill_name": row.get("skill_name"),
                        "current_level": row.get("level_name"),
                        "progress_percentage": row.get("progress_percentage"),
                        "mastery_date": row.get("mastery_date"),
                        "last_practiced": row.get("last_practiced"),
                        "total_practice_hours": row.get("total_practice_hours"),
                        "streak_days": row.get("streak_days"),
                        "average_score": row.get("average_score"),
                        "trend_direction": row.get("trend_direction"),
                    },
                    raw_record=row,
                )
                entities.append(entity)

            # === Extract Learning Recommendations ===
            rows = self._execute_query("""
                SELECT * FROM learning_recommendations WHERE is_active = 1
            """)
            for row in rows:
                entity = ExtractedEntity(
                    source_system=self.source_name,
                    entity_type="recommendation",
                    external_id=self._create_external_id("rec", row["id"]),
                    data={
                        "student_id": row.get("student_id"),
                        "recommendation_type": row.get("recommendation_type"),
                        "target_name": row.get("target_name"),
                        "reason": row.get("reason"),
                        "priority_score": row.get("priority_score"),
                    },
                    raw_record=row,
                )
                entities.append(entity)

            # === Extract Interventions ===
            rows = self._execute_query("""
                SELECT * FROM interventions WHERE status != 'resolved'
            """)
            for row in rows:
                entity = ExtractedEntity(
                    source_system=self.source_name,
                    entity_type="intervention",
                    external_id=self._create_external_id("intervention", row["id"]),
                    data={
                        "student_id": row.get("student_id"),
                        "student_name": row.get("student_name"),
                        "risk_level": row.get("risk_level"),
                        "intervention_type": row.get("intervention_type"),
                        "issue_description": row.get("issue_description"),
                        "recommended_actions": row.get("recommended_actions"),
                        "assigned_teacher_name": row.get("assigned_teacher_name"),
                        "status": row.get("status"),
                        "target_date": row.get("target_date"),
                    },
                    raw_record=row,
                )
                entities.append(entity)

            result.entities = entities
            result.relations = relations
            result.record_count = len(entities) + len(relations)

        except Exception as e:
            self.logger.error(f"Skills extraction failed: {e}")
            result.errors.append(str(e))
        finally:
            self.disconnect()

        result.duration_seconds = (datetime.now() - start_time).total_seconds()
        return result

    def extract_incremental(self, since=None) -> ExtractionResult:
        """Extract incremental data (full sync for now)."""
        return self.extract_all()
