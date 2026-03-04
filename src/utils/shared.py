"""Shared utility functions used across the application."""

import csv
import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Any
from functools import lru_cache

from loguru import logger


# ============================================================================
# Database Paths (centralized)
# ============================================================================

DATA_PATHS = {
    "skills_db": Path.home() / "data-pipeline" / "databases" / "skills_taxonomy.db",
    "personality_json": Path.home() / "Stellar" / "student-report-viewer" / "data" / "personality-data.json",
    "reports_csv": Path.home() / "Stellar" / "teacher-report-generator" / "reports.csv",
    "attendance_db": Path.home() / "ican-teacher-attendance-checker" / "attendance.db",
    "student_attendance_db": Path.home() / "ican-student-attendance" / "student_attendance.db",
    "coaching_db": Path.home() / "coaching-feedback-system" / "coaching.db",
    "marketplace_db": Path.home() / "ican-app-marketplace" / "marketplace.db",
    "demo_db": Path.home() / "ican-demo-english-assessment-tracker" / "demo_assessments.db",
    "interviews_db": Path.home() / "interview-sheet-generator" / "server" / "interviews.db",
    "reports_db": Path.home() / "unified-ontology-platform" / "backend" / "databases" / "student_reports.db",
    "analytics_db": Path.home() / "unified-ontology-platform" / "backend" / "databases" / "student_analytics.db",
    "classes_db": Path.home() / "unified-ontology-platform" / "backend" / "databases" / "ican_classes.db",
    "books_db": Path.home() / "unified-ontology-platform" / "backend" / "databases" / "books_library.db",
    "eduspace_db": Path.home() / "unified-ontology-platform" / "backend" / "databases" / "eduspace.db",
}


# ============================================================================
# Personality Dimensions (single source of truth)
# ============================================================================

PERSONALITY_DIMENSIONS = {
    "EI": {
        "code": "EI",
        "name": "Interest Scope",
        "left_pole": {"code": "E", "name": "Explorer", "description": "Enjoys variety and breadth"},
        "right_pole": {"code": "I", "name": "Investigator", "description": "Prefers depth and mastery"},
    },
    "SC": {
        "code": "SC",
        "name": "Work Style",
        "left_pole": {"code": "S", "name": "Social", "description": "Energized by collaboration"},
        "right_pole": {"code": "C", "name": "Concentrated", "description": "Prefers independent focus"},
    },
    "PT": {
        "code": "PT",
        "name": "Learning Mode",
        "left_pole": {"code": "P", "name": "Practical", "description": "Learns by doing"},
        "right_pole": {"code": "T", "name": "Theoretical", "description": "Learns by thinking"},
    },
    "RN": {
        "code": "RN",
        "name": "Change Preference",
        "left_pole": {"code": "R", "name": "Routine", "description": "Values consistency"},
        "right_pole": {"code": "N", "name": "Novel", "description": "Embraces change"},
    },
    "AD": {
        "code": "AD",
        "name": "Decision Style",
        "left_pole": {"code": "A", "name": "Analytical", "description": "Deliberate and thorough"},
        "right_pole": {"code": "D", "name": "Decisive", "description": "Quick and action-oriented"},
    },
    "LG": {
        "code": "LG",
        "name": "Focus Level",
        "left_pole": {"code": "L", "name": "Local", "description": "Detail-oriented"},
        "right_pole": {"code": "G", "name": "Global", "description": "Big-picture thinker"},
    },
}


# ============================================================================
# Database Connection Utilities
# ============================================================================

def get_db_connection(db_key: str) -> Optional[sqlite3.Connection]:
    """Get a database connection by key name.

    Args:
        db_key: Key from DATA_PATHS dict (e.g., 'skills_db', 'attendance_db')

    Returns:
        SQLite connection with row_factory set, or None if db doesn't exist
    """
    db_path = DATA_PATHS.get(db_key)
    if not db_path:
        logger.warning(f"Unknown database key: {db_key}")
        return None

    if not db_path.exists():
        logger.warning(f"Database not found: {db_path}")
        return None

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to {db_key}: {e}")
        return None


def get_db_path(db_key: str) -> Optional[Path]:
    """Get database path by key name."""
    return DATA_PATHS.get(db_key)


# ============================================================================
# Name Normalization
# ============================================================================

def normalize_name(name: str) -> str:
    """Normalize a name for comparison/matching.

    Removes brackets, parentheses, common prefixes, and normalizes whitespace.
    Used for entity resolution across systems.

    Args:
        name: Raw name string

    Returns:
        Normalized lowercase name
    """
    if not name:
        return ""

    # Convert to lowercase
    normalized = name.lower().strip()

    # Remove brackets and their contents (Korean names, nicknames)
    import re
    normalized = re.sub(r'\[.*?\]', '', normalized)
    normalized = re.sub(r'\(.*?\)', '', normalized)

    # Remove common prefixes
    prefixes = ['teacher ', 'mr. ', 'mrs. ', 'ms. ', 'dr. ', 'prof. ']
    for prefix in prefixes:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]

    # Normalize whitespace
    normalized = ' '.join(normalized.split())

    return normalized.strip()


def sanitize_id(name: str) -> str:
    """Sanitize a name for use as an ID.

    Args:
        name: Name to sanitize

    Returns:
        ID-safe string with special chars removed
    """
    return name.replace(" ", "_").replace("[", "").replace("]", "").replace("(", "").replace(")", "").replace("'", "")


# ============================================================================
# Personality Functions
# ============================================================================

def get_tendency(dim_code: str, score: int) -> str:
    """Get the tendency description for a personality dimension score.

    Args:
        dim_code: Dimension code (EI, SC, PT, RN, AD, LG)
        score: Score from 0-100 (50 is balanced)

    Returns:
        Human-readable tendency description
    """
    dim = PERSONALITY_DIMENSIONS.get(dim_code, {})
    left_name = dim.get("left_pole", {}).get("name", "Left")
    right_name = dim.get("right_pole", {}).get("name", "Right")

    if score < 35:
        return f"Strong {left_name}"
    elif score < 45:
        return f"Moderate {left_name}"
    elif score <= 55:
        return "Balanced"
    elif score <= 65:
        return f"Moderate {right_name}"
    else:
        return f"Strong {right_name}"


def calculate_personality_type(scores: Dict[str, int]) -> str:
    """Calculate the 6-letter personality type code from dimension scores.

    Args:
        scores: Dict with keys EI, SC, PT, RN, AD, LG and int values 0-100

    Returns:
        6-letter type code (e.g., "ESPTAG" or "IXXXXG" where X is balanced)
    """
    type_code = ""
    dim_mapping = {
        "EI": ("E", "I"),
        "SC": ("S", "C"),
        "PT": ("P", "T"),
        "RN": ("R", "N"),
        "AD": ("A", "D"),
        "LG": ("L", "G"),
    }

    for dim, (left, right) in dim_mapping.items():
        score = scores.get(dim, 50)
        if score < 45:
            type_code += left
        elif score > 55:
            type_code += right
        else:
            type_code += "X"  # Balanced

    return type_code


# ============================================================================
# Data Loaders (with caching)
# ============================================================================

@lru_cache(maxsize=1)
def load_personality_data() -> Dict:
    """Load personality quiz data from JSON file.

    Returns:
        Dict with student names as keys and quiz data as values.
        Returns empty dict if file not found.
    """
    json_path = DATA_PATHS["personality_json"]
    if not json_path.exists():
        logger.warning(f"Personality data not found: {json_path}")
        return {}

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load personality data: {e}")
        return {}


def clear_personality_cache():
    """Clear the personality data cache."""
    load_personality_data.cache_clear()


def load_reports(limit: Optional[int] = None) -> List[Dict]:
    """Load student reports from CSV file.

    Args:
        limit: Optional max number of reports to return

    Returns:
        List of report dicts. Returns empty list if file not found.
    """
    csv_path = DATA_PATHS["reports_csv"]
    if not csv_path.exists():
        logger.warning(f"Reports CSV not found: {csv_path}")
        return []

    try:
        reports = []
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if limit and i >= limit:
                    break
                reports.append(row)
        return reports
    except Exception as e:
        logger.error(f"Failed to load reports: {e}")
        return []


# ============================================================================
# Safe Type Conversions
# ============================================================================

def safe_int(value: Any, default: int = 0) -> int:
    """Safely convert value to int.

    Args:
        value: Value to convert
        default: Default value if conversion fails

    Returns:
        Integer value or default
    """
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert value to float.

    Args:
        value: Value to convert
        default: Default value if conversion fails

    Returns:
        Float value or default
    """
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_bool(value: Any) -> bool:
    """Safely convert value to boolean.

    Args:
        value: Value to convert

    Returns:
        Boolean value
    """
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes", "on")
    return bool(value)
