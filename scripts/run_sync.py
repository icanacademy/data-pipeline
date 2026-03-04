#!/usr/bin/env python3
"""Manual sync script to populate the knowledge graph."""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

from src.config import settings
from src.extractors import PostgreSQLExtractor, NotionExtractor, FaceAttendanceExtractor, SkillsExtractor, StellarExtractor
from src.extractors.sqlite import (
    TeacherAttendanceExtractor,
    StudentAttendanceExtractor,
    CoachingExtractor,
    DemoAssessmentExtractor,
    InterviewExtractor,
    StudentReportExtractor,
    MarketplaceExtractor,
    StudentAnalyticsExtractor,
    IcanClassesExtractor,
    BooksLibraryExtractor,
    EduspaceExtractor,
)
from src.loaders import TypeDBLoader
from src.transformers import EntityResolver


def main():
    """Run a full sync from all data sources."""
    start_time = datetime.now()
    logger.info("Starting full sync...")

    all_entities = []
    all_relations = []
    errors = []

    # PostgreSQL
    logger.info("Extracting from PostgreSQL...")
    try:
        pg_extractor = PostgreSQLExtractor()
        result = pg_extractor.extract_all()
        all_entities.extend(result.entities)
        all_relations.extend(result.relations)
        errors.extend(result.errors)
        logger.info(f"  PostgreSQL: {len(result.entities)} entities, {len(result.relations)} relations")
    except Exception as e:
        logger.error(f"  PostgreSQL failed: {e}")
        errors.append(f"PostgreSQL: {e}")

    # SQLite databases
    sqlite_extractors = [
        ("Teacher Attendance", TeacherAttendanceExtractor),
        ("Student Attendance", StudentAttendanceExtractor),
        ("Coaching", CoachingExtractor),
        ("Demo Assessments", DemoAssessmentExtractor),
        ("Interviews", InterviewExtractor),
        ("Student Reports", StudentReportExtractor),
        ("Marketplace", MarketplaceExtractor),
        ("Student Analytics", StudentAnalyticsExtractor),
        ("ICAN Classes", IcanClassesExtractor),
        ("Books Library", BooksLibraryExtractor),
        ("Eduspace/ICANX", EduspaceExtractor),
    ]

    # JSON data sources
    logger.info("Extracting from Face Attendance (JSON)...")
    try:
        face_extractor = FaceAttendanceExtractor()
        result = face_extractor.extract_all()
        all_entities.extend(result.entities)
        all_relations.extend(result.relations)
        errors.extend(result.errors)
        logger.info(f"  Face Attendance: {len(result.entities)} entities")
    except Exception as e:
        logger.error(f"  Face Attendance failed: {e}")
        errors.append(f"Face Attendance: {e}")

    # Skills Taxonomy (Ontology)
    logger.info("Extracting from Skills Taxonomy...")
    try:
        skills_extractor = SkillsExtractor()
        result = skills_extractor.extract_all()
        all_entities.extend(result.entities)
        all_relations.extend(result.relations)
        errors.extend(result.errors)
        logger.info(f"  Skills Taxonomy: {len(result.entities)} entities, {len(result.relations)} relations")
    except Exception as e:
        logger.error(f"  Skills Taxonomy failed: {e}")
        errors.append(f"Skills Taxonomy: {e}")

    # STELLAR Student Reports and Personas
    logger.info("Extracting from STELLAR (Reports & Personas)...")
    try:
        stellar_extractor = StellarExtractor()
        result = stellar_extractor.extract_all()
        all_entities.extend(result.entities)
        all_relations.extend(result.relations)
        errors.extend(result.errors)
        logger.info(f"  STELLAR: {len(result.entities)} entities, {len(result.relations)} relations")
    except Exception as e:
        logger.error(f"  STELLAR failed: {e}")
        errors.append(f"STELLAR: {e}")

    for name, ExtractorClass in sqlite_extractors:
        logger.info(f"Extracting from {name}...")
        try:
            extractor = ExtractorClass()
            result = extractor.extract_all()
            all_entities.extend(result.entities)
            all_relations.extend(result.relations)
            errors.extend(result.errors)
            logger.info(f"  {name}: {len(result.entities)} entities, {len(result.relations)} relations")
        except Exception as e:
            logger.error(f"  {name} failed: {e}")
            errors.append(f"{name}: {e}")

    # Notion
    if settings.notion_api_key:
        logger.info("Extracting from Notion...")
        try:
            notion_extractor = NotionExtractor()
            result = notion_extractor.extract_all()
            all_entities.extend(result.entities)
            all_relations.extend(result.relations)
            errors.extend(result.errors)
            logger.info(f"  Notion: {len(result.entities)} entities")
        except Exception as e:
            logger.error(f"  Notion failed: {e}")
            errors.append(f"Notion: {e}")
    else:
        logger.info("Skipping Notion (no API key configured)")

    logger.info(f"\nTotal extracted: {len(all_entities)} entities, {len(all_relations)} relations")

    # Entity resolution
    logger.info("\nResolving entities across systems...")
    resolver = EntityResolver()

    resolved_teachers = resolver.resolve_teachers(all_entities)
    resolved_students = resolver.resolve_students(all_entities)

    logger.info(f"  Resolved to {len(resolved_teachers)} unique teachers")
    logger.info(f"  Resolved to {len(resolved_students)} unique students")

    # Load into TypeDB
    logger.info("\nLoading into TypeDB...")
    loader = TypeDBLoader()

    if not loader.connect():
        logger.error("Failed to connect to TypeDB")
        logger.info("\nTo start TypeDB:")
        logger.info("  docker run -d --name typedb -p 1729:1729 vaticle/typedb:latest")
        return False

    # First, set up database if needed
    schema_path = Path(__file__).parent.parent / "schema" / "ican_schema.tql"
    if schema_path.exists():
        loader.setup_database(schema_path)

    # Load resolved entities
    teachers_loaded = loader.load_resolved_entities(resolved_teachers)
    students_loaded = loader.load_resolved_entities(resolved_students)

    # Load other entities
    other_entities = [
        e for e in all_entities
        if e.entity_type not in ("teacher", "employee", "student")
    ]
    others_loaded = loader.load_entities(other_entities)

    # Load relations
    relations_loaded = loader.load_relations(all_relations)

    loader.disconnect()

    # Summary
    duration = (datetime.now() - start_time).total_seconds()
    logger.info("\n" + "=" * 50)
    logger.info("SYNC COMPLETE")
    logger.info("=" * 50)
    logger.info(f"Duration: {duration:.2f} seconds")
    logger.info(f"Teachers loaded: {teachers_loaded}")
    logger.info(f"Students loaded: {students_loaded}")
    logger.info(f"Other entities loaded: {others_loaded}")
    logger.info(f"Relations loaded: {relations_loaded}")

    if errors:
        logger.warning(f"\nErrors ({len(errors)}):")
        for error in errors:
            logger.warning(f"  - {error}")

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
