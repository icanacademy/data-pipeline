#!/usr/bin/env python3
"""Check health of all data sources."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings
from src.extractors import PostgreSQLExtractor, NotionExtractor
from src.extractors.sqlite import (
    TeacherAttendanceExtractor,
    StudentAttendanceExtractor,
    CoachingExtractor,
    DemoAssessmentExtractor,
    InterviewExtractor,
    StudentReportExtractor,
    MarketplaceExtractor,
)
from src.loaders import TypeDBLoader


def check_source(name: str, check_func) -> bool:
    """Check a single data source."""
    try:
        result = check_func()
        status = "OK" if result else "FAILED"
        print(f"  [{status}] {name}")
        return result
    except Exception as e:
        print(f"  [ERROR] {name}: {e}")
        return False


def main():
    """Run health checks on all data sources."""
    print("=" * 50)
    print("ICAN Data Center - Health Check")
    print("=" * 50)

    all_ok = True

    # TypeDB
    print("\nTypeDB:")
    loader = TypeDBLoader()
    if check_source(f"TypeDB ({settings.typedb_address})", loader.healthcheck):
        pass
    else:
        all_ok = False
        print("    Tip: docker run -d --name typedb -p 1729:1729 vaticle/typedb:latest")

    # PostgreSQL
    print("\nPostgreSQL:")
    pg = PostgreSQLExtractor()
    if not check_source(f"scheduling_db ({settings.postgres_host}:{settings.postgres_port})", pg.healthcheck):
        all_ok = False

    # SQLite databases
    print("\nSQLite Databases:")
    sqlite_checks = [
        ("Teacher Attendance", TeacherAttendanceExtractor),
        ("Student Attendance", StudentAttendanceExtractor),
        ("Coaching", CoachingExtractor),
        ("Demo Assessments", DemoAssessmentExtractor),
        ("Interviews", InterviewExtractor),
        ("Student Reports", StudentReportExtractor),
        ("Marketplace", MarketplaceExtractor),
    ]

    for name, ExtractorClass in sqlite_checks:
        extractor = ExtractorClass()
        if not check_source(f"{name} ({extractor.db_path})", extractor.healthcheck):
            all_ok = False

    # Notion
    print("\nNotion:")
    if settings.notion_api_key:
        notion = NotionExtractor()
        if not check_source("Notion API", notion.healthcheck):
            all_ok = False
    else:
        print("  [SKIP] Notion API (no API key configured)")

    # Summary
    print("\n" + "=" * 50)
    if all_ok:
        print("All checks passed!")
    else:
        print("Some checks failed. Please review above.")
    print("=" * 50)

    return all_ok


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
