"""Notion API extractor."""

from datetime import datetime
from typing import Any, Dict, Generator, List, Optional

from ..config import settings
from .base import (
    BaseExtractor,
    ExtractedEntity,
    ExtractedRelation,
    ExtractionResult,
)

try:
    from notion_client import Client
    NOTION_AVAILABLE = True
except ImportError:
    NOTION_AVAILABLE = False


class NotionExtractor(BaseExtractor):
    """Extract data from Notion databases."""

    def __init__(self):
        super().__init__("notion")
        self.client = None

    def connect(self) -> bool:
        """Connect to Notion API."""
        if not NOTION_AVAILABLE:
            self.logger.error("notion-client not installed")
            return False

        if not settings.notion_api_key:
            self.logger.error("Notion API key not configured")
            return False

        try:
            self.client = Client(auth=settings.notion_api_key)
            # Test connection by fetching user info
            self.client.users.me()
            self.logger.info("Connected to Notion API")
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to Notion: {e}")
            return False

    def disconnect(self) -> None:
        """Disconnect from Notion (no-op for HTTP API)."""
        self.client = None
        self.logger.info("Disconnected from Notion API")

    def extract_all(self) -> ExtractionResult:
        """Extract all data from configured Notion databases."""
        start_time = datetime.now()
        result = ExtractionResult(source_system=self.source_name)

        try:
            if not self.connect():
                result.errors.append("Failed to connect to Notion")
                return result

            entities = []
            relations = []

            # Extract teachers if database ID is configured
            if settings.notion_teachers_db_id:
                teachers = list(
                    self._extract_database(
                        settings.notion_teachers_db_id,
                        "teacher",
                        self._parse_employee_page,
                    )
                )
                entities.extend(teachers)
                self.logger.info(f"Extracted {len(teachers)} teachers from Notion")

            # Extract online teachers
            if getattr(settings, 'notion_online_teachers_db_id', None):
                online_teachers = list(
                    self._extract_database(
                        settings.notion_online_teachers_db_id,
                        "teacher",
                        self._parse_employee_page,
                    )
                )
                entities.extend(online_teachers)
                self.logger.info(f"Extracted {len(online_teachers)} online teachers from Notion")

            # Extract students if database ID is configured
            if settings.notion_students_db_id:
                students = list(
                    self._extract_database(
                        settings.notion_students_db_id,
                        "student",
                        self._parse_student_page,
                    )
                )
                entities.extend(students)
                self.logger.info(f"Extracted {len(students)} students from Notion")

            # Extract online students
            if getattr(settings, 'notion_online_students_db_id', None):
                online_students = list(
                    self._extract_database(
                        settings.notion_online_students_db_id,
                        "student",
                        self._parse_online_student_page,
                    )
                )
                entities.extend(online_students)
                self.logger.info(f"Extracted {len(online_students)} online students from Notion")

            # Extract books
            if getattr(settings, 'notion_books_db_id', None):
                books = list(
                    self._extract_database(
                        settings.notion_books_db_id,
                        "book",
                        self._parse_book_page,
                    )
                )
                entities.extend(books)
                self.logger.info(f"Extracted {len(books)} books from Notion")

            # Extract interviews
            if getattr(settings, 'notion_interviews_db_id', None):
                interviews = list(
                    self._extract_database(
                        settings.notion_interviews_db_id,
                        "interview",
                        self._parse_interview_page,
                    )
                )
                entities.extend(interviews)
                self.logger.info(f"Extracted {len(interviews)} interviews from Notion")

            # Extract demo assessments
            if getattr(settings, 'notion_demo_data_db_id', None):
                demos = list(
                    self._extract_database(
                        settings.notion_demo_data_db_id,
                        "demo_assessment",
                        self._parse_demo_page,
                    )
                )
                entities.extend(demos)
                self.logger.info(f"Extracted {len(demos)} demo assessments from Notion")

            # Extract daily reports
            if getattr(settings, 'notion_daily_report_db_id', None):
                reports = list(
                    self._extract_database(
                        settings.notion_daily_report_db_id,
                        "daily_report",
                        self._parse_daily_report_page,
                    )
                )
                entities.extend(reports)
                self.logger.info(f"Extracted {len(reports)} daily reports from Notion")

            # Extract lessons/curriculum
            if getattr(settings, 'notion_lessons_db_id', None):
                lessons = list(
                    self._extract_database(
                        settings.notion_lessons_db_id,
                        "lesson",
                        self._parse_lesson_page,
                    )
                )
                entities.extend(lessons)
                self.logger.info(f"Extracted {len(lessons)} lessons from Notion")

            # Extract rubrics
            if getattr(settings, 'notion_rubrics_db_id', None):
                rubrics = list(
                    self._extract_database(
                        settings.notion_rubrics_db_id,
                        "rubric",
                        self._parse_rubric_page,
                    )
                )
                entities.extend(rubrics)
                self.logger.info(f"Extracted {len(rubrics)} rubrics from Notion")

            # Extract skills
            if getattr(settings, 'notion_skills_db_id', None):
                skills = list(
                    self._extract_database(
                        settings.notion_skills_db_id,
                        "skill",
                        self._parse_skill_page,
                    )
                )
                entities.extend(skills)
                self.logger.info(f"Extracted {len(skills)} skills from Notion")

            # Extract teacher endorsements
            if getattr(settings, 'notion_teacher_endorsements_db_id', None):
                endorsements = list(
                    self._extract_database(
                        settings.notion_teacher_endorsements_db_id,
                        "endorsement",
                        self._parse_endorsement_page,
                    )
                )
                entities.extend(endorsements)
                self.logger.info(f"Extracted {len(endorsements)} endorsements from Notion")

            # Extract Noah's Ark (teacher check-ins)
            if getattr(settings, 'notion_noahs_ark_db_id', None):
                checkins = list(
                    self._extract_database(
                        settings.notion_noahs_ark_db_id,
                        "teacher_checkin",
                        self._parse_noahs_ark_page,
                    )
                )
                entities.extend(checkins)
                self.logger.info(f"Extracted {len(checkins)} teacher check-ins from Notion")

            # Extract reading level assessments
            if getattr(settings, 'notion_reading_level_db_id', None):
                reading_assessments = list(
                    self._extract_database(
                        settings.notion_reading_level_db_id,
                        "reading_assessment",
                        self._parse_reading_level_page,
                    )
                )
                entities.extend(reading_assessments)
                self.logger.info(f"Extracted {len(reading_assessments)} reading assessments from Notion")

            # Extract Korean student registrations
            if getattr(settings, 'notion_korean_registration_db_id', None):
                registrations = list(
                    self._extract_database(
                        settings.notion_korean_registration_db_id,
                        "registration",
                        self._parse_korean_registration_page,
                    )
                )
                entities.extend(registrations)
                self.logger.info(f"Extracted {len(registrations)} Korean registrations from Notion")

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
        """Extract data modified since timestamp."""
        if since is None:
            return self.extract_all()

        start_time = datetime.now()
        result = ExtractionResult(source_system=self.source_name)

        try:
            if not self.connect():
                result.errors.append("Failed to connect to Notion")
                return result

            entities = []

            # Use Notion's filter to get recently modified pages
            filter_params = {
                "filter": {
                    "timestamp": "last_edited_time",
                    "last_edited_time": {
                        "after": since.isoformat(),
                    },
                }
            }

            if settings.notion_teachers_db_id:
                teachers = list(
                    self._extract_database(
                        settings.notion_teachers_db_id,
                        "teacher",
                        self._parse_employee_page,
                        filter_params,
                    )
                )
                entities.extend(teachers)

            if settings.notion_students_db_id:
                students = list(
                    self._extract_database(
                        settings.notion_students_db_id,
                        "student",
                        self._parse_student_page,
                        filter_params,
                    )
                )
                entities.extend(students)

            result.entities = entities
            result.record_count = len(entities)

        except Exception as e:
            self.logger.error(f"Incremental extraction failed: {e}")
            result.errors.append(str(e))
        finally:
            self.disconnect()

        result.duration_seconds = (datetime.now() - start_time).total_seconds()
        return result

    def _extract_database(
        self,
        database_id: str,
        entity_type: str,
        parser_func,
        query_params: Optional[Dict] = None,
    ) -> Generator[ExtractedEntity, None, None]:
        """Extract all pages from a Notion database."""
        has_more = True
        start_cursor = None

        while has_more:
            params = query_params.copy() if query_params else {}
            if start_cursor:
                params["start_cursor"] = start_cursor

            response = self.client.databases.query(
                database_id=database_id, **params
            )

            for page in response.get("results", []):
                try:
                    entity = parser_func(page, entity_type)
                    if entity:
                        yield entity
                except Exception as e:
                    self.logger.warning(
                        f"Failed to parse page {page.get('id')}: {e}"
                    )

            has_more = response.get("has_more", False)
            start_cursor = response.get("next_cursor")

    def _parse_employee_page(
        self, page: Dict[str, Any], entity_type: str
    ) -> ExtractedEntity:
        """Parse a Notion employee page into an ExtractedEntity."""
        props = page.get("properties", {})

        return ExtractedEntity(
            source_system=self.source_name,
            entity_type=entity_type,
            external_id=self._create_external_id("employee", page["id"]),
            data={
                "notion_id": page["id"],
                "name": self._get_title(props.get("Name", {})),
                "first_name": self._get_text(props.get("First Name", {})),
                "last_name": self._get_text(props.get("Last Name", {})),
                "email": self._get_email(props.get("Email", {})),
                "phone": self._get_phone(props.get("Phone", {})),
                "position": self._get_select(props.get("Position", {})),
                "department": self._get_select(props.get("Department", {})),
                "hire_date": self._get_date(props.get("Hire Date", {})),
                "status": self._get_select(props.get("Status", {})),
                "is_active": self._get_select(props.get("Status", {})) == "Active",
                "created_at": self._safe_datetime(page.get("created_time")),
                "updated_at": self._safe_datetime(page.get("last_edited_time")),
            },
            raw_record=page,
        )

    def _parse_student_page(
        self, page: Dict[str, Any], entity_type: str
    ) -> ExtractedEntity:
        """Parse a Notion student page into an ExtractedEntity."""
        props = page.get("properties", {})

        return ExtractedEntity(
            source_system=self.source_name,
            entity_type=entity_type,
            external_id=self._create_external_id("student", page["id"]),
            data={
                "notion_id": page["id"],
                "name": self._get_title(props.get("Name", {})),
                "english_name": self._get_text(props.get("English Name", {})),
                "student_id": self._get_text(props.get("Student ID", {})),
                "grade": self._get_select(props.get("Grade", {})),
                "school": self._get_text(props.get("School", {})),
                "gender": self._get_select(props.get("Gender", {})),
                "program_start_date": self._get_date(
                    props.get("Program Start", {})
                ),
                "program_end_date": self._get_date(props.get("Program End", {})),
                "is_active": self._get_checkbox(props.get("Active", {})),
                "created_at": self._safe_datetime(page.get("created_time")),
                "updated_at": self._safe_datetime(page.get("last_edited_time")),
            },
            raw_record=page,
        )

    def _parse_course_page(
        self, page: Dict[str, Any], entity_type: str
    ) -> ExtractedEntity:
        """Parse a Notion course/curriculum page into an ExtractedEntity."""
        props = page.get("properties", {})

        return ExtractedEntity(
            source_system=self.source_name,
            entity_type=entity_type,
            external_id=self._create_external_id("course", page["id"]),
            data={
                "notion_id": page["id"],
                "title": self._get_title(props.get("Name", {})),
                "description": self._get_text(props.get("Description", {})),
                "category": self._get_select(props.get("Category", {})),
                "student_levels": self._get_multi_select(
                    props.get("Levels", {})
                ),
                "created_at": self._safe_datetime(page.get("created_time")),
                "updated_at": self._safe_datetime(page.get("last_edited_time")),
            },
            raw_record=page,
        )

    # Helper methods for extracting Notion property values
    def _get_title(self, prop: Dict) -> Optional[str]:
        """Extract title property value."""
        title_list = prop.get("title", [])
        if title_list:
            return title_list[0].get("plain_text", "")
        return None

    def _get_text(self, prop: Dict) -> Optional[str]:
        """Extract rich text property value."""
        text_list = prop.get("rich_text", [])
        if text_list:
            return text_list[0].get("plain_text", "")
        return None

    def _get_select(self, prop: Dict) -> Optional[str]:
        """Extract select property value."""
        select = prop.get("select")
        if select:
            return select.get("name")
        return None

    def _get_multi_select(self, prop: Dict) -> List[str]:
        """Extract multi-select property values."""
        multi = prop.get("multi_select", [])
        return [item.get("name") for item in multi if item.get("name")]

    def _get_email(self, prop: Dict) -> Optional[str]:
        """Extract email property value."""
        return prop.get("email")

    def _get_phone(self, prop: Dict) -> Optional[str]:
        """Extract phone property value."""
        return prop.get("phone_number")

    def _get_date(self, prop: Dict) -> Optional[str]:
        """Extract date property value."""
        date = prop.get("date")
        if date:
            return date.get("start")
        return None

    def _get_checkbox(self, prop: Dict) -> bool:
        """Extract checkbox property value."""
        return prop.get("checkbox", False)

    def _get_number(self, prop: Dict) -> Optional[float]:
        """Extract number property value."""
        return prop.get("number")

    def _get_unique_id(self, prop: Dict) -> Optional[str]:
        """Extract unique_id property value."""
        unique_id = prop.get("unique_id")
        if unique_id:
            prefix = unique_id.get("prefix", "")
            number = unique_id.get("number", "")
            return f"{prefix}{number}" if prefix else str(number)
        return None

    def _get_people(self, prop: Dict) -> List[str]:
        """Extract people property values."""
        people = prop.get("people", [])
        return [p.get("name", "") for p in people if p.get("name")]

    def _get_status(self, prop: Dict) -> Optional[str]:
        """Extract status property value."""
        status = prop.get("status")
        if status:
            return status.get("name")
        return None

    # Additional parser methods for new database types

    def _parse_online_student_page(
        self, page: Dict[str, Any], entity_type: str
    ) -> ExtractedEntity:
        """Parse an online student page."""
        props = page.get("properties", {})

        return ExtractedEntity(
            source_system=self.source_name,
            entity_type=entity_type,
            external_id=self._create_external_id("online_student", page["id"]),
            data={
                "notion_id": page["id"],
                "name": self._get_title(props.get("Full Name", {})),
                "korean_name": self._get_text(props.get("Korean Name", {})),
                "english_name": self._get_text(props.get("English Name", {})),
                "student_id": self._get_unique_id(props.get("Student ID", {})),
                "grade": self._get_text(props.get("Grade", {})),
                "gender": self._get_select(props.get("Gender", {})),
                "country": self._get_text(props.get("Country", {})),
                "status": self._get_select(props.get("Status", {})),
                "student_type": self._get_select(props.get("Student Type", {})),
                "reading": self._get_text(props.get("Reading", {})),
                "writing": self._get_text(props.get("Writing", {})),
                "grammar": self._get_text(props.get("Grammar", {})),
                "listening": self._get_text(props.get("Listening", {})),
                "vocabulary": self._get_text(props.get("Vocabulary", {})),
                "level_test_total": self._get_text(props.get("Level Test Total", {})),
                "is_online": True,
                "created_at": self._safe_datetime(page.get("created_time")),
                "updated_at": self._safe_datetime(page.get("last_edited_time")),
            },
            raw_record=page,
        )

    def _parse_book_page(
        self, page: Dict[str, Any], entity_type: str
    ) -> ExtractedEntity:
        """Parse a book page."""
        props = page.get("properties", {})

        return ExtractedEntity(
            source_system=self.source_name,
            entity_type=entity_type,
            external_id=self._create_external_id("book", page["id"]),
            data={
                "notion_id": page["id"],
                "name": self._get_title(props.get("Name", {})),
                "author": self._get_text(props.get("Author", {})),
                "publisher": self._get_text(props.get("Publisher", {})),
                "isbn": self._get_text(props.get("ISBN Number", {})),
                "pages": self._get_number(props.get("Pages", {})),
                "category": self._get_select(props.get("Book category", {})),
                "edition": self._get_select(props.get("Edition", {})),
                "subjects": self._get_multi_select(props.get("Subject", {})),
                "reading_levels": self._get_multi_select(props.get("Reading level", {})),
                "description": self._get_text(props.get("Description", {})),
                "location": self._get_text(props.get("Location", {})),
                "created_at": self._safe_datetime(page.get("created_time")),
                "updated_at": self._safe_datetime(page.get("last_edited_time")),
            },
            raw_record=page,
        )

    def _parse_interview_page(
        self, page: Dict[str, Any], entity_type: str
    ) -> ExtractedEntity:
        """Parse an interview page."""
        props = page.get("properties", {})

        return ExtractedEntity(
            source_system=self.source_name,
            entity_type=entity_type,
            external_id=self._create_external_id("interview", page["id"]),
            data={
                "notion_id": page["id"],
                "type": self._get_title(props.get("Type", {})),
                "student_name": self._get_text(props.get("Name", {})),
                "student_id": self._get_text(props.get("Student ID", {})),
                "interview_date": self._get_date(props.get("Date of Interview", {})),
                "interviewer": self._get_people(props.get("Interviewer", {})),
                "pronunciation": self._get_number(props.get("Pronunciation", {})),
                "fluency": self._get_number(props.get("Fluency", {})),
                "comprehension": self._get_number(props.get("Comprehension", {})),
                "vocab_mechanics": self._get_number(props.get("Vocab/Mechanics", {})),
                "insight": self._get_number(props.get("Insight", {})),
                "knowledge_level": self._get_number(props.get("Knowledge Level", {})),
                "overall_score": self._get_text(props.get("Overall Score", {})),
                "level": self._get_text(props.get("Level", {})),
                "questions": self._get_text(props.get("Questions", {})),
                "created_at": self._safe_datetime(page.get("created_time")),
                "updated_at": self._safe_datetime(page.get("last_edited_time")),
            },
            raw_record=page,
        )

    def _parse_demo_page(
        self, page: Dict[str, Any], entity_type: str
    ) -> ExtractedEntity:
        """Parse a demo assessment page."""
        props = page.get("properties", {})

        return ExtractedEntity(
            source_system=self.source_name,
            entity_type=entity_type,
            external_id=self._create_external_id("demo", page["id"]),
            data={
                "notion_id": page["id"],
                "applicant_name": self._get_title(props.get("Applicant Name", {})),
                "assessor": self._get_text(props.get("Assessor", {})),
                "topic": self._get_text(props.get("Topic", {})),
                "demo_date": self._get_date(props.get("Demo Date", {})),
                "level": self._get_select(props.get("Level", {})),
                "final_result": self._get_select(props.get("Final Result", {})),
                "score": self._get_text(props.get("Score", {})),
                "met": self._get_number(props.get("Met", {})),
                "ni": self._get_number(props.get("NI", {})),
                "fail": self._get_number(props.get("Fail", {})),
                "ai_feedback": self._get_text(props.get("AI Feedback", {})),
                "created_at": self._safe_datetime(page.get("created_time")),
                "updated_at": self._safe_datetime(page.get("last_edited_time")),
            },
            raw_record=page,
        )

    def _parse_daily_report_page(
        self, page: Dict[str, Any], entity_type: str
    ) -> ExtractedEntity:
        """Parse a daily student report page."""
        props = page.get("properties", {})

        return ExtractedEntity(
            source_system=self.source_name,
            entity_type=entity_type,
            external_id=self._create_external_id("daily_report", page["id"]),
            data={
                "notion_id": page["id"],
                "title": self._get_title(props.get("StudentID/Subject/MMDDYY", {})),
                "date": self._get_date(props.get("Date", {})),
                "grade_level": self._get_select(props.get("Grade Level", {})),
                "subjects": self._get_multi_select(props.get("Subject", {})),
                "skill_focus": self._get_text(props.get("Skill Focus", {})),
                "homework": self._get_text(props.get("Homework", {})),
                "additional_notes": self._get_text(props.get("Additional Notes", {})),
                "behavior": self._get_number(props.get("Behavior", {})),
                "attention": self._get_number(props.get("Attention", {})),
                "comprehension": self._get_number(props.get("Comprehension", {})),
                "retention": self._get_number(props.get("Retention", {})),
                "conversation": self._get_number(props.get("Conversation", {})),
                "handwriting": self._get_number(props.get("Handwriting", {})),
                "created_at": self._safe_datetime(page.get("created_time")),
                "updated_at": self._safe_datetime(page.get("last_edited_time")),
            },
            raw_record=page,
        )

    def _parse_lesson_page(
        self, page: Dict[str, Any], entity_type: str
    ) -> ExtractedEntity:
        """Parse a lesson/curriculum page."""
        props = page.get("properties", {})

        return ExtractedEntity(
            source_system=self.source_name,
            entity_type=entity_type,
            external_id=self._create_external_id("lesson", page["id"]),
            data={
                "notion_id": page["id"],
                "name": self._get_title(props.get("Name", {})),
                "lesson": self._get_text(props.get("Lesson", {})),
                "grade": self._get_select(props.get("Grade", {})),
                "subject": self._get_select(props.get("Subject", {})),
                "specific_subject": self._get_select(props.get("Specific Subject", {})),
                "quarter": self._get_select(props.get("Quarter", {})),
                "created_at": self._safe_datetime(page.get("created_time")),
                "updated_at": self._safe_datetime(page.get("last_edited_time")),
            },
            raw_record=page,
        )

    def _parse_rubric_page(
        self, page: Dict[str, Any], entity_type: str
    ) -> ExtractedEntity:
        """Parse a rubric page."""
        props = page.get("properties", {})

        return ExtractedEntity(
            source_system=self.source_name,
            entity_type=entity_type,
            external_id=self._create_external_id("rubric", page["id"]),
            data={
                "notion_id": page["id"],
                "name": self._get_title(props.get("Name", {})),
                "criteria": self._get_text(props.get("Criteria", {})),
                "description": self._get_text(props.get("Description", {})),
                "score": self._get_select(props.get("Score", {})),
                "grade_level": self._get_select(props.get("Grade Level", {})),
                "subject": self._get_select(props.get("Subject", {})),
                "created_at": self._safe_datetime(page.get("created_time")),
                "updated_at": self._safe_datetime(page.get("last_edited_time")),
            },
            raw_record=page,
        )

    def _parse_skill_page(
        self, page: Dict[str, Any], entity_type: str
    ) -> ExtractedEntity:
        """Parse a skill page."""
        props = page.get("properties", {})

        return ExtractedEntity(
            source_system=self.source_name,
            entity_type=entity_type,
            external_id=self._create_external_id("skill", page["id"]),
            data={
                "notion_id": page["id"],
                "name": self._get_title(props.get("Name", {})),
                "description": self._get_text(props.get("Description", {})),
                "skill": self._get_select(props.get("Skill", {})),
                "grade": self._get_select(props.get("Grade", {})),
                "created_at": self._safe_datetime(page.get("created_time")),
                "updated_at": self._safe_datetime(page.get("last_edited_time")),
            },
            raw_record=page,
        )

    def _parse_endorsement_page(
        self, page: Dict[str, Any], entity_type: str
    ) -> ExtractedEntity:
        """Parse a teacher endorsement page."""
        props = page.get("properties", {})

        return ExtractedEntity(
            source_system=self.source_name,
            entity_type=entity_type,
            external_id=self._create_external_id("endorsement", page["id"]),
            data={
                "notion_id": page["id"],
                "student_name": self._get_title(props.get("Student Name", {})),
                "date": self._get_date(props.get("Date", {})),
                "absent_teacher": self._get_text(props.get("Absent Teacher", {})),
                "time_slot": self._get_text(props.get("Time Slot", {})),
                "class_type": self._get_select(props.get("Class Type", {})),
                "status": self._get_select(props.get("Status", {})),
                "book_material": self._get_text(props.get("Book/Material", {})),
                "last_lesson": self._get_text(props.get("Last Lesson", {})),
                "next_lesson": self._get_text(props.get("Next Lesson", {})),
                "homework": self._get_text(props.get("Homework", {})),
                "notes": self._get_text(props.get("Notes", {})),
                "ai_summary": self._get_text(props.get("AI Summary", {})),
                "created_at": self._safe_datetime(page.get("created_time")),
                "updated_at": self._safe_datetime(page.get("last_edited_time")),
            },
            raw_record=page,
        )

    def _parse_noahs_ark_page(
        self, page: Dict[str, Any], entity_type: str
    ) -> ExtractedEntity:
        """Parse a Noah's Ark (teacher check-in) page."""
        props = page.get("properties", {})

        return ExtractedEntity(
            source_system=self.source_name,
            entity_type=entity_type,
            external_id=self._create_external_id("checkin", page["id"]),
            data={
                "notion_id": page["id"],
                "teacher_name": self._get_title(props.get("Teacher Name", {})),
                "teacher_id": self._get_text(props.get("Teacher ID", {})),
                "timestamp": self._get_date(props.get("Timestamp", {})),
                "location": self._get_text(props.get("Location", {})),
                "coordinates": self._get_text(props.get("Coordinates", {})),
                "status": self._get_select(props.get("Status", {})),
                "reason": self._get_text(props.get("Reason", {})),
                "created_at": self._safe_datetime(page.get("created_time")),
                "updated_at": self._safe_datetime(page.get("last_edited_time")),
            },
            raw_record=page,
        )

    def _parse_reading_level_page(
        self, page: Dict[str, Any], entity_type: str
    ) -> ExtractedEntity:
        """Parse a reading level assessment page."""
        props = page.get("properties", {})

        return ExtractedEntity(
            source_system=self.source_name,
            entity_type=entity_type,
            external_id=self._create_external_id("reading_assessment", page["id"]),
            data={
                "notion_id": page["id"],
                "student_name": self._get_title(props.get("Student Name", {})),
                "student_id": self._get_text(props.get("Student ID", {})),
                "assessment_date": self._get_date(props.get("Assessment Date", {})),
                "grade_level": self._get_select(props.get("Grade level", {})),
                "test_type": self._get_select(props.get("Test Type", {})),
                "wpm_score": self._get_number(props.get("WPM Score", {})),
                "wpm_grade_tested": self._get_select(props.get("WPM Grade Tested", {})),
                "gbwt_grade_tested": self._get_select(props.get("GBWT Grade Tested", {})),
                "assessment_status": self._get_status(props.get("Assessment Status", {})),
                "assessment_summary": self._get_text(props.get("Assessment Summary", {})),
                "created_at": self._safe_datetime(page.get("created_time")),
                "updated_at": self._safe_datetime(page.get("last_edited_time")),
            },
            raw_record=page,
        )

    def _parse_korean_registration_page(
        self, page: Dict[str, Any], entity_type: str
    ) -> ExtractedEntity:
        """Parse a Korean student registration page."""
        props = page.get("properties", {})

        return ExtractedEntity(
            source_system=self.source_name,
            entity_type=entity_type,
            external_id=self._create_external_id("registration", page["id"]),
            data={
                "notion_id": page["id"],
                "korean_name": self._get_title(props.get("한국어 이름", {})),
                "english_name": self._get_text(props.get("영어 이름", {})),
                "grade": self._get_select(props.get("학년", {})),
                "country": self._get_text(props.get("거주 국가", {})),
                "class_subject": self._get_text(props.get("수업 과목", {})),
                "class_time": self._get_select(props.get("수업 시간", {})),
                "available_time": self._get_text(props.get("수업 가능 시간", {})),
                "weekly_classes": self._get_number(props.get("주간 수업 횟수", {})),
                "start_date": self._get_date(props.get("시작일", {})),
                "status": self._get_select(props.get("상태", {})),
                "notes": self._get_text(props.get("메모", {})),
                "registration_date": self._safe_datetime(page.get("created_time")),
                "updated_at": self._safe_datetime(page.get("last_edited_time")),
            },
            raw_record=page,
        )
