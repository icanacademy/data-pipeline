"""Extractor for STELLAR student reports and personality data."""

import csv
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

from loguru import logger

from .base import (
    BaseExtractor,
    ExtractedEntity,
    ExtractedRelation,
    ExtractionResult,
)


# Personality dimension definitions
PERSONALITY_DIMENSIONS = {
    "EI": {
        "code": "EI",
        "name": "Interest Scope",
        "left_pole": {"code": "E", "name": "Explorer", "description": "Enjoys variety and breadth"},
        "right_pole": {"code": "I", "name": "Investigator", "description": "Prefers depth and mastery"},
    },
    "SC": {
        "code": "SC",
        "name": "Work Style",
        "left_pole": {"code": "S", "name": "Social", "description": "Energized by collaboration"},
        "right_pole": {"code": "C", "name": "Concentrated", "description": "Prefers independent focus"},
    },
    "PT": {
        "code": "PT",
        "name": "Learning Mode",
        "left_pole": {"code": "P", "name": "Practical", "description": "Learns by doing"},
        "right_pole": {"code": "T", "name": "Theoretical", "description": "Learns by thinking"},
    },
    "RN": {
        "code": "RN",
        "name": "Change Preference",
        "left_pole": {"code": "R", "name": "Routine", "description": "Values consistency"},
        "right_pole": {"code": "N", "name": "Novel", "description": "Embraces change"},
    },
    "AD": {
        "code": "AD",
        "name": "Decision Style",
        "left_pole": {"code": "A", "name": "Analytical", "description": "Deliberate and thorough"},
        "right_pole": {"code": "D", "name": "Decisive", "description": "Quick and action-oriented"},
    },
    "LG": {
        "code": "LG",
        "name": "Focus Level",
        "left_pole": {"code": "L", "name": "Local", "description": "Detail-oriented"},
        "right_pole": {"code": "G", "name": "Global", "description": "Big-picture thinker"},
    },
}


class StellarExtractor(BaseExtractor):
    """Extracts data from STELLAR student reports and personality assessments."""

    def __init__(self):
        super().__init__("stellar")
        self.reports_csv = Path.home() / "Stellar" / "teacher-report-generator" / "reports.csv"
        self.personality_json = Path.home() / "Stellar" / "student-report-viewer" / "data" / "personality-data.json"

    def connect(self) -> bool:
        """Check if data files exist."""
        csv_exists = self.reports_csv.exists()
        json_exists = self.personality_json.exists()
        if csv_exists or json_exists:
            self.logger.info(f"STELLAR data files found (CSV: {csv_exists}, JSON: {json_exists})")
            return True
        self.logger.warning("No STELLAR data files found")
        return False

    def disconnect(self) -> None:
        """No connection to close."""
        pass

    def extract_all(self) -> ExtractionResult:
        """Extract all STELLAR data."""
        start_time = datetime.now()
        entities = []
        relations = []
        errors = []

        # Extract personality dimension definitions
        dim_entities = self._extract_personality_dimensions()
        entities.extend(dim_entities)

        # Extract personality data
        try:
            persona_entities, persona_relations = self._extract_personality_data()
            entities.extend(persona_entities)
            relations.extend(persona_relations)
        except Exception as e:
            self.logger.error(f"Error extracting personality data: {e}")
            errors.append(f"Personality data: {e}")

        # Extract student reports
        try:
            report_entities, report_relations = self._extract_student_reports()
            entities.extend(report_entities)
            relations.extend(report_relations)
        except Exception as e:
            self.logger.error(f"Error extracting student reports: {e}")
            errors.append(f"Student reports: {e}")

        duration = (datetime.now() - start_time).total_seconds()

        return ExtractionResult(
            source_system="stellar",
            entities=entities,
            relations=relations,
            errors=errors,
            extracted_at=datetime.now(),
            duration_seconds=duration,
            record_count=len(entities),
        )

    def extract_incremental(self, since: Optional[datetime] = None) -> ExtractionResult:
        """Extract incremental data (not implemented, returns full extract)."""
        return self.extract_all()

    def _extract_personality_dimensions(self) -> List[ExtractedEntity]:
        """Extract personality dimension definitions as entities."""
        entities = []

        for dim_code, dim_info in PERSONALITY_DIMENSIONS.items():
            entities.append(ExtractedEntity(
                source_system="stellar",
                entity_type="personality_dimension",
                external_id=f"stellar_dim_{dim_code}",
                data={
                    "code": dim_code,
                    "name": dim_info["name"],
                    "left_pole_code": dim_info["left_pole"]["code"],
                    "left_pole_name": dim_info["left_pole"]["name"],
                    "left_pole_description": dim_info["left_pole"]["description"],
                    "right_pole_code": dim_info["right_pole"]["code"],
                    "right_pole_name": dim_info["right_pole"]["name"],
                    "right_pole_description": dim_info["right_pole"]["description"],
                },
            ))

        return entities

    def _extract_personality_data(self) -> tuple:
        """Extract student personality quiz data."""
        entities = []
        relations = []

        if not self.personality_json.exists():
            self.logger.warning(f"Personality data file not found: {self.personality_json}")
            return entities, relations

        with open(self.personality_json, "r") as f:
            personality_data = json.load(f)

        for student_name, data in personality_data.items():
            quiz_data = data.get("quizData", {})
            if not quiz_data.get("taken"):
                continue

            scores = quiz_data.get("scores", {})
            answers = quiz_data.get("answers", [])
            taken_at = quiz_data.get("takenAt")

            # Create student persona entity
            student_id = self._sanitize_id(student_name)

            # Determine personality type code based on scores
            type_code = self._calculate_personality_type(scores)

            entities.append(ExtractedEntity(
                source_system="stellar",
                entity_type="student_persona",
                external_id=f"persona_{student_id}",
                data={
                    "student_name": student_name,
                    "student_id": student_id,
                    "personality_type": type_code,
                    "quiz_taken_at": taken_at,
                    "quiz_answers": json.dumps(answers),
                    # Individual dimension scores (0-100, 50 is balanced)
                    "score_ei": scores.get("EI", 50),
                    "score_sc": scores.get("SC", 50),
                    "score_pt": scores.get("PT", 50),
                    "score_rn": scores.get("RN", 50),
                    "score_ad": scores.get("AD", 50),
                    "score_lg": scores.get("LG", 50),
                },
            ))

            # Create relations for each dimension score
            for dim_code in ["EI", "SC", "PT", "RN", "AD", "LG"]:
                score = scores.get(dim_code, 50)
                relations.append(ExtractedRelation(
                    source_system="stellar",
                    relation_type="has_personality_score",
                    from_entity_id=f"persona_{student_id}",
                    to_entity_id=f"stellar_dim_{dim_code}",
                    from_entity_type="student_persona",
                    to_entity_type="personality_dimension",
                    attributes={
                        "score": score,
                        "tendency": self._get_tendency(dim_code, score),
                    },
                ))

        self.logger.info(f"Extracted {len(entities)} student personas")
        return entities, relations

    def _sanitize_id(self, name: str) -> str:
        """Sanitize a name for use as an ID."""
        return name.replace(" ", "_").replace("[", "").replace("]", "").replace("(", "").replace(")", "")

    def _calculate_personality_type(self, scores: Dict[str, int]) -> str:
        """Calculate the 6-letter personality type code from scores."""
        type_code = ""

        dim_mapping = {
            "EI": ("E", "I"),
            "SC": ("S", "C"),
            "PT": ("P", "T"),
            "RN": ("R", "N"),
            "AD": ("A", "D"),
            "LG": ("L", "G"),
        }

        for dim, (left, right) in dim_mapping.items():
            score = scores.get(dim, 50)
            if score < 45:
                type_code += left
            elif score > 55:
                type_code += right
            else:
                type_code += "X"  # Balanced

        return type_code

    def _get_tendency(self, dim_code: str, score: int) -> str:
        """Get the tendency description for a dimension score."""
        dim = PERSONALITY_DIMENSIONS.get(dim_code, {})
        left_name = dim.get("left_pole", {}).get("name", "Left")
        right_name = dim.get("right_pole", {}).get("name", "Right")

        if score < 35:
            return f"Strong {left_name}"
        elif score < 45:
            return f"Moderate {left_name}"
        elif score <= 55:
            return "Balanced"
        elif score <= 65:
            return f"Moderate {right_name}"
        else:
            return f"Strong {right_name}"

    def _extract_student_reports(self) -> tuple:
        """Extract student reports from CSV."""
        entities = []
        relations = []

        if not self.reports_csv.exists():
            self.logger.warning(f"Reports CSV not found: {self.reports_csv}")
            return entities, relations

        seen_students = set()
        seen_teachers = set()
        report_count = 0

        with open(self.reports_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:
                student_name = row.get("Student Name", "").strip()
                teacher_name = row.get("Teacher Name", "").strip()
                report_date = row.get("Date", "")
                subject = row.get("Subject", "")

                if not student_name:
                    continue

                # Create student entity (deduped)
                student_id = self._sanitize_id(student_name)
                if student_id not in seen_students:
                    seen_students.add(student_id)
                    entities.append(ExtractedEntity(
                        source_system="stellar",
                        entity_type="student",
                        external_id=f"stellar_student_{student_id}",
                        data={
                            "name": student_name,
                            "grade_level": row.get("Grade Level"),
                            "student_id": row.get("Student ID"),
                            "gender": row.get("Student Gender"),
                            "wpm_initial": row.get("WPM Initial"),
                            "reading_level": row.get("Reading Level Initial"),
                        },
                    ))

                # Create teacher entity (deduped)
                if teacher_name:
                    teacher_id = self._sanitize_id(teacher_name)
                    if teacher_id not in seen_teachers:
                        seen_teachers.add(teacher_id)
                        entities.append(ExtractedEntity(
                            source_system="stellar",
                            entity_type="teacher",
                            external_id=f"stellar_teacher_{teacher_id}",
                            data={
                                "name": teacher_name,
                                "teacher_id": row.get("Teacher ID"),
                            },
                        ))

                # Create report entity
                report_id = self._sanitize_id(f"{student_name}_{report_date}_{subject}")
                report_count += 1

                # Parse skill scores JSON
                skills_json = row.get("Skills", "{}")
                scores_json = row.get("Scores", "{}")

                try:
                    skills = json.loads(skills_json) if skills_json else {}
                except json.JSONDecodeError:
                    skills = {}

                try:
                    scores = json.loads(scores_json) if scores_json else {}
                except json.JSONDecodeError:
                    scores = {}

                entities.append(ExtractedEntity(
                    source_system="stellar",
                    entity_type="student_report",
                    external_id=f"stellar_report_{report_id}_{report_count}",
                    data={
                        "student_name": student_name,
                        "teacher_name": teacher_name,
                        "date": report_date,
                        "day_of_week": row.get("Day of Week"),
                        "subject": subject,
                        "skill_focus": row.get("Skill Focus"),
                        "skill_focus_met": row.get("SF Met"),
                        "current_lesson": row.get("Current Lesson"),
                        "materials": row.get("Materials"),
                        "homework": row.get("Homework"),
                        "next_lesson": row.get("Next Lesson"),
                        "activities_finished": row.get("Activities Finished"),
                        "activities_not_finished": row.get("Activities Not Finished"),
                        # Ratings (1-5 scale)
                        "attention": self._safe_int(row.get("Attention")),
                        "retention": self._safe_int(row.get("Retention")),
                        "comprehension": self._safe_int(row.get("Comprehension")),
                        "behavior": self._safe_int(row.get("Behavior")),
                        "handwriting": self._safe_int(row.get("Handwriting")),
                        "conversation": self._safe_int(row.get("Conversation")),
                        # Parsed JSON data
                        "skills": skills,
                        "scores": scores,
                        "narrative": row.get("Narrative"),
                    },
                ))

                # Create student-report relation
                relations.append(ExtractedRelation(
                    source_system="stellar",
                    relation_type="has_report",
                    from_entity_id=f"stellar_student_{student_id}",
                    to_entity_id=f"stellar_report_{report_id}_{report_count}",
                    from_entity_type="student",
                    to_entity_type="student_report",
                    attributes={"date": report_date},
                ))

                # Create teacher-report relation
                if teacher_name:
                    teacher_id = self._sanitize_id(teacher_name)
                    relations.append(ExtractedRelation(
                        source_system="stellar",
                        relation_type="authored_report",
                        from_entity_id=f"stellar_teacher_{teacher_id}",
                        to_entity_id=f"stellar_report_{report_id}_{report_count}",
                        from_entity_type="teacher",
                        to_entity_type="student_report",
                        attributes={"date": report_date},
                    ))

        self.logger.info(f"Extracted {len(seen_students)} students, {len(seen_teachers)} teachers, {report_count} reports")
        return entities, relations

    def _safe_int(self, value: Any) -> int:
        """Safely convert value to int."""
        if value is None or value == "":
            return 0
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0
