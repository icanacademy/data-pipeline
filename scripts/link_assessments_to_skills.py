#!/usr/bin/env python3
"""Link existing assessment data to skills in the taxonomy."""

import sqlite3
import json
from pathlib import Path
from datetime import datetime

SKILLS_DB = Path.home() / "data-pipeline" / "databases" / "skills_taxonomy.db"
INTERVIEWS_DB = Path.home() / "interview-sheet-generator" / "server" / "interviews.db"
STUDENT_ANALYTICS_DB = Path.home() / "unified-ontology-platform" / "backend" / "databases" / "student_analytics.db"


def get_skill_mappings(cursor):
    """Get skill code to ID mappings."""
    cursor.execute("SELECT id, code, name FROM skills")
    return {row[1]: {"id": row[0], "name": row[2]} for row in cursor.fetchall()}


def link_interview_assessments():
    """Link interview assessment scores to skill progress."""
    print("\n=== Linking Interview Assessments to Skills ===")

    if not INTERVIEWS_DB.exists():
        print("  Interviews database not found, skipping...")
        return

    skills_conn = sqlite3.connect(str(SKILLS_DB))
    skills_cursor = skills_conn.cursor()

    interviews_conn = sqlite3.connect(str(INTERVIEWS_DB))
    interviews_conn.row_factory = sqlite3.Row
    interviews_cursor = interviews_conn.cursor()

    skill_map = get_skill_mappings(skills_cursor)

    # Map interview fields to skills
    field_to_skill = {
        "pronunciation": "SPEAK-PRO-01",  # Pronunciation Basics
        "fluency": "SPEAK-FLU-01",        # Conversational Fluency
        "comprehension": "READ-CMP-01",   # Literal Comprehension
        "insight": "READ-CMP-02",         # Inferential Comprehension
        "vocab": "VOCAB-WRD-02",          # Academic Vocabulary
    }

    # Get all interviews with scores
    interviews_cursor.execute("""
        SELECT student_name, student_id, pronunciation, fluency,
               comprehension, insight, vocab, date, grade
        FROM interviews
        WHERE pronunciation IS NOT NULL
    """)

    progress_records = []
    for row in interviews_cursor.fetchall():
        student_id = row["student_id"] or f"interview_{row['student_name']}"
        student_name = row["student_name"]

        for field, skill_code in field_to_skill.items():
            score = row[field]
            if score is not None and skill_code in skill_map:
                skill_id = skill_map[skill_code]["id"]

                # Normalize score to 0-100
                if isinstance(score, (int, float)):
                    progress_pct = min(100, max(0, score * 10))  # Assume 1-10 scale

                    # Determine level based on score
                    if progress_pct >= 90:
                        level_id = 4  # Expert
                    elif progress_pct >= 75:
                        level_id = 3  # Advanced
                    elif progress_pct >= 50:
                        level_id = 2  # Intermediate
                    else:
                        level_id = 1  # Beginner

                    progress_records.append((
                        student_id,
                        student_name,
                        skill_id,
                        level_id,
                        progress_pct,
                        row["date"],  # mastery_date if high score
                        row["date"],  # last_practiced
                        1,            # assessment_count
                        score,        # average_score
                        "stable",     # trend_direction
                    ))

    # Insert progress records
    skills_cursor.executemany("""
        INSERT OR REPLACE INTO student_skill_progress
        (student_id, student_name, skill_id, current_level_id, progress_percentage,
         mastery_date, last_practiced, assessment_count, average_score, trend_direction,
         created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """, progress_records)

    skills_conn.commit()
    print(f"  Created {len(progress_records)} skill progress records from interviews")

    interviews_conn.close()
    skills_conn.close()


def link_student_analytics():
    """Link student analytics assessments to skill progress."""
    print("\n=== Linking Student Analytics to Skills ===")

    if not STUDENT_ANALYTICS_DB.exists():
        print("  Student analytics database not found, skipping...")
        return

    skills_conn = sqlite3.connect(str(SKILLS_DB))
    skills_cursor = skills_conn.cursor()

    analytics_conn = sqlite3.connect(str(STUDENT_ANALYTICS_DB))
    analytics_conn.row_factory = sqlite3.Row
    analytics_cursor = analytics_conn.cursor()

    skill_map = get_skill_mappings(skills_cursor)

    # Get skill progressions from analytics
    analytics_cursor.execute("""
        SELECT * FROM skill_progressions
    """)

    progress_records = []
    for row in analytics_cursor.fetchall():
        # Try to match skill name to our taxonomy
        skill_name = (row["skill_name"] or "").lower()

        # Simple matching
        matched_skill = None
        for code, info in skill_map.items():
            if skill_name in info["name"].lower() or info["name"].lower() in skill_name:
                matched_skill = code
                break

        if matched_skill:
            skill_id = skill_map[matched_skill]["id"]
            proficiency = row["percentage"] if row["percentage"] else 0

            # Normalize proficiency to 0-100
            if isinstance(proficiency, (int, float)):
                progress_pct = min(100, max(0, proficiency))
            else:
                progress_pct = 50  # Default

            level_id = 2 if progress_pct >= 50 else 1

            progress_records.append((
                str(row["student_id"]),
                None,  # student_name not available
                skill_id,
                level_id,
                progress_pct,
                row["test_date"],
                row["test_date"],
                1,
                progress_pct,
                "stable",
            ))

    if progress_records:
        skills_cursor.executemany("""
            INSERT OR REPLACE INTO student_skill_progress
            (student_id, student_name, skill_id, current_level_id, progress_percentage,
             mastery_date, last_practiced, assessment_count, average_score, trend_direction,
             created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, progress_records)
        skills_conn.commit()
        print(f"  Created {len(progress_records)} skill progress records from analytics")
    else:
        print("  No matching skill progressions found")

    analytics_conn.close()
    skills_conn.close()


def create_sample_recommendations():
    """Create sample learning recommendations based on skill gaps."""
    print("\n=== Creating Sample Recommendations ===")

    skills_conn = sqlite3.connect(str(SKILLS_DB))
    skills_cursor = skills_conn.cursor()

    # Get students with low progress on core skills
    skills_cursor.execute("""
        SELECT DISTINCT sp.student_id, sp.student_name, s.id as skill_id,
               s.name as skill_name, sp.progress_percentage
        FROM student_skill_progress sp
        JOIN skills s ON sp.skill_id = s.id
        WHERE sp.progress_percentage < 50
        AND s.is_core_skill = 1
        ORDER BY sp.progress_percentage ASC
        LIMIT 20
    """)

    recommendations = []
    for row in skills_cursor.fetchall():
        recommendations.append((
            row[0],  # student_id
            "skill",  # recommendation_type
            row[2],   # target_id (skill_id)
            row[3],   # target_name (skill_name)
            f"Student needs more practice with {row[3]}. Current progress: {row[4]:.0f}%",
            100 - row[4],  # priority_score (higher for lower progress)
            1,  # is_active
        ))

    if recommendations:
        skills_cursor.executemany("""
            INSERT INTO learning_recommendations
            (student_id, recommendation_type, target_id, target_name, reason, priority_score, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, recommendations)
        skills_conn.commit()
        print(f"  Created {len(recommendations)} learning recommendations")
    else:
        print("  No recommendations to create (no low-progress students)")

    skills_conn.close()


def create_sample_interventions():
    """Create sample interventions for at-risk students."""
    print("\n=== Creating Sample Interventions ===")

    skills_conn = sqlite3.connect(str(SKILLS_DB))
    skills_cursor = skills_conn.cursor()

    # Get students with very low progress on multiple skills
    skills_cursor.execute("""
        SELECT sp.student_id, sp.student_name, COUNT(*) as low_skill_count,
               AVG(sp.progress_percentage) as avg_progress
        FROM student_skill_progress sp
        WHERE sp.progress_percentage < 40
        GROUP BY sp.student_id
        HAVING COUNT(*) >= 2
        ORDER BY avg_progress ASC
        LIMIT 10
    """)

    interventions = []
    for row in skills_cursor.fetchall():
        risk_level = "high" if row[3] < 25 else "medium"
        interventions.append((
            row[0],  # student_id
            row[1],  # student_name
            risk_level,
            "academic",  # intervention_type
            f"Student has low progress ({row[3]:.0f}% avg) across {row[2]} core skills",
            "1. Schedule one-on-one tutoring\n2. Review prerequisite skills\n3. Provide additional practice materials",
            "pending",
        ))

    if interventions:
        skills_cursor.executemany("""
            INSERT INTO interventions
            (student_id, student_name, risk_level, intervention_type, issue_description,
             recommended_actions, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, interventions)
        skills_conn.commit()
        print(f"  Created {len(interventions)} interventions")
    else:
        print("  No interventions to create")

    skills_conn.close()


def create_progress_snapshots():
    """Create monthly progress snapshots for students."""
    print("\n=== Creating Progress Snapshots ===")

    skills_conn = sqlite3.connect(str(SKILLS_DB))
    skills_cursor = skills_conn.cursor()

    # Get aggregated progress per student
    skills_cursor.execute("""
        SELECT student_id,
               AVG(progress_percentage) as avg_progress,
               SUM(CASE WHEN progress_percentage >= 85 THEN 1 ELSE 0 END) as mastered,
               SUM(CASE WHEN progress_percentage >= 40 AND progress_percentage < 85 THEN 1 ELSE 0 END) as in_progress,
               SUM(CASE WHEN progress_percentage < 40 THEN 1 ELSE 0 END) as not_started
        FROM student_skill_progress
        GROUP BY student_id
    """)

    snapshots = []
    for row in skills_cursor.fetchall():
        trend = "improving" if row[1] >= 60 else ("stable" if row[1] >= 40 else "declining")
        snapshots.append((
            row[0],  # student_id
            datetime.now().strftime("%Y-%m-%d"),
            "monthly",
            row[1],  # overall_mastery_pct
            row[2],  # skills_mastered
            row[3],  # skills_in_progress
            row[4],  # skills_not_started
            None,    # attendance_rate (would need to calculate)
            row[1],  # assessment_average
            trend,
        ))

    if snapshots:
        skills_cursor.executemany("""
            INSERT INTO progress_snapshots
            (student_id, snapshot_date, snapshot_type, overall_mastery_pct,
             skills_mastered, skills_in_progress, skills_not_started,
             attendance_rate, assessment_average, trend_direction, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, snapshots)
        skills_conn.commit()
        print(f"  Created {len(snapshots)} progress snapshots")
    else:
        print("  No snapshots to create")

    skills_conn.close()


def main():
    """Main function."""
    print("\n" + "=" * 50)
    print("  Linking Assessments to Skills Taxonomy")
    print("=" * 50)

    link_interview_assessments()
    link_student_analytics()
    create_sample_recommendations()
    create_sample_interventions()
    create_progress_snapshots()

    print("\n" + "=" * 50)
    print("  Linking Complete!")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    main()
