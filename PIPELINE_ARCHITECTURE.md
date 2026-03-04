# ICAN Academy Data Pipeline Architecture

## Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DATA SOURCES                                       │
├─────────────┬─────────────┬─────────────┬─────────────┬─────────────────────┤
│  PostgreSQL │   SQLite    │   Notion    │    n8n      │   Knowledge Base    │
│ (scheduling)│  (7 DBs)    │   (API)     │ (workflows) │     (text file)     │
└──────┬──────┴──────┬──────┴──────┬──────┴──────┬──────┴──────────┬──────────┘
       │             │             │             │                 │
       ▼             ▼             ▼             ▼                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         EXTRACTION LAYER                                     │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────────┐  │
│  │ PostgreSQL│ │  SQLite   │ │  Notion   │ │    n8n    │ │   Text/File   │  │
│  │ Extractor │ │ Extractor │ │ Extractor │ │ Extractor │ │   Extractor   │  │
│  └─────┬─────┘ └─────┬─────┘ └─────┬─────┘ └─────┬─────┘ └───────┬───────┘  │
└────────┼─────────────┼─────────────┼─────────────┼───────────────┼──────────┘
         │             │             │             │               │
         ▼             ▼             ▼             ▼               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       TRANSFORMATION LAYER                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    Entity Resolution & Mapping                       │    │
│  │  • Normalize names (Teacher "John Doe" = Employee "Doe, John")      │    │
│  │  • Match IDs across systems (teacher_id, employee_number, notion_id)│    │
│  │  • Deduplicate records                                               │    │
│  │  • Standardize data formats (dates, scores, statuses)               │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    TypeDB Entity Mapper                              │    │
│  │  • Convert to TypeDB entities and relations                         │    │
│  │  • Generate unique external_ids                                      │    │
│  │  • Build relationship connections                                    │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          LOADING LAYER                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     TypeDB Ingestion Engine                          │    │
│  │  • Batch insert entities                                             │    │
│  │  • Create relations                                                  │    │
│  │  • Handle upserts (update existing, insert new)                     │    │
│  │  • Track sync timestamps                                             │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            TypeDB                                            │
│                       ICAN Data Center                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Entities: Teachers, Students, Assignments, Assessments, etc.       │    │
│  │  Relations: teaching, attendance, coaching, enrollment, etc.        │    │
│  │  Rules: Inferred relationships (supervision, collaboration)         │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           QUERY LAYER                                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   FastAPI    │  │   Web UI     │  │  GraphQL     │  │   CLI Tool   │     │
│  │   REST API   │  │  (Explorer)  │  │  (Optional)  │  │   (Query)    │     │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Details

### 1. Extractors

#### PostgreSQL Extractor
```python
# Source: localhost:5432/scheduling_db
# Tables: students, teachers, assignments, rooms, time_slots, etc.
# Method: Direct SQL queries via psycopg2
# Frequency: Every 15 minutes (scheduling data changes frequently)
```

#### SQLite Extractors
```python
# Sources:
#   - ~/attendance-checker/attendance.db         (teacher attendance)
#   - ~/student-attendance-checker/student-attendance.db
#   - ~/academy-coaching-app/coaching.db
#   - ~/ican-app-marketplace/marketplace.db
#   - ~/ican-demo-assessment/demo_assessments.db
#   - ~/interview-sheet-generator/server/interviews.db
#   - ~/student-report-app/student_reports.db
# Method: sqlite3 module
# Frequency: Hourly or on-demand
```

#### Notion Extractor
```python
# Source: Notion API
# Databases: Employees, Students, Curriculum
# Method: notion-client SDK
# Frequency: Webhook-triggered + daily full sync
```

### 2. Transformation Rules

#### Entity Mapping Table

| Source System | Source Entity | TypeDB Entity | Key Mapping |
|--------------|---------------|---------------|-------------|
| PostgreSQL | students | student | `pg_student_{id}` |
| PostgreSQL | teachers | teacher | `pg_teacher_{id}` |
| PostgreSQL | assignments | class-assignment | `pg_assignment_{id}` |
| PostgreSQL | rooms | room | `pg_room_{id}` |
| SQLite (attendance) | attendance | attendance | `att_teacher_{id}_{date}` |
| SQLite (coaching) | employees | teacher | `coaching_emp_{id}` |
| SQLite (coaching) | coaching_records | coaching-record | `coaching_{id}` |
| SQLite (demo) | assessments | demo-assessment | `demo_{id}` |
| SQLite (interview) | interviews | interview-assessment | `interview_{id}` |
| SQLite (reports) | student_reports | student-report | `report_{id}` |
| SQLite (marketplace) | apps | educational-app | `app_{id}` |
| Notion | Employee DB | teacher | `notion_{page_id}` |
| Notion | Student DB | student | `notion_{page_id}` |

#### Name Normalization Rules
```python
def normalize_teacher_name(name: str) -> str:
    """
    Handles variations:
    - "John Doe" -> "john_doe"
    - "Doe, John" -> "john_doe"
    - "T. John" -> "john"  (Teacher prefix)
    """
    pass

def match_teacher_across_systems(pg_teacher, coaching_employee, notion_employee):
    """
    Matching criteria (in order):
    1. Exact email match
    2. Notion ID match (if present in coaching.db)
    3. Fuzzy name match (>90% similarity)
    """
    pass
```

### 3. Sync Strategies

| Data Source | Strategy | Trigger | Notes |
|------------|----------|---------|-------|
| PostgreSQL scheduling | Incremental | Cron (*/15 * * * *) | Use `updated_at` for delta |
| Teacher attendance | Full sync | Daily 6 AM | Small dataset |
| Student attendance | Full sync | Daily 6 AM | Small dataset |
| Coaching records | Incremental | Hourly | Sensitive data |
| Assessments | Full sync | Daily | Historical data |
| Marketplace apps | Full sync | Daily | Rarely changes |
| Notion | Webhook + Full | On change + Daily | Real-time updates |

---

## Project Structure

```
data-pipeline/
├── DISCOVERY_REPORT.md          # This file
├── PIPELINE_ARCHITECTURE.md     # Architecture docs
├── schema/
│   └── ican_schema.tql          # TypeDB schema
├── src/
│   ├── __init__.py
│   ├── config.py                # Configuration management
│   ├── extractors/
│   │   ├── __init__.py
│   │   ├── base.py              # Base extractor class
│   │   ├── postgresql.py        # PostgreSQL extractor
│   │   ├── sqlite.py            # SQLite extractor (handles all DBs)
│   │   ├── notion.py            # Notion API extractor
│   │   └── n8n.py               # n8n workflow extractor
│   ├── transformers/
│   │   ├── __init__.py
│   │   ├── entity_resolver.py   # Cross-system entity matching
│   │   ├── normalizers.py       # Data normalization functions
│   │   └── typedb_mapper.py     # Map to TypeDB entities
│   ├── loaders/
│   │   ├── __init__.py
│   │   └── typedb_loader.py     # TypeDB ingestion
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI application
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── teachers.py
│   │   │   ├── students.py
│   │   │   ├── schedules.py
│   │   │   ├── assessments.py
│   │   │   └── search.py        # Full-text and graph search
│   │   └── models.py            # Pydantic models
│   └── web/
│       ├── templates/
│       │   ├── base.html
│       │   ├── index.html       # Dashboard
│       │   ├── graph.html       # Graph visualization
│       │   └── query.html       # Query interface
│       └── static/
│           ├── css/
│           └── js/
├── scripts/
│   ├── setup_typedb.py          # Initialize TypeDB schema
│   ├── run_sync.py              # Manual sync trigger
│   └── healthcheck.py           # Verify all connections
├── tests/
│   ├── test_extractors.py
│   ├── test_transformers.py
│   └── test_loaders.py
├── docker-compose.yml           # TypeDB + App containers
├── requirements.txt
├── .env.example
└── README.md
```

---

## Data Flow Examples

### Example 1: Teacher Data Flow

```
PostgreSQL.teachers                    TypeDB.teacher
┌──────────────────┐                  ┌──────────────────────────┐
│ id: 42           │                  │ external_id: pg_teacher_42│
│ name: "John Doe" │ ───────────────► │ name: "John Doe"         │
│ availability: {} │   Transform      │ source_system: "postgres"│
│ color: "blue"    │                  │ color_keyword: "blue"    │
└──────────────────┘                  └──────────────────────────┘
                                                 │
coaching.db.employees                            │ Entity
┌──────────────────┐                            │ Resolution
│ id: "emp-001"    │                            │ (same person!)
│ first: "John"    │ ──────────────────────────►│
│ last: "Doe"      │                            ▼
│ notion_id: "abc" │              ┌──────────────────────────┐
└──────────────────┘              │ external_id: pg_teacher_42│
                                  │ name: "John Doe"         │
Notion.Employees                  │ employee_number: "emp-001"│
┌──────────────────┐              │ notion_id: "abc"         │
│ id: "abc"        │ ────────────►│ source_system: "merged"  │
│ Name: "John Doe" │              │ position: "Senior Teacher"│
│ Dept: "English"  │              │ department: "English"    │
└──────────────────┘              └──────────────────────────┘
```

### Example 2: Assessment Relationship

```
interview_assessment (TypeDB)
┌─────────────────────────────┐
│ external_id: interview_123  │
│ date: 2024-12-10           │
│ pronunciation: 8.5          │
│ fluency: 7.0               │
└─────────────────────────────┘
            │
            │ assessment-event relation
            ▼
┌─────────────────────────────────────────────────────────┐
│ (assessor: $teacher, subject: $student, evaluation: $a) │
│  isa assessment-event, has date 2024-12-10             │
└─────────────────────────────────────────────────────────┘
            │                           │
            ▼                           ▼
    ┌───────────────┐           ┌───────────────┐
    │ teacher       │           │ student       │
    │ "Jane Smith"  │           │ "Kim Lee"     │
    └───────────────┘           └───────────────┘
```

---

## Query Examples

### TypeQL Queries

```typeql
# Find all students taught by a specific teacher
match
  $teacher isa teacher, has name "John Doe";
  $student isa student;
  $class isa class-assignment;
  (instructor: $teacher, learner: $student, class: $class) isa teaching;
fetch $student: name, grade, school;

# Find teachers with attendance issues this month
match
  $teacher isa teacher;
  $attendance isa attendance, has attendance_status "late", has date $date;
  (attendee: $teacher, record: $attendance) isa attendance-record;
  $date >= 2024-12-01;
fetch $teacher: name; $attendance: date, minutes_late, late_reason;

# Find all assessments for a student
match
  $student isa student, has name "Kim Lee";
  $assessment isa assessment;
  (subject: $student, evaluation: $assessment) isa assessment-event;
fetch $assessment: assessment_type, date, assessment_score, feedback;

# Find coaching records and related offenses
match
  $teacher isa teacher;
  $record isa coaching-record;
  $offense isa offense-type;
  (coachee: $teacher, session: $record, offense-committed: $offense) isa coaching-session;
fetch
  $teacher: name;
  $record: coaching_type, date, issue_description;
  $offense: offense_name, offense_severity;
```

---

## API Endpoints

### REST API (FastAPI)

```
GET  /api/teachers                    # List all teachers
GET  /api/teachers/{id}               # Get teacher details + relations
GET  /api/teachers/{id}/students      # Students taught by teacher
GET  /api/teachers/{id}/attendance    # Teacher attendance history
GET  /api/teachers/{id}/coaching      # Coaching records

GET  /api/students                    # List all students
GET  /api/students/{id}               # Get student details + relations
GET  /api/students/{id}/assessments   # All assessments for student
GET  /api/students/{id}/teachers      # Teachers who taught student

GET  /api/schedules                   # Today's schedule
GET  /api/schedules/{date}            # Schedule for specific date

GET  /api/search?q={query}            # Full-text search across all entities

POST /api/sync                        # Trigger manual sync
GET  /api/sync/status                 # Check sync status

GET  /api/graph/visualize             # Get graph data for visualization
```

---

## Next Steps

1. **Set up TypeDB** - Install and configure TypeDB locally
2. **Create base extractors** - Start with PostgreSQL (richest data)
3. **Build entity resolution** - Critical for merging teacher/employee data
4. **Implement TypeDB loader** - Ingest first dataset
5. **Add remaining extractors** - SQLite databases, Notion
6. **Build API layer** - FastAPI with basic endpoints
7. **Create Web UI** - Simple graph explorer
