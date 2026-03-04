"""Pydantic models for API requests and responses."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class TeacherResponse(BaseModel):
    """Teacher entity response."""

    id: str
    name: Optional[str] = None
    email: Optional[str] = None
    position: Optional[str] = None
    department: Optional[str] = None
    is_active: bool = True
    sources: List[str] = []


class StudentResponse(BaseModel):
    """Student entity response."""

    id: str
    name: Optional[str] = None
    student_id: Optional[str] = None
    grade: Optional[str] = None
    school: Optional[str] = None
    is_active: bool = True
    sources: List[str] = []


class AttendanceResponse(BaseModel):
    """Attendance record response."""

    id: str
    date: Optional[str] = None
    status: Optional[str] = None
    minutes_late: Optional[int] = None
    reason: Optional[str] = None


class AssessmentResponse(BaseModel):
    """Assessment response."""

    id: str
    type: str
    date: Optional[str] = None
    score: Optional[str] = None
    result: Optional[str] = None
    feedback: Optional[str] = None


class SyncRequest(BaseModel):
    """Request to trigger a sync operation."""

    sources: Optional[List[str]] = None  # None = all sources
    incremental: bool = True


class SyncResponse(BaseModel):
    """Response from sync operation."""

    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    entities_processed: int = 0
    relations_processed: int = 0
    errors: List[str] = []


class QueryRequest(BaseModel):
    """Request for custom TypeQL query."""

    query: str


class QueryResponse(BaseModel):
    """Response from custom query."""

    results: List[Dict[str, Any]]
    count: int
    execution_time_ms: float


class GraphNode(BaseModel):
    """Node in graph visualization."""

    id: str
    label: str
    type: str
    group: Optional[str] = None
    metadata: Dict[str, Any] = {}
    attributes: Dict[str, Any] = {}


class GraphEdge(BaseModel):
    """Edge in graph visualization."""

    source: str
    target: str
    type: str
    weight: int = 1
    attributes: Dict[str, Any] = {}


class GraphResponse(BaseModel):
    """Graph visualization response."""

    nodes: List[GraphNode]
    edges: List[GraphEdge]


class StatsResponse(BaseModel):
    """Statistics response."""

    total_teachers: int = 0
    total_students: int = 0
    total_assignments: int = 0
    total_assessments: int = 0
    last_sync: Optional[datetime] = None
    entity_counts: Dict[str, int] = {}
