# ICAN Academy Data Discovery Report

**Generated:** December 12, 2025
**Purpose:** Document all local data sources for unified knowledge graph

---

## Executive Summary

Your local environment contains a rich ecosystem of **education-focused applications** managing:
- Teacher and student scheduling
- Attendance tracking (both teacher and student)
- Coaching/HR records
- Assessments and interviews
- App marketplace
- Automation workflows (n8n)

All systems share common entities: **Teachers**, **Students**, **Schedules**, and **Assessments**.

---

## 1. Running Services

### Docker Containers

| Container | Image | Port | Purpose |
|-----------|-------|------|---------|
| scheduling_db | postgres:16-alpine | 5432 | Main scheduling PostgreSQL database |
| papra | ghcr.io/papra-hq/papra | 1221 | Document management |
| n8n | n8nio/n8n | 8000 | Workflow automation |
| open-webui | open-webui:main | 3000 | AI chat interface (Ollama) |

### Node.js Applications

| App | Port | Directory |
|-----|------|-----------|
| Scheduling App (Client) | 4444 | ~/scheduling-app/client |
| Scheduling App (Server) | 5555 | ~/scheduling-app/server |
| OL Scheduling App (Client) | 4477 | ~/ol-scheduling-app/client |
| OL Scheduling App (Server) | 4488 | ~/ol-scheduling-app/server |
| Iron Suit AI Portal | 7777 | ~/dr.ican's-iron-suit-ai-portal |
| Attendance Checker | 7778 | ~/attendance-checker |
| Various other Node servers | 919, 1120, 1441-1443, 2006, 3001-3003, 3010, 5556-5557 | Multiple apps |

### Other Services

- **ngrok** - Tunneling (port 4040 for dashboard)
- **Python HTTP server** - Port 1230

---

## 2. Databases

### PostgreSQL (Docker - scheduling_db)

**Connection:** `localhost:5432`, user: `postgres`, password: `postgres`

#### Tables:
| Table | Description | Key Fields |
|-------|-------------|------------|
| **students** | Student records | id, name, english_name, student_id, grade, gender, school, availability (JSONB), scores (reading, grammar, listening, writing, interview, vocabulary) |
| **teachers** | Teacher records | id, name, availability (JSONB), color_keyword, is_active |
| **assignments** | Class assignments | id, date, time_slot_id, room_id |
| **assignment_students** | Student-assignment mapping | student_id, assignment_id |
| **assignment_teachers** | Teacher-assignment mapping | teacher_id, assignment_id |
| **rooms** | Physical rooms | id, name |
| **time_slots** | Schedule time slots | id, start_time, end_time |
| **attendance** | General attendance | id, date, status |
| **teacher_attendance** | Teacher-specific attendance | id, teacher_id, date |
| **student_tuition** | Tuition records | id, student_id, amount |
| **tuition_payments** | Payment records | id, student_id, payment_date |
| **holidays** | Holiday calendar | id, date, name |
| **student_notes** | Notes on students | id, student_id, note |
| **incoming_student_batches** | New student batches | id, batch_info |
| **backup_metadata** | System backups | id, backup_date |

### SQLite Databases

#### 1. Teacher Attendance (`~/attendance-checker/attendance.db`)
```sql
-- Tracks daily teacher attendance
attendance: id, teacher_name, teacher_id, date, status, start_time, end_time,
            late_reason, absent_reason, minutes_late, undertime info

class_assignments: id, attendance_id, class_slot, substitute_teacher info
```

#### 2. Student Attendance (`~/student-attendance-checker/student-attendance.db`)
```sql
-- Tracks daily student attendance
attendance: id, student_name, student_id, date, status, start_time, end_time,
            late_reason, absent_reason, minutes_late, undertime info

class_assignments: id, attendance_id, class_slot, substitute info
```

#### 3. Coaching Records (`~/academy-coaching-app/coaching.db`)
```sql
-- HR coaching and employee management
users: id, username, email, role, employee_id
employees: id, employee_number, first_name, last_name, position, department,
           hire_date, supervisor_id, status, notion_id
coaching_categories: id, name, description
offense_types: id, category_id, code, name, severity
coaching_records: id, employee_id, supervisor_id, coaching_type, offense details,
                  improvement plans, signatures
company_settings: notion_api_key, notion_database_id (Notion integration!)
```

#### 4. App Marketplace (`~/ican-app-marketplace/marketplace.db`)
```sql
-- Educational app sharing platform
apps: id, teacher_name, title, description, category, student_levels, app_link
ratings: id, app_id, rating, teacher_name
comments: id, app_id, teacher_name, comment
```

#### 5. Demo Assessments (`~/ican-demo-assessment/demo_assessments.db`)
```sql
-- Teacher demo lesson assessments
assessments: id, applicant_name, demo_date, assessor_name, topic, level_targeted,
             assessment_score, criteria (JSON), additional_comments, final_result,
             met_total, ni_total, fail_total, ai_feedback
```

#### 6. Interview Generator (`~/interview-sheet-generator/server/interviews.db`)
```sql
-- Student interview assessments
interviews: id, student_name, student_id, interview_type, date, interviewer,
            grade, gender, age, questions, pronunciation, fluency, comprehension,
            insight, vocab, knowledge_level, persuasion_text, report_text
```

#### 7. Student Reports (`~/student-report-app/student_reports.db`)
```sql
-- Student progress reports
student_reports: id, student_name, student_id, report_date, grade, subject,
                 attendance, homework, participation, behavior, notes
```

#### 8. n8n Workflow Database (`~/.n8n/database.sqlite`)
```sql
-- Automation workflows
workflow_entity: workflow definitions
execution_entity: workflow run history
credentials_entity: API credentials
variables: workflow variables
```

---

## 3. External Integrations

### Notion (Confirmed)
- **Status:** API key available
- **Databases to integrate:**
  - Employee/Staff database
  - Student database
  - Curriculum/Courses
- **Existing Integration:** coaching.db already has `notion_api_key` and `notion_database_id` fields

### ngrok
- Local tunneling for external access
- Dashboard at `localhost:4040`

### Open WebUI / Ollama
- Local AI chat interface
- Could be used for intelligent querying of knowledge graph

---

## 4. Common Entities Across Systems

### Teachers/Employees
Found in: PostgreSQL scheduling_db, attendance.db, coaching.db, marketplace.db, demo_assessments.db, Notion

**Key fields:** name, id, email, position, department, availability

### Students
Found in: PostgreSQL scheduling_db, student-attendance.db, interviews.db, student_reports.db, Notion

**Key fields:** name, student_id, grade, school, scores

### Schedules/Assignments
Found in: PostgreSQL (assignments, time_slots, rooms), attendance DBs

**Key fields:** date, time_slot, room, teacher, students

### Assessments/Evaluations
Found in: demo_assessments.db, interviews.db, student_reports.db, coaching.db

**Key fields:** scores, feedback, dates, evaluator

---

## 5. Data Relationships Map

```
                    ┌─────────────┐
                    │   NOTION    │
                    │ (External)  │
                    └──────┬──────┘
                           │
    ┌──────────────────────┼──────────────────────┐
    │                      │                      │
    ▼                      ▼                      ▼
┌────────┐           ┌──────────┐           ┌──────────┐
│TEACHERS│◄─────────►│SCHEDULES │◄─────────►│STUDENTS  │
└───┬────┘           └────┬─────┘           └────┬─────┘
    │                     │                      │
    │  ┌──────────────────┼──────────────────┐   │
    │  │                  │                  │   │
    ▼  ▼                  ▼                  ▼   ▼
┌───────────┐       ┌───────────┐       ┌───────────┐
│ATTENDANCE │       │   ROOMS   │       │ATTENDANCE │
│ (Teacher) │       │           │       │ (Student) │
└───────────┘       └───────────┘       └───────────┘
    │                                        │
    ▼                                        ▼
┌───────────┐                          ┌───────────┐
│ COACHING  │                          │ASSESSMENTS│
│ RECORDS   │                          │INTERVIEWS │
└───────────┘                          │ REPORTS   │
                                       └───────────┘
```

---

## 6. Recommended Pipeline Components

### Extractors Needed:
1. **PostgreSQL Extractor** - scheduling_db (students, teachers, assignments)
2. **SQLite Extractor (x7)** - All SQLite databases
3. **Notion Extractor** - Employees, Students, Courses
4. **n8n Extractor** - Workflows and execution history (optional)

### Sync Strategies:
| Source | Strategy | Frequency |
|--------|----------|-----------|
| PostgreSQL scheduling | Real-time/Scheduled | Every 5-15 min |
| SQLite attendance DBs | Scheduled | Hourly or daily |
| Notion | Webhook + Scheduled | On change + daily sync |
| n8n workflows | One-time + on-demand | Initial + manual refresh |

---

## Next Steps

1. **Design TypeDB schema** modeling all entities and relationships
2. **Build extractors** for each data source
3. **Create transformation layer** to normalize data
4. **Build ingestion pipeline** into TypeDB
5. **Create query interface** (FastAPI + Web UI)

---

## File Locations Summary

```
~/data-pipeline/                    # New pipeline project (to create)
~/attendance-checker/attendance.db
~/student-attendance-checker/student-attendance.db
~/academy-coaching-app/coaching.db
~/ican-app-marketplace/marketplace.db
~/ican-demo-assessment/demo_assessments.db
~/interview-sheet-generator/server/interviews.db
~/student-report-app/student_reports.db
~/.n8n/database.sqlite
~/icanacademy_knowledge_base.txt    # Text knowledge base
Docker: postgres:5432/scheduling_db
```
