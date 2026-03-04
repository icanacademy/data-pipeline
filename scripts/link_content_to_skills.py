#!/usr/bin/env python3
"""Link books and educational apps to skills in the taxonomy."""

import sqlite3
import re
from pathlib import Path

SKILLS_DB = Path.home() / "data-pipeline" / "databases" / "skills_taxonomy.db"
BOOKS_DB = Path.home() / "unified-ontology-platform" / "backend" / "databases" / "books_library.db"
MARKETPLACE_DB = Path.home() / "ican-app-marketplace" / "marketplace.db"


def get_skills_for_matching(cursor):
    """Get skills with keywords for matching."""
    cursor.execute("""
        SELECT s.id, s.code, s.name, s.description, c.name as category_name
        FROM skills s
        JOIN skill_categories c ON s.category_id = c.id
    """)
    skills = []
    for row in cursor.fetchall():
        # Create keywords from skill name and description
        keywords = set()
        keywords.add(row[2].lower())  # skill name
        if row[3]:
            for word in row[3].lower().split():
                if len(word) > 3:
                    keywords.add(word)
        keywords.add(row[4].lower())  # category name

        skills.append({
            "id": row[0],
            "code": row[1],
            "name": row[2],
            "category": row[4],
            "keywords": keywords,
        })
    return skills


def match_content_to_skills(title, description, category, skills):
    """Match content to relevant skills based on text."""
    matched = []
    text = f"{title} {description} {category}".lower()

    # Keywords that map to specific skill categories
    keyword_mapping = {
        "reading": ["READ"],
        "read": ["READ"],
        "phonics": ["READ-PHO"],
        "fluency": ["READ-FLU", "SPEAK-FLU"],
        "comprehension": ["READ-CMP", "LIST-CMP"],
        "writing": ["WRITE"],
        "write": ["WRITE"],
        "grammar": ["GRAM"],
        "spelling": ["WRITE-MEC"],
        "vocabulary": ["VOCAB"],
        "vocab": ["VOCAB"],
        "speaking": ["SPEAK"],
        "speak": ["SPEAK"],
        "pronunciation": ["SPEAK-PRO"],
        "listening": ["LIST"],
        "listen": ["LIST"],
        "conversation": ["SPEAK-FLU"],
        "story": ["READ-CMP", "WRITE-COM"],
        "narrative": ["WRITE-COM-04"],
        "essay": ["WRITE-COM-03"],
        "paragraph": ["WRITE-COM-02"],
        "sentence": ["WRITE-COM-01", "GRAM-SEN"],
    }

    for keyword, skill_prefixes in keyword_mapping.items():
        if keyword in text:
            for skill in skills:
                for prefix in skill_prefixes:
                    if skill["code"].startswith(prefix):
                        if skill["id"] not in [m["id"] for m in matched]:
                            matched.append(skill)

    # Also do general keyword matching
    for skill in skills:
        for kw in skill["keywords"]:
            if kw in text and skill["id"] not in [m["id"] for m in matched]:
                matched.append(skill)
                break

    return matched[:5]  # Limit to 5 skills per content


def link_books_to_skills():
    """Link books to skills based on title and description."""
    print("\n=== Linking Books to Skills ===")

    if not BOOKS_DB.exists():
        print("  Books database not found, skipping...")
        return

    skills_conn = sqlite3.connect(str(SKILLS_DB))
    skills_cursor = skills_conn.cursor()

    books_conn = sqlite3.connect(str(BOOKS_DB))
    books_conn.row_factory = sqlite3.Row
    books_cursor = books_conn.cursor()

    skills = get_skills_for_matching(skills_cursor)

    # Get all books
    books_cursor.execute("""
        SELECT id, title, description, reading_level, age_rating
        FROM books
        WHERE title IS NOT NULL
    """)

    links = []
    for book in books_cursor.fetchall():
        title = book["title"] or ""
        description = book["description"] or ""

        matched_skills = match_content_to_skills(title, description, "reading", skills)

        for skill in matched_skills:
            # Determine proficiency level based on reading_level or age_rating
            proficiency = "intermediate"
            lexile = book["reading_level"]

            links.append((
                "book",
                str(book["id"]),
                title[:200],
                skill["id"],
                proficiency,
                lexile,
                0.8,  # relevance score
            ))

    if links:
        skills_cursor.executemany("""
            INSERT OR REPLACE INTO content_skill_links
            (content_type, content_id, content_name, skill_id, proficiency_level,
             relevance_score, created_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, [(l[0], l[1], l[2], l[3], l[4], l[6]) for l in links])
        skills_conn.commit()
        print(f"  Created {len(links)} book-skill links")
    else:
        print("  No book-skill links to create")

    books_conn.close()
    skills_conn.close()


def link_apps_to_skills():
    """Link educational apps to skills based on title and description."""
    print("\n=== Linking Educational Apps to Skills ===")

    if not MARKETPLACE_DB.exists():
        print("  Marketplace database not found, skipping...")
        return

    skills_conn = sqlite3.connect(str(SKILLS_DB))
    skills_cursor = skills_conn.cursor()

    apps_conn = sqlite3.connect(str(MARKETPLACE_DB))
    apps_conn.row_factory = sqlite3.Row
    apps_cursor = apps_conn.cursor()

    skills = get_skills_for_matching(skills_cursor)

    # Get all apps
    apps_cursor.execute("""
        SELECT id, title, description, category, student_levels
        FROM apps
        WHERE title IS NOT NULL
    """)

    links = []
    for app in apps_cursor.fetchall():
        title = app["title"] or ""
        description = app["description"] or ""
        category = app["category"] or ""

        matched_skills = match_content_to_skills(title, description, category, skills)

        for skill in matched_skills:
            # Determine proficiency level
            student_levels = (app["student_levels"] or "").lower()
            if "beginner" in student_levels or "elementary" in student_levels:
                proficiency = "beginner"
            elif "advanced" in student_levels:
                proficiency = "advanced"
            else:
                proficiency = "intermediate"

            links.append((
                "app",
                str(app["id"]),
                title[:200],
                skill["id"],
                proficiency,
                0.75,  # relevance score
            ))

    if links:
        skills_cursor.executemany("""
            INSERT OR REPLACE INTO content_skill_links
            (content_type, content_id, content_name, skill_id, proficiency_level,
             relevance_score, created_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, links)
        skills_conn.commit()
        print(f"  Created {len(links)} app-skill links")
    else:
        print("  No app-skill links to create")

    apps_conn.close()
    skills_conn.close()


def link_classes_to_skills():
    """Link ICAN classes to skills."""
    print("\n=== Linking Classes to Skills ===")

    classes_db = Path.home() / "unified-ontology-platform" / "backend" / "databases" / "ican_classes.db"
    if not classes_db.exists():
        print("  Classes database not found, skipping...")
        return

    skills_conn = sqlite3.connect(str(SKILLS_DB))
    skills_cursor = skills_conn.cursor()

    classes_conn = sqlite3.connect(str(classes_db))
    classes_conn.row_factory = sqlite3.Row
    classes_cursor = classes_conn.cursor()

    skills = get_skills_for_matching(skills_cursor)

    # Get all classes
    classes_cursor.execute("""
        SELECT id, name, description, skills_focus, learning_objectives
        FROM classes
        WHERE is_active = 1
    """)

    links = []
    for cls in classes_cursor.fetchall():
        name = cls["name"] or ""
        description = cls["description"] or ""
        skills_focus = cls["skills_focus"] or ""
        objectives = cls["learning_objectives"] or ""

        combined_text = f"{name} {description} {skills_focus} {objectives}"
        matched_skills = match_content_to_skills(combined_text, "", "", skills)

        for skill in matched_skills:
            links.append((
                "class",
                str(cls["id"]),
                name[:200],
                skill["id"],
                "intermediate",
                0.9,  # relevance score (classes are very relevant)
            ))

    if links:
        skills_cursor.executemany("""
            INSERT OR REPLACE INTO content_skill_links
            (content_type, content_id, content_name, skill_id, proficiency_level,
             relevance_score, created_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, links)
        skills_conn.commit()
        print(f"  Created {len(links)} class-skill links")
    else:
        print("  No class-skill links to create")

    classes_conn.close()
    skills_conn.close()


def create_teacher_specializations():
    """Create teacher specializations based on their teaching history."""
    print("\n=== Creating Teacher Specializations ===")

    skills_conn = sqlite3.connect(str(SKILLS_DB))
    skills_cursor = skills_conn.cursor()

    # Get core skills
    skills_cursor.execute("""
        SELECT id, code, name, category_id
        FROM skills
        WHERE is_core_skill = 1
        LIMIT 10
    """)
    core_skills = skills_cursor.fetchall()

    # For demo, assign random specializations
    # In production, this would come from actual teaching data
    sample_teachers = [
        ("T001", "John Smith"),
        ("T002", "Sarah Johnson"),
        ("T003", "Michael Brown"),
        ("T004", "Emily Davis"),
        ("T005", "David Wilson"),
    ]

    specializations = []
    for i, (teacher_id, teacher_name) in enumerate(sample_teachers):
        # Each teacher specializes in 2-3 skills
        for j in range(min(3, len(core_skills))):
            skill = core_skills[(i + j) % len(core_skills)]
            specializations.append((
                teacher_id,
                teacher_name,
                skill[0],  # skill_id
                "advanced",
                0.85 + (j * 0.05),  # effectiveness_score
                10 + j * 5,  # students_taught
                15.0 + j * 2,  # average_student_improvement
            ))

    if specializations:
        skills_cursor.executemany("""
            INSERT OR REPLACE INTO teacher_specializations
            (teacher_id, teacher_name, skill_id, proficiency_level,
             effectiveness_score, students_taught, average_student_improvement,
             created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, specializations)
        skills_conn.commit()
        print(f"  Created {len(specializations)} teacher specializations")
    else:
        print("  No specializations to create")

    skills_conn.close()


def main():
    """Main function."""
    print("\n" + "=" * 50)
    print("  Linking Content to Skills Taxonomy")
    print("=" * 50)

    link_books_to_skills()
    link_apps_to_skills()
    link_classes_to_skills()
    create_teacher_specializations()

    # Summary
    skills_conn = sqlite3.connect(str(SKILLS_DB))
    skills_cursor = skills_conn.cursor()
    skills_cursor.execute("SELECT content_type, COUNT(*) FROM content_skill_links GROUP BY content_type")
    print("\n=== Summary ===")
    for row in skills_cursor.fetchall():
        print(f"  {row[0]}: {row[1]} links")
    skills_conn.close()

    print("\n" + "=" * 50)
    print("  Content Linking Complete!")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    main()
