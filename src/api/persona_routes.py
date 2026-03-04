"""Student Persona API routes."""

from typing import List, Optional

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

# Import shared utilities (eliminates duplicate code)
from ..utils import (
    get_tendency,
    calculate_personality_type,
    load_personality_data,
    load_reports,
    safe_int,
    PERSONALITY_DIMENSIONS,
)

router = APIRouter(prefix="/api/personas", tags=["personas"])


# ============================================================================
# Response Models
# ============================================================================

class PersonalityDimension(BaseModel):
    code: str
    name: str
    left_pole_code: str
    left_pole_name: str
    left_pole_description: str
    right_pole_code: str
    right_pole_name: str
    right_pole_description: str


class StudentPersona(BaseModel):
    student_name: str
    personality_type: str
    quiz_taken_at: Optional[str] = None
    scores: dict
    tendencies: dict


class StudentReport(BaseModel):
    student_name: str
    teacher_name: str
    date: str
    subject: str
    skill_focus: Optional[str] = None
    skill_focus_met: Optional[str] = None
    attention: int = 0
    retention: int = 0
    comprehension: int = 0
    behavior: int = 0
    handwriting: int = 0
    conversation: int = 0
    narrative: Optional[str] = None


class PersonaStats(BaseModel):
    total_personas: int
    total_reports: int
    total_students: int
    total_teachers: int
    dimension_distribution: dict


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/dimensions", response_model=List[PersonalityDimension])
async def get_dimensions():
    """Get all personality dimensions."""
    dimensions = []
    for code, dim in PERSONALITY_DIMENSIONS.items():
        dimensions.append(PersonalityDimension(
            code=dim["code"],
            name=dim["name"],
            left_pole_code=dim["left_pole"]["code"],
            left_pole_name=dim["left_pole"]["name"],
            left_pole_description=dim["left_pole"]["description"],
            right_pole_code=dim["right_pole"]["code"],
            right_pole_name=dim["right_pole"]["name"],
            right_pole_description=dim["right_pole"]["description"],
        ))
    return dimensions


@router.get("/list", response_model=List[StudentPersona])
async def list_personas():
    """List all student personas."""
    personality_data = load_personality_data()
    personas = []

    for student_name, data in personality_data.items():
        quiz_data = data.get("quizData", {})
        if not quiz_data.get("taken"):
            continue

        scores = quiz_data.get("scores", {})
        personality_type = calculate_personality_type(scores)

        tendencies = {}
        for dim_code in ["EI", "SC", "PT", "RN", "AD", "LG"]:
            score = scores.get(dim_code, 50)
            tendencies[dim_code] = get_tendency(dim_code, score)

        personas.append(StudentPersona(
            student_name=student_name,
            personality_type=personality_type,
            quiz_taken_at=quiz_data.get("takenAt"),
            scores=scores,
            tendencies=tendencies,
        ))

    return personas


@router.get("/persona/{student_name}")
async def get_persona(student_name: str):
    """Get persona details for a specific student."""
    personality_data = load_personality_data()

    if student_name not in personality_data:
        raise HTTPException(status_code=404, detail="Student persona not found")

    data = personality_data[student_name]
    quiz_data = data.get("quizData", {})

    if not quiz_data.get("taken"):
        raise HTTPException(status_code=404, detail="Quiz not taken by this student")

    scores = quiz_data.get("scores", {})
    answers = quiz_data.get("answers", [])
    personality_type = calculate_personality_type(scores)

    tendencies = {}
    dimension_details = []
    for dim_code in ["EI", "SC", "PT", "RN", "AD", "LG"]:
        score = scores.get(dim_code, 50)
        tendency = get_tendency(dim_code, score)
        tendencies[dim_code] = tendency

        dim_info = PERSONALITY_DIMENSIONS[dim_code]
        dimension_details.append({
            "code": dim_code,
            "name": dim_info["name"],
            "score": score,
            "tendency": tendency,
            "left_pole": dim_info["left_pole"],
            "right_pole": dim_info["right_pole"],
        })

    return {
        "student_name": student_name,
        "personality_type": personality_type,
        "quiz_taken_at": quiz_data.get("takenAt"),
        "answers": answers,
        "scores": scores,
        "tendencies": tendencies,
        "dimension_details": dimension_details,
    }


@router.get("/reports", response_model=List[StudentReport])
async def get_reports(
    student_name: Optional[str] = None,
    teacher_name: Optional[str] = None,
    subject: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
):
    """Get student reports with optional filtering."""
    all_reports = load_reports()
    filtered = []

    for row in all_reports:
        if student_name and row.get("Student Name") != student_name:
            continue
        if teacher_name and row.get("Teacher Name") != teacher_name:
            continue
        if subject and row.get("Subject") != subject:
            continue

        filtered.append(StudentReport(
            student_name=row.get("Student Name", ""),
            teacher_name=row.get("Teacher Name", ""),
            date=row.get("Date", ""),
            subject=row.get("Subject", ""),
            skill_focus=row.get("Skill Focus"),
            skill_focus_met=row.get("SF Met"),
            attention=safe_int(row.get("Attention")),
            retention=safe_int(row.get("Retention")),
            comprehension=safe_int(row.get("Comprehension")),
            behavior=safe_int(row.get("Behavior")),
            handwriting=safe_int(row.get("Handwriting")),
            conversation=safe_int(row.get("Conversation")),
            narrative=row.get("Narrative"),
        ))

        if len(filtered) >= limit:
            break

    return filtered


@router.get("/students")
async def list_students():
    """Get list of all unique students from reports."""
    reports = load_reports()
    students = set()
    for row in reports:
        if row.get("Student Name"):
            students.add(row["Student Name"])
    return sorted(list(students))


@router.get("/teachers")
async def list_teachers():
    """Get list of all unique teachers from reports."""
    reports = load_reports()
    teachers = set()
    for row in reports:
        if row.get("Teacher Name"):
            teachers.add(row["Teacher Name"])
    return sorted(list(teachers))


@router.get("/subjects")
async def list_subjects():
    """Get list of all unique subjects from reports."""
    reports = load_reports()
    subjects = set()
    for row in reports:
        if row.get("Subject"):
            subjects.add(row["Subject"])
    return sorted(list(subjects))


@router.get("/stats", response_model=PersonaStats)
async def get_stats():
    """Get persona and report statistics."""
    personality_data = load_personality_data()
    reports = load_reports()

    # Count personas with completed quizzes
    total_personas = sum(
        1 for data in personality_data.values()
        if data.get("quizData", {}).get("taken")
    )

    # Count unique students and teachers from reports
    students = set()
    teachers = set()
    for row in reports:
        if row.get("Student Name"):
            students.add(row["Student Name"])
        if row.get("Teacher Name"):
            teachers.add(row["Teacher Name"])

    # Calculate dimension distribution
    dimension_distribution = {
        dim: {"left": 0, "balanced": 0, "right": 0}
        for dim in ["EI", "SC", "PT", "RN", "AD", "LG"]
    }

    for data in personality_data.values():
        quiz_data = data.get("quizData", {})
        if not quiz_data.get("taken"):
            continue

        scores = quiz_data.get("scores", {})
        for dim in ["EI", "SC", "PT", "RN", "AD", "LG"]:
            score = scores.get(dim, 50)
            if score < 45:
                dimension_distribution[dim]["left"] += 1
            elif score > 55:
                dimension_distribution[dim]["right"] += 1
            else:
                dimension_distribution[dim]["balanced"] += 1

    return PersonaStats(
        total_personas=total_personas,
        total_reports=len(reports),
        total_students=len(students),
        total_teachers=len(teachers),
        dimension_distribution=dimension_distribution,
    )
