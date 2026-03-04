"""Skills Taxonomy API routes."""

import sqlite3
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/skills", tags=["skills"])

SKILLS_DB = Path.home() / "data-pipeline" / "databases" / "skills_taxonomy.db"


def get_db_connection():
    """Get database connection."""
    if not SKILLS_DB.exists():
        raise HTTPException(status_code=503, detail="Skills database not available")
    conn = sqlite3.connect(str(SKILLS_DB))
    conn.row_factory = sqlite3.Row
    return conn


# ============================================================================
# Response Models
# ============================================================================

class SkillDomain(BaseModel):
    id: int
    code: str
    name: str
    description: Optional[str] = None
    color: Optional[str] = None
    category_count: int = 0
    skill_count: int = 0


class SkillCategory(BaseModel):
    id: int
    code: str
    name: str
    description: Optional[str] = None
    domain_code: str
    color: Optional[str] = None
    skill_count: int = 0


class Skill(BaseModel):
    id: int
    code: str
    name: str
    description: Optional[str] = None
    category_code: str
    domain_code: str
    cefr_level: Optional[str] = None
    target_age_min: Optional[int] = None
    target_age_max: Optional[int] = None
    estimated_hours: Optional[int] = None
    is_core_skill: bool = False
    prerequisites: List[str] = []


class StudentProgress(BaseModel):
    student_id: str
    student_name: Optional[str] = None
    skill_code: str
    skill_name: str
    domain_code: Optional[str] = None
    category_code: Optional[str] = None
    progress_percentage: float
    current_level: Optional[str] = None
    trend_direction: Optional[str] = None
    last_practiced: Optional[str] = None


class Recommendation(BaseModel):
    id: int
    student_id: str
    recommendation_type: str
    target_name: Optional[str] = None
    reason: Optional[str] = None
    priority_score: float


class Intervention(BaseModel):
    id: int
    student_id: str
    student_name: Optional[str] = None
    risk_level: str
    intervention_type: Optional[str] = None
    issue_description: Optional[str] = None
    status: str


class Achievement(BaseModel):
    id: int
    code: str
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    points: int = 0
    icon: Optional[str] = None
    color: Optional[str] = None


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/domains", response_model=List[SkillDomain])
async def list_domains():
    """List all skill domains with counts."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT d.*,
               (SELECT COUNT(*) FROM skill_categories WHERE domain_id = d.id) as category_count,
               (SELECT COUNT(*) FROM skills s
                JOIN skill_categories c ON s.category_id = c.id
                WHERE c.domain_id = d.id) as skill_count
        FROM skill_domains d
        WHERE d.is_active = 1
        ORDER BY d.sort_order
    """)

    domains = []
    for row in cursor.fetchall():
        domains.append(SkillDomain(
            id=row["id"],
            code=row["code"],
            name=row["name"],
            description=row["description"],
            color=row["color"],
            category_count=row["category_count"],
            skill_count=row["skill_count"],
        ))

    conn.close()
    return domains


@router.get("/categories", response_model=List[SkillCategory])
async def list_categories(domain_code: Optional[str] = None):
    """List skill categories, optionally filtered by domain."""
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT c.*, d.code as domain_code,
               (SELECT COUNT(*) FROM skills WHERE category_id = c.id) as skill_count
        FROM skill_categories c
        JOIN skill_domains d ON c.domain_id = d.id
        WHERE c.is_active = 1
    """
    params = []

    if domain_code:
        query += " AND d.code = ?"
        params.append(domain_code)

    query += " ORDER BY d.sort_order, c.sort_order"

    cursor.execute(query, params)

    categories = []
    for row in cursor.fetchall():
        categories.append(SkillCategory(
            id=row["id"],
            code=row["code"],
            name=row["name"],
            description=row["description"],
            domain_code=row["domain_code"],
            color=row["color"],
            skill_count=row["skill_count"],
        ))

    conn.close()
    return categories


@router.get("/list", response_model=List[Skill])
async def list_skills(
    category_code: Optional[str] = None,
    domain_code: Optional[str] = None,
    core_only: bool = False,
):
    """List skills with optional filtering."""
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT s.*, c.code as category_code, d.code as domain_code
        FROM skills s
        JOIN skill_categories c ON s.category_id = c.id
        JOIN skill_domains d ON c.domain_id = d.id
        WHERE s.is_active = 1
    """
    params = []

    if category_code:
        query += " AND c.code = ?"
        params.append(category_code)

    if domain_code:
        query += " AND d.code = ?"
        params.append(domain_code)

    if core_only:
        query += " AND s.is_core_skill = 1"

    query += " ORDER BY d.sort_order, c.sort_order, s.sort_order"

    cursor.execute(query, params)

    skills = []
    for row in cursor.fetchall():
        # Get prerequisites
        cursor.execute("""
            SELECT s2.code
            FROM skill_prerequisites p
            JOIN skills s2 ON p.prerequisite_skill_id = s2.id
            WHERE p.skill_id = ?
        """, (row["id"],))
        prereqs = [r[0] for r in cursor.fetchall()]

        skills.append(Skill(
            id=row["id"],
            code=row["code"],
            name=row["name"],
            description=row["description"],
            category_code=row["category_code"],
            domain_code=row["domain_code"],
            cefr_level=row["cefr_level"],
            target_age_min=row["target_age_min"],
            target_age_max=row["target_age_max"],
            estimated_hours=row["estimated_hours"],
            is_core_skill=bool(row["is_core_skill"]),
            prerequisites=prereqs,
        ))

    conn.close()
    return skills


@router.get("/tree")
async def get_skill_tree():
    """Get hierarchical skill tree for visualization."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get domains
    cursor.execute("""
        SELECT * FROM skill_domains WHERE is_active = 1 ORDER BY sort_order
    """)
    domains = {row["id"]: dict(row) for row in cursor.fetchall()}

    # Get categories
    cursor.execute("""
        SELECT * FROM skill_categories WHERE is_active = 1 ORDER BY sort_order
    """)
    categories = {}
    for row in cursor.fetchall():
        cat = dict(row)
        cat["skills"] = []
        categories[cat["id"]] = cat

    # Get skills
    cursor.execute("""
        SELECT * FROM skills WHERE is_active = 1 ORDER BY sort_order
    """)
    for row in cursor.fetchall():
        skill = dict(row)
        if skill["category_id"] in categories:
            categories[skill["category_id"]]["skills"].append(skill)

    # Build tree
    tree = []
    for domain_id, domain in domains.items():
        domain["categories"] = []
        for cat_id, cat in categories.items():
            if cat["domain_id"] == domain_id:
                domain["categories"].append(cat)
        tree.append(domain)

    conn.close()
    return tree


@router.get("/progress", response_model=List[StudentProgress])
async def get_student_progress(
    student_id: Optional[str] = None,
    skill_code: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
):
    """Get student skill progress records."""
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT p.student_id, p.student_name, s.code as skill_code, s.name as skill_name,
               c.code as category_code, d.code as domain_code,
               MAX(p.progress_percentage) as progress_percentage,
               l.name as level_name,
               p.trend_direction, MAX(p.last_practiced) as last_practiced
        FROM student_skill_progress p
        JOIN skills s ON p.skill_id = s.id
        JOIN skill_categories c ON s.category_id = c.id
        JOIN skill_domains d ON c.domain_id = d.id
        LEFT JOIN competency_levels l ON p.current_level_id = l.id
        WHERE 1=1
    """
    params = []

    if student_id:
        query += " AND p.student_id = ?"
        params.append(student_id)

    if skill_code:
        query += " AND s.code = ?"
        params.append(skill_code)

    query += f" GROUP BY p.student_id, s.id ORDER BY progress_percentage DESC LIMIT {limit}"

    cursor.execute(query, params)

    progress = []
    for row in cursor.fetchall():
        progress.append(StudentProgress(
            student_id=row["student_id"],
            student_name=row["student_name"],
            skill_code=row["skill_code"],
            skill_name=row["skill_name"],
            domain_code=row["domain_code"],
            category_code=row["category_code"],
            progress_percentage=row["progress_percentage"] or 0,
            current_level=row["level_name"],
            trend_direction=row["trend_direction"],
            last_practiced=row["last_practiced"],
        ))

    conn.close()
    return progress


@router.get("/recommendations", response_model=List[Recommendation])
async def get_recommendations(
    student_id: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
):
    """Get learning recommendations."""
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT * FROM learning_recommendations
        WHERE is_active = 1
    """
    params = []

    if student_id:
        query += " AND student_id = ?"
        params.append(student_id)

    query += f" ORDER BY priority_score DESC LIMIT {limit}"

    cursor.execute(query, params)

    recs = []
    for row in cursor.fetchall():
        recs.append(Recommendation(
            id=row["id"],
            student_id=row["student_id"],
            recommendation_type=row["recommendation_type"],
            target_name=row["target_name"],
            reason=row["reason"],
            priority_score=row["priority_score"] or 0,
        ))

    conn.close()
    return recs


@router.get("/students")
async def get_students_with_skills():
    """Get list of students who have skill progress data."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT student_id, student_name,
               COUNT(*) as skill_count,
               AVG(progress_percentage) as avg_progress
        FROM student_skill_progress
        WHERE student_id IS NOT NULL
        GROUP BY student_id
        ORDER BY student_name
    """)

    students = []
    for row in cursor.fetchall():
        students.append({
            "student_id": row["student_id"],
            "student_name": row["student_name"] or row["student_id"],
            "skill_count": row["skill_count"],
            "avg_progress": round(row["avg_progress"] or 0, 1),
        })

    conn.close()
    return students


@router.get("/interventions", response_model=List[Intervention])
async def get_interventions(
    status: Optional[str] = None,
    risk_level: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
):
    """Get intervention records."""
    conn = get_db_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM interventions WHERE 1=1"
    params = []

    if status:
        query += " AND status = ?"
        params.append(status)
    else:
        query += " AND status != 'resolved'"

    if risk_level:
        query += " AND risk_level = ?"
        params.append(risk_level)

    query += f" ORDER BY CASE risk_level WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END LIMIT {limit}"

    cursor.execute(query, params)

    interventions = []
    for row in cursor.fetchall():
        interventions.append(Intervention(
            id=row["id"],
            student_id=row["student_id"],
            student_name=row["student_name"],
            risk_level=row["risk_level"],
            intervention_type=row["intervention_type"],
            issue_description=row["issue_description"],
            status=row["status"],
        ))

    conn.close()
    return interventions


@router.get("/achievements", response_model=List[Achievement])
async def get_achievements():
    """Get all available achievements."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM achievements WHERE is_active = 1 ORDER BY points DESC
    """)

    achievements = []
    for row in cursor.fetchall():
        achievements.append(Achievement(
            id=row["id"],
            code=row["code"],
            name=row["name"],
            description=row["description"],
            category=row["category"],
            points=row["points"] or 0,
            icon=row["icon"],
            color=row["color"],
        ))

    conn.close()
    return achievements


@router.get("/content-links")
async def get_content_skill_links(
    content_type: Optional[str] = None,
    skill_code: Optional[str] = None,
):
    """Get content-skill links."""
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT l.*, s.code as skill_code, s.name as skill_name
        FROM content_skill_links l
        JOIN skills s ON l.skill_id = s.id
        WHERE 1=1
    """
    params = []

    if content_type:
        query += " AND l.content_type = ?"
        params.append(content_type)

    if skill_code:
        query += " AND s.code = ?"
        params.append(skill_code)

    query += " ORDER BY l.relevance_score DESC LIMIT 100"

    cursor.execute(query, params)

    links = []
    for row in cursor.fetchall():
        links.append({
            "id": row["id"],
            "content_type": row["content_type"],
            "content_id": row["content_id"],
            "content_name": row["content_name"],
            "skill_code": row["skill_code"],
            "skill_name": row["skill_name"],
            "proficiency_level": row["proficiency_level"],
            "relevance_score": row["relevance_score"],
        })

    conn.close()
    return links


@router.get("/stats")
async def get_skills_stats():
    """Get skills taxonomy statistics."""
    conn = get_db_connection()
    cursor = conn.cursor()

    stats = {}

    cursor.execute("SELECT COUNT(*) FROM skill_domains WHERE is_active = 1")
    stats["total_domains"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM skill_categories WHERE is_active = 1")
    stats["total_categories"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM skills WHERE is_active = 1")
    stats["total_skills"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM skills WHERE is_core_skill = 1")
    stats["core_skills"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM skill_prerequisites")
    stats["total_prerequisites"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT student_id) FROM student_skill_progress")
    stats["students_with_progress"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM student_skill_progress WHERE progress_percentage >= 85")
    stats["mastery_records"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM learning_recommendations WHERE is_active = 1")
    stats["active_recommendations"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM interventions WHERE status != 'resolved'")
    stats["active_interventions"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM content_skill_links")
    stats["content_links"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM achievements WHERE is_active = 1")
    stats["total_achievements"] = cursor.fetchone()[0]

    conn.close()
    return stats
