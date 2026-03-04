#!/usr/bin/env python3
"""Create and populate the Skills Taxonomy database for ICAN Academy."""

import sqlite3
from pathlib import Path
from datetime import datetime

# Database path
DB_PATH = Path.home() / "data-pipeline" / "databases" / "skills_taxonomy.db"

def create_database():
    """Create the skills taxonomy database with all tables."""

    # Ensure directory exists
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # =========================================================================
    # CREATE TABLES
    # =========================================================================

    # Skill Domains (Top level: English, Math, etc.)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS skill_domains (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code VARCHAR(20) UNIQUE NOT NULL,
            name VARCHAR(100) NOT NULL,
            description TEXT,
            color VARCHAR(20) DEFAULT '#1976d2',
            icon VARCHAR(50),
            sort_order INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Skill Categories (Second level: Reading, Writing, Speaking, etc.)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS skill_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain_id INTEGER NOT NULL,
            code VARCHAR(20) UNIQUE NOT NULL,
            name VARCHAR(100) NOT NULL,
            description TEXT,
            color VARCHAR(20),
            icon VARCHAR(50),
            sort_order INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (domain_id) REFERENCES skill_domains(id)
        )
    """)

    # Skills (Individual skills: Phonics, Fluency, Grammar, etc.)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL,
            code VARCHAR(30) UNIQUE NOT NULL,
            name VARCHAR(100) NOT NULL,
            description TEXT,
            proficiency_levels TEXT,  -- JSON: which levels this skill spans
            target_age_min INTEGER,
            target_age_max INTEGER,
            target_grade_min VARCHAR(10),
            target_grade_max VARCHAR(10),
            lexile_level VARCHAR(20),
            cefr_level VARCHAR(10),
            estimated_hours INTEGER,
            is_core_skill BOOLEAN DEFAULT 0,
            sort_order INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES skill_categories(id)
        )
    """)

    # Competency Levels (Beginner, Intermediate, Advanced, Expert)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS competency_levels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code VARCHAR(20) UNIQUE NOT NULL,
            name VARCHAR(50) NOT NULL,
            description TEXT,
            level_number INTEGER NOT NULL,  -- 1, 2, 3, 4
            mastery_threshold REAL,  -- Percentage needed (e.g., 70, 85, 95)
            color VARCHAR(20),
            sort_order INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Skill Prerequisites (Which skills must come before others)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS skill_prerequisites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            skill_id INTEGER NOT NULL,
            prerequisite_skill_id INTEGER NOT NULL,
            is_required BOOLEAN DEFAULT 1,  -- Required vs recommended
            description TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (skill_id) REFERENCES skills(id),
            FOREIGN KEY (prerequisite_skill_id) REFERENCES skills(id),
            UNIQUE(skill_id, prerequisite_skill_id)
        )
    """)

    # Student Skill Progress
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS student_skill_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id VARCHAR(50) NOT NULL,
            student_name VARCHAR(100),
            skill_id INTEGER NOT NULL,
            current_level_id INTEGER,
            progress_percentage REAL DEFAULT 0.0,
            mastery_date DATETIME,
            last_practiced DATETIME,
            total_practice_hours REAL DEFAULT 0.0,
            streak_days INTEGER DEFAULT 0,
            assessment_count INTEGER DEFAULT 0,
            average_score REAL,
            trend_direction VARCHAR(20),  -- improving, stable, declining
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (skill_id) REFERENCES skills(id),
            FOREIGN KEY (current_level_id) REFERENCES competency_levels(id)
        )
    """)

    # Progress Snapshots (Monthly/quarterly snapshots)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS progress_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id VARCHAR(50) NOT NULL,
            snapshot_date DATE NOT NULL,
            snapshot_type VARCHAR(20) DEFAULT 'monthly',  -- weekly, monthly, quarterly
            overall_mastery_pct REAL,
            skills_mastered INTEGER DEFAULT 0,
            skills_in_progress INTEGER DEFAULT 0,
            skills_not_started INTEGER DEFAULT 0,
            attendance_rate REAL,
            assessment_average REAL,
            trend_direction VARCHAR(20),
            strengths TEXT,  -- JSON array of skill IDs
            gaps TEXT,       -- JSON array of skill IDs
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Achievements/Badges
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code VARCHAR(30) UNIQUE NOT NULL,
            name VARCHAR(100) NOT NULL,
            description TEXT,
            category VARCHAR(50),  -- skill, attendance, streak, milestone
            requirement_type VARCHAR(50),  -- skill_mastery, streak, assessment
            requirement_value TEXT,  -- JSON with requirements
            points INTEGER DEFAULT 0,
            icon VARCHAR(100),
            color VARCHAR(20),
            is_active BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Student Achievements
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS student_achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id VARCHAR(50) NOT NULL,
            achievement_id INTEGER NOT NULL,
            earned_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            notes TEXT,
            FOREIGN KEY (achievement_id) REFERENCES achievements(id),
            UNIQUE(student_id, achievement_id)
        )
    """)

    # Learning Recommendations
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS learning_recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id VARCHAR(50) NOT NULL,
            recommendation_type VARCHAR(50) NOT NULL,  -- skill, class, book, app, intervention
            target_id INTEGER,  -- ID of skill, class, book, or app
            target_name VARCHAR(100),
            reason TEXT,
            priority_score REAL DEFAULT 0.0,
            is_active BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            expires_at DATETIME,
            completed_at DATETIME
        )
    """)

    # Interventions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS interventions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id VARCHAR(50) NOT NULL,
            student_name VARCHAR(100),
            risk_level VARCHAR(20) NOT NULL,  -- low, medium, high, critical
            intervention_type VARCHAR(50),  -- academic, attendance, behavioral
            issue_description TEXT,
            recommended_actions TEXT,
            assigned_teacher_id VARCHAR(50),
            assigned_teacher_name VARCHAR(100),
            status VARCHAR(20) DEFAULT 'pending',  -- pending, in_progress, resolved
            start_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            target_date DATETIME,
            resolution_date DATETIME,
            outcome TEXT,
            notes TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Content-Skill Links (Books, Apps linked to skills)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS content_skill_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_type VARCHAR(20) NOT NULL,  -- book, app, class, lesson
            content_id VARCHAR(50) NOT NULL,
            content_name VARCHAR(200),
            skill_id INTEGER NOT NULL,
            proficiency_level VARCHAR(20),
            relevance_score REAL DEFAULT 1.0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (skill_id) REFERENCES skills(id)
        )
    """)

    # Teacher Specializations
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS teacher_specializations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id VARCHAR(50) NOT NULL,
            teacher_name VARCHAR(100),
            skill_id INTEGER NOT NULL,
            proficiency_level VARCHAR(20),
            effectiveness_score REAL,
            students_taught INTEGER DEFAULT 0,
            average_student_improvement REAL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (skill_id) REFERENCES skills(id)
        )
    """)

    conn.commit()
    print("✓ Tables created successfully")
    return conn

def seed_competency_levels(cursor):
    """Seed the competency levels."""
    levels = [
        ('BEG', 'Beginner', 'Just starting to learn the skill', 1, 0.0, '#64B5F6', 1),
        ('INT', 'Intermediate', 'Developing understanding and can apply with guidance', 2, 50.0, '#4CAF50', 2),
        ('ADV', 'Advanced', 'Strong understanding and can apply independently', 3, 75.0, '#FF9800', 3),
        ('EXP', 'Expert', 'Mastery level, can teach others', 4, 90.0, '#9C27B0', 4),
    ]

    cursor.executemany("""
        INSERT OR IGNORE INTO competency_levels
        (code, name, description, level_number, mastery_threshold, color, sort_order)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, levels)
    print("✓ Competency levels seeded")

def seed_skill_domains(cursor):
    """Seed the skill domains."""
    domains = [
        ('ENG', 'English Language Arts', 'Core English language skills including reading, writing, speaking, and listening', '#2196F3', 'fa-book', 1),
        ('MATH', 'Mathematics', 'Mathematical concepts and problem-solving skills', '#4CAF50', 'fa-calculator', 2),
        ('SCI', 'Science', 'Scientific inquiry and knowledge', '#FF9800', 'fa-flask', 3),
        ('SOC', 'Social Skills', 'Interpersonal and communication skills', '#9C27B0', 'fa-users', 4),
        ('TECH', 'Technology', 'Digital literacy and technology skills', '#607D8B', 'fa-laptop', 5),
    ]

    cursor.executemany("""
        INSERT OR IGNORE INTO skill_domains
        (code, name, description, color, icon, sort_order)
        VALUES (?, ?, ?, ?, ?, ?)
    """, domains)
    print("✓ Skill domains seeded")

def seed_skill_categories(cursor):
    """Seed the skill categories."""
    # Get domain IDs
    cursor.execute("SELECT id, code FROM skill_domains")
    domains = {row[1]: row[0] for row in cursor.fetchall()}

    categories = [
        # English Language Arts
        (domains['ENG'], 'READ', 'Reading', 'Decoding, fluency, and comprehension skills', '#1E88E5', 'fa-book-open', 1),
        (domains['ENG'], 'WRITE', 'Writing', 'Written expression and composition skills', '#1565C0', 'fa-pen', 2),
        (domains['ENG'], 'SPEAK', 'Speaking', 'Oral communication and presentation skills', '#0D47A1', 'fa-microphone', 3),
        (domains['ENG'], 'LISTEN', 'Listening', 'Listening comprehension and note-taking', '#5C6BC0', 'fa-headphones', 4),
        (domains['ENG'], 'VOCAB', 'Vocabulary', 'Word knowledge and usage', '#3949AB', 'fa-spell-check', 5),
        (domains['ENG'], 'GRAM', 'Grammar', 'Language structure and mechanics', '#303F9F', 'fa-language', 6),

        # Mathematics
        (domains['MATH'], 'NUM', 'Number Sense', 'Understanding of numbers and operations', '#43A047', 'fa-sort-numeric-up', 1),
        (domains['MATH'], 'ALG', 'Algebra', 'Algebraic thinking and equations', '#388E3C', 'fa-superscript', 2),
        (domains['MATH'], 'GEO', 'Geometry', 'Shapes, space, and measurement', '#2E7D32', 'fa-shapes', 3),
        (domains['MATH'], 'DATA', 'Data & Statistics', 'Data analysis and probability', '#1B5E20', 'fa-chart-bar', 4),

        # Social Skills
        (domains['SOC'], 'COMM', 'Communication', 'Effective interpersonal communication', '#8E24AA', 'fa-comments', 1),
        (domains['SOC'], 'COLLAB', 'Collaboration', 'Working effectively with others', '#7B1FA2', 'fa-handshake', 2),
        (domains['SOC'], 'LEAD', 'Leadership', 'Leading and motivating others', '#6A1B9A', 'fa-crown', 3),
    ]

    cursor.executemany("""
        INSERT OR IGNORE INTO skill_categories
        (domain_id, code, name, description, color, icon, sort_order)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, categories)
    print("✓ Skill categories seeded")

def seed_skills(cursor):
    """Seed the individual skills - focused on English for ICAN Academy."""
    # Get category IDs
    cursor.execute("SELECT id, code FROM skill_categories")
    categories = {row[1]: row[0] for row in cursor.fetchall()}

    skills = [
        # ===== READING SKILLS =====
        # Phonics & Decoding
        (categories['READ'], 'READ-PHO-01', 'Letter Recognition', 'Identifying uppercase and lowercase letters', 4, 6, 'Pre-K', '1st', None, 'Pre-A1', 20, 1, 1),
        (categories['READ'], 'READ-PHO-02', 'Phonemic Awareness', 'Understanding that words are made up of sounds', 4, 7, 'K', '1st', None, 'Pre-A1', 30, 1, 2),
        (categories['READ'], 'READ-PHO-03', 'Basic Phonics', 'Connecting letters to sounds (consonants, short vowels)', 5, 7, 'K', '1st', '200L-400L', 'A1', 40, 1, 3),
        (categories['READ'], 'READ-PHO-04', 'Advanced Phonics', 'Blends, digraphs, long vowels, r-controlled vowels', 6, 8, '1st', '2nd', '400L-600L', 'A1', 50, 1, 4),
        (categories['READ'], 'READ-PHO-05', 'Multisyllabic Decoding', 'Reading words with multiple syllables', 7, 10, '2nd', '4th', '600L-800L', 'A2', 40, 0, 5),

        # Fluency
        (categories['READ'], 'READ-FLU-01', 'Word Recognition', 'Automatically recognizing high-frequency words', 5, 8, 'K', '2nd', '200L-500L', 'A1', 30, 1, 10),
        (categories['READ'], 'READ-FLU-02', 'Reading Rate', 'Reading at an appropriate pace', 6, 10, '1st', '4th', '400L-700L', 'A2', 40, 1, 11),
        (categories['READ'], 'READ-FLU-03', 'Prosody', 'Reading with expression and proper phrasing', 7, 12, '2nd', '5th', '500L-900L', 'A2', 50, 0, 12),
        (categories['READ'], 'READ-FLU-04', 'Oral Reading Fluency', 'Smooth, accurate, expressive oral reading', 7, 14, '2nd', '6th', '600L-1000L', 'B1', 60, 1, 13),

        # Comprehension
        (categories['READ'], 'READ-CMP-01', 'Literal Comprehension', 'Understanding explicitly stated information', 5, 10, 'K', '3rd', '200L-700L', 'A1', 40, 1, 20),
        (categories['READ'], 'READ-CMP-02', 'Inferential Comprehension', 'Making inferences and drawing conclusions', 7, 12, '2nd', '5th', '500L-900L', 'A2', 50, 1, 21),
        (categories['READ'], 'READ-CMP-03', 'Critical Comprehension', 'Evaluating and analyzing text', 9, 14, '4th', '8th', '800L-1100L', 'B1', 60, 0, 22),
        (categories['READ'], 'READ-CMP-04', 'Story Elements', 'Identifying characters, setting, plot, theme', 6, 10, '1st', '4th', '400L-800L', 'A2', 30, 1, 23),
        (categories['READ'], 'READ-CMP-05', 'Main Idea & Details', 'Finding main ideas and supporting details', 7, 12, '2nd', '6th', '500L-900L', 'A2', 40, 1, 24),
        (categories['READ'], 'READ-CMP-06', 'Text Structure', 'Understanding how texts are organized', 8, 14, '3rd', '7th', '700L-1000L', 'B1', 40, 0, 25),

        # ===== WRITING SKILLS =====
        (categories['WRITE'], 'WRITE-MEC-01', 'Handwriting', 'Legible letter and word formation', 4, 8, 'Pre-K', '2nd', None, 'Pre-A1', 30, 1, 1),
        (categories['WRITE'], 'WRITE-MEC-02', 'Spelling', 'Correct spelling of words', 5, 12, 'K', '5th', None, 'A1', 50, 1, 2),
        (categories['WRITE'], 'WRITE-MEC-03', 'Punctuation', 'Using punctuation correctly', 6, 12, '1st', '5th', None, 'A2', 40, 1, 3),
        (categories['WRITE'], 'WRITE-MEC-04', 'Capitalization', 'Using capital letters correctly', 5, 10, 'K', '3rd', None, 'A1', 20, 1, 4),

        (categories['WRITE'], 'WRITE-COM-01', 'Sentence Writing', 'Writing complete, correct sentences', 5, 9, 'K', '2nd', None, 'A1', 40, 1, 10),
        (categories['WRITE'], 'WRITE-COM-02', 'Paragraph Writing', 'Organizing ideas into paragraphs', 7, 12, '2nd', '5th', None, 'A2', 50, 1, 11),
        (categories['WRITE'], 'WRITE-COM-03', 'Essay Writing', 'Writing multi-paragraph essays', 9, 14, '4th', '8th', None, 'B1', 60, 0, 12),
        (categories['WRITE'], 'WRITE-COM-04', 'Narrative Writing', 'Writing stories with plot and characters', 7, 12, '2nd', '6th', None, 'A2', 50, 1, 13),
        (categories['WRITE'], 'WRITE-COM-05', 'Informative Writing', 'Writing to explain or inform', 8, 14, '3rd', '7th', None, 'B1', 50, 1, 14),
        (categories['WRITE'], 'WRITE-COM-06', 'Opinion/Persuasive Writing', 'Writing to convince or persuade', 8, 14, '3rd', '8th', None, 'B1', 50, 0, 15),

        # ===== SPEAKING SKILLS =====
        (categories['SPEAK'], 'SPEAK-PRO-01', 'Pronunciation Basics', 'Clear pronunciation of English sounds', 4, 10, 'Pre-K', '3rd', None, 'A1', 40, 1, 1),
        (categories['SPEAK'], 'SPEAK-PRO-02', 'Word Stress', 'Correct stress patterns in words', 7, 14, '2nd', '7th', None, 'A2', 30, 0, 2),
        (categories['SPEAK'], 'SPEAK-PRO-03', 'Intonation', 'Using appropriate pitch patterns', 8, 14, '3rd', '8th', None, 'B1', 40, 0, 3),

        (categories['SPEAK'], 'SPEAK-FLU-01', 'Conversational Fluency', 'Speaking smoothly in conversations', 5, 14, 'K', '8th', None, 'A1', 60, 1, 10),
        (categories['SPEAK'], 'SPEAK-FLU-02', 'Presentation Skills', 'Speaking clearly to groups', 8, 14, '3rd', '8th', None, 'B1', 40, 0, 11),
        (categories['SPEAK'], 'SPEAK-FLU-03', 'Discussion Skills', 'Participating in group discussions', 7, 14, '2nd', '8th', None, 'A2', 40, 1, 12),

        # ===== LISTENING SKILLS =====
        (categories['LISTEN'], 'LIST-CMP-01', 'Following Directions', 'Understanding and following spoken instructions', 4, 10, 'Pre-K', '3rd', None, 'A1', 30, 1, 1),
        (categories['LISTEN'], 'LIST-CMP-02', 'Listening for Main Idea', 'Identifying main points when listening', 6, 12, '1st', '5th', None, 'A2', 40, 1, 2),
        (categories['LISTEN'], 'LIST-CMP-03', 'Listening for Details', 'Identifying specific information', 6, 12, '1st', '5th', None, 'A2', 40, 1, 3),
        (categories['LISTEN'], 'LIST-CMP-04', 'Critical Listening', 'Evaluating and analyzing what is heard', 9, 14, '4th', '8th', None, 'B1', 50, 0, 4),

        # ===== VOCABULARY SKILLS =====
        (categories['VOCAB'], 'VOCAB-WRD-01', 'Sight Words', 'Recognizing common high-frequency words', 4, 8, 'Pre-K', '2nd', None, 'A1', 30, 1, 1),
        (categories['VOCAB'], 'VOCAB-WRD-02', 'Academic Vocabulary', 'Words used in academic contexts', 7, 14, '2nd', '8th', None, 'A2', 60, 1, 2),
        (categories['VOCAB'], 'VOCAB-WRD-03', 'Context Clues', 'Using context to understand new words', 7, 14, '2nd', '8th', None, 'A2', 40, 1, 3),
        (categories['VOCAB'], 'VOCAB-WRD-04', 'Word Relationships', 'Synonyms, antonyms, analogies', 8, 14, '3rd', '8th', None, 'B1', 40, 0, 4),
        (categories['VOCAB'], 'VOCAB-WRD-05', 'Word Parts', 'Prefixes, suffixes, root words', 8, 14, '3rd', '8th', None, 'B1', 50, 1, 5),

        # ===== GRAMMAR SKILLS =====
        (categories['GRAM'], 'GRAM-SEN-01', 'Parts of Speech', 'Nouns, verbs, adjectives, adverbs', 6, 12, '1st', '5th', None, 'A1', 40, 1, 1),
        (categories['GRAM'], 'GRAM-SEN-02', 'Subject-Verb Agreement', 'Matching subjects and verbs', 7, 12, '2nd', '5th', None, 'A2', 30, 1, 2),
        (categories['GRAM'], 'GRAM-SEN-03', 'Verb Tenses', 'Using correct verb tenses', 7, 14, '2nd', '7th', None, 'A2', 50, 1, 3),
        (categories['GRAM'], 'GRAM-SEN-04', 'Pronouns', 'Using pronouns correctly', 7, 12, '2nd', '5th', None, 'A2', 30, 0, 4),
        (categories['GRAM'], 'GRAM-SEN-05', 'Sentence Types', 'Simple, compound, complex sentences', 8, 14, '3rd', '7th', None, 'B1', 40, 0, 5),
        (categories['GRAM'], 'GRAM-SEN-06', 'Modifiers', 'Using adjectives and adverbs effectively', 8, 14, '3rd', '7th', None, 'B1', 30, 0, 6),
    ]

    cursor.executemany("""
        INSERT OR IGNORE INTO skills
        (category_id, code, name, description, target_age_min, target_age_max,
         target_grade_min, target_grade_max, lexile_level, cefr_level,
         estimated_hours, is_core_skill, sort_order)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, skills)
    print(f"✓ {len(skills)} skills seeded")

def seed_skill_prerequisites(cursor):
    """Seed skill prerequisites - which skills must come before others."""
    # Get skill IDs
    cursor.execute("SELECT id, code FROM skills")
    skills = {row[1]: row[0] for row in cursor.fetchall()}

    prerequisites = [
        # Reading progression
        (skills['READ-PHO-02'], skills['READ-PHO-01'], 1, 'Letter recognition before phonemic awareness'),
        (skills['READ-PHO-03'], skills['READ-PHO-02'], 1, 'Phonemic awareness before basic phonics'),
        (skills['READ-PHO-04'], skills['READ-PHO-03'], 1, 'Basic phonics before advanced phonics'),
        (skills['READ-PHO-05'], skills['READ-PHO-04'], 1, 'Advanced phonics before multisyllabic'),

        (skills['READ-FLU-01'], skills['READ-PHO-03'], 1, 'Basic phonics before word recognition'),
        (skills['READ-FLU-02'], skills['READ-FLU-01'], 1, 'Word recognition before reading rate'),
        (skills['READ-FLU-03'], skills['READ-FLU-02'], 1, 'Reading rate before prosody'),
        (skills['READ-FLU-04'], skills['READ-FLU-03'], 1, 'Prosody before oral reading fluency'),

        (skills['READ-CMP-01'], skills['READ-PHO-03'], 1, 'Basic phonics before literal comprehension'),
        (skills['READ-CMP-02'], skills['READ-CMP-01'], 1, 'Literal before inferential comprehension'),
        (skills['READ-CMP-03'], skills['READ-CMP-02'], 1, 'Inferential before critical comprehension'),
        (skills['READ-CMP-04'], skills['READ-CMP-01'], 1, 'Literal comprehension before story elements'),
        (skills['READ-CMP-05'], skills['READ-CMP-01'], 1, 'Literal comprehension before main idea'),

        # Writing progression
        (skills['WRITE-MEC-02'], skills['WRITE-MEC-01'], 1, 'Handwriting before spelling'),
        (skills['WRITE-MEC-03'], skills['WRITE-COM-01'], 1, 'Sentence writing before punctuation mastery'),
        (skills['WRITE-COM-01'], skills['WRITE-MEC-01'], 1, 'Handwriting before sentence writing'),
        (skills['WRITE-COM-02'], skills['WRITE-COM-01'], 1, 'Sentence writing before paragraph writing'),
        (skills['WRITE-COM-03'], skills['WRITE-COM-02'], 1, 'Paragraph writing before essay writing'),
        (skills['WRITE-COM-04'], skills['WRITE-COM-02'], 1, 'Paragraph writing before narrative writing'),
        (skills['WRITE-COM-05'], skills['WRITE-COM-02'], 1, 'Paragraph writing before informative writing'),
        (skills['WRITE-COM-06'], skills['WRITE-COM-05'], 1, 'Informative writing before persuasive writing'),

        # Speaking progression
        (skills['SPEAK-PRO-02'], skills['SPEAK-PRO-01'], 1, 'Pronunciation basics before word stress'),
        (skills['SPEAK-PRO-03'], skills['SPEAK-PRO-02'], 1, 'Word stress before intonation'),
        (skills['SPEAK-FLU-02'], skills['SPEAK-FLU-01'], 1, 'Conversational fluency before presentation skills'),

        # Vocabulary progression
        (skills['VOCAB-WRD-02'], skills['VOCAB-WRD-01'], 1, 'Sight words before academic vocabulary'),
        (skills['VOCAB-WRD-03'], skills['VOCAB-WRD-02'], 0, 'Academic vocab recommended before context clues'),
        (skills['VOCAB-WRD-04'], skills['VOCAB-WRD-03'], 0, 'Context clues recommended before word relationships'),

        # Grammar progression
        (skills['GRAM-SEN-02'], skills['GRAM-SEN-01'], 1, 'Parts of speech before subject-verb agreement'),
        (skills['GRAM-SEN-03'], skills['GRAM-SEN-01'], 1, 'Parts of speech before verb tenses'),
        (skills['GRAM-SEN-04'], skills['GRAM-SEN-01'], 1, 'Parts of speech before pronouns'),
        (skills['GRAM-SEN-05'], skills['GRAM-SEN-02'], 1, 'Subject-verb agreement before sentence types'),
    ]

    cursor.executemany("""
        INSERT OR IGNORE INTO skill_prerequisites
        (skill_id, prerequisite_skill_id, is_required, description)
        VALUES (?, ?, ?, ?)
    """, prerequisites)
    print(f"✓ {len(prerequisites)} skill prerequisites seeded")

def seed_achievements(cursor):
    """Seed achievements and badges."""
    achievements = [
        # Skill mastery badges
        ('FIRST_SKILL', 'First Skill Mastered', 'Mastered your first skill!', 'skill', 'skill_mastery', '{"count": 1}', 10, 'fa-star', '#FFD700'),
        ('SKILL_5', 'Rising Star', 'Mastered 5 skills', 'skill', 'skill_mastery', '{"count": 5}', 50, 'fa-star', '#FFA500'),
        ('SKILL_10', 'Skill Builder', 'Mastered 10 skills', 'skill', 'skill_mastery', '{"count": 10}', 100, 'fa-medal', '#C0C0C0'),
        ('SKILL_25', 'Knowledge Seeker', 'Mastered 25 skills', 'skill', 'skill_mastery', '{"count": 25}', 250, 'fa-medal', '#FFD700'),
        ('SKILL_50', 'Master Learner', 'Mastered 50 skills', 'skill', 'skill_mastery', '{"count": 50}', 500, 'fa-trophy', '#FFD700'),

        # Category mastery
        ('READ_MASTER', 'Reading Champion', 'Mastered all core reading skills', 'category', 'category_mastery', '{"category": "READ"}', 200, 'fa-book-reader', '#2196F3'),
        ('WRITE_MASTER', 'Writing Wizard', 'Mastered all core writing skills', 'category', 'category_mastery', '{"category": "WRITE"}', 200, 'fa-pen-fancy', '#4CAF50'),
        ('SPEAK_MASTER', 'Speaking Star', 'Mastered all core speaking skills', 'category', 'category_mastery', '{"category": "SPEAK"}', 200, 'fa-microphone', '#FF9800'),

        # Streak badges
        ('STREAK_7', 'Week Warrior', '7-day practice streak', 'streak', 'streak', '{"days": 7}', 25, 'fa-fire', '#FF5722'),
        ('STREAK_30', 'Month Master', '30-day practice streak', 'streak', 'streak', '{"days": 30}', 100, 'fa-fire-alt', '#FF5722'),
        ('STREAK_100', 'Century Club', '100-day practice streak', 'streak', 'streak', '{"days": 100}', 500, 'fa-burn', '#FF5722'),

        # Attendance badges
        ('ATTEND_PERFECT', 'Perfect Attendance', 'No absences for a month', 'attendance', 'attendance', '{"rate": 100, "period": "month"}', 50, 'fa-calendar-check', '#4CAF50'),
        ('ATTEND_95', 'Almost Perfect', '95%+ attendance for a quarter', 'attendance', 'attendance', '{"rate": 95, "period": "quarter"}', 75, 'fa-calendar-check', '#8BC34A'),

        # Assessment badges
        ('ASSESS_ACE', 'Assessment Ace', 'Score 100% on an assessment', 'assessment', 'assessment_score', '{"score": 100}', 25, 'fa-check-double', '#9C27B0'),
        ('ASSESS_IMPROVE', 'Improvement Star', 'Improve score by 20+ points', 'assessment', 'assessment_improvement', '{"improvement": 20}', 50, 'fa-chart-line', '#00BCD4'),

        # Milestones
        ('LEVEL_UP', 'Level Up!', 'Advanced to a new competency level', 'milestone', 'level_up', '{}', 30, 'fa-level-up-alt', '#673AB7'),
        ('FIRST_MONTH', 'First Month', 'Completed first month at ICAN', 'milestone', 'enrollment', '{"months": 1}', 20, 'fa-award', '#3F51B5'),
        ('SEMESTER', 'Semester Strong', 'Completed a full semester', 'milestone', 'enrollment', '{"months": 6}', 100, 'fa-graduation-cap', '#3F51B5'),
    ]

    cursor.executemany("""
        INSERT OR IGNORE INTO achievements
        (code, name, description, category, requirement_type, requirement_value, points, icon, color)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, achievements)
    print(f"✓ {len(achievements)} achievements seeded")

def main():
    """Main function to create and seed the database."""
    print("\n" + "=" * 50)
    print("  ICAN Skills Taxonomy Database Setup")
    print("=" * 50 + "\n")

    conn = create_database()
    cursor = conn.cursor()

    print("\nSeeding data...")
    seed_competency_levels(cursor)
    seed_skill_domains(cursor)
    seed_skill_categories(cursor)
    seed_skills(cursor)
    seed_skill_prerequisites(cursor)
    seed_achievements(cursor)

    conn.commit()
    conn.close()

    print("\n" + "=" * 50)
    print(f"  Database created at: {DB_PATH}")
    print("=" * 50 + "\n")

    # Print summary
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    tables = ['skill_domains', 'skill_categories', 'skills', 'competency_levels',
              'skill_prerequisites', 'achievements']

    print("Summary:")
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"  - {table}: {count} records")

    conn.close()

if __name__ == "__main__":
    main()
