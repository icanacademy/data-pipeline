# ICAN Data Center

A unified data platform that connects all ICAN Academy local apps and databases into a centralized data center with TypeDB knowledge graph.

## Quick Start

### 1. Install Dependencies

```bash
cd data-pipeline
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your Notion API key and database IDs
```

### 3. Start TypeDB

```bash
# Using Docker (recommended)
docker run -d --name typedb -p 1729:1729 vaticle/typedb:latest

# Or use docker-compose to start everything
docker-compose up -d
```

### 4. Initialize Database

```bash
python scripts/setup_typedb.py
```

### 5. Run Initial Sync

```bash
python scripts/run_sync.py
```

### 6. Start the API

```bash
python -m uvicorn src.api.main:app --reload --port 8080
```

Then open http://localhost:8080 in your browser.

## Architecture

```
┌────────────────────────────────────────────────────────────┐
│                      DATA SOURCES                          │
├──────────┬──────────┬──────────┬──────────┬───────────────┤
│PostgreSQL│  SQLite  │  Notion  │   n8n    │ Knowledge Base│
│scheduling│  (7 DBs) │  (API)   │workflows │   (text)      │
└────┬─────┴────┬─────┴────┬─────┴────┬─────┴───────┬───────┘
     │          │          │          │             │
     ▼          ▼          ▼          ▼             ▼
┌────────────────────────────────────────────────────────────┐
│                   EXTRACTION LAYER                          │
│    PostgreSQL, SQLite, Notion, n8n Extractors              │
└────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────────┐
│                 TRANSFORMATION LAYER                        │
│      Entity Resolution • Normalization • Mapping           │
└────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────────┐
│                       TypeDB                                │
│                 ICAN Data Center                            │
└────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────────┐
│                     QUERY LAYER                             │
│          FastAPI REST API • Web Dashboard                   │
└────────────────────────────────────────────────────────────┘
```

## Data Sources

| Source | Type | Data |
|--------|------|------|
| scheduling_db | PostgreSQL | Students, Teachers, Assignments, Rooms |
| attendance.db | SQLite | Teacher attendance records |
| student-attendance.db | SQLite | Student attendance records |
| coaching.db | SQLite | HR coaching records, employees |
| marketplace.db | SQLite | Educational app marketplace |
| demo_assessments.db | SQLite | Teacher demo evaluations |
| interviews.db | SQLite | Student interview assessments |
| student_reports.db | SQLite | Student progress reports |
| Notion | API | Employees, Students, Curriculum |

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Web dashboard |
| `GET /api/teachers` | List teachers |
| `GET /api/teachers/{id}` | Get teacher details |
| `GET /api/teachers/{id}/students` | Students taught by teacher |
| `GET /api/students` | List students |
| `GET /api/students/{id}` | Get student details |
| `GET /api/students/{id}/assessments` | Student assessments |
| `GET /api/search?q=...` | Search across entities |
| `POST /api/sync` | Trigger data sync |
| `POST /api/query` | Execute TypeQL query |
| `GET /api/stats` | Knowledge graph statistics |
| `GET /docs` | API documentation |

## TypeQL Query Examples

```typeql
# Find all students taught by a specific teacher
match
  $teacher isa teacher, has name "John Doe";
  $student isa student;
  (instructor: $teacher, learner: $student) isa teaching;
fetch $student: name, grade;

# Find teachers with attendance issues
match
  $teacher isa teacher;
  $attendance isa attendance, has attendance_status "late";
  (attendee: $teacher, record: $attendance) isa attendance-record;
fetch $teacher: name; $attendance: date, minutes_late;

# Find all assessments for a student
match
  $student isa student, has name "Kim Lee";
  $assessment isa assessment;
  (subject: $student, evaluation: $assessment) isa assessment-event;
fetch $assessment: assessment_type, date, assessment_score;
```

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/setup_typedb.py` | Initialize TypeDB and load schema |
| `scripts/run_sync.py` | Run full data sync |
| `scripts/healthcheck.py` | Check all data source connections |

## Project Structure

```
data-pipeline/
├── schema/
│   └── ican_schema.tql      # TypeDB schema
├── src/
│   ├── config.py            # Configuration
│   ├── extractors/          # Data extractors
│   ├── transformers/        # Entity resolution & mapping
│   ├── loaders/             # TypeDB loader
│   └── api/                 # FastAPI application
├── scripts/                 # Utility scripts
├── docker-compose.yml       # Docker setup
├── requirements.txt         # Python dependencies
└── README.md
```

## Entity Resolution

The pipeline resolves entities across systems using:

1. **Email matching** - Exact email match
2. **Notion ID matching** - Same Notion page ID
3. **Employee/Student ID matching** - Same ID numbers
4. **Fuzzy name matching** - >85% name similarity

This ensures "John Doe" from scheduling, "Doe, John" from coaching, and the corresponding Notion employee are merged into a single unified entity.

## Scheduled Sync (Optional)

To set up scheduled syncing, add a cron job:

```bash
# Sync every 15 minutes
*/15 * * * * cd /path/to/data-pipeline && ./venv/bin/python scripts/run_sync.py >> /var/log/ican-sync.log 2>&1
```

## License

Internal use only - ICAN Academy
