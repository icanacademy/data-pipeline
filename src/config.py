"""Configuration management for ICAN Data Pipeline."""

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # TypeDB
    typedb_host: str = "localhost"
    typedb_port: int = 1729
    typedb_database: str = "ican_knowledge_graph"

    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_database: str = "scheduling_db"

    # SQLite Paths
    sqlite_attendance_db: Path = Path.home() / "attendance-checker/attendance.db"
    sqlite_student_attendance_db: Path = Path.home() / "student-attendance-checker/student-attendance.db"
    sqlite_coaching_db: Path = Path.home() / "academy-coaching-app/coaching.db"
    sqlite_marketplace_db: Path = Path.home() / "ican-app-marketplace/marketplace.db"
    sqlite_demo_assessment_db: Path = Path.home() / "ican-demo-assessment/demo_assessments.db"
    sqlite_interviews_db: Path = Path.home() / "interview-sheet-generator/server/interviews.db"
    sqlite_reports_db: Path = Path.home() / "student-report-app/student_reports.db"
    sqlite_n8n_db: Path = Path.home() / ".n8n/database.sqlite"

    # Unified Ontology Platform databases
    sqlite_student_analytics_db: Path = Path.home() / "unified-ontology-platform/backend/databases/student_analytics.db"
    sqlite_ican_classes_db: Path = Path.home() / "unified-ontology-platform/backend/databases/ican_classes.db"
    sqlite_books_library_db: Path = Path.home() / "unified-ontology-platform/backend/databases/books_library.db"

    # Eduspace / ICANX Academy
    sqlite_eduspace_db: Path = Path.home() / "Downloads/eduspace app/icanx-academy.db"

    # Face Attendance App (JSON)
    face_attendance_users_json: Path = Path.home() / "face-attendance-app/users.json"
    face_attendance_records_json: Path = Path.home() / "face-attendance-app/attendance.json"

    # Skills Taxonomy Database
    sqlite_skills_db: Path = Path.home() / "data-pipeline/databases/skills_taxonomy.db"

    # Notion
    notion_api_key: Optional[str] = None
    notion_teachers_db_id: Optional[str] = None
    notion_students_db_id: Optional[str] = None
    notion_online_students_db_id: Optional[str] = None
    notion_online_teachers_db_id: Optional[str] = None
    notion_student_schedule_db_id: Optional[str] = None
    notion_teacher_endorsements_db_id: Optional[str] = None
    notion_demo_data_db_id: Optional[str] = None
    notion_interviews_db_id: Optional[str] = None
    notion_books_db_id: Optional[str] = None
    notion_daily_report_db_id: Optional[str] = None
    notion_rubrics_db_id: Optional[str] = None
    notion_lessons_db_id: Optional[str] = None
    notion_teacher_attendance_db_id: Optional[str] = None
    notion_student_attendance_db_id: Optional[str] = None
    notion_noahs_ark_db_id: Optional[str] = None
    notion_reading_level_db_id: Optional[str] = None
    notion_skills_db_id: Optional[str] = None
    notion_microskills_db_id: Optional[str] = None
    notion_korean_registration_db_id: Optional[str] = None

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8080
    api_debug: bool = True

    # Sync
    sync_interval_minutes: int = 15
    full_sync_hour: int = 6

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def postgres_url(self) -> str:
        """Get PostgreSQL connection URL."""
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_database}"

    @property
    def typedb_address(self) -> str:
        """Get TypeDB server address."""
        return f"{self.typedb_host}:{self.typedb_port}"


# Global settings instance
settings = Settings()
