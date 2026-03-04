"""Student and Teacher Profile API routes - unified view of all related data."""

from typing import List, Optional

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

# Import shared utilities (eliminates duplicate code)
from ..utils import (
    get_db_connection,
    normalize_name,
    get_tendency,
    calculate_personality_type,
    load_personality_data,
    load_reports,
    safe_int,
    PERSONALITY_DIMENSIONS,
)

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


# ============================================================================
# Response Models
# ============================================================================

class SkillProgress(BaseModel):
    skill_code: str
    skill_name: str
    domain_code: Optional[str] = None
    category_code: Optional[str] = None
    progress_percentage: float
    current_level: Optional[str] = None
    trend_direction: Optional[str] = None
    last_practiced: Optional[str] = None


class PersonaDimension(BaseModel):
    code: str
    name: str
    score: int
    tendency: str


class ReportSummary(BaseModel):
    date: str
    subject: str
    teacher_name: str
    skill_focus: Optional[str] = None
    skill_focus_met: Optional[str] = None
    attention: int
    retention: int
    comprehension: int
    behavior: int


class StudentProfile(BaseModel):
    student_id: str
    student_name: str
    grade_level: Optional[str] = None
    gender: Optional[str] = None
    personality_type: Optional[str] = None
    persona_dimensions: List[PersonaDimension] = []
    skills_progress: List[SkillProgress] = []
    skills_summary: dict = {}
    recent_reports: List[ReportSummary] = []
    reports_summary: dict = {}
    recommendations: List[dict] = []
    interventions: List[dict] = []


class TeacherProfile(BaseModel):
    teacher_id: str
    teacher_name: str
    students: List[dict] = []
    student_count: int = 0
    specializations: List[dict] = []
    reports_count: int = 0
    subjects_taught: List[str] = []
    effectiveness: dict = {}


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/students")
async def list_all_students():
    """Get a combined list of all students from all sources."""
    students = {}

    # From skills database
    conn = get_db_connection("skills_db")
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT student_id, student_name
            FROM student_skill_progress
            WHERE student_id IS NOT NULL
        """)
        for row in cursor.fetchall():
            sid = row["student_id"]
            students[sid] = {
                "student_id": sid,
                "student_name": row["student_name"] or sid,
                "has_skills": True,
                "has_persona": False,
                "has_reports": False,
            }
        conn.close()

    # From reports
    reports = load_reports()
    for report in reports:
        name = report.get("Student Name", "").strip()
        if name:
            norm_name = normalize_name(name)
            found = False
            for sid, sdata in students.items():
                if normalize_name(sdata["student_name"]) == norm_name:
                    sdata["has_reports"] = True
                    found = True
                    break
            if not found:
                students[name] = {
                    "student_id": name,
                    "student_name": name,
                    "has_skills": False,
                    "has_persona": False,
                    "has_reports": True,
                }

    # From personality data
    personality_data = load_personality_data()
    for name, data in personality_data.items():
        if data.get("quizData", {}).get("taken"):
            norm_name = normalize_name(name)
            found = False
            for sid, sdata in students.items():
                if normalize_name(sdata["student_name"]) == norm_name:
                    sdata["has_persona"] = True
                    found = True
                    break
            if not found:
                students[name] = {
                    "student_id": name,
                    "student_name": name,
                    "has_skills": False,
                    "has_persona": True,
                    "has_reports": False,
                }

    return sorted(students.values(), key=lambda x: x["student_name"])


@router.get("/student/{student_id:path}", response_model=StudentProfile)
async def get_student_profile(student_id: str):
    """Get comprehensive student profile with all related data."""
    student_name = student_id
    norm_id = normalize_name(student_id)

    profile = StudentProfile(
        student_id=student_id,
        student_name=student_name,
    )

    # Get skills progress from skills database
    conn = get_db_connection("skills_db")
    if conn:
        cursor = conn.cursor()

        # Find student in skills DB
        cursor.execute("""
            SELECT DISTINCT student_id, student_name
            FROM student_skill_progress
            WHERE student_id = ? OR student_name = ?
               OR LOWER(student_id) LIKE ? OR LOWER(student_name) LIKE ?
            LIMIT 1
        """, (student_id, student_id, f"%{norm_id}%", f"%{norm_id}%"))
        row = cursor.fetchone()

        if row:
            db_student_id = row["student_id"]
            profile.student_name = row["student_name"] or student_id

            # Get skill progress
            cursor.execute("""
                SELECT sp.*, s.code as skill_code, s.name as skill_name,
                       c.code as category_code, d.code as domain_code,
                       l.name as level_name
                FROM student_skill_progress sp
                JOIN skills s ON sp.skill_id = s.id
                JOIN skill_categories c ON s.category_id = c.id
                JOIN skill_domains d ON c.domain_id = d.id
                LEFT JOIN competency_levels l ON sp.current_level_id = l.id
                WHERE sp.student_id = ?
                ORDER BY sp.progress_percentage DESC
            """, (db_student_id,))

            for row in cursor.fetchall():
                profile.skills_progress.append(SkillProgress(
                    skill_code=row["skill_code"],
                    skill_name=row["skill_name"],
                    domain_code=row["domain_code"],
                    category_code=row["category_code"],
                    progress_percentage=row["progress_percentage"] or 0,
                    current_level=row["level_name"],
                    trend_direction=row["trend_direction"],
                    last_practiced=row["last_practiced"],
                ))

            # Get skills summary
            cursor.execute("""
                SELECT
                    COUNT(*) as total_skills,
                    SUM(CASE WHEN progress_percentage >= 85 THEN 1 ELSE 0 END) as mastered,
                    SUM(CASE WHEN progress_percentage >= 40 AND progress_percentage < 85 THEN 1 ELSE 0 END) as in_progress,
                    SUM(CASE WHEN progress_percentage < 40 THEN 1 ELSE 0 END) as needs_work,
                    AVG(progress_percentage) as avg_progress
                FROM student_skill_progress
                WHERE student_id = ?
            """, (db_student_id,))
            summary = cursor.fetchone()
            if summary:
                profile.skills_summary = {
                    "total_skills": summary["total_skills"],
                    "mastered": summary["mastered"],
                    "in_progress": summary["in_progress"],
                    "needs_work": summary["needs_work"],
                    "avg_progress": round(summary["avg_progress"] or 0, 1),
                }

            # Get recommendations
            cursor.execute("""
                SELECT * FROM learning_recommendations
                WHERE student_id = ? AND is_active = 1
                ORDER BY priority_score DESC
                LIMIT 5
            """, (db_student_id,))
            for row in cursor.fetchall():
                profile.recommendations.append({
                    "type": row["recommendation_type"],
                    "target": row["target_name"],
                    "reason": row["reason"],
                    "priority": row["priority_score"],
                })

            # Get interventions
            cursor.execute("""
                SELECT * FROM interventions
                WHERE student_id = ? AND status != 'resolved'
                ORDER BY CASE risk_level WHEN 'critical' THEN 1 WHEN 'high' THEN 2 ELSE 3 END
            """, (db_student_id,))
            for row in cursor.fetchall():
                profile.interventions.append({
                    "risk_level": row["risk_level"],
                    "type": row["intervention_type"],
                    "issue": row["issue_description"],
                    "status": row["status"],
                })

        conn.close()

    # Get persona data
    personality_data = load_personality_data()
    for name, data in personality_data.items():
        if normalize_name(name) == norm_id or name == student_id:
            quiz_data = data.get("quizData", {})
            if quiz_data.get("taken"):
                scores = quiz_data.get("scores", {})
                profile.student_name = name
                profile.personality_type = calculate_personality_type(scores)

                # Add dimension details
                for dim_code in ["EI", "SC", "PT", "RN", "AD", "LG"]:
                    score = scores.get(dim_code, 50)
                    dim_info = PERSONALITY_DIMENSIONS.get(dim_code, {})
                    profile.persona_dimensions.append(PersonaDimension(
                        code=dim_code,
                        name=dim_info.get("name", dim_code),
                        score=score,
                        tendency=get_tendency(dim_code, score),
                    ))
            break

    # Get reports
    reports = load_reports()
    student_reports = []
    for report in reports:
        report_name = report.get("Student Name", "").strip()
        if normalize_name(report_name) == norm_id or report_name == student_id:
            profile.student_name = report_name
            if not profile.grade_level:
                profile.grade_level = report.get("Grade Level")
            if not profile.gender:
                profile.gender = report.get("Student Gender")
            student_reports.append(report)

    # Sort by date descending and take recent
    student_reports.sort(key=lambda x: x.get("Date", ""), reverse=True)
    for report in student_reports[:10]:
        profile.recent_reports.append(ReportSummary(
            date=report.get("Date", ""),
            subject=report.get("Subject", ""),
            teacher_name=report.get("Teacher Name", ""),
            skill_focus=report.get("Skill Focus"),
            skill_focus_met=report.get("SF Met"),
            attention=safe_int(report.get("Attention")),
            retention=safe_int(report.get("Retention")),
            comprehension=safe_int(report.get("Comprehension")),
            behavior=safe_int(report.get("Behavior")),
        ))

    # Reports summary
    if student_reports:
        profile.reports_summary = {
            "total_reports": len(student_reports),
            "subjects": list(set(r.get("Subject", "") for r in student_reports if r.get("Subject"))),
            "teachers": list(set(r.get("Teacher Name", "") for r in student_reports if r.get("Teacher Name"))),
            "avg_attention": round(sum(safe_int(r.get("Attention")) for r in student_reports) / len(student_reports), 1),
            "avg_comprehension": round(sum(safe_int(r.get("Comprehension")) for r in student_reports) / len(student_reports), 1),
            "skill_focus_met_rate": round(
                sum(1 for r in student_reports if r.get("SF Met") == "YES") / len(student_reports) * 100, 1
            ),
        }

    return profile


@router.get("/teachers")
async def list_all_teachers():
    """Get list of all teachers from reports."""
    teachers = {}

    reports = load_reports()
    for report in reports:
        name = report.get("Teacher Name", "").strip()
        if name:
            if name not in teachers:
                teachers[name] = {
                    "teacher_id": name,
                    "teacher_name": name,
                    "reports_count": 0,
                    "students_count": 0,
                    "subjects": set(),
                }
            teachers[name]["reports_count"] += 1
            teachers[name]["subjects"].add(report.get("Subject", ""))

    # Count unique students per teacher
    for name in teachers:
        students = set()
        for report in reports:
            if report.get("Teacher Name", "").strip() == name:
                students.add(report.get("Student Name", ""))
        teachers[name]["students_count"] = len(students)
        teachers[name]["subjects"] = list(teachers[name]["subjects"])

    # Get specializations from skills DB
    conn = get_db_connection("skills_db")
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT teacher_id, teacher_name, COUNT(*) as specialization_count
            FROM teacher_specializations
            GROUP BY teacher_id
        """)
        for row in cursor.fetchall():
            tid = row["teacher_id"]
            tname = row["teacher_name"]
            if tname and tname not in teachers:
                teachers[tname] = {
                    "teacher_id": tid,
                    "teacher_name": tname,
                    "reports_count": 0,
                    "students_count": 0,
                    "subjects": [],
                    "specialization_count": row["specialization_count"],
                }
            elif tname:
                teachers[tname]["specialization_count"] = row["specialization_count"]
        conn.close()

    return sorted(teachers.values(), key=lambda x: x["teacher_name"])


@router.get("/teacher/{teacher_id:path}", response_model=TeacherProfile)
async def get_teacher_profile(teacher_id: str):
    """Get comprehensive teacher profile."""
    norm_id = normalize_name(teacher_id)

    profile = TeacherProfile(
        teacher_id=teacher_id,
        teacher_name=teacher_id,
    )

    # Get reports data
    reports = load_reports()
    teacher_reports = []
    students_set = set()
    subjects_set = set()

    for report in reports:
        teacher_name = report.get("Teacher Name", "").strip()
        if normalize_name(teacher_name) == norm_id or teacher_name == teacher_id:
            profile.teacher_name = teacher_name
            teacher_reports.append(report)
            if report.get("Student Name"):
                students_set.add(report["Student Name"])
            if report.get("Subject"):
                subjects_set.add(report["Subject"])

    profile.reports_count = len(teacher_reports)
    profile.subjects_taught = sorted(list(subjects_set))
    profile.student_count = len(students_set)

    # Build student list with metrics
    student_metrics = {}
    for student_name in students_set:
        student_reports_list = [r for r in teacher_reports if r.get("Student Name") == student_name]
        if student_reports_list:
            student_metrics[student_name] = {
                "student_name": student_name,
                "reports_count": len(student_reports_list),
                "avg_attention": round(sum(safe_int(r.get("Attention")) for r in student_reports_list) / len(student_reports_list), 1),
                "avg_comprehension": round(sum(safe_int(r.get("Comprehension")) for r in student_reports_list) / len(student_reports_list), 1),
                "skill_met_rate": round(sum(1 for r in student_reports_list if r.get("SF Met") == "YES") / len(student_reports_list) * 100, 1),
                "last_report": max(r.get("Date", "") for r in student_reports_list),
            }

    profile.students = sorted(student_metrics.values(), key=lambda x: x["student_name"])

    # Calculate effectiveness metrics
    if teacher_reports:
        profile.effectiveness = {
            "avg_attention": round(sum(safe_int(r.get("Attention")) for r in teacher_reports) / len(teacher_reports), 1),
            "avg_retention": round(sum(safe_int(r.get("Retention")) for r in teacher_reports) / len(teacher_reports), 1),
            "avg_comprehension": round(sum(safe_int(r.get("Comprehension")) for r in teacher_reports) / len(teacher_reports), 1),
            "avg_behavior": round(sum(safe_int(r.get("Behavior")) for r in teacher_reports) / len(teacher_reports), 1),
            "skill_met_rate": round(sum(1 for r in teacher_reports if r.get("SF Met") == "YES") / len(teacher_reports) * 100, 1),
        }

    # Get specializations from skills DB
    conn = get_db_connection("skills_db")
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ts.*, s.name as skill_name, s.code as skill_code
            FROM teacher_specializations ts
            JOIN skills s ON ts.skill_id = s.id
            WHERE ts.teacher_name LIKE ? OR ts.teacher_id LIKE ?
        """, (f"%{norm_id}%", f"%{norm_id}%"))
        for row in cursor.fetchall():
            profile.specializations.append({
                "skill_code": row["skill_code"],
                "skill_name": row["skill_name"],
                "proficiency": row["proficiency_level"],
                "effectiveness": row["effectiveness_score"],
                "students_taught": row["students_taught"],
                "avg_improvement": row["average_student_improvement"],
            })
        conn.close()

    return profile
