"""Entity resolution for matching records across systems."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from fuzzywuzzy import fuzz
from loguru import logger

from ..extractors.base import ExtractedEntity
from .normalizers import normalize_email, normalize_name


@dataclass
class ResolvedEntity:
    """Represents a resolved/merged entity from multiple sources."""

    canonical_id: str
    entity_type: str
    source_ids: Dict[str, str] = field(default_factory=dict)  # source -> external_id
    merged_data: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0


class EntityResolver:
    """Resolves and merges entities across different data sources."""

    def __init__(self, name_match_threshold: int = 85):
        self.name_match_threshold = name_match_threshold
        self.resolved_teachers: Dict[str, ResolvedEntity] = {}
        self.resolved_students: Dict[str, ResolvedEntity] = {}
        self.logger = logger.bind(component="entity_resolver")

    def resolve_teachers(
        self, entities: List[ExtractedEntity]
    ) -> List[ResolvedEntity]:
        """
        Resolve teacher entities from multiple sources.

        Matching priority:
        1. Exact email match
        2. Notion ID match
        3. Employee number match
        4. Fuzzy name match (>threshold)
        """
        # Group entities by type
        teacher_entities = [
            e for e in entities if e.entity_type in ("teacher", "employee")
        ]

        self.logger.info(f"Resolving {len(teacher_entities)} teacher entities")

        resolved = []
        processed_ids: Set[str] = set()

        for entity in teacher_entities:
            if entity.external_id in processed_ids:
                continue

            # Find matches for this entity
            matches = self._find_teacher_matches(entity, teacher_entities)

            # Create resolved entity
            canonical_id = self._generate_canonical_id("teacher", entity)
            merged = self._merge_teacher_data([entity] + matches)

            resolved_entity = ResolvedEntity(
                canonical_id=canonical_id,
                entity_type="teacher",
                source_ids={e.source_system: e.external_id for e in [entity] + matches},
                merged_data=merged,
                confidence=self._calculate_confidence([entity] + matches),
            )

            resolved.append(resolved_entity)

            # Mark all matched entities as processed
            processed_ids.add(entity.external_id)
            for match in matches:
                processed_ids.add(match.external_id)

        self.logger.info(f"Resolved to {len(resolved)} unique teachers")
        return resolved

    def resolve_students(
        self, entities: List[ExtractedEntity]
    ) -> List[ResolvedEntity]:
        """
        Resolve student entities from multiple sources.

        Matching priority:
        1. Student ID match
        2. Notion ID match
        3. Exact name + grade match
        4. Fuzzy name match (>threshold)
        """
        student_entities = [e for e in entities if e.entity_type == "student"]

        self.logger.info(f"Resolving {len(student_entities)} student entities")

        resolved = []
        processed_ids: Set[str] = set()

        for entity in student_entities:
            if entity.external_id in processed_ids:
                continue

            matches = self._find_student_matches(entity, student_entities)

            canonical_id = self._generate_canonical_id("student", entity)
            merged = self._merge_student_data([entity] + matches)

            resolved_entity = ResolvedEntity(
                canonical_id=canonical_id,
                entity_type="student",
                source_ids={e.source_system: e.external_id for e in [entity] + matches},
                merged_data=merged,
                confidence=self._calculate_confidence([entity] + matches),
            )

            resolved.append(resolved_entity)

            processed_ids.add(entity.external_id)
            for match in matches:
                processed_ids.add(match.external_id)

        self.logger.info(f"Resolved to {len(resolved)} unique students")
        return resolved

    def _find_teacher_matches(
        self, entity: ExtractedEntity, all_entities: List[ExtractedEntity]
    ) -> List[ExtractedEntity]:
        """Find matching teacher entities."""
        matches = []
        entity_data = entity.data

        for candidate in all_entities:
            if candidate.external_id == entity.external_id:
                continue

            candidate_data = candidate.data

            # 1. Exact email match
            if (
                entity_data.get("email")
                and candidate_data.get("email")
                and normalize_email(entity_data["email"])
                == normalize_email(candidate_data["email"])
            ):
                matches.append(candidate)
                continue

            # 2. Notion ID match
            if (
                entity_data.get("notion_id")
                and candidate_data.get("notion_id")
                and entity_data["notion_id"] == candidate_data["notion_id"]
            ):
                matches.append(candidate)
                continue

            # 3. Employee number match
            if (
                entity_data.get("employee_number")
                and candidate_data.get("employee_number")
                and entity_data["employee_number"] == candidate_data["employee_number"]
            ):
                matches.append(candidate)
                continue

            # 4. Fuzzy name match
            entity_name = normalize_name(entity_data.get("name"))
            candidate_name = normalize_name(candidate_data.get("name"))

            if entity_name and candidate_name:
                ratio = fuzz.ratio(entity_name, candidate_name)
                if ratio >= self.name_match_threshold:
                    matches.append(candidate)

        return matches

    def _find_student_matches(
        self, entity: ExtractedEntity, all_entities: List[ExtractedEntity]
    ) -> List[ExtractedEntity]:
        """Find matching student entities."""
        matches = []
        entity_data = entity.data

        for candidate in all_entities:
            if candidate.external_id == entity.external_id:
                continue

            candidate_data = candidate.data

            # 1. Student ID match
            if (
                entity_data.get("student_id")
                and candidate_data.get("student_id")
                and entity_data["student_id"] == candidate_data["student_id"]
            ):
                matches.append(candidate)
                continue

            # 2. Notion ID match
            if (
                entity_data.get("notion_id")
                and candidate_data.get("notion_id")
                and entity_data["notion_id"] == candidate_data["notion_id"]
            ):
                matches.append(candidate)
                continue

            # 3. Exact name + grade match
            entity_name = normalize_name(entity_data.get("name"))
            candidate_name = normalize_name(candidate_data.get("name"))
            entity_grade = entity_data.get("grade")
            candidate_grade = candidate_data.get("grade")

            if (
                entity_name
                and candidate_name
                and entity_name == candidate_name
                and entity_grade
                and candidate_grade
                and entity_grade == candidate_grade
            ):
                matches.append(candidate)
                continue

            # 4. Fuzzy name match (higher threshold for students)
            if entity_name and candidate_name:
                ratio = fuzz.ratio(entity_name, candidate_name)
                if ratio >= self.name_match_threshold + 5:  # Higher threshold
                    matches.append(candidate)

        return matches

    def _merge_teacher_data(
        self, entities: List[ExtractedEntity]
    ) -> Dict[str, Any]:
        """Merge data from multiple teacher entities."""
        merged = {}

        # Priority order for sources
        source_priority = ["notion", "coaching", "postgres", "teacher_attendance"]

        # Fields to merge
        fields = [
            "name",
            "first_name",
            "last_name",
            "english_name",
            "email",
            "phone",
            "position",
            "department",
            "employee_number",
            "hire_date",
            "role_start_date",
            "color_keyword",
            "is_active",
            "notion_id",
            "photo_url",
        ]

        for field in fields:
            for source in source_priority:
                for entity in entities:
                    if entity.source_system == source:
                        value = entity.data.get(field)
                        if value is not None and field not in merged:
                            merged[field] = value
                            break

            # If still not found, take from any source
            if field not in merged:
                for entity in entities:
                    value = entity.data.get(field)
                    if value is not None:
                        merged[field] = value
                        break

        # Track source systems
        merged["_sources"] = list(set(e.source_system for e in entities))

        return merged

    def _merge_student_data(
        self, entities: List[ExtractedEntity]
    ) -> Dict[str, Any]:
        """Merge data from multiple student entities."""
        merged = {}

        # Priority order for sources
        source_priority = ["notion", "postgres", "student_attendance", "interviews"]

        # Fields to merge
        fields = [
            "name",
            "english_name",
            "student_id",
            "grade",
            "school",
            "gender",
            "age",
            "student_type",
            "weakness_level",
            "program_start_date",
            "program_end_date",
            "is_active",
            "notion_id",
            # Scores
            "reading_score",
            "grammar_score",
            "listening_score",
            "writing_score",
            "vocabulary_score",
            "interview_score",
            "level_test_total",
            "wpm_score",
            "pronunciation_score",
            "fluency_score",
            "comprehension_score",
        ]

        for field in fields:
            for source in source_priority:
                for entity in entities:
                    if entity.source_system == source:
                        value = entity.data.get(field)
                        if value is not None and field not in merged:
                            merged[field] = value
                            break

            if field not in merged:
                for entity in entities:
                    value = entity.data.get(field)
                    if value is not None:
                        merged[field] = value
                        break

        merged["_sources"] = list(set(e.source_system for e in entities))

        return merged

    def _generate_canonical_id(
        self, entity_type: str, entity: ExtractedEntity
    ) -> str:
        """Generate a canonical ID for a resolved entity."""
        data = entity.data

        # Try to use the most stable identifier
        if data.get("notion_id"):
            return f"{entity_type}_notion_{data['notion_id'][:8]}"
        if data.get("employee_number"):
            return f"{entity_type}_emp_{data['employee_number']}"
        if data.get("student_id"):
            return f"{entity_type}_sid_{data['student_id']}"
        if data.get("email"):
            return f"{entity_type}_email_{normalize_email(data['email']).replace('@', '_at_')}"

        # Fall back to first external_id
        return f"{entity_type}_{entity.external_id}"

    def _calculate_confidence(self, entities: List[ExtractedEntity]) -> float:
        """Calculate confidence score for the resolution."""
        if len(entities) == 1:
            return 1.0

        # More sources = more confidence
        sources = len(set(e.source_system for e in entities))

        # Check for strong matches (email, ID matches)
        has_email_match = False
        has_id_match = False

        for i, e1 in enumerate(entities):
            for e2 in entities[i + 1 :]:
                if (
                    e1.data.get("email")
                    and e2.data.get("email")
                    and normalize_email(e1.data["email"])
                    == normalize_email(e2.data["email"])
                ):
                    has_email_match = True
                if (
                    e1.data.get("notion_id")
                    and e2.data.get("notion_id")
                    and e1.data["notion_id"] == e2.data["notion_id"]
                ):
                    has_id_match = True

        confidence = 0.5 + (sources * 0.1)
        if has_email_match:
            confidence += 0.2
        if has_id_match:
            confidence += 0.2

        return min(confidence, 1.0)
