"""FastAPI application for ICAN Data Center."""

import time
import secrets
import hashlib
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query, Request, Response, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from loguru import logger

# Authentication settings
APP_PASSWORD = "wecaninican"
APP_PASSWORD_HINT = "wcii"
SESSION_SECRET = secrets.token_hex(32)

from ..config import settings
from ..extractors import PostgreSQLExtractor, NotionExtractor
from ..extractors.sqlite import (
    TeacherAttendanceExtractor,
    StudentAttendanceExtractor,
    CoachingExtractor,
    DemoAssessmentExtractor,
    InterviewExtractor,
    StudentReportExtractor,
    MarketplaceExtractor,
)
from ..loaders import TypeDBLoader
from ..transformers import EntityResolver
from .models import (
    TeacherResponse,
    StudentResponse,
    AttendanceResponse,
    AssessmentResponse,
    SyncRequest,
    SyncResponse,
    QueryRequest,
    QueryResponse,
    GraphResponse,
    GraphNode,
    GraphEdge,
    StatsResponse,
)

# Global state
loader: Optional[TypeDBLoader] = None
last_sync: Optional[datetime] = None
SYNC_STATUS_FILE = Path.home() / ".ican-data-center" / "last_sync.txt"


def load_last_sync() -> Optional[datetime]:
    """Load last sync timestamp from file."""
    try:
        if SYNC_STATUS_FILE.exists():
            timestamp_str = SYNC_STATUS_FILE.read_text().strip()
            return datetime.fromisoformat(timestamp_str)
    except Exception:
        pass
    return None


def save_last_sync(dt: datetime):
    """Save last sync timestamp to file."""
    try:
        SYNC_STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SYNC_STATUS_FILE.write_text(dt.isoformat())
    except Exception as e:
        logger.warning(f"Could not save sync status: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    global loader, last_sync

    logger.info("Starting ICAN Data Center API")

    # Load persisted sync status
    last_sync = load_last_sync()
    if last_sync:
        logger.info(f"Last sync was at: {last_sync}")

    loader = TypeDBLoader()

    if loader.connect():
        logger.info("Connected to TypeDB")
    else:
        logger.warning("TypeDB not available - running in limited mode")

    yield

    if loader:
        loader.disconnect()
    logger.info("Shutting down ICAN Data Center API")


app = FastAPI(
    title="ICAN Data Center API",
    description="Unified data center connecting all ICAN Academy data sources",
    version="1.0.0",
    lifespan=lifespan,
)

# Add session middleware for authentication
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include skills API routes
from .skills_routes import router as skills_router
app.include_router(skills_router)

# Include persona API routes
from .persona_routes import router as persona_router
app.include_router(persona_router)

# Include profile API routes
from .profile_routes import router as profile_router
app.include_router(profile_router)


# ============================================================================
# HTML TEMPLATES
# ============================================================================

BASE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - ICAN Data Center</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3/dist/cdn.min.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        [x-cloak] {{ display: none !important; }}
        .sidebar {{ width: 250px; }}
        .main-content {{ margin-left: 250px; }}
        @media (max-width: 768px) {{
            .sidebar {{ width: 100%; position: relative; }}
            .main-content {{ margin-left: 0; }}
        }}
    </style>
</head>
<body class="bg-gray-100 min-h-screen">
    <!-- Sidebar -->
    <div class="sidebar fixed top-0 left-0 h-full bg-slate-800 text-white p-4 overflow-y-auto">
        <div class="mb-8">
            <h1 class="text-xl font-bold flex items-center gap-2">
                <i class="fas fa-database"></i>
                ICAN Data Center
            </h1>
            <p class="text-slate-400 text-sm mt-1">Unified Data Platform</p>
        </div>

        <nav class="space-y-2">
            <a href="/" class="block px-4 py-2 rounded hover:bg-slate-700 {active_dashboard}">
                <i class="fas fa-home w-6"></i> Dashboard
            </a>
            <a href="/view/teachers" class="block px-4 py-2 rounded hover:bg-slate-700 {active_teachers}">
                <i class="fas fa-chalkboard-teacher w-6"></i> Teachers
            </a>
            <a href="/view/students" class="block px-4 py-2 rounded hover:bg-slate-700 {active_students}">
                <i class="fas fa-user-graduate w-6"></i> Students
            </a>
            <a href="/view/schedules" class="block px-4 py-2 rounded hover:bg-slate-700 {active_schedules}">
                <i class="fas fa-calendar-alt w-6"></i> Schedules
            </a>
            <a href="/view/attendance" class="block px-4 py-2 rounded hover:bg-slate-700 {active_attendance}">
                <i class="fas fa-clipboard-check w-6"></i> Attendance
            </a>
            <a href="/view/assessments" class="block px-4 py-2 rounded hover:bg-slate-700 {active_assessments}">
                <i class="fas fa-file-alt w-6"></i> Assessments
            </a>
            <a href="/view/coaching" class="block px-4 py-2 rounded hover:bg-slate-700 {active_coaching}">
                <i class="fas fa-comments w-6"></i> Coaching
            </a>
            <a href="/view/apps" class="block px-4 py-2 rounded hover:bg-slate-700 {active_apps}">
                <i class="fas fa-th-large w-6"></i> App Marketplace
            </a>

            <div class="border-t border-slate-700 my-4"></div>
            <p class="text-xs text-slate-500 uppercase tracking-wider mb-2 px-4">Ontology</p>

            <a href="/view/skills" class="block px-4 py-2 rounded hover:bg-slate-700 {active_skills}">
                <i class="fas fa-sitemap w-6"></i> Skills Taxonomy
            </a>
            <a href="/view/progress" class="block px-4 py-2 rounded hover:bg-slate-700 {active_progress}">
                <i class="fas fa-chart-line w-6"></i> Learning Progress
            </a>
            <a href="/view/interventions" class="block px-4 py-2 rounded hover:bg-slate-700 {active_interventions}">
                <i class="fas fa-exclamation-triangle w-6"></i> Interventions
            </a>
            <a href="/view/personas" class="block px-4 py-2 rounded hover:bg-slate-700 {active_personas}">
                <i class="fas fa-user-circle w-6"></i> Student Personas
            </a>
            <a href="/view/profiles" class="block px-4 py-2 rounded hover:bg-slate-700 {active_profiles}">
                <i class="fas fa-id-card w-6"></i> Student/Teacher Profiles
            </a>

            <div class="border-t border-slate-700 my-4"></div>

            <a href="/view/graph" class="block px-4 py-2 rounded hover:bg-slate-700 {active_graph}">
                <i class="fas fa-share-alt w-6"></i> Graph Explorer
            </a>
            <a href="/view/galaxy" class="block px-4 py-2 rounded hover:bg-slate-700 {active_galaxy}">
                <i class="fas fa-globe w-6"></i> Galaxy View
            </a>
            <a href="/view/query" class="block px-4 py-2 rounded hover:bg-slate-700 {active_query}">
                <i class="fas fa-terminal w-6"></i> Query Console
            </a>
            <a href="/view/sync" class="block px-4 py-2 rounded hover:bg-slate-700 {active_sync}">
                <i class="fas fa-sync w-6"></i> Data Sync
            </a>
            <a href="/view/databases" class="block px-4 py-2 rounded hover:bg-slate-700 {active_databases}">
                <i class="fas fa-database w-6"></i> Database Explorer
            </a>

            <div class="border-t border-slate-700 my-4"></div>

            <a href="/docs" class="block px-4 py-2 rounded hover:bg-slate-700">
                <i class="fas fa-book w-6"></i> API Docs
            </a>

            <div class="border-t border-slate-700 my-4"></div>

            <a href="/logout" class="block px-4 py-2 rounded hover:bg-red-700 text-red-300 hover:text-white">
                <i class="fas fa-sign-out-alt w-6"></i> Logout
            </a>
        </nav>

        <div class="absolute bottom-4 left-4 right-4 text-xs text-slate-500">
            <div id="sync-status">Last sync: Never</div>
        </div>
    </div>

    <!-- Main Content -->
    <div class="main-content min-h-screen p-6">
        {content}
    </div>

    <script>
        // Update last sync status
        fetch('/api/stats').then(r => r.json()).then(data => {{
            if (data.last_sync) {{
                document.getElementById('sync-status').innerText = 'Last sync: ' + new Date(data.last_sync).toLocaleString();
            }}
        }}).catch(() => {{}});
    </script>
</body>
</html>
"""


def render_page(title: str, content: str, active: str = "") -> str:
    """Render a page with the base template."""
    active_states = {
        "active_dashboard": "bg-slate-700" if active == "dashboard" else "",
        "active_teachers": "bg-slate-700" if active == "teachers" else "",
        "active_students": "bg-slate-700" if active == "students" else "",
        "active_schedules": "bg-slate-700" if active == "schedules" else "",
        "active_attendance": "bg-slate-700" if active == "attendance" else "",
        "active_assessments": "bg-slate-700" if active == "assessments" else "",
        "active_coaching": "bg-slate-700" if active == "coaching" else "",
        "active_apps": "bg-slate-700" if active == "apps" else "",
        "active_skills": "bg-slate-700" if active == "skills" else "",
        "active_progress": "bg-slate-700" if active == "progress" else "",
        "active_interventions": "bg-slate-700" if active == "interventions" else "",
        "active_personas": "bg-slate-700" if active == "personas" else "",
        "active_profiles": "bg-slate-700" if active == "profiles" else "",
        "active_graph": "bg-slate-700" if active == "graph" else "",
        "active_galaxy": "bg-slate-700" if active == "galaxy" else "",
        "active_query": "bg-slate-700" if active == "query" else "",
        "active_sync": "bg-slate-700" if active == "sync" else "",
        "active_databases": "bg-slate-700" if active == "databases" else "",
    }
    return BASE_HTML.format(title=title, content=content, **active_states)


# ============================================================================
# AUTHENTICATION
# ============================================================================

def check_auth(request: Request) -> bool:
    """Check if user is authenticated."""
    return request.session.get("authenticated", False)


async def require_auth(request: Request):
    """Dependency to require authentication."""
    if not check_auth(request):
        raise HTTPException(status_code=401, detail="Not authenticated")


LOGIN_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - ICAN Data Center</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
</head>
<body class="bg-gradient-to-br from-slate-800 to-slate-900 min-h-screen flex items-center justify-center">
    <div class="bg-white rounded-2xl shadow-2xl p-8 w-full max-w-md mx-4">
        <div class="text-center mb-8">
            <div class="inline-flex items-center justify-center w-16 h-16 bg-slate-800 rounded-full mb-4">
                <i class="fas fa-database text-white text-2xl"></i>
            </div>
            <h1 class="text-2xl font-bold text-gray-800">ICAN Data Center</h1>
            <p class="text-gray-500 text-sm mt-1">Enter password to access</p>
        </div>

        {error_message}

        <form method="POST" action="/login" class="space-y-6">
            <div>
                <label for="password" class="block text-sm font-medium text-gray-700 mb-2">Password</label>
                <div class="relative">
                    <input type="password" id="password" name="password" required
                           class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-slate-500 focus:border-slate-500 outline-none transition"
                           placeholder="Enter password">
                    <i class="fas fa-lock absolute right-4 top-1/2 -translate-y-1/2 text-gray-400"></i>
                </div>
                <p class="text-xs text-gray-400 mt-2">Hint: {hint}</p>
            </div>
            <button type="submit"
                    class="w-full bg-slate-800 text-white py-3 rounded-lg font-medium hover:bg-slate-700 transition flex items-center justify-center gap-2">
                <i class="fas fa-sign-in-alt"></i>
                Sign In
            </button>
        </form>
    </div>
</body>
</html>
"""


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = None):
    """Show login page."""
    if check_auth(request):
        return RedirectResponse(url="/", status_code=302)

    error_html = ""
    if error:
        error_html = '<div class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded-lg mb-6"><i class="fas fa-exclamation-circle mr-2"></i>Invalid password. Please try again.</div>'

    return LOGIN_PAGE.format(error_message=error_html, hint=APP_PASSWORD_HINT)


@app.post("/login")
async def login(request: Request, password: str = Form(...)):
    """Process login."""
    if password == APP_PASSWORD:
        request.session["authenticated"] = True
        return RedirectResponse(url="/", status_code=302)
    else:
        return RedirectResponse(url="/login?error=1", status_code=302)


@app.get("/logout")
async def logout(request: Request):
    """Logout user."""
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)


# ============================================================================
# PAGE ROUTES
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard."""
    if not check_auth(request):
        return RedirectResponse(url="/login", status_code=302)
    content = """
    <div x-data="dashboard()" x-init="loadStats()">
        <!-- Header with Search -->
        <div class="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-6">
            <div>
                <h1 class="text-3xl font-bold text-gray-800">Dashboard</h1>
                <p class="text-gray-500 text-sm mt-1" x-show="stats.last_sync">
                    Last synced: <span x-text="stats.last_sync ? new Date(stats.last_sync).toLocaleString() : 'Never'"></span>
                </p>
            </div>

            <!-- Global Search -->
            <div class="relative w-full md:w-96">
                <div class="flex gap-2 mb-2">
                    <button @click="searchMode = 'keyword'"
                            :class="searchMode === 'keyword' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600'"
                            class="px-3 py-1 text-xs rounded-full transition">
                        <i class="fas fa-search mr-1"></i> Keyword
                    </button>
                    <button @click="searchMode = 'semantic'"
                            :class="searchMode === 'semantic' ? 'bg-purple-600 text-white' : 'bg-gray-100 text-gray-600'"
                            class="px-3 py-1 text-xs rounded-full transition">
                        <i class="fas fa-brain mr-1"></i> AI/Semantic
                    </button>
                </div>
                <input type="text"
                    x-model="searchQuery"
                    @input.debounce.300ms="search()"
                    @keydown.escape="searchResults = []; searchQuery = ''"
                    :placeholder="searchMode === 'semantic' ? 'Try: math apps for beginners, struggling students...' : 'Search teachers, students, apps...'"
                    class="w-full pl-10 pr-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
                <i :class="searchMode === 'semantic' ? 'fas fa-brain text-purple-400' : 'fas fa-search text-gray-400'" class="absolute left-3 top-12 text-gray-400"></i>
                <div x-show="searching" class="absolute right-3 top-12">
                    <i class="fas fa-spinner fa-spin text-gray-400"></i>
                </div>

                <!-- Search Results Dropdown -->
                <div x-show="searchResults.length > 0"
                     x-transition
                     @click.outside="searchResults = []"
                     class="absolute z-50 w-full mt-1 bg-white rounded-lg shadow-xl border max-h-96 overflow-y-auto">
                    <div x-show="searchMode === 'semantic'" class="px-3 py-2 bg-purple-50 text-purple-700 text-xs border-b">
                        <i class="fas fa-brain mr-1"></i> AI-powered semantic search results
                    </div>
                    <template x-for="result in searchResults" :key="result.id + result.type">
                        <a :href="result.url || '#'"
                           class="flex items-center gap-3 px-4 py-3 hover:bg-gray-50 border-b last:border-0">
                            <span class="w-8 h-8 rounded-full flex items-center justify-center text-white text-sm"
                                  :class="{
                                      'bg-blue-500': result.type === 'teacher',
                                      'bg-green-500': result.type === 'student',
                                      'bg-orange-500': result.type === 'employee',
                                      'bg-cyan-500': result.type === 'interview',
                                      'bg-rose-500': result.type === 'assessment',
                                      'bg-purple-500': result.type === 'app',
                                      'bg-amber-500': result.type === 'coaching'
                                  }">
                                <i :class="{
                                    'fas fa-chalkboard-teacher': result.type === 'teacher',
                                    'fas fa-user-graduate': result.type === 'student',
                                    'fas fa-user-tie': result.type === 'employee',
                                    'fas fa-microphone': result.type === 'interview',
                                    'fas fa-clipboard-check': result.type === 'assessment',
                                    'fas fa-th-large': result.type === 'app',
                                    'fas fa-comments': result.type === 'coaching'
                                }"></i>
                            </span>
                            <div class="flex-1 min-w-0">
                                <p class="font-medium truncate" x-text="result.name"></p>
                                <p class="text-xs text-gray-500">
                                    <span class="capitalize" x-text="result.type"></span>
                                    <span x-show="result.similarity"> • </span>
                                    <span x-show="result.similarity" class="text-purple-600" x-text="Math.round(result.similarity * 100) + '% match'"></span>
                                </p>
                            </div>
                        </a>
                    </template>
                    <div x-show="searchResults.length === 0 && searchQuery.length >= 2 && !searching" class="px-4 py-3 text-gray-500 text-sm">
                        No results found
                    </div>
                </div>
            </div>
        </div>

        <!-- Stats Cards with loading states -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            <div class="bg-white rounded-lg shadow p-6 hover:shadow-lg transition cursor-pointer" @click="window.location='/view/teachers'">
                <div class="flex items-center">
                    <div class="p-3 rounded-full bg-blue-100 text-blue-600">
                        <i class="fas fa-chalkboard-teacher text-2xl"></i>
                    </div>
                    <div class="ml-4">
                        <p class="text-sm text-gray-500">Teachers</p>
                        <p class="text-2xl font-bold" x-show="!loading" x-text="stats.total_teachers || '0'"></p>
                        <div x-show="loading" class="h-8 w-16 bg-gray-200 animate-pulse rounded"></div>
                    </div>
                </div>
            </div>

            <div class="bg-white rounded-lg shadow p-6 hover:shadow-lg transition cursor-pointer" @click="window.location='/view/students'">
                <div class="flex items-center">
                    <div class="p-3 rounded-full bg-green-100 text-green-600">
                        <i class="fas fa-user-graduate text-2xl"></i>
                    </div>
                    <div class="ml-4">
                        <p class="text-sm text-gray-500">Students</p>
                        <p class="text-2xl font-bold" x-show="!loading" x-text="stats.total_students || '0'"></p>
                        <div x-show="loading" class="h-8 w-16 bg-gray-200 animate-pulse rounded"></div>
                    </div>
                </div>
            </div>

            <div class="bg-white rounded-lg shadow p-6 hover:shadow-lg transition cursor-pointer" @click="window.location='/view/schedules'">
                <div class="flex items-center">
                    <div class="p-3 rounded-full bg-purple-100 text-purple-600">
                        <i class="fas fa-calendar-alt text-2xl"></i>
                    </div>
                    <div class="ml-4">
                        <p class="text-sm text-gray-500">Active Assignments</p>
                        <p class="text-2xl font-bold" x-show="!loading" x-text="(stats.total_assignments || 0).toLocaleString()"></p>
                        <div x-show="loading" class="h-8 w-16 bg-gray-200 animate-pulse rounded"></div>
                    </div>
                </div>
            </div>

            <div class="bg-white rounded-lg shadow p-6 hover:shadow-lg transition cursor-pointer" @click="window.location='/view/assessments'">
                <div class="flex items-center">
                    <div class="p-3 rounded-full bg-orange-100 text-orange-600">
                        <i class="fas fa-file-alt text-2xl"></i>
                    </div>
                    <div class="ml-4">
                        <p class="text-sm text-gray-500">Assessments</p>
                        <p class="text-2xl font-bold" x-show="!loading" x-text="stats.total_assessments || '0'"></p>
                        <div x-show="loading" class="h-8 w-16 bg-gray-200 animate-pulse rounded"></div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Secondary Stats Row -->
        <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mb-8">
            <div class="bg-white rounded-lg shadow p-4 hover:shadow-lg transition cursor-pointer" @click="window.location='/view/attendance'">
                <div class="flex items-center gap-3">
                    <i class="fas fa-clipboard-check text-indigo-500"></i>
                    <div>
                        <p class="text-xs text-gray-500">Teacher Attendance</p>
                        <p class="text-lg font-bold" x-text="(stats.entity_counts?.teacher_attendance || 0).toLocaleString()"></p>
                    </div>
                </div>
            </div>
            <div class="bg-white rounded-lg shadow p-4 hover:shadow-lg transition cursor-pointer" @click="window.location='/view/attendance'">
                <div class="flex items-center gap-3">
                    <i class="fas fa-clipboard-list text-teal-500"></i>
                    <div>
                        <p class="text-xs text-gray-500">Student Attendance</p>
                        <p class="text-lg font-bold" x-text="(stats.entity_counts?.student_attendance || 0).toLocaleString()"></p>
                    </div>
                </div>
            </div>
            <div class="bg-white rounded-lg shadow p-4 hover:shadow-lg transition cursor-pointer" @click="window.location='/view/coaching'">
                <div class="flex items-center gap-3">
                    <i class="fas fa-users text-pink-500"></i>
                    <div>
                        <p class="text-xs text-gray-500">Employees</p>
                        <p class="text-lg font-bold" x-text="stats.entity_counts?.employees || '0'"></p>
                    </div>
                </div>
            </div>
            <div class="bg-white rounded-lg shadow p-4 hover:shadow-lg transition cursor-pointer" @click="window.location='/view/assessments'">
                <div class="flex items-center gap-3">
                    <i class="fas fa-microphone text-cyan-500"></i>
                    <div>
                        <p class="text-xs text-gray-500">Interviews</p>
                        <p class="text-lg font-bold" x-text="stats.entity_counts?.interviews || '0'"></p>
                    </div>
                </div>
            </div>
            <div class="bg-white rounded-lg shadow p-4 hover:shadow-lg transition cursor-pointer" @click="window.location='/view/coaching'">
                <div class="flex items-center gap-3">
                    <i class="fas fa-comments text-amber-500"></i>
                    <div>
                        <p class="text-xs text-gray-500">Coaching Records</p>
                        <p class="text-lg font-bold" x-text="stats.entity_counts?.coaching_records || '0'"></p>
                    </div>
                </div>
            </div>
            <div class="bg-white rounded-lg shadow p-4 hover:shadow-lg transition cursor-pointer" @click="window.location='/view/apps'">
                <div class="flex items-center gap-3">
                    <i class="fas fa-th-large text-violet-500"></i>
                    <div>
                        <p class="text-xs text-gray-500">Apps</p>
                        <p class="text-lg font-bold" x-text="stats.entity_counts?.apps || '0'"></p>
                    </div>
                </div>
            </div>
        </div>

        <!-- Data Sources & Export Section -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
            <!-- Connected Databases -->
            <div class="bg-white rounded-lg shadow p-6">
                <div class="flex justify-between items-center mb-4">
                    <h2 class="text-xl font-semibold">Connected Databases</h2>
                    <a href="/view/databases" class="text-blue-600 text-sm hover:underline">Browse All</a>
                </div>
                <div class="space-y-3">
                    <div class="flex items-center justify-between p-3 bg-green-50 rounded-lg">
                        <div class="flex items-center gap-3">
                            <i class="fas fa-database text-green-600"></i>
                            <span class="font-medium">PostgreSQL (Scheduling)</span>
                        </div>
                        <span class="text-green-600 text-sm"><i class="fas fa-check-circle"></i> Connected</span>
                    </div>
                    <div class="flex items-center justify-between p-3 bg-blue-50 rounded-lg">
                        <div class="flex items-center gap-3">
                            <i class="fas fa-database text-blue-600"></i>
                            <span class="font-medium">SQLite Databases (7)</span>
                        </div>
                        <span class="text-blue-600 text-sm"><i class="fas fa-check-circle"></i> Connected</span>
                    </div>
                    <div class="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                        <div class="flex items-center gap-3">
                            <i class="fab fa-notion text-gray-600"></i>
                            <span class="font-medium">Notion</span>
                        </div>
                        <span class="text-gray-500 text-sm">Optional</span>
                    </div>
                </div>
            </div>

            <!-- Quick Exports -->
            <div class="bg-white rounded-lg shadow p-6">
                <h2 class="text-xl font-semibold mb-4">Export Data</h2>
                <div class="grid grid-cols-2 gap-3">
                    <a href="/api/export/teachers?format=csv" class="flex items-center gap-2 p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition">
                        <i class="fas fa-file-csv text-green-600"></i>
                        <span class="text-sm">Teachers CSV</span>
                    </a>
                    <a href="/api/export/students?format=csv" class="flex items-center gap-2 p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition">
                        <i class="fas fa-file-csv text-green-600"></i>
                        <span class="text-sm">Students CSV</span>
                    </a>
                    <a href="/api/export/attendance?type=teacher&format=csv" class="flex items-center gap-2 p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition">
                        <i class="fas fa-file-csv text-blue-600"></i>
                        <span class="text-sm">Teacher Attendance</span>
                    </a>
                    <a href="/api/export/attendance?type=student&format=csv" class="flex items-center gap-2 p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition">
                        <i class="fas fa-file-csv text-blue-600"></i>
                        <span class="text-sm">Student Attendance</span>
                    </a>
                </div>
            </div>
        </div>

        <!-- Quick Actions -->
        <div class="grid grid-cols-1 md:grid-cols-4 gap-6">
            <a href="/view/teachers" class="bg-white rounded-lg shadow p-6 hover:shadow-lg transition border-l-4 border-blue-500">
                <h3 class="font-semibold text-lg mb-2">Browse Teachers</h3>
                <p class="text-gray-500 text-sm">View all teachers and their profiles</p>
            </a>
            <a href="/view/students" class="bg-white rounded-lg shadow p-6 hover:shadow-lg transition border-l-4 border-green-500">
                <h3 class="font-semibold text-lg mb-2">Browse Students</h3>
                <p class="text-gray-500 text-sm">View students, grades, and assessments</p>
            </a>
            <a href="/view/graph" class="bg-white rounded-lg shadow p-6 hover:shadow-lg transition border-l-4 border-purple-500">
                <h3 class="font-semibold text-lg mb-2">Knowledge Graph</h3>
                <p class="text-gray-500 text-sm">Explore entity relationships visually</p>
            </a>
            <a href="/view/sync" class="bg-white rounded-lg shadow p-6 hover:shadow-lg transition border-l-4 border-orange-500">
                <h3 class="font-semibold text-lg mb-2">Sync Data</h3>
                <p class="text-gray-500 text-sm">Update from all data sources</p>
            </a>
        </div>
    </div>

    <script>
        function dashboard() {
            return {
                stats: {},
                loading: true,
                searchQuery: '',
                searchResults: [],
                searching: false,
                searchMode: 'keyword',  // 'keyword' or 'semantic'
                vectorStatus: null,

                async loadStats() {
                    this.loading = true;
                    try {
                        const res = await fetch('/api/stats');
                        this.stats = await res.json();

                        // Also check vector status
                        const vRes = await fetch('/api/vector/status');
                        this.vectorStatus = await vRes.json();
                    } catch (e) {
                        console.error('Failed to load stats:', e);
                    }
                    this.loading = false;
                },

                async search() {
                    if (this.searchQuery.length < 2) {
                        this.searchResults = [];
                        return;
                    }
                    this.searching = true;
                    try {
                        let url;
                        if (this.searchMode === 'semantic') {
                            url = `/api/vector/search?q=${encodeURIComponent(this.searchQuery)}&limit=10`;
                        } else {
                            url = `/api/search?q=${encodeURIComponent(this.searchQuery)}&limit=10`;
                        }

                        const res = await fetch(url);
                        const data = await res.json();
                        this.searchResults = data.results || [];

                        // If semantic search returns empty and not indexed, show message
                        if (this.searchMode === 'semantic' && this.searchResults.length === 0 && data.message) {
                            console.log('Semantic search:', data.message);
                        }
                    } catch (e) {
                        console.error('Search failed:', e);
                        // Fall back to keyword search if semantic fails
                        if (this.searchMode === 'semantic') {
                            this.searchMode = 'keyword';
                            this.search();
                        }
                    }
                    this.searching = false;
                }
            }
        }
    </script>
    """
    return render_page("Dashboard", content, "dashboard")


@app.get("/view/teachers", response_class=HTMLResponse)
async def view_teachers(request: Request):
    """Teachers list view."""
    if not check_auth(request):
        return RedirectResponse(url="/login", status_code=302)
    content = """
    <div x-data="teachersPage()" x-init="loadTeachers()">
        <div class="flex justify-between items-center mb-6">
            <h1 class="text-3xl font-bold text-gray-800">Teachers</h1>
            <div class="flex gap-2">
                <input type="text" x-model="search" @input.debounce.300ms="searchTeachers()"
                    placeholder="Search teachers..."
                    class="px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                <select x-model="filter" @change="loadTeachers()" class="px-4 py-2 border rounded-lg">
                    <option value="all">All Teachers</option>
                    <option value="active">Active Only</option>
                </select>
            </div>
        </div>

        <!-- Teachers Table -->
        <div class="bg-white rounded-lg shadow overflow-hidden">
            <table class="min-w-full divide-y divide-gray-200">
                <thead class="bg-gray-50">
                    <tr>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Email</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Position</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
                    </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-200">
                    <template x-for="(teacher, idx) in teachers" :key="teacher.notion_id || teacher.id || idx">
                        <tr class="hover:bg-gray-50 cursor-pointer" @click="window.location.href='/view/teacher/' + teacher.pg_id">
                            <td class="px-6 py-4 whitespace-nowrap">
                                <div class="flex items-center">
                                    <div class="h-10 w-10 rounded-full bg-blue-100 flex items-center justify-center">
                                        <span class="text-blue-600 font-medium" x-text="(teacher.name || '?')[0].toUpperCase()"></span>
                                    </div>
                                    <div class="ml-4">
                                        <div class="font-medium text-gray-900" x-text="teacher.name || 'Unknown'"></div>
                                    </div>
                                </div>
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap text-gray-500" x-text="teacher.email || '—'"></td>
                            <td class="px-6 py-4 whitespace-nowrap text-gray-500" x-text="teacher.position || '—'"></td>
                            <td class="px-6 py-4 whitespace-nowrap">
                                <span x-show="teacher.is_active" class="px-2 py-1 text-xs rounded-full bg-green-100 text-green-800">Active</span>
                                <span x-show="!teacher.is_active" class="px-2 py-1 text-xs rounded-full bg-gray-100 text-gray-800">Inactive</span>
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap">
                                <a :href="'/view/teacher/' + teacher.pg_id" class="text-blue-600 hover:text-blue-800">
                                    <i class="fas fa-eye"></i> View Profile
                                </a>
                            </td>
                        </tr>
                    </template>
                </tbody>
            </table>

            <div x-show="teachers.length === 0" class="p-8 text-center text-gray-500">
                <i class="fas fa-users text-4xl mb-4"></i>
                <p>No teachers found. Try syncing data first.</p>
            </div>
        </div>
    </div>

    <script>
        function teachersPage() {
            return {
                teachers: [],
                search: '',
                filter: 'active',

                async loadTeachers() {
                    try {
                        const activeOnly = this.filter === 'active';
                        const res = await fetch(`/api/teachers?limit=200&active_only=${activeOnly}`);
                        const result = await res.json();
                        const teachers = result.data || result;
                        // Add pg_id for links - extract ID from the full id string
                        this.teachers = teachers.map(t => ({
                            ...t,
                            pg_id: t.notion_id || t.id?.replace('pg_teacher_', '').replace('notion_teacher_', '') || t.id
                        }));
                    } catch (e) {
                        console.error('Failed to load teachers:', e);
                    }
                },

                async searchTeachers() {
                    if (this.search.length < 2) {
                        return this.loadTeachers();
                    }
                    try {
                        const res = await fetch(`/api/search?q=${encodeURIComponent(this.search)}&entity_types=teacher`);
                        const data = await res.json();
                        this.teachers = data.results.map(r => ({...r, sources: [], pg_id: r.id.replace('pg_teacher_', '')}));
                    } catch (e) {
                        console.error('Search failed:', e);
                    }
                }
            }
        }
    </script>
    """
    return render_page("Teachers", content, "teachers")


@app.get("/view/teacher/{teacher_id}", response_class=HTMLResponse)
async def view_teacher_profile(request: Request, teacher_id: str):
    """Teacher profile view - shows all connected data across apps."""
    if not check_auth(request):
        return RedirectResponse(url="/login", status_code=302)
    content = """
    <div x-data="teacherProfile()" x-init="loadProfile()">
        <!-- Back Button -->
        <a href="/view/teachers" class="inline-flex items-center text-blue-600 hover:text-blue-800 mb-4">
            <i class="fas fa-arrow-left mr-2"></i> Back to Teachers
        </a>

        <!-- Loading State -->
        <div x-show="loading" class="text-center py-12">
            <i class="fas fa-spinner fa-spin text-4xl text-blue-500 mb-4"></i>
            <p class="text-gray-500">Loading teacher profile...</p>
        </div>

        <!-- Profile Content -->
        <div x-show="!loading && profile">
            <!-- Header Card -->
            <div class="bg-white rounded-lg shadow-lg p-6 mb-6">
                <div class="flex items-start gap-6">
                    <div class="h-24 w-24 rounded-full bg-gradient-to-br from-blue-400 to-blue-600 flex items-center justify-center flex-shrink-0">
                        <span class="text-white text-4xl font-bold" x-text="(profile.name || '?')[0].toUpperCase()"></span>
                    </div>
                    <div class="flex-grow">
                        <h1 class="text-3xl font-bold text-gray-800" x-text="profile.name"></h1>
                        <p class="text-gray-500 text-lg" x-text="profile.position || 'Teacher'"></p>
                        <div class="flex flex-wrap gap-2 mt-3">
                            <span x-show="profile.is_active" class="px-3 py-1 text-sm rounded-full bg-green-100 text-green-800">
                                <i class="fas fa-check-circle mr-1"></i> Active
                            </span>
                            <span x-show="!profile.is_active" class="px-3 py-1 text-sm rounded-full bg-gray-100 text-gray-800">
                                <i class="fas fa-times-circle mr-1"></i> Inactive
                            </span>
                            <template x-for="source in profile.data_sources || []" :key="source">
                                <span class="px-3 py-1 text-sm rounded-full bg-blue-100 text-blue-800" x-text="source"></span>
                            </template>
                        </div>
                    </div>
                    <div class="text-right">
                        <p class="text-sm text-gray-500">Teacher ID</p>
                        <p class="font-mono text-lg" x-text="profile.id"></p>
                    </div>
                </div>
            </div>

            <!-- Stats Summary -->
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                <div class="bg-white rounded-lg shadow p-4 text-center">
                    <p class="text-3xl font-bold text-blue-600" x-text="profile.students?.length || 0"></p>
                    <p class="text-sm text-gray-500">Students</p>
                </div>
                <div class="bg-white rounded-lg shadow p-4 text-center">
                    <p class="text-3xl font-bold text-green-600" x-text="profile.assignments?.length || 0"></p>
                    <p class="text-sm text-gray-500">Assignments</p>
                </div>
                <div class="bg-white rounded-lg shadow p-4 text-center">
                    <p class="text-3xl font-bold text-purple-600" x-text="profile.attendance?.length || 0"></p>
                    <p class="text-sm text-gray-500">Attendance Records</p>
                </div>
                <div class="bg-white rounded-lg shadow p-4 text-center">
                    <p class="text-3xl font-bold text-orange-600" x-text="profile.coaching?.length || 0"></p>
                    <p class="text-sm text-gray-500">Coaching Records</p>
                </div>
            </div>

            <!-- Tabbed Content -->
            <div class="bg-white rounded-lg shadow">
                <!-- Tabs -->
                <div class="border-b">
                    <nav class="flex -mb-px">
                        <button @click="activeTab = 'overview'"
                            :class="activeTab === 'overview' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'"
                            class="px-6 py-4 border-b-2 font-medium text-sm">
                            <i class="fas fa-user mr-2"></i> Overview
                        </button>
                        <button @click="activeTab = 'students'"
                            :class="activeTab === 'students' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'"
                            class="px-6 py-4 border-b-2 font-medium text-sm">
                            <i class="fas fa-user-graduate mr-2"></i> Students
                            <span class="ml-1 px-2 py-0.5 text-xs rounded-full bg-gray-100" x-text="profile.students?.length || 0"></span>
                        </button>
                        <button @click="activeTab = 'schedule'"
                            :class="activeTab === 'schedule' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'"
                            class="px-6 py-4 border-b-2 font-medium text-sm">
                            <i class="fas fa-calendar mr-2"></i> Schedule
                            <span class="ml-1 px-2 py-0.5 text-xs rounded-full bg-gray-100" x-text="profile.assignments?.length || 0"></span>
                        </button>
                        <button @click="activeTab = 'attendance'"
                            :class="activeTab === 'attendance' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'"
                            class="px-6 py-4 border-b-2 font-medium text-sm">
                            <i class="fas fa-clipboard-check mr-2"></i> Attendance
                            <span class="ml-1 px-2 py-0.5 text-xs rounded-full bg-gray-100" x-text="profile.attendance?.length || 0"></span>
                        </button>
                        <button @click="activeTab = 'coaching'"
                            :class="activeTab === 'coaching' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'"
                            class="px-6 py-4 border-b-2 font-medium text-sm">
                            <i class="fas fa-comments mr-2"></i> Coaching
                            <span class="ml-1 px-2 py-0.5 text-xs rounded-full bg-gray-100" x-text="profile.coaching?.length || 0"></span>
                        </button>
                        <button @click="activeTab = 'apps'"
                            :class="activeTab === 'apps' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'"
                            class="px-6 py-4 border-b-2 font-medium text-sm">
                            <i class="fas fa-th-large mr-2"></i> Apps
                            <span class="ml-1 px-2 py-0.5 text-xs rounded-full bg-gray-100" x-text="profile.apps?.length || 0"></span>
                        </button>
                    </nav>
                </div>

                <!-- Tab Content -->
                <div class="p-6">
                    <!-- Overview Tab -->
                    <div x-show="activeTab === 'overview'">
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <div>
                                <h3 class="font-semibold text-lg mb-4">Basic Information</h3>
                                <dl class="space-y-3">
                                    <div class="flex">
                                        <dt class="w-32 text-gray-500">Name:</dt>
                                        <dd class="font-medium" x-text="profile.name || '—'"></dd>
                                    </div>
                                    <div class="flex">
                                        <dt class="w-32 text-gray-500">Email:</dt>
                                        <dd class="font-medium" x-text="profile.email || '—'"></dd>
                                    </div>
                                    <div class="flex">
                                        <dt class="w-32 text-gray-500">Position:</dt>
                                        <dd class="font-medium" x-text="profile.position || '—'"></dd>
                                    </div>
                                    <div class="flex">
                                        <dt class="w-32 text-gray-500">Phone:</dt>
                                        <dd class="font-medium" x-text="profile.phone || '—'"></dd>
                                    </div>
                                    <div class="flex">
                                        <dt class="w-32 text-gray-500">Status:</dt>
                                        <dd>
                                            <span x-show="profile.is_active" class="text-green-600 font-medium">Active</span>
                                            <span x-show="!profile.is_active" class="text-gray-500 font-medium">Inactive</span>
                                        </dd>
                                    </div>
                                </dl>

                                <!-- Notion Data -->
                                <div x-show="profile.notion_data" class="mt-6">
                                    <h3 class="font-semibold text-lg mb-4">Notion Profile</h3>
                                    <dl class="space-y-2 text-sm">
                                        <template x-for="[key, value] in Object.entries(profile.notion_data || {}).filter(([k,v]) => v && !['notion_id','notion_url'].includes(k))" :key="key">
                                            <div class="flex">
                                                <dt class="w-32 text-gray-500" x-text="key + ':'"></dt>
                                                <dd class="font-medium" x-text="value"></dd>
                                            </div>
                                        </template>
                                    </dl>
                                </div>
                            </div>
                            <div>
                                <h3 class="font-semibold text-lg mb-4">Quick Stats</h3>
                                <div class="space-y-3">
                                    <div class="flex justify-between items-center p-3 bg-gray-50 rounded">
                                        <span class="text-gray-600">Current Students</span>
                                        <span class="font-bold" x-text="profile.students?.length || 0"></span>
                                    </div>
                                    <div class="flex justify-between items-center p-3 bg-gray-50 rounded">
                                        <span class="text-gray-600">Active Assignments</span>
                                        <span class="font-bold" x-text="profile.assignments?.length || 0"></span>
                                    </div>
                                    <div class="flex justify-between items-center p-3 bg-gray-50 rounded">
                                        <span class="text-gray-600">Attendance Rate</span>
                                        <span class="font-bold" x-text="calculateAttendanceRate()"></span>
                                    </div>
                                    <div class="flex justify-between items-center p-3 bg-gray-50 rounded">
                                        <span class="text-gray-600">Published Apps</span>
                                        <span class="font-bold" x-text="profile.apps?.length || 0"></span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Students Tab -->
                    <div x-show="activeTab === 'students'">
                        <h3 class="font-semibold text-lg mb-4">Students Taught</h3>
                        <div x-show="!profile.students?.length" class="text-center py-8 text-gray-500">
                            <i class="fas fa-user-graduate text-4xl mb-4"></i>
                            <p>No students assigned</p>
                        </div>
                        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                            <template x-for="student in profile.students || []" :key="student.id">
                                <a :href="'/view/student/' + student.id" class="block p-4 border rounded-lg hover:shadow-md transition">
                                    <div class="flex items-center gap-3">
                                        <div class="h-10 w-10 rounded-full bg-green-100 flex items-center justify-center">
                                            <span class="text-green-600 font-medium" x-text="(student.name || '?')[0].toUpperCase()"></span>
                                        </div>
                                        <div>
                                            <p class="font-medium" x-text="student.name"></p>
                                            <p class="text-sm text-gray-500">
                                                <span x-text="'Grade ' + (student.grade || '—')"></span>
                                                <span x-show="student.school"> • <span x-text="student.school"></span></span>
                                            </p>
                                        </div>
                                    </div>
                                </a>
                            </template>
                        </div>
                    </div>

                    <!-- Schedule Tab -->
                    <div x-show="activeTab === 'schedule'">
                        <h3 class="font-semibold text-lg mb-4">Class Assignments</h3>
                        <div x-show="!profile.assignments?.length" class="text-center py-8 text-gray-500">
                            <i class="fas fa-calendar text-4xl mb-4"></i>
                            <p>No assignments found</p>
                        </div>
                        <div class="overflow-x-auto">
                            <table x-show="profile.assignments?.length" class="min-w-full divide-y divide-gray-200">
                                <thead class="bg-gray-50">
                                    <tr>
                                        <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                                        <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Time Slot</th>
                                        <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Room</th>
                                        <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Students</th>
                                        <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Notes</th>
                                    </tr>
                                </thead>
                                <tbody class="bg-white divide-y divide-gray-200">
                                    <template x-for="assignment in profile.assignments || []" :key="assignment.id">
                                        <tr class="hover:bg-gray-50">
                                            <td class="px-4 py-3 whitespace-nowrap" x-text="assignment.date"></td>
                                            <td class="px-4 py-3 whitespace-nowrap" x-text="assignment.time_slot || '—'"></td>
                                            <td class="px-4 py-3 whitespace-nowrap" x-text="assignment.room || '—'"></td>
                                            <td class="px-4 py-3" x-text="assignment.student_count + ' students'"></td>
                                            <td class="px-4 py-3 text-gray-500 max-w-xs truncate" x-text="assignment.notes || '—'"></td>
                                        </tr>
                                    </template>
                                </tbody>
                            </table>
                        </div>
                    </div>

                    <!-- Attendance Tab -->
                    <div x-show="activeTab === 'attendance'">
                        <h3 class="font-semibold text-lg mb-4">Attendance History</h3>
                        <div x-show="!profile.attendance?.length" class="text-center py-8 text-gray-500">
                            <i class="fas fa-clipboard-check text-4xl mb-4"></i>
                            <p>No attendance records found</p>
                        </div>
                        <div class="overflow-x-auto">
                            <table x-show="profile.attendance?.length" class="min-w-full divide-y divide-gray-200">
                                <thead class="bg-gray-50">
                                    <tr>
                                        <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                                        <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                                        <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Time In</th>
                                        <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Minutes Late</th>
                                        <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Reason</th>
                                    </tr>
                                </thead>
                                <tbody class="bg-white divide-y divide-gray-200">
                                    <template x-for="record in profile.attendance || []" :key="record.id">
                                        <tr class="hover:bg-gray-50">
                                            <td class="px-4 py-3 whitespace-nowrap" x-text="record.date"></td>
                                            <td class="px-4 py-3 whitespace-nowrap">
                                                <span class="px-2 py-1 text-xs rounded-full"
                                                    :class="{
                                                        'bg-green-100 text-green-800': record.status === 'present',
                                                        'bg-yellow-100 text-yellow-800': record.status === 'late',
                                                        'bg-red-100 text-red-800': record.status === 'absent'
                                                    }"
                                                    x-text="record.status"></span>
                                            </td>
                                            <td class="px-4 py-3 whitespace-nowrap" x-text="record.start_time || '—'"></td>
                                            <td class="px-4 py-3 whitespace-nowrap" x-text="record.minutes_late || '—'"></td>
                                            <td class="px-4 py-3 text-gray-500 max-w-xs truncate" x-text="record.late_reason || record.absent_reason || '—'"></td>
                                        </tr>
                                    </template>
                                </tbody>
                            </table>
                        </div>
                    </div>

                    <!-- Coaching Tab -->
                    <div x-show="activeTab === 'coaching'">
                        <h3 class="font-semibold text-lg mb-4">Coaching Records</h3>
                        <div x-show="!profile.coaching?.length" class="text-center py-8 text-gray-500">
                            <i class="fas fa-comments text-4xl mb-4"></i>
                            <p>No coaching records found</p>
                        </div>
                        <div class="space-y-4">
                            <template x-for="record in profile.coaching || []" :key="record.id">
                                <div class="border rounded-lg p-4">
                                    <div class="flex justify-between items-start mb-2">
                                        <div>
                                            <span class="px-2 py-1 text-xs rounded-full mr-2"
                                                :class="{
                                                    'bg-yellow-100 text-yellow-800': record.coaching_type === 'verbal',
                                                    'bg-orange-100 text-orange-800': record.coaching_type === 'written',
                                                    'bg-red-100 text-red-800': record.coaching_type === 'final'
                                                }"
                                                x-text="record.coaching_type"></span>
                                            <span class="font-medium" x-text="record.offense_name || 'Unspecified'"></span>
                                        </div>
                                        <span class="text-sm text-gray-500" x-text="record.date"></span>
                                    </div>
                                    <p class="text-gray-600 text-sm" x-text="record.issue_description || 'No description provided'"></p>
                                    <div class="mt-2 flex items-center gap-4 text-sm">
                                        <span :class="record.employee_acknowledged ? 'text-green-600' : 'text-gray-400'">
                                            <i class="fas" :class="record.employee_acknowledged ? 'fa-check-circle' : 'fa-clock'"></i>
                                            <span x-text="record.employee_acknowledged ? 'Acknowledged' : 'Pending Acknowledgement'"></span>
                                        </span>
                                    </div>
                                </div>
                            </template>
                        </div>
                    </div>

                    <!-- Apps Tab -->
                    <div x-show="activeTab === 'apps'">
                        <h3 class="font-semibold text-lg mb-4">Published Educational Apps</h3>
                        <div x-show="!profile.apps?.length" class="text-center py-8 text-gray-500">
                            <i class="fas fa-th-large text-4xl mb-4"></i>
                            <p>No apps published</p>
                        </div>
                        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                            <template x-for="app in profile.apps || []" :key="app.id">
                                <div class="border rounded-lg p-4 hover:shadow-md transition">
                                    <h4 class="font-semibold" x-text="app.title"></h4>
                                    <p class="text-sm text-gray-500 mt-1 line-clamp-2" x-text="app.description"></p>
                                    <div class="flex flex-wrap gap-1 mt-2">
                                        <span class="px-2 py-0.5 text-xs rounded bg-blue-100 text-blue-800" x-text="app.category"></span>
                                        <span class="px-2 py-0.5 text-xs rounded bg-green-100 text-green-800" x-text="app.student_levels"></span>
                                    </div>
                                    <a x-show="app.app_link" :href="app.app_link" target="_blank"
                                        class="inline-block mt-3 text-sm text-blue-600 hover:text-blue-800">
                                        Open App <i class="fas fa-external-link-alt ml-1"></i>
                                    </a>
                                </div>
                            </template>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Not Found State -->
        <div x-show="!loading && !profile" class="text-center py-12">
            <i class="fas fa-user-slash text-4xl text-gray-400 mb-4"></i>
            <p class="text-gray-500">Teacher not found</p>
            <a href="/view/teachers" class="text-blue-600 hover:text-blue-800 mt-2 inline-block">
                Back to Teachers List
            </a>
        </div>
    </div>

    <script>
        function teacherProfile() {
            return {
                profile: null,
                loading: true,
                activeTab: 'overview',
                teacherId: window.location.pathname.split('/').pop(),

                async loadProfile() {
                    try {
                        const res = await fetch(`/api/teachers/${this.teacherId}/profile`);
                        if (res.ok) {
                            this.profile = await res.json();
                        }
                    } catch (e) {
                        console.error('Failed to load profile:', e);
                    } finally {
                        this.loading = false;
                    }
                },

                calculateAttendanceRate() {
                    if (!this.profile?.attendance?.length) return '—';
                    const present = this.profile.attendance.filter(a => a.status === 'present').length;
                    const total = this.profile.attendance.length;
                    return Math.round((present / total) * 100) + '%';
                }
            }
        }
    </script>
    """
    return render_page("Teacher Profile", content, "teachers")


@app.get("/view/students", response_class=HTMLResponse)
async def view_students(request: Request):
    """Students list view."""
    if not check_auth(request):
        return RedirectResponse(url="/login", status_code=302)
    content = """
    <div x-data="studentsPage()" x-init="loadStudents()">
        <div class="flex justify-between items-center mb-6">
            <h1 class="text-3xl font-bold text-gray-800">Students</h1>
            <div class="flex gap-2">
                <input type="text" x-model="search" @input.debounce.300ms="searchStudents()"
                    placeholder="Search students..."
                    class="px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                <select x-model="gradeFilter" @change="loadStudents()" class="px-4 py-2 border rounded-lg">
                    <option value="">All Grades</option>
                    <option value="1">Grade 1</option>
                    <option value="2">Grade 2</option>
                    <option value="3">Grade 3</option>
                    <option value="4">Grade 4</option>
                    <option value="5">Grade 5</option>
                    <option value="6">Grade 6</option>
                    <option value="7">Grade 7</option>
                    <option value="8">Grade 8</option>
                    <option value="9">Grade 9</option>
                    <option value="10">Grade 10</option>
                    <option value="11">Grade 11</option>
                    <option value="12">Grade 12</option>
                </select>
            </div>
        </div>

        <!-- Students Grid -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            <template x-for="student in students" :key="student.id">
                <a :href="'/view/student/' + student.pg_id" class="block bg-white rounded-lg shadow p-6 hover:shadow-lg transition">
                    <div class="flex items-center mb-4">
                        <div class="h-12 w-12 rounded-full bg-green-100 flex items-center justify-center">
                            <span class="text-green-600 font-bold text-lg" x-text="(student.name || '?')[0].toUpperCase()"></span>
                        </div>
                        <div class="ml-4">
                            <h3 class="font-semibold text-gray-900" x-text="student.name || 'Unknown'"></h3>
                            <p class="text-sm text-gray-500" x-text="'ID: ' + (student.student_id || '—')"></p>
                        </div>
                    </div>
                    <div class="grid grid-cols-2 gap-2 text-sm">
                        <div>
                            <span class="text-gray-500">Grade:</span>
                            <span class="font-medium ml-1" x-text="student.grade || '—'"></span>
                        </div>
                        <div>
                            <span class="text-gray-500">School:</span>
                            <span class="font-medium ml-1" x-text="student.school || '—'"></span>
                        </div>
                    </div>
                    <div class="mt-3 text-blue-600 text-sm">
                        <i class="fas fa-eye mr-1"></i> View Profile
                    </div>
                </a>
            </template>
        </div>

        <div x-show="students.length === 0" class="bg-white rounded-lg shadow p-8 text-center text-gray-500">
            <i class="fas fa-user-graduate text-4xl mb-4"></i>
            <p>No students found. Try syncing data first.</p>
        </div>
    </div>

    <script>
        function studentsPage() {
            return {
                students: [],
                search: '',
                gradeFilter: '',

                async loadStudents() {
                    try {
                        let url = '/api/students?limit=200&active_only=true';
                        if (this.gradeFilter) url += `&grade=${this.gradeFilter}`;
                        const res = await fetch(url);
                        const result = await res.json();
                        this.students = result.data || result;
                    } catch (e) {
                        console.error('Failed to load students:', e);
                    }
                },

                async searchStudents() {
                    if (this.search.length < 2) {
                        return this.loadStudents();
                    }
                    try {
                        const res = await fetch(`/api/search?q=${encodeURIComponent(this.search)}&entity_types=student`);
                        const data = await res.json();
                        this.students = data.results.map(r => ({...r, sources: [], pg_id: r.id.replace('pg_student_', '')}));
                    } catch (e) {
                        console.error('Search failed:', e);
                    }
                }
            }
        }
    </script>
    """
    return render_page("Students", content, "students")


@app.get("/view/student/{student_id}", response_class=HTMLResponse)
async def view_student_profile(request: Request, student_id: int):
    """Student profile view - shows all connected data across apps."""
    if not check_auth(request):
        return RedirectResponse(url="/login", status_code=302)
    content = """
    <div x-data="studentProfile()" x-init="loadProfile()">
        <!-- Back Button -->
        <a href="/view/students" class="inline-flex items-center text-blue-600 hover:text-blue-800 mb-4">
            <i class="fas fa-arrow-left mr-2"></i> Back to Students
        </a>

        <!-- Loading State -->
        <div x-show="loading" class="text-center py-12">
            <i class="fas fa-spinner fa-spin text-4xl text-green-500 mb-4"></i>
            <p class="text-gray-500">Loading student profile...</p>
        </div>

        <!-- Profile Content -->
        <div x-show="!loading && profile">
            <!-- Header Card -->
            <div class="bg-white rounded-lg shadow-lg p-6 mb-6">
                <div class="flex items-start gap-6">
                    <div class="h-24 w-24 rounded-full bg-gradient-to-br from-green-400 to-green-600 flex items-center justify-center flex-shrink-0">
                        <span class="text-white text-4xl font-bold" x-text="(profile.name || '?')[0].toUpperCase()"></span>
                    </div>
                    <div class="flex-grow">
                        <h1 class="text-3xl font-bold text-gray-800" x-text="profile.name"></h1>
                        <p class="text-gray-500 text-lg">Student ID: <span x-text="profile.student_id || '—'"></span></p>
                        <div class="flex flex-wrap gap-2 mt-3">
                            <span x-show="profile.is_active" class="px-3 py-1 text-sm rounded-full bg-green-100 text-green-800">
                                <i class="fas fa-check-circle mr-1"></i> Active
                            </span>
                            <span x-show="!profile.is_active" class="px-3 py-1 text-sm rounded-full bg-gray-100 text-gray-800">
                                <i class="fas fa-times-circle mr-1"></i> Inactive
                            </span>
                            <span class="px-3 py-1 text-sm rounded-full bg-blue-100 text-blue-800" x-text="'Grade ' + (profile.grade || '—')"></span>
                            <template x-for="source in profile.data_sources || []" :key="source">
                                <span class="px-3 py-1 text-sm rounded-full bg-purple-100 text-purple-800" x-text="source"></span>
                            </template>
                        </div>
                    </div>
                    <div class="text-right">
                        <p class="text-sm text-gray-500">School</p>
                        <p class="font-medium text-lg" x-text="profile.school || '—'"></p>
                    </div>
                </div>
            </div>

            <!-- Stats Summary -->
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                <div class="bg-white rounded-lg shadow p-4 text-center">
                    <p class="text-3xl font-bold text-blue-600" x-text="profile.teachers?.length || 0"></p>
                    <p class="text-sm text-gray-500">Teachers</p>
                </div>
                <div class="bg-white rounded-lg shadow p-4 text-center">
                    <p class="text-3xl font-bold text-green-600" x-text="profile.assignments?.length || 0"></p>
                    <p class="text-sm text-gray-500">Classes</p>
                </div>
                <div class="bg-white rounded-lg shadow p-4 text-center">
                    <p class="text-3xl font-bold text-purple-600" x-text="profile.attendance?.length || 0"></p>
                    <p class="text-sm text-gray-500">Attendance Records</p>
                </div>
                <div class="bg-white rounded-lg shadow p-4 text-center">
                    <p class="text-3xl font-bold text-orange-600" x-text="(profile.interviews?.length || 0) + (profile.reports?.length || 0)"></p>
                    <p class="text-sm text-gray-500">Assessments</p>
                </div>
            </div>

            <!-- Tabbed Content -->
            <div class="bg-white rounded-lg shadow">
                <!-- Tabs -->
                <div class="border-b">
                    <nav class="flex -mb-px overflow-x-auto">
                        <button @click="activeTab = 'overview'"
                            :class="activeTab === 'overview' ? 'border-green-500 text-green-600' : 'border-transparent text-gray-500 hover:text-gray-700'"
                            class="px-6 py-4 border-b-2 font-medium text-sm whitespace-nowrap">
                            <i class="fas fa-user mr-2"></i> Overview
                        </button>
                        <button @click="activeTab = 'teachers'"
                            :class="activeTab === 'teachers' ? 'border-green-500 text-green-600' : 'border-transparent text-gray-500 hover:text-gray-700'"
                            class="px-6 py-4 border-b-2 font-medium text-sm whitespace-nowrap">
                            <i class="fas fa-chalkboard-teacher mr-2"></i> Teachers
                            <span class="ml-1 px-2 py-0.5 text-xs rounded-full bg-gray-100" x-text="profile.teachers?.length || 0"></span>
                        </button>
                        <button @click="activeTab = 'schedule'"
                            :class="activeTab === 'schedule' ? 'border-green-500 text-green-600' : 'border-transparent text-gray-500 hover:text-gray-700'"
                            class="px-6 py-4 border-b-2 font-medium text-sm whitespace-nowrap">
                            <i class="fas fa-calendar mr-2"></i> Schedule
                            <span class="ml-1 px-2 py-0.5 text-xs rounded-full bg-gray-100" x-text="profile.assignments?.length || 0"></span>
                        </button>
                        <button @click="activeTab = 'attendance'"
                            :class="activeTab === 'attendance' ? 'border-green-500 text-green-600' : 'border-transparent text-gray-500 hover:text-gray-700'"
                            class="px-6 py-4 border-b-2 font-medium text-sm whitespace-nowrap">
                            <i class="fas fa-clipboard-check mr-2"></i> Attendance
                            <span class="ml-1 px-2 py-0.5 text-xs rounded-full bg-gray-100" x-text="profile.attendance?.length || 0"></span>
                        </button>
                        <button @click="activeTab = 'interviews'"
                            :class="activeTab === 'interviews' ? 'border-green-500 text-green-600' : 'border-transparent text-gray-500 hover:text-gray-700'"
                            class="px-6 py-4 border-b-2 font-medium text-sm whitespace-nowrap">
                            <i class="fas fa-comments mr-2"></i> Interviews
                            <span class="ml-1 px-2 py-0.5 text-xs rounded-full bg-gray-100" x-text="profile.interviews?.length || 0"></span>
                        </button>
                        <button @click="activeTab = 'reports'"
                            :class="activeTab === 'reports' ? 'border-green-500 text-green-600' : 'border-transparent text-gray-500 hover:text-gray-700'"
                            class="px-6 py-4 border-b-2 font-medium text-sm whitespace-nowrap">
                            <i class="fas fa-file-alt mr-2"></i> Reports
                            <span class="ml-1 px-2 py-0.5 text-xs rounded-full bg-gray-100" x-text="profile.reports?.length || 0"></span>
                        </button>
                    </nav>
                </div>

                <!-- Tab Content -->
                <div class="p-6">
                    <!-- Overview Tab -->
                    <div x-show="activeTab === 'overview'">
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <div>
                                <h3 class="font-semibold text-lg mb-4">Basic Information</h3>
                                <dl class="space-y-3">
                                    <div class="flex">
                                        <dt class="w-32 text-gray-500">Name:</dt>
                                        <dd class="font-medium" x-text="profile.name || '—'"></dd>
                                    </div>
                                    <div class="flex">
                                        <dt class="w-32 text-gray-500">Student ID:</dt>
                                        <dd class="font-medium" x-text="profile.student_id || '—'"></dd>
                                    </div>
                                    <div class="flex">
                                        <dt class="w-32 text-gray-500">Grade:</dt>
                                        <dd class="font-medium" x-text="profile.grade || '—'"></dd>
                                    </div>
                                    <div class="flex">
                                        <dt class="w-32 text-gray-500">School:</dt>
                                        <dd class="font-medium" x-text="profile.school || '—'"></dd>
                                    </div>
                                    <div class="flex">
                                        <dt class="w-32 text-gray-500">Status:</dt>
                                        <dd>
                                            <span x-show="profile.is_active" class="text-green-600 font-medium">Active</span>
                                            <span x-show="!profile.is_active" class="text-gray-500 font-medium">Inactive</span>
                                        </dd>
                                    </div>
                                </dl>
                            </div>
                            <div>
                                <h3 class="font-semibold text-lg mb-4">Quick Stats</h3>
                                <div class="space-y-3">
                                    <div class="flex justify-between items-center p-3 bg-gray-50 rounded">
                                        <span class="text-gray-600">Assigned Teachers</span>
                                        <span class="font-bold" x-text="profile.teachers?.length || 0"></span>
                                    </div>
                                    <div class="flex justify-between items-center p-3 bg-gray-50 rounded">
                                        <span class="text-gray-600">Scheduled Classes</span>
                                        <span class="font-bold" x-text="profile.assignments?.length || 0"></span>
                                    </div>
                                    <div class="flex justify-between items-center p-3 bg-gray-50 rounded">
                                        <span class="text-gray-600">Attendance Rate</span>
                                        <span class="font-bold" x-text="calculateAttendanceRate()"></span>
                                    </div>
                                    <div class="flex justify-between items-center p-3 bg-gray-50 rounded">
                                        <span class="text-gray-600">Total Assessments</span>
                                        <span class="font-bold" x-text="(profile.interviews?.length || 0) + (profile.reports?.length || 0)"></span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Teachers Tab -->
                    <div x-show="activeTab === 'teachers'">
                        <h3 class="font-semibold text-lg mb-4">Assigned Teachers</h3>
                        <div x-show="!profile.teachers?.length" class="text-center py-8 text-gray-500">
                            <i class="fas fa-chalkboard-teacher text-4xl mb-4"></i>
                            <p>No teachers assigned</p>
                        </div>
                        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                            <template x-for="teacher in profile.teachers || []" :key="teacher.id">
                                <a :href="'/view/teacher/' + teacher.id" class="block p-4 border rounded-lg hover:shadow-md transition">
                                    <div class="flex items-center gap-3">
                                        <div class="h-10 w-10 rounded-full bg-blue-100 flex items-center justify-center">
                                            <span class="text-blue-600 font-medium" x-text="(teacher.name || '?')[0].toUpperCase()"></span>
                                        </div>
                                        <div>
                                            <p class="font-medium" x-text="teacher.name"></p>
                                            <p class="text-sm text-gray-500" x-text="teacher.position || 'Teacher'"></p>
                                        </div>
                                    </div>
                                </a>
                            </template>
                        </div>
                    </div>

                    <!-- Schedule Tab -->
                    <div x-show="activeTab === 'schedule'">
                        <h3 class="font-semibold text-lg mb-4">Class Schedule</h3>
                        <div x-show="!profile.assignments?.length" class="text-center py-8 text-gray-500">
                            <i class="fas fa-calendar text-4xl mb-4"></i>
                            <p>No classes scheduled</p>
                        </div>
                        <div class="overflow-x-auto">
                            <table x-show="profile.assignments?.length" class="min-w-full divide-y divide-gray-200">
                                <thead class="bg-gray-50">
                                    <tr>
                                        <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                                        <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Time Slot</th>
                                        <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Room</th>
                                        <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Teacher</th>
                                        <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Notes</th>
                                    </tr>
                                </thead>
                                <tbody class="bg-white divide-y divide-gray-200">
                                    <template x-for="assignment in profile.assignments || []" :key="assignment.id">
                                        <tr class="hover:bg-gray-50">
                                            <td class="px-4 py-3 whitespace-nowrap" x-text="assignment.date"></td>
                                            <td class="px-4 py-3 whitespace-nowrap" x-text="assignment.time_slot || '—'"></td>
                                            <td class="px-4 py-3 whitespace-nowrap" x-text="assignment.room || '—'"></td>
                                            <td class="px-4 py-3" x-text="assignment.teacher_names || '—'"></td>
                                            <td class="px-4 py-3 text-gray-500 max-w-xs truncate" x-text="assignment.notes || '—'"></td>
                                        </tr>
                                    </template>
                                </tbody>
                            </table>
                        </div>
                    </div>

                    <!-- Attendance Tab -->
                    <div x-show="activeTab === 'attendance'">
                        <h3 class="font-semibold text-lg mb-4">Attendance History</h3>
                        <div x-show="!profile.attendance?.length" class="text-center py-8 text-gray-500">
                            <i class="fas fa-clipboard-check text-4xl mb-4"></i>
                            <p>No attendance records found</p>
                        </div>
                        <div class="overflow-x-auto">
                            <table x-show="profile.attendance?.length" class="min-w-full divide-y divide-gray-200">
                                <thead class="bg-gray-50">
                                    <tr>
                                        <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                                        <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                                        <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Time In</th>
                                        <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Reason</th>
                                    </tr>
                                </thead>
                                <tbody class="bg-white divide-y divide-gray-200">
                                    <template x-for="record in profile.attendance || []" :key="record.id">
                                        <tr class="hover:bg-gray-50">
                                            <td class="px-4 py-3 whitespace-nowrap" x-text="record.date"></td>
                                            <td class="px-4 py-3 whitespace-nowrap">
                                                <span class="px-2 py-1 text-xs rounded-full"
                                                    :class="{
                                                        'bg-green-100 text-green-800': record.status === 'present',
                                                        'bg-yellow-100 text-yellow-800': record.status === 'late',
                                                        'bg-red-100 text-red-800': record.status === 'absent'
                                                    }"
                                                    x-text="record.status"></span>
                                            </td>
                                            <td class="px-4 py-3 whitespace-nowrap" x-text="record.time_in || '—'"></td>
                                            <td class="px-4 py-3 text-gray-500 max-w-xs truncate" x-text="record.reason || '—'"></td>
                                        </tr>
                                    </template>
                                </tbody>
                            </table>
                        </div>
                    </div>

                    <!-- Interviews Tab -->
                    <div x-show="activeTab === 'interviews'">
                        <h3 class="font-semibold text-lg mb-4">Interview Assessments</h3>
                        <div x-show="!profile.interviews?.length" class="text-center py-8 text-gray-500">
                            <i class="fas fa-comments text-4xl mb-4"></i>
                            <p>No interview records found</p>
                        </div>
                        <div class="space-y-4">
                            <template x-for="interview in profile.interviews || []" :key="interview.id">
                                <div class="border rounded-lg p-4">
                                    <div class="flex justify-between items-start mb-2">
                                        <span class="font-medium">Interview Assessment</span>
                                        <span class="text-sm text-gray-500" x-text="interview.date"></span>
                                    </div>
                                    <p class="text-gray-600 text-sm" x-text="interview.notes || 'No notes'"></p>
                                    <div class="mt-2 text-sm text-gray-500">
                                        <span>Assessor: <span x-text="interview.assessor_name || '—'"></span></span>
                                    </div>
                                </div>
                            </template>
                        </div>
                    </div>

                    <!-- Reports Tab -->
                    <div x-show="activeTab === 'reports'">
                        <h3 class="font-semibold text-lg mb-4">Progress Reports</h3>
                        <div x-show="!profile.reports?.length" class="text-center py-8 text-gray-500">
                            <i class="fas fa-file-alt text-4xl mb-4"></i>
                            <p>No reports found</p>
                        </div>
                        <div class="space-y-4">
                            <template x-for="report in profile.reports || []" :key="report.id">
                                <div class="border rounded-lg p-4">
                                    <div class="flex justify-between items-start mb-2">
                                        <span class="font-medium">Progress Report</span>
                                        <span class="text-sm text-gray-500" x-text="report.date"></span>
                                    </div>
                                    <p class="text-gray-600 text-sm" x-text="report.notes || 'No notes'"></p>
                                    <div class="mt-2 text-sm text-gray-500">
                                        <span>Teacher: <span x-text="report.teacher_name || '—'"></span></span>
                                    </div>
                                </div>
                            </template>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Not Found State -->
        <div x-show="!loading && !profile" class="text-center py-12">
            <i class="fas fa-user-slash text-4xl text-gray-400 mb-4"></i>
            <p class="text-gray-500">Student not found</p>
            <a href="/view/students" class="text-blue-600 hover:text-blue-800 mt-2 inline-block">
                Back to Students List
            </a>
        </div>
    </div>

    <script>
        function studentProfile() {
            return {
                profile: null,
                loading: true,
                activeTab: 'overview',
                studentId: window.location.pathname.split('/').pop(),

                async loadProfile() {
                    try {
                        const res = await fetch(`/api/students/${this.studentId}/profile`);
                        if (res.ok) {
                            this.profile = await res.json();
                        }
                    } catch (e) {
                        console.error('Failed to load profile:', e);
                    } finally {
                        this.loading = false;
                    }
                },

                calculateAttendanceRate() {
                    if (!this.profile?.attendance?.length) return '—';
                    const present = this.profile.attendance.filter(a => a.status === 'present').length;
                    const total = this.profile.attendance.length;
                    return Math.round((present / total) * 100) + '%';
                }
            }
        }
    </script>
    """
    return render_page("Student Profile", content, "students")


@app.get("/view/attendance", response_class=HTMLResponse)
async def view_attendance(request: Request):
    """Attendance view."""
    if not check_auth(request):
        return RedirectResponse(url="/login", status_code=302)
    content = """
    <div x-data="attendancePage()" x-init="loadAttendance()">
        <div class="flex justify-between items-center mb-6">
            <h1 class="text-3xl font-bold text-gray-800">Attendance Records</h1>
            <div class="flex gap-2">
                <select x-model="type" @change="loadAttendance()" class="px-4 py-2 border rounded-lg">
                    <option value="teacher">Teacher Attendance</option>
                    <option value="student">Student Attendance</option>
                </select>
                <input type="date" x-model="date" @change="loadAttendance()" class="px-4 py-2 border rounded-lg">
            </div>
        </div>

        <!-- Stats Summary -->
        <div class="grid grid-cols-4 gap-4 mb-6">
            <div class="bg-white rounded-lg shadow p-4">
                <p class="text-sm text-gray-500">Total Records</p>
                <p class="text-2xl font-bold" x-text="records.length"></p>
            </div>
            <div class="bg-green-50 rounded-lg shadow p-4">
                <p class="text-sm text-green-600">Present</p>
                <p class="text-2xl font-bold text-green-700" x-text="records.filter(r => r.status === 'present').length"></p>
            </div>
            <div class="bg-yellow-50 rounded-lg shadow p-4">
                <p class="text-sm text-yellow-600">Late</p>
                <p class="text-2xl font-bold text-yellow-700" x-text="records.filter(r => r.status === 'late').length"></p>
            </div>
            <div class="bg-red-50 rounded-lg shadow p-4">
                <p class="text-sm text-red-600">Absent</p>
                <p class="text-2xl font-bold text-red-700" x-text="records.filter(r => r.status === 'absent').length"></p>
            </div>
        </div>

        <!-- Attendance Table -->
        <div class="bg-white rounded-lg shadow overflow-hidden">
            <table class="min-w-full divide-y divide-gray-200">
                <thead class="bg-gray-50">
                    <tr>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Time In</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Minutes Late</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Reason</th>
                    </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-200">
                    <template x-for="record in records" :key="record.id">
                        <tr class="hover:bg-gray-50">
                            <td class="px-6 py-4 whitespace-nowrap font-medium" x-text="record.name || record.teacher_name || record.student_name || '—'"></td>
                            <td class="px-6 py-4 whitespace-nowrap text-gray-500" x-text="record.date || '—'"></td>
                            <td class="px-6 py-4 whitespace-nowrap">
                                <span class="px-2 py-1 text-xs rounded-full"
                                    :class="{
                                        'bg-green-100 text-green-800': record.status === 'present',
                                        'bg-yellow-100 text-yellow-800': record.status === 'late',
                                        'bg-red-100 text-red-800': record.status === 'absent'
                                    }"
                                    x-text="record.status || '—'"></span>
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap text-gray-500" x-text="record.start_time || '—'"></td>
                            <td class="px-6 py-4 whitespace-nowrap text-gray-500" x-text="record.minutes_late || '—'"></td>
                            <td class="px-6 py-4 text-gray-500 max-w-xs truncate" x-text="record.late_reason || record.absent_reason || '—'"></td>
                        </tr>
                    </template>
                </tbody>
            </table>

            <div x-show="records.length === 0" class="p-8 text-center text-gray-500">
                <i class="fas fa-clipboard-check text-4xl mb-4"></i>
                <p>No attendance records found.</p>
            </div>
        </div>
    </div>

    <script>
        function attendancePage() {
            return {
                records: [],
                type: 'teacher',
                date: new Date().toISOString().split('T')[0],

                async loadAttendance() {
                    try {
                        const res = await fetch(`/api/attendance?type=${this.type}&date=${this.date}&limit=100`);
                        this.records = await res.json();
                    } catch (e) {
                        console.error('Failed to load attendance:', e);
                        this.records = [];
                    }
                }
            }
        }
    </script>
    """
    return render_page("Attendance", content, "attendance")


@app.get("/view/assessments", response_class=HTMLResponse)
async def view_assessments(request: Request):
    """Assessments view."""
    if not check_auth(request):
        return RedirectResponse(url="/login", status_code=302)
    content = """
    <div x-data="assessmentsPage()" x-init="loadAssessments()">
        <div class="flex justify-between items-center mb-6">
            <h1 class="text-3xl font-bold text-gray-800">Assessments</h1>
            <div class="flex gap-2">
                <select x-model="type" @change="loadAssessments()" class="px-4 py-2 border rounded-lg">
                    <option value="all">All Types</option>
                    <option value="demo">Demo Assessments</option>
                    <option value="interview">Interviews</option>
                    <option value="report">Student Reports</option>
                </select>
            </div>
        </div>

        <!-- Assessments Grid -->
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            <template x-for="assessment in assessments" :key="assessment.id">
                <div class="bg-white rounded-lg shadow p-6">
                    <div class="flex justify-between items-start mb-4">
                        <div>
                            <span class="px-2 py-1 text-xs rounded-full bg-blue-100 text-blue-800" x-text="assessment.type"></span>
                            <h3 class="font-semibold mt-2" x-text="assessment.name || assessment.applicant_name || assessment.student_name || 'Unknown'"></h3>
                        </div>
                        <span class="text-sm text-gray-500" x-text="assessment.date"></span>
                    </div>

                    <div class="space-y-2 text-sm">
                        <div x-show="assessment.score">
                            <span class="text-gray-500">Score:</span>
                            <span class="font-medium ml-1" x-text="assessment.score"></span>
                        </div>
                        <div x-show="assessment.result">
                            <span class="text-gray-500">Result:</span>
                            <span class="font-medium ml-1 px-2 py-0.5 rounded"
                                :class="assessment.result === 'pass' || assessment.result === 'Hire' ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'"
                                x-text="assessment.result"></span>
                        </div>
                        <div x-show="assessment.assessor">
                            <span class="text-gray-500">Assessor:</span>
                            <span class="font-medium ml-1" x-text="assessment.assessor"></span>
                        </div>
                    </div>

                    <div x-show="assessment.feedback" class="mt-4 pt-4 border-t">
                        <p class="text-sm text-gray-500">Feedback</p>
                        <p class="text-sm mt-1 line-clamp-3" x-text="assessment.feedback"></p>
                    </div>
                </div>
            </template>
        </div>

        <div x-show="assessments.length === 0" class="bg-white rounded-lg shadow p-8 text-center text-gray-500">
            <i class="fas fa-file-alt text-4xl mb-4"></i>
            <p>No assessments found.</p>
        </div>
    </div>

    <script>
        function assessmentsPage() {
            return {
                assessments: [],
                type: 'all',

                async loadAssessments() {
                    try {
                        const res = await fetch(`/api/assessments?type=${this.type}&limit=50`);
                        this.assessments = await res.json();
                    } catch (e) {
                        console.error('Failed to load assessments:', e);
                        this.assessments = [];
                    }
                }
            }
        }
    </script>
    """
    return render_page("Assessments", content, "assessments")


@app.get("/view/sync", response_class=HTMLResponse)
async def view_sync(request: Request):
    """Data sync view."""
    if not check_auth(request):
        return RedirectResponse(url="/login", status_code=302)
    content = """
    <div x-data="syncPage()">
        <h1 class="text-3xl font-bold text-gray-800 mb-6">Data Sync</h1>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <!-- Sync Control -->
            <div class="bg-white rounded-lg shadow p-6">
                <h2 class="text-xl font-semibold mb-4">Sync Control</h2>

                <div class="space-y-4 mb-6">
                    <label class="flex items-center">
                        <input type="checkbox" x-model="sources.postgres" class="mr-2">
                        <span>PostgreSQL (Scheduling DB)</span>
                    </label>
                    <label class="flex items-center">
                        <input type="checkbox" x-model="sources.teacher_attendance" class="mr-2">
                        <span>Teacher Attendance</span>
                    </label>
                    <label class="flex items-center">
                        <input type="checkbox" x-model="sources.student_attendance" class="mr-2">
                        <span>Student Attendance</span>
                    </label>
                    <label class="flex items-center">
                        <input type="checkbox" x-model="sources.coaching" class="mr-2">
                        <span>Coaching Records</span>
                    </label>
                    <label class="flex items-center">
                        <input type="checkbox" x-model="sources.demo_assessment" class="mr-2">
                        <span>Demo Assessments</span>
                    </label>
                    <label class="flex items-center">
                        <input type="checkbox" x-model="sources.interviews" class="mr-2">
                        <span>Interview Assessments</span>
                    </label>
                    <label class="flex items-center">
                        <input type="checkbox" x-model="sources.student_reports" class="mr-2">
                        <span>Student Reports</span>
                    </label>
                    <label class="flex items-center">
                        <input type="checkbox" x-model="sources.marketplace" class="mr-2">
                        <span>App Marketplace</span>
                    </label>
                    <label class="flex items-center">
                        <input type="checkbox" x-model="sources.notion" class="mr-2">
                        <span>Notion (if configured)</span>
                    </label>
                </div>

                <div class="flex gap-2">
                    <button @click="selectAll()" class="px-4 py-2 bg-gray-200 rounded hover:bg-gray-300">Select All</button>
                    <button @click="selectNone()" class="px-4 py-2 bg-gray-200 rounded hover:bg-gray-300">Select None</button>
                </div>

                <button @click="runSync()" :disabled="syncing"
                    class="w-full mt-6 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed">
                    <span x-show="!syncing"><i class="fas fa-sync mr-2"></i> Run Sync</span>
                    <span x-show="syncing"><i class="fas fa-spinner fa-spin mr-2"></i> Syncing...</span>
                </button>
            </div>

            <!-- Sync Status -->
            <div class="bg-white rounded-lg shadow p-6">
                <h2 class="text-xl font-semibold mb-4">Sync Status</h2>

                <div x-show="!syncResult && !syncing" class="text-gray-500 text-center py-8">
                    <i class="fas fa-info-circle text-4xl mb-4"></i>
                    <p>No recent sync. Click "Run Sync" to start.</p>
                </div>

                <div x-show="syncing" class="text-center py-8">
                    <i class="fas fa-spinner fa-spin text-4xl text-blue-600 mb-4"></i>
                    <p class="text-gray-600">Syncing data from all sources...</p>
                    <p class="text-sm text-gray-500 mt-2">This may take a minute.</p>
                </div>

                <div x-show="syncResult" class="space-y-4">
                    <div class="flex items-center gap-2">
                        <span class="px-3 py-1 rounded-full text-sm"
                            :class="syncResult?.status === 'completed' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'"
                            x-text="syncResult?.status"></span>
                    </div>

                    <div class="grid grid-cols-2 gap-4">
                        <div class="bg-gray-50 p-4 rounded">
                            <p class="text-sm text-gray-500">Entities Processed</p>
                            <p class="text-2xl font-bold" x-text="syncResult?.entities_processed || 0"></p>
                        </div>
                        <div class="bg-gray-50 p-4 rounded">
                            <p class="text-sm text-gray-500">Relations Processed</p>
                            <p class="text-2xl font-bold" x-text="syncResult?.relations_processed || 0"></p>
                        </div>
                    </div>

                    <div x-show="syncResult?.errors?.length > 0" class="bg-red-50 p-4 rounded">
                        <p class="text-sm font-semibold text-red-800 mb-2">Errors:</p>
                        <ul class="text-sm text-red-700 list-disc list-inside">
                            <template x-for="error in syncResult?.errors || []" :key="error">
                                <li x-text="error"></li>
                            </template>
                        </ul>
                    </div>

                    <div class="text-sm text-gray-500">
                        <p>Started: <span x-text="new Date(syncResult?.started_at).toLocaleString()"></span></p>
                        <p x-show="syncResult?.completed_at">Completed: <span x-text="new Date(syncResult?.completed_at).toLocaleString()"></span></p>
                    </div>
                </div>
            </div>

            <!-- Vector Index -->
            <div class="bg-white rounded-lg shadow p-6">
                <h2 class="text-xl font-semibold mb-4">
                    <i class="fas fa-brain text-purple-600 mr-2"></i>
                    Vector Index
                </h2>
                <p class="text-sm text-gray-600 mb-4">
                    Build a semantic search index to find records by meaning, not just keywords.
                </p>

                <div x-show="!vectorIndexing && !vectorResult" class="mb-4">
                    <div class="bg-gray-50 p-4 rounded">
                        <p class="text-sm text-gray-500 mb-2">Vector Store Status</p>
                        <p class="font-semibold" :class="vectorStatus?.status === 'ready' ? 'text-green-600' : 'text-yellow-600'"
                            x-text="vectorStatus?.status === 'ready' ? 'Ready (' + vectorStatus?.count + ' documents)' : 'Not initialized'">
                        </p>
                    </div>
                </div>

                <div x-show="vectorIndexing" class="text-center py-6">
                    <i class="fas fa-spinner fa-spin text-4xl text-purple-600 mb-4"></i>
                    <p class="text-gray-600">Building vector index...</p>
                    <p class="text-sm text-gray-500 mt-2">This may take a few minutes.</p>
                </div>

                <div x-show="vectorResult && !vectorIndexing" class="mb-4">
                    <div class="bg-green-50 p-4 rounded">
                        <p class="text-sm text-green-800 font-semibold mb-2">Index Built Successfully</p>
                        <div class="grid grid-cols-2 gap-2 text-sm">
                            <template x-for="(count, type) in vectorResult" :key="type">
                                <div class="flex justify-between">
                                    <span class="capitalize" x-text="type"></span>
                                    <span class="font-semibold" x-text="count"></span>
                                </div>
                            </template>
                        </div>
                    </div>
                </div>

                <button @click="buildVectorIndex()" :disabled="vectorIndexing"
                    class="w-full px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed">
                    <span x-show="!vectorIndexing"><i class="fas fa-database mr-2"></i> Build Vector Index</span>
                    <span x-show="vectorIndexing"><i class="fas fa-spinner fa-spin mr-2"></i> Building...</span>
                </button>

                <p class="text-xs text-gray-500 mt-3 text-center">
                    Indexes teachers, students, employees, apps, assessments, and more.
                </p>
            </div>
        </div>
    </div>

    <script>
        function syncPage() {
            return {
                sources: {
                    postgres: true,
                    teacher_attendance: true,
                    student_attendance: true,
                    coaching: true,
                    demo_assessment: true,
                    interviews: true,
                    student_reports: true,
                    marketplace: true,
                    notion: true
                },
                syncing: false,
                syncResult: null,
                vectorIndexing: false,
                vectorResult: null,
                vectorStatus: null,

                async init() {
                    await this.loadVectorStatus();
                },

                async loadVectorStatus() {
                    try {
                        const res = await fetch('/api/vector/status');
                        this.vectorStatus = await res.json();
                    } catch (e) {
                        this.vectorStatus = { status: 'error' };
                    }
                },

                async buildVectorIndex() {
                    this.vectorIndexing = true;
                    this.vectorResult = null;
                    try {
                        const res = await fetch('/api/vector/index', { method: 'POST' });
                        const data = await res.json();
                        this.vectorResult = data.indexed || data;
                        await this.loadVectorStatus();
                    } catch (e) {
                        console.error('Vector indexing failed:', e);
                    } finally {
                        this.vectorIndexing = false;
                    }
                },

                selectAll() {
                    Object.keys(this.sources).forEach(k => this.sources[k] = true);
                },

                selectNone() {
                    Object.keys(this.sources).forEach(k => this.sources[k] = false);
                },

                async runSync() {
                    this.syncing = true;
                    this.syncResult = null;

                    const selectedSources = Object.entries(this.sources)
                        .filter(([k, v]) => v)
                        .map(([k]) => k);

                    try {
                        const res = await fetch('/api/sync', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({ sources: selectedSources.length ? selectedSources : null })
                        });
                        this.syncResult = await res.json();
                    } catch (e) {
                        this.syncResult = { status: 'failed', errors: [e.message] };
                    } finally {
                        this.syncing = false;
                    }
                }
            }
        }
    </script>
    """
    return render_page("Data Sync", content, "sync")


@app.get("/view/query", response_class=HTMLResponse)
async def view_query(request: Request):
    """Query console view."""
    if not check_auth(request):
        return RedirectResponse(url="/login", status_code=302)
    content = """
    <div x-data="queryPage()">
        <h1 class="text-3xl font-bold text-gray-800 mb-6">Query Console</h1>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <!-- Query Input -->
            <div class="lg:col-span-2 bg-white rounded-lg shadow p-6">
                <h2 class="text-xl font-semibold mb-4">TypeQL Query</h2>

                <textarea x-model="query" rows="8"
                    class="w-full p-4 font-mono text-sm border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Enter TypeQL query..."></textarea>

                <div class="flex gap-2 mt-4">
                    <button @click="runQuery()" :disabled="loading"
                        class="px-6 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50">
                        <span x-show="!loading"><i class="fas fa-play mr-2"></i> Run</span>
                        <span x-show="loading"><i class="fas fa-spinner fa-spin mr-2"></i> Running...</span>
                    </button>
                    <button @click="clearQuery()" class="px-6 py-2 bg-gray-200 rounded hover:bg-gray-300">Clear</button>
                </div>

                <!-- Results -->
                <div class="mt-6">
                    <div class="flex justify-between items-center mb-2">
                        <h3 class="font-semibold">Results</h3>
                        <span x-show="result" class="text-sm text-gray-500">
                            <span x-text="result?.count || 0"></span> results in
                            <span x-text="(result?.execution_time_ms || 0).toFixed(2)"></span>ms
                        </span>
                    </div>

                    <div class="bg-gray-900 text-green-400 p-4 rounded-lg font-mono text-sm max-h-96 overflow-auto">
                        <pre x-text="JSON.stringify(result?.results || [], null, 2)"></pre>
                    </div>

                    <div x-show="error" class="mt-4 p-4 bg-red-50 text-red-700 rounded-lg">
                        <p class="font-semibold">Error:</p>
                        <p x-text="error"></p>
                    </div>
                </div>
            </div>

            <!-- Example Queries -->
            <div class="bg-white rounded-lg shadow p-6">
                <h2 class="text-xl font-semibold mb-4">Example Queries</h2>

                <div class="space-y-4">
                    <div class="p-3 bg-gray-50 rounded cursor-pointer hover:bg-gray-100" @click="setQuery(examples[0])">
                        <p class="font-medium text-sm">List all teachers</p>
                        <code class="text-xs text-gray-500">match $t isa teacher; fetch...</code>
                    </div>

                    <div class="p-3 bg-gray-50 rounded cursor-pointer hover:bg-gray-100" @click="setQuery(examples[1])">
                        <p class="font-medium text-sm">List all students</p>
                        <code class="text-xs text-gray-500">match $s isa student; fetch...</code>
                    </div>

                    <div class="p-3 bg-gray-50 rounded cursor-pointer hover:bg-gray-100" @click="setQuery(examples[2])">
                        <p class="font-medium text-sm">Teaching relationships</p>
                        <code class="text-xs text-gray-500">match (instructor: $t, learner: $s)...</code>
                    </div>

                    <div class="p-3 bg-gray-50 rounded cursor-pointer hover:bg-gray-100" @click="setQuery(examples[3])">
                        <p class="font-medium text-sm">Late attendance</p>
                        <code class="text-xs text-gray-500">match $a has attendance_status "late"...</code>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        function queryPage() {
            return {
                query: 'match $t isa teacher; fetch $t: name, email; limit 10;',
                result: null,
                error: null,
                loading: false,
                examples: [
                    'match $t isa teacher; fetch $t: external_id, name, email, position; limit 20;',
                    'match $s isa student; fetch $s: external_id, name, grade, school; limit 20;',
                    'match $t isa teacher; $s isa student; (instructor: $t, learner: $s) isa teaching; fetch $t: name; $s: name; limit 20;',
                    'match $a isa attendance, has attendance_status "late"; fetch $a: external_id, date, minutes_late; limit 20;'
                ],

                setQuery(q) {
                    this.query = q;
                },

                clearQuery() {
                    this.query = '';
                    this.result = null;
                    this.error = null;
                },

                async runQuery() {
                    this.loading = true;
                    this.error = null;

                    try {
                        const res = await fetch('/api/query', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({ query: this.query })
                        });

                        if (!res.ok) {
                            const err = await res.json();
                            throw new Error(err.detail || 'Query failed');
                        }

                        this.result = await res.json();
                    } catch (e) {
                        this.error = e.message;
                        this.result = null;
                    } finally {
                        this.loading = false;
                    }
                }
            }
        }
    </script>
    """
    return render_page("Query Console", content, "query")


@app.get("/view/graph", response_class=HTMLResponse)
async def view_graph(request: Request):
    """Graph visualization view."""
    if not check_auth(request):
        return RedirectResponse(url="/login", status_code=302)
    content = """
    <div x-data="graphPage()" x-init="loadGraph()">
        <div class="flex justify-between items-center mb-6">
            <h1 class="text-3xl font-bold text-gray-800">Knowledge Graph Explorer</h1>
            <div class="flex gap-2">
                <select x-model="viewMode" @change="renderGraph()" class="px-3 py-2 border rounded-lg text-sm">
                    <option value="all">All Entities</option>
                    <option value="teachers">Teachers Focus</option>
                    <option value="students">Students Focus</option>
                    <option value="assignments">Assignments Focus</option>
                </select>
                <button @click="loadGraph()" class="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">
                    <i class="fas fa-refresh mr-2"></i> Refresh
                </button>
            </div>
        </div>

        <div class="bg-white rounded-lg shadow p-6">
            <!-- Legend -->
            <div class="flex flex-wrap gap-4 mb-4 pb-4 border-b">
                <div class="flex items-center gap-2">
                    <span class="w-4 h-4 rounded-full bg-blue-500"></span>
                    <span class="text-sm">Teachers</span>
                </div>
                <div class="flex items-center gap-2">
                    <span class="w-4 h-4 rounded-full bg-emerald-500"></span>
                    <span class="text-sm">Students</span>
                </div>
                <div class="flex items-center gap-2">
                    <span class="w-3 h-3 rotate-45 bg-purple-500"></span>
                    <span class="text-sm">Assignments</span>
                </div>
                <div class="flex items-center gap-2">
                    <span class="w-3 h-3 bg-amber-500"></span>
                    <span class="text-sm">Time Slots</span>
                </div>
                <div class="flex items-center gap-2">
                    <span class="w-4 h-3 rounded bg-pink-500"></span>
                    <span class="text-sm">Rooms</span>
                </div>
                <div class="flex items-center gap-2">
                    <span class="w-0 h-0 border-l-[6px] border-r-[6px] border-b-[10px] border-l-transparent border-r-transparent border-b-rose-500"></span>
                    <span class="text-sm">Assessments</span>
                </div>
                <div class="flex items-center gap-2">
                    <span class="w-4 h-4 bg-cyan-500" style="clip-path: polygon(50% 0%, 61% 35%, 98% 35%, 68% 57%, 79% 91%, 50% 70%, 21% 91%, 32% 57%, 2% 35%, 39% 35%);"></span>
                    <span class="text-sm">Interviews</span>
                </div>
                <div class="flex items-center gap-2">
                    <span class="w-4 h-4 rounded-full bg-orange-500"></span>
                    <span class="text-sm">Coaching</span>
                </div>
            </div>

            <!-- Stats bar -->
            <div class="flex gap-6 mb-4 text-sm text-gray-600">
                <span><strong x-text="graph.nodes?.length || 0"></strong> nodes</span>
                <span><strong x-text="graph.edges?.length || 0"></strong> connections</span>
                <span x-show="loading"><i class="fas fa-spinner fa-spin"></i> Loading...</span>
            </div>

            <div id="graph-container" class="w-full h-[650px] border rounded-lg bg-gradient-to-br from-slate-50 to-slate-100 relative">
                <div x-show="!graph.nodes?.length && !loading" class="absolute inset-0 flex items-center justify-center">
                    <div class="text-center text-gray-500">
                        <i class="fas fa-project-diagram text-4xl mb-4"></i>
                        <p>No graph data. Run a sync first to populate the knowledge graph.</p>
                    </div>
                </div>
            </div>

            <!-- Controls -->
            <div class="flex gap-2 mt-4">
                <button @click="network?.fit()" class="px-3 py-1.5 text-sm bg-gray-100 rounded hover:bg-gray-200">
                    <i class="fas fa-expand mr-1"></i> Fit View
                </button>
                <button @click="togglePhysics()" class="px-3 py-1.5 text-sm bg-gray-100 rounded hover:bg-gray-200">
                    <i class="fas fa-atom mr-1"></i> <span x-text="physicsEnabled ? 'Freeze' : 'Unfreeze'"></span>
                </button>
                <button @click="clusterByGroup()" class="px-3 py-1.5 text-sm bg-gray-100 rounded hover:bg-gray-200">
                    <i class="fas fa-object-group mr-1"></i> Cluster by Type
                </button>
            </div>
        </div>

        <!-- Node Details Panel -->
        <div x-show="selectedNode" x-transition class="fixed right-6 top-24 w-96 bg-white rounded-lg shadow-2xl z-50 overflow-hidden">
            <div class="bg-gradient-to-r from-slate-700 to-slate-800 text-white px-6 py-4">
                <div class="flex justify-between items-start">
                    <div>
                        <h3 class="font-semibold text-lg" x-text="selectedNode?.label"></h3>
                        <span class="text-xs opacity-75 uppercase tracking-wide" x-text="selectedNode?.type"></span>
                    </div>
                    <button @click="selectedNode = null" class="text-white/60 hover:text-white">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            </div>
            <div class="p-6 space-y-4 max-h-96 overflow-y-auto">
                <div>
                    <span class="text-xs text-gray-400 uppercase tracking-wide">ID</span>
                    <p class="font-mono text-xs text-gray-600 mt-1" x-text="selectedNode?.id"></p>
                </div>
                <div x-show="selectedNode?.group">
                    <span class="text-xs text-gray-400 uppercase tracking-wide">Group</span>
                    <p class="mt-1">
                        <span class="px-2 py-0.5 rounded bg-slate-100 text-sm" x-text="selectedNode?.group"></span>
                    </p>
                </div>
                <div x-show="selectedNode?.metadata && Object.keys(selectedNode.metadata).length > 0">
                    <span class="text-xs text-gray-400 uppercase tracking-wide">Details</span>
                    <div class="mt-2 space-y-1">
                        <template x-for="(value, key) in selectedNode?.metadata || {}" :key="key">
                            <div x-show="value" class="flex justify-between text-sm">
                                <span class="text-gray-500 capitalize" x-text="key.replace(/_/g, ' ')"></span>
                                <span class="font-medium" x-text="value"></span>
                            </div>
                        </template>
                    </div>
                </div>
                <div>
                    <span class="text-xs text-gray-400 uppercase tracking-wide">Connections</span>
                    <p class="mt-1 text-2xl font-bold text-slate-700" x-text="getConnectionCount(selectedNode?.id)"></p>
                </div>

                <!-- Action buttons -->
                <div class="pt-4 border-t flex gap-2">
                    <button @click="focusNode(selectedNode?.id)" class="flex-1 px-3 py-2 text-sm bg-blue-50 text-blue-600 rounded hover:bg-blue-100">
                        <i class="fas fa-crosshairs mr-1"></i> Focus
                    </button>
                    <button @click="highlightConnected(selectedNode?.id)" class="flex-1 px-3 py-2 text-sm bg-purple-50 text-purple-600 rounded hover:bg-purple-100">
                        <i class="fas fa-project-diagram mr-1"></i> Show Links
                    </button>
                </div>
            </div>
        </div>
    </div>

    <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <script>
        function graphPage() {
            return {
                graph: { nodes: [], edges: [] },
                network: null,
                selectedNode: null,
                loading: false,
                physicsEnabled: true,
                viewMode: 'all',

                async loadGraph() {
                    this.loading = true;
                    try {
                        const res = await fetch('/api/graph?limit=150&include_assignments=true&include_schedules=true');
                        this.graph = await res.json();
                        this.renderGraph();
                    } catch (e) {
                        console.error('Failed to load graph:', e);
                    }
                    this.loading = false;
                },

                getNodeColor(type) {
                    const colors = {
                        'teacher': { background: '#3B82F6', border: '#2563EB', highlight: { background: '#60A5FA', border: '#3B82F6' } },
                        'student': { background: '#10B981', border: '#059669', highlight: { background: '#34D399', border: '#10B981' } },
                        'assignment': { background: '#8B5CF6', border: '#7C3AED', highlight: { background: '#A78BFA', border: '#8B5CF6' } },
                        'schedule': { background: '#F59E0B', border: '#D97706', highlight: { background: '#FBBF24', border: '#F59E0B' } },
                        'room': { background: '#EC4899', border: '#DB2777', highlight: { background: '#F472B6', border: '#EC4899' } },
                        'assessment': { background: '#F43F5E', border: '#E11D48', highlight: { background: '#FB7185', border: '#F43F5E' } },
                        'interview': { background: '#06B6D4', border: '#0891B2', highlight: { background: '#22D3EE', border: '#06B6D4' } },
                        'employee': { background: '#F97316', border: '#EA580C', highlight: { background: '#FB923C', border: '#F97316' } }
                    };
                    return colors[type] || { background: '#94A3B8', border: '#64748B' };
                },

                getNodeShape(type) {
                    const shapes = {
                        'teacher': 'dot',
                        'student': 'dot',
                        'assignment': 'diamond',
                        'schedule': 'square',
                        'room': 'box',
                        'assessment': 'triangle',
                        'interview': 'star',
                        'employee': 'dot'
                    };
                    return shapes[type] || 'dot';
                },

                getNodeSize(type) {
                    const sizes = {
                        'teacher': 25,
                        'student': 18,
                        'assignment': 15,
                        'schedule': 25,
                        'room': 30,
                        'assessment': 20,
                        'interview': 18,
                        'employee': 20
                    };
                    return sizes[type] || 15;
                },

                getEdgeColor(type) {
                    const colors = {
                        'teaches_in': '#3B82F6',
                        'has_student': '#10B981',
                        'location': '#EC4899',
                        'assessed': '#F43F5E',
                        'interviewed': '#06B6D4',
                        'conducted': '#8B5CF6',
                        'coaching_profile': '#F97316'
                    };
                    return colors[type] || '#94A3B8';
                },

                renderGraph() {
                    const container = document.getElementById('graph-container');
                    if (!container || !this.graph.nodes) return;

                    // Filter nodes based on view mode
                    let filteredNodes = this.graph.nodes;
                    let filteredEdges = this.graph.edges;

                    if (this.viewMode !== 'all') {
                        const focusType = this.viewMode.replace('s', ''); // teachers -> teacher
                        const focusNodeIds = new Set(this.graph.nodes.filter(n => n.type === focusType).map(n => n.id));

                        // Include connected nodes
                        this.graph.edges.forEach(e => {
                            if (focusNodeIds.has(e.source)) focusNodeIds.add(e.target);
                            if (focusNodeIds.has(e.target)) focusNodeIds.add(e.source);
                        });

                        filteredNodes = this.graph.nodes.filter(n => focusNodeIds.has(n.id));
                        filteredEdges = this.graph.edges.filter(e => focusNodeIds.has(e.source) && focusNodeIds.has(e.target));
                    }

                    const nodes = new vis.DataSet(filteredNodes.map(n => ({
                        id: n.id,
                        label: n.label?.length > 20 ? n.label.substring(0, 18) + '...' : n.label,
                        title: n.label,
                        color: this.getNodeColor(n.type),
                        shape: this.getNodeShape(n.type),
                        size: this.getNodeSize(n.type),
                        font: { color: '#374151', size: 11 },
                        borderWidth: 2,
                        shadow: true
                    })));

                    const edges = new vis.DataSet(filteredEdges.map(e => ({
                        from: e.source,
                        to: e.target,
                        title: e.type.replace(/_/g, ' '),
                        arrows: { to: { enabled: true, scaleFactor: 0.5 } },
                        color: { color: this.getEdgeColor(e.type), opacity: 0.7 },
                        width: 1.5,
                        smooth: { type: 'continuous' }
                    })));

                    const options = {
                        physics: {
                            enabled: this.physicsEnabled,
                            stabilization: { iterations: 100 },
                            barnesHut: {
                                gravitationalConstant: -3000,
                                centralGravity: 0.3,
                                springLength: 120,
                                springConstant: 0.04,
                                damping: 0.09
                            }
                        },
                        interaction: {
                            hover: true,
                            tooltipDelay: 100,
                            hideEdgesOnDrag: true,
                            multiselect: true
                        },
                        nodes: {
                            font: { face: 'system-ui' }
                        },
                        groups: {
                            teachers: { color: this.getNodeColor('teacher') },
                            students: { color: this.getNodeColor('student') },
                            assignments: { color: this.getNodeColor('assignment') },
                            schedule: { color: this.getNodeColor('schedule') },
                            assessments: { color: this.getNodeColor('assessment') },
                            interviews: { color: this.getNodeColor('interview') },
                            coaching: { color: this.getNodeColor('employee') }
                        }
                    };

                    this.network = new vis.Network(container, { nodes, edges }, options);

                    this.network.on('click', (params) => {
                        if (params.nodes.length > 0) {
                            const nodeId = params.nodes[0];
                            const node = this.graph.nodes.find(n => n.id === nodeId);
                            this.selectedNode = node;
                        } else {
                            this.selectedNode = null;
                        }
                    });

                    this.network.on('doubleClick', (params) => {
                        if (params.nodes.length > 0) {
                            this.highlightConnected(params.nodes[0]);
                        }
                    });
                },

                togglePhysics() {
                    this.physicsEnabled = !this.physicsEnabled;
                    if (this.network) {
                        this.network.setOptions({ physics: { enabled: this.physicsEnabled } });
                    }
                },

                clusterByGroup() {
                    if (!this.network) return;
                    const groups = ['teachers', 'students', 'assignments', 'schedule'];
                    groups.forEach(group => {
                        this.network.cluster({
                            joinCondition: (nodeOptions) => this.graph.nodes.find(n => n.id === nodeOptions.id)?.group === group,
                            clusterNodeProperties: {
                                id: 'cluster_' + group,
                                label: group.charAt(0).toUpperCase() + group.slice(1),
                                shape: 'dot',
                                size: 40,
                                color: this.getNodeColor(group.replace('s', ''))
                            }
                        });
                    });
                },

                getConnectionCount(nodeId) {
                    if (!nodeId || !this.graph.edges) return 0;
                    return this.graph.edges.filter(e => e.source === nodeId || e.target === nodeId).length;
                },

                focusNode(nodeId) {
                    if (this.network && nodeId) {
                        this.network.focus(nodeId, { scale: 1.5, animation: true });
                    }
                },

                highlightConnected(nodeId) {
                    if (!this.network || !nodeId) return;

                    // Get connected node IDs
                    const connectedNodes = new Set([nodeId]);
                    this.graph.edges.forEach(e => {
                        if (e.source === nodeId) connectedNodes.add(e.target);
                        if (e.target === nodeId) connectedNodes.add(e.source);
                    });

                    // Update node colors
                    const allNodes = this.network.body.data.nodes.get();
                    allNodes.forEach(node => {
                        if (connectedNodes.has(node.id)) {
                            this.network.body.data.nodes.update({ id: node.id, opacity: 1 });
                        } else {
                            this.network.body.data.nodes.update({ id: node.id, opacity: 0.2 });
                        }
                    });

                    // Focus on the selection
                    this.network.fit({ nodes: Array.from(connectedNodes), animation: true });
                }
            }
        }
    </script>
    """
    return render_page("Graph Explorer", content, "graph")


@app.get("/view/galaxy", response_class=HTMLResponse)
async def view_galaxy(request: Request):
    """Galaxy visualization view — 3D rotating knowledge graph."""
    if not check_auth(request):
        return RedirectResponse(url="/login", status_code=302)
    content = """
    <style>
        body { background: #0B1120 !important; min-height: 0 !important; overflow: hidden !important; margin: 0; }
        .main-content { padding: 0 !important; background: #0B1120 !important; overflow: hidden; }
        #galaxy-wrap { position: fixed; top: 0; left: 250px; right: 0; bottom: 0; overflow: hidden; background: #0B1120; }
        #galaxy-canvas { display: block; cursor: default; }
        .hud-panel {
            font-family: 'Courier New', monospace;
            border: 1px solid rgba(96,165,250,0.3);
            background: rgba(15,23,42,0.88);
            position: relative;
        }
        .hud-panel::before, .hud-panel::after {
            content: ''; position: absolute; width: 10px; height: 10px; border-color: #60A5FA;
        }
        .hud-panel::before { top: -1px; left: -1px; border-top: 2px solid; border-left: 2px solid; }
        .hud-panel::after { top: -1px; right: -1px; border-top: 2px solid; border-right: 2px solid; }
        .hud-bl, .hud-br { position: absolute; width: 10px; height: 10px; border-color: #60A5FA; }
        .hud-bl { bottom: -1px; left: -1px; border-bottom: 2px solid; border-left: 2px solid; }
        .hud-br { bottom: -1px; right: -1px; border-bottom: 2px solid; border-right: 2px solid; }
        .scan-line {
            position: absolute; top: 0; left: 0; right: 0; height: 2px;
            background: linear-gradient(90deg, transparent, rgba(96,165,250,0.25), transparent);
            animation: scanMove 4s linear infinite;
        }
        @keyframes scanMove { 0% { top: 0; } 100% { top: 100%; } }
        @keyframes twinkle { 0%,100% { opacity: 0.6; } 50% { opacity: 1; } }
        .detail-panel {
            backdrop-filter: blur(12px); background: rgba(15,23,42,0.92);
            border: 1px solid rgba(96,165,250,0.3); border-radius: 12px;
        }
    </style>

    <div x-data="galaxyApp()" x-init="init()">
        <div id="galaxy-wrap">
            <canvas id="galaxy-canvas"
                    @mousemove="onMouseMove($event)"
                    @click="onCanvasClick($event)"
                    @mouseleave="hoveredNode = null"></canvas>

            <!-- Top Bar -->
            <div class="absolute top-0 left-0 right-0 z-20 flex justify-between items-center px-6 py-3"
                 style="background: linear-gradient(to bottom, rgba(11,17,32,0.95) 50%, transparent);">
                <div>
                    <h1 class="text-lg font-bold text-white tracking-widest" style="font-family: 'Courier New', monospace;">
                        <i class="fas fa-star text-blue-400 mr-1" style="font-size:12px"></i> SPACE WAYMAKER
                    </h1>
                    <p class="text-blue-400/50 text-xs italic mt-0.5">A vast galaxy of knowledge, where our children's minds connect</p>
                </div>
                <div class="flex gap-2 items-center">
                    <button @click="togglePause()" class="px-3 py-1.5 rounded text-xs font-medium transition border"
                            :class="paused ? 'border-green-500/50 text-green-400 hover:bg-green-500/10' : 'border-blue-500/30 text-blue-300 hover:bg-blue-500/10'">
                        <i :class="paused ? 'fas fa-play' : 'fas fa-pause'" class="mr-1"></i>
                        <span x-text="paused ? 'Resume' : 'Pause'"></span>
                    </button>
                    <button @click="speed = Math.max(0.1, speed - 0.2)" class="px-2 py-1.5 border border-blue-500/20 text-blue-400 rounded text-xs hover:bg-blue-500/10">
                        <i class="fas fa-minus"></i>
                    </button>
                    <span class="text-xs text-blue-300/70 w-12 text-center font-mono" x-text="speed.toFixed(1) + 'x'"></span>
                    <button @click="speed = Math.min(3.0, speed + 0.2)" class="px-2 py-1.5 border border-blue-500/20 text-blue-400 rounded text-xs hover:bg-blue-500/10">
                        <i class="fas fa-plus"></i>
                    </button>
                    <button @click="loadData()" class="px-3 py-1.5 border border-blue-500/20 text-blue-400 rounded text-xs hover:bg-blue-500/10">
                        <i class="fas fa-sync mr-1"></i> Reload
                    </button>
                </div>
            </div>

            <!-- HUD Panel -->
            <div class="hud-panel absolute top-16 left-4 p-3 text-xs text-blue-300 w-52 z-10">
                <div class="scan-line"></div>
                <div class="hud-bl"></div><div class="hud-br"></div>
                <div class="text-blue-400 font-bold text-xs mb-2 tracking-widest">
                    <i class="fas fa-satellite text-blue-500 mr-1"></i> STAR MAP
                </div>
                <div class="space-y-0.5">
                    <div class="flex justify-between"><span class="text-blue-500/70">STARS</span><span x-text="typeCounts['student'] || 0"></span></div>
                    <div class="flex justify-between"><span class="text-blue-500/70">CONSTELLATIONS</span><span x-text="typeCounts['teacher'] || 0"></span></div>
                    <div class="flex justify-between"><span class="text-blue-500/70">CONNECTIONS</span><span x-text="galaxyEdges.length"></span></div>
                    <div class="flex justify-between"><span class="text-blue-500/70">ORBIT</span><span x-text="(rotationAngle % 360).toFixed(0) + '°'"></span></div>
                    <div class="flex justify-between">
                        <span class="text-blue-500/70">STATUS</span>
                        <span :class="paused ? 'text-amber-400' : 'text-green-400'" x-text="paused ? 'PAUSED' : 'EXPLORING'"></span>
                    </div>
                </div>
            </div>

            <!-- Filter Panel -->
            <div class="absolute top-16 right-4 w-48 z-10 max-h-[calc(100vh-100px)] overflow-y-auto">
                <div class="hud-panel p-3">
                    <div class="hud-bl"></div><div class="hud-br"></div>
                    <div class="text-blue-400 font-bold text-xs mb-2 tracking-widest">
                        <i class="fas fa-filter text-blue-500 mr-1"></i> EXPLORE
                    </div>
                    <input type="text" x-model="searchTerm" @input="applyFilters()"
                           placeholder="Search a star..."
                           class="w-full px-2 py-1 mb-2 bg-slate-800/80 border border-blue-500/20 rounded text-xs text-white placeholder-blue-400/40 focus:outline-none focus:border-blue-400">
                    <div class="space-y-0.5">
                        <template x-for="t in entityTypes" :key="t.key">
                            <button @click="t.visible = !t.visible; applyFilters()"
                                    class="flex items-center gap-2 w-full px-2 py-1 rounded text-xs text-left transition"
                                    :class="t.visible ? 'bg-slate-700/60 text-white' : 'bg-transparent text-gray-600 line-through'">
                                <span class="w-2.5 h-2.5 rounded-full" :style="'background:' + t.color"></span>
                                <span class="flex-1" x-text="t.label"></span>
                                <span class="text-blue-400/40" x-text="typeCounts[t.key] || 0"></span>
                            </button>
                        </template>
                    </div>
                </div>
            </div>

            <!-- Story Panel (click a star to reveal its story) -->
            <div x-show="selectedNode" x-transition class="detail-panel absolute bottom-4 left-4 w-80 p-4 z-10 text-white">
                <div class="flex justify-between items-start mb-3">
                    <div>
                        <div class="flex items-center gap-2">
                            <span class="w-3 h-3 rounded-full" :style="'background:' + getColor(selectedNode?.type)"></span>
                            <h3 class="font-bold text-sm" x-text="selectedNode?.label"></h3>
                        </div>
                        <p class="text-xs mt-1 italic" :style="'color:' + getColor(selectedNode?.type)"
                           x-text="selectedNode?.type === 'student' ? 'A star in the galaxy of knowledge'
                                  : selectedNode?.type === 'teacher' ? 'Constellation guide'
                                  : selectedNode?.type === 'room' ? 'Space station'
                                  : selectedNode?.type === 'assignment' ? 'Knowledge pathway'
                                  : 'Galaxy entity'">
                        </p>
                    </div>
                    <button @click="selectedNode = null" class="text-gray-500 hover:text-white text-xs ml-2">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div class="space-y-2 text-xs max-h-64 overflow-y-auto">
                    <!-- All connections grouped by type -->
                    <template x-for="(items, type) in getConnections(selectedNode?.id)" :key="type">
                        <div class="bg-slate-800/50 rounded px-3 py-2">
                            <div class="flex items-center gap-1.5 mb-1">
                                <span class="w-2 h-2 rounded-full" :style="'background:' + getColor(type)"></span>
                                <span class="capitalize font-medium" :style="'color:' + getColor(type)" x-text="type + 's'"></span>
                                <span class="text-gray-500 ml-auto" x-text="items.length"></span>
                            </div>
                            <div class="space-y-0.5 ml-3.5">
                                <template x-for="item in items.slice(0, 6)" :key="item.id">
                                    <div class="text-gray-300 truncate" x-text="item.label"></div>
                                </template>
                                <div x-show="items.length > 6" class="text-gray-500 italic"
                                     x-text="'+' + (items.length - 6) + ' more'"></div>
                            </div>
                        </div>
                    </template>
                    <!-- Metadata -->
                    <div x-show="selectedNode?.metadata && Object.keys(selectedNode.metadata).length > 0">
                        <div class="space-y-0.5 bg-slate-800/30 rounded px-3 py-2">
                            <div class="text-gray-500 font-medium mb-1">Details</div>
                            <template x-for="(v, k) in selectedNode?.metadata || {}" :key="k">
                                <div x-show="v" class="flex justify-between">
                                    <span class="text-gray-500 capitalize" x-text="k.replace(/_/g, ' ')"></span>
                                    <span class="text-gray-300 truncate ml-2" style="max-width:160px" x-text="String(v).substring(0,40)"></span>
                                </div>
                            </template>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Tooltip -->
            <div x-show="hoveredNode && !selectedNode" x-transition.opacity
                 class="absolute pointer-events-none z-20 px-3 py-1.5 rounded-lg bg-black/85 text-white text-xs whitespace-nowrap border border-blue-500/20"
                 :style="'left:' + tooltipX + 'px; top:' + tooltipY + 'px'">
                <span class="w-2 h-2 rounded-full inline-block mr-1" :style="'background:' + getColor(hoveredNode?.type)"></span>
                <span x-text="hoveredNode?.label"></span>
                <span class="text-blue-400/50 ml-1 capitalize" x-text="hoveredNode?.type"></span>
            </div>

            <!-- Loading -->
            <div x-show="loading" class="absolute inset-0 flex items-center justify-center bg-black/70 z-30">
                <div class="text-center text-white">
                    <i class="fas fa-spinner fa-spin text-4xl text-blue-400 mb-4"></i>
                    <p class="text-sm text-blue-300">Mapping the galaxy of knowledge...</p>
                </div>
            </div>

            <!-- Legend -->
            <div class="absolute bottom-0 left-0 right-0 z-10 flex flex-wrap justify-center gap-4 px-6 py-3"
                 style="background: linear-gradient(to top, rgba(11,17,32,0.9) 50%, transparent);">
                <template x-for="t in entityTypes" :key="t.key">
                    <div class="flex items-center gap-1.5 text-xs text-gray-400">
                        <span class="w-2 h-2 rounded-full" :style="'background:' + t.color"></span>
                        <span x-text="t.label + ' (' + (typeCounts[t.key] || 0) + ')'"></span>
                    </div>
                </template>
                <div class="text-xs text-gray-600 italic ml-4">Each star holds its own unique story</div>
            </div>
        </div>
    </div>

    <script>
    function galaxyApp() {
        return {
            galaxyNodes: [],
            galaxyEdges: [],
            visibleNodes: [],
            rawGraph: { nodes: [], edges: [] },
            loading: false,
            paused: false,
            speed: 0.3,
            rotationAngle: 0,
            selectedNode: null,
            hoveredNode: null,
            tooltipX: 0,
            tooltipY: 0,
            searchTerm: '',
            typeCounts: {},
            canvas: null,
            ctx: null,
            animFrame: null,
            starDust: [],
            teacherMap: {},    // teacherId -> teacher label
            studentTeacher: {}, // studentId -> teacher label
            teacherStudentNames: {}, // teacherId -> [student labels]
            connectedIds: new Set(),  // IDs of nodes connected to selected student
            entityTypes: [
                { key: 'student', label: 'Stars (Students)', color: '#60A5FA', visible: true },
                { key: 'teacher', label: 'Constellations (Teachers)', color: '#FBBF24', visible: true },
                { key: 'room', label: 'Stations (Rooms)', color: '#EC4899', visible: true },
                { key: 'assignment', label: 'Pathways (Assignments)', color: '#8B5CF6', visible: false },
                { key: 'assessment', label: 'Assessments', color: '#F43F5E', visible: false },
                { key: 'interview', label: 'Interviews', color: '#06B6D4', visible: false },
                { key: 'employee', label: 'Employees', color: '#F97316', visible: false },
                { key: 'schedule', label: 'Schedules', color: '#F59E0B', visible: false },
            ],

            init() {
                this.canvas = document.getElementById('galaxy-canvas');
                this.ctx = this.canvas.getContext('2d');
                this.resizeCanvas();
                window.addEventListener('resize', () => this.resizeCanvas());
                for (let i = 0; i < 400; i++) {
                    this.starDust.push({
                        x: Math.random() * 2 - 1,
                        y: Math.random() * 2 - 1,
                        z: Math.random() * 2 - 1,
                        size: Math.random() * 1.2 + 0.2,
                        brightness: Math.random() * 0.4 + 0.1
                    });
                }
                this.loadData();
            },

            resizeCanvas() {
                if (!this.canvas) return;
                const w = window.innerWidth - 250;
                const h = window.innerHeight;
                this.canvas.width = w;
                this.canvas.height = h;
                if (this.visibleNodes.length) this.render(performance.now() / 1000);
            },

            getColor(type) {
                const c = { teacher:'#FBBF24', student:'#60A5FA', room:'#EC4899', assignment:'#8B5CF6', assessment:'#F43F5E', interview:'#06B6D4', employee:'#F97316', schedule:'#F59E0B' };
                return c[type] || '#94A3B8';
            },

            getConnectionCount(nodeId) {
                if (!nodeId) return 0;
                return this.galaxyEdges.filter(e => e.source === nodeId || e.target === nodeId).length;
            },

            getTeacherFor(studentId) {
                return this.studentTeacher[studentId] || null;
            },

            getStudentsFor(teacherId) {
                return this.teacherStudentNames[teacherId] || [];
            },

            getConnections(nodeId) {
                // Returns all connected nodes grouped by type
                if (!nodeId) return {};
                const nodeMap = {};
                this.galaxyNodes.forEach(n => nodeMap[n.id] = n);
                const groups = {};
                this.galaxyEdges.forEach(e => {
                    let otherId = null;
                    if (e.source === nodeId) otherId = e.target;
                    else if (e.target === nodeId) otherId = e.source;
                    if (!otherId || !nodeMap[otherId]) return;
                    const other = nodeMap[otherId];
                    if (!groups[other.type]) groups[other.type] = [];
                    groups[other.type].push({ id: other.id, label: other.label, edgeType: e.type });
                });
                return groups;
            },

            async loadData() {
                this.loading = true;
                try {
                    const res = await fetch('/api/graph?limit=500&include_assignments=true&include_schedules=true');
                    this.rawGraph = await res.json();
                    this.buildGalaxy();
                    this.applyFilters();
                    if (!this.animFrame) this.animate();
                } catch (e) {
                    console.error('Failed to load graph:', e);
                }
                this.loading = false;
            },

            buildGalaxy() {
                const nodes = this.rawGraph.nodes || [];
                const edges = this.rawGraph.edges || [];

                // Build label lookup
                const labelMap = {};
                nodes.forEach(n => { labelMap[n.id] = n.label || n.id; });

                // Build teacher-student relationships
                const teacherStudentIds = {};
                edges.forEach(e => {
                    if (e.type === 'has_student' || e.type === 'teaches') {
                        if (!teacherStudentIds[e.source]) teacherStudentIds[e.source] = [];
                        teacherStudentIds[e.source].push(e.target);
                    }
                });

                // Build reverse maps for story panel
                this.studentTeacher = {};
                this.teacherStudentNames = {};
                for (const [tId, sIds] of Object.entries(teacherStudentIds)) {
                    this.teacherStudentNames[tId] = sIds.map(s => labelMap[s] || s);
                    sIds.forEach(s => { this.studentTeacher[s] = labelMap[tId] || tId; });
                }

                // Place teachers as constellation anchors, evenly around disk
                const teachers = nodes.filter(n => n.type === 'teacher');
                const teacherPositions = {};
                teachers.forEach((t, i) => {
                    const angle = (i / Math.max(teachers.length, 1)) * Math.PI * 2;
                    const radius = 0.2 + (i % 4) * 0.13;
                    teacherPositions[t.id] = {
                        x: Math.cos(angle) * radius,
                        y: (Math.random() - 0.5) * 0.06,
                        z: Math.sin(angle) * radius
                    };
                });

                const galaxyNodes = [];
                nodes.forEach(n => {
                    let x, y, z, orbitTarget, orbitRadius, orbitSpeed, orbitAngle;
                    const type = n.type;

                    if (type === 'teacher' && teacherPositions[n.id]) {
                        const tp = teacherPositions[n.id];
                        x = tp.x; y = tp.y; z = tp.z;
                    } else if (type === 'student') {
                        // Find parent teacher, orbit near them
                        let parentId = null;
                        for (const [tId, sIds] of Object.entries(teacherStudentIds)) {
                            if (sIds.includes(n.id)) { parentId = tId; break; }
                        }
                        if (parentId && teacherPositions[parentId]) {
                            orbitTarget = parentId;
                            orbitRadius = 0.04 + Math.random() * 0.06;
                            orbitSpeed = 0.2 + Math.random() * 0.4;
                            orbitAngle = Math.random() * Math.PI * 2;
                            const tp = teacherPositions[parentId];
                            x = tp.x + Math.cos(orbitAngle) * orbitRadius;
                            y = tp.y;
                            z = tp.z + Math.sin(orbitAngle) * orbitRadius;
                        } else {
                            const a = Math.random() * Math.PI * 2;
                            const r = 0.1 + Math.random() * 0.45;
                            x = Math.cos(a) * r; y = (Math.random()-0.5)*0.15; z = Math.sin(a) * r;
                        }
                    } else if (type === 'room') {
                        const rooms = nodes.filter(nn => nn.type === 'room');
                        const ri = rooms.indexOf(n);
                        const a = (ri / Math.max(rooms.length, 1)) * Math.PI * 2;
                        x = Math.cos(a) * 0.6; y = (Math.random()-0.5)*0.04; z = Math.sin(a) * 0.6;
                    } else if (type === 'assignment') {
                        const a = Math.random() * Math.PI * 2;
                        const r = 0.08 + Math.random() * 0.48;
                        x = Math.cos(a)*r; y = (Math.random()-0.5)*0.12; z = Math.sin(a)*r;
                    } else if (type === 'schedule') {
                        const a = Math.random() * Math.PI * 2;
                        const r = 0.6 + Math.random() * 0.1;
                        x = Math.cos(a)*r; y = (Math.random()-0.5)*0.03; z = Math.sin(a)*r;
                    } else {
                        const a = Math.random() * Math.PI * 2;
                        const r = 0.1 + Math.random() * 0.5;
                        x = Math.cos(a)*r; y = (Math.random()-0.5)*0.2; z = Math.sin(a)*r;
                    }

                    galaxyNodes.push({
                        id: n.id, label: n.label || n.id, type: n.type,
                        group: n.group, metadata: n.metadata || {},
                        x, y, z, baseX: x, baseY: y, baseZ: z,
                        orbitTarget: orbitTarget || null,
                        orbitRadius: orbitRadius || 0,
                        orbitSpeed: orbitSpeed || 0,
                        orbitAngle: orbitAngle || 0,
                        driftPhase: Math.random() * Math.PI * 2,
                        driftSpeed: 0.15 + Math.random() * 0.25,
                        pulsePhase: Math.random() * Math.PI * 2,
                        screenX: 0, screenY: 0, screenScale: 1
                    });
                });

                this.galaxyNodes = galaxyNodes;
                this.galaxyEdges = edges;
                const counts = {};
                galaxyNodes.forEach(n => { counts[n.type] = (counts[n.type] || 0) + 1; });
                this.typeCounts = counts;
            },

            applyFilters() {
                const vis = new Set(this.entityTypes.filter(t => t.visible).map(t => t.key));
                const s = this.searchTerm.toLowerCase();

                // Build set of connected node IDs when a node is selected
                this.connectedIds = new Set();
                if (this.selectedNode) {
                    this.connectedIds.add(this.selectedNode.id);
                    this.galaxyEdges.forEach(e => {
                        if (e.source === this.selectedNode.id) this.connectedIds.add(e.target);
                        if (e.target === this.selectedNode.id) this.connectedIds.add(e.source);
                    });
                }

                this.visibleNodes = this.galaxyNodes.filter(n => {
                    // Always show connected nodes when a node is selected
                    if (this.connectedIds.has(n.id)) return true;
                    if (!vis.has(n.type)) return false;
                    if (s && !n.label.toLowerCase().includes(s)) return false;
                    return true;
                });
            },

            togglePause() {
                this.paused = !this.paused;
                if (!this.paused && !this.animFrame) this.animate();
            },

            project(x, y, z, angle) {
                const rad = angle * Math.PI / 180;
                const cosA = Math.cos(rad), sinA = Math.sin(rad);
                const rx = x * cosA - z * sinA;
                const rz = x * sinA + z * cosA;
                const ry = y;
                const fov = 800, depth = 10;
                const denom = fov + rz * depth * 100;
                if (denom <= 0) return { sx: -999, sy: -999, scale: 0.01, z: rz, behind: true };
                const scale = Math.max(0.05, fov / denom);
                const cx = this.canvas.width / 2, cy = this.canvas.height / 2;
                const spread = Math.min(this.canvas.width, this.canvas.height) * 0.55;
                return { sx: cx + rx * spread * scale, sy: cy + ry * spread * scale, scale, z: rz };
            },

            animate() {
                if (this.paused) { this.animFrame = null; return; }
                const time = performance.now() / 1000;
                this.rotationAngle += 0.06 * this.speed;

                const nodeMap = {};
                this.galaxyNodes.forEach(n => nodeMap[n.id] = n);

                this.galaxyNodes.forEach(n => {
                    if (n.orbitTarget && nodeMap[n.orbitTarget]) {
                        const p = nodeMap[n.orbitTarget];
                        n.orbitAngle += n.orbitSpeed * 0.016 * this.speed;
                        n.x = p.x + Math.cos(n.orbitAngle) * n.orbitRadius;
                        n.y = p.y + Math.sin(n.orbitAngle * 0.7) * n.orbitRadius * 0.25;
                        n.z = p.z + Math.sin(n.orbitAngle) * n.orbitRadius;
                    } else if (n.type !== 'teacher' && n.type !== 'room' && n.type !== 'student') {
                        n.x = n.baseX + Math.sin(time * n.driftSpeed + n.driftPhase) * 0.01;
                        n.y = n.baseY + Math.cos(time * n.driftSpeed * 0.7 + n.driftPhase) * 0.008;
                        n.z = n.baseZ + Math.sin(time * n.driftSpeed * 0.5 + n.driftPhase + 1) * 0.01;
                    }
                });
                this.render(time);
                this.animFrame = requestAnimationFrame(() => this.animate());
            },

            render(time) {
                const ctx = this.ctx, W = this.canvas.width, H = this.canvas.height;
                if (!W || !H) return;

                ctx.fillStyle = '#0B1120';
                ctx.fillRect(0, 0, W, H);

                // Star dust
                this.starDust.forEach(s => {
                    const p = this.project(s.x, s.y, s.z, this.rotationAngle * 0.2);
                    if (p.behind || p.scale <= 0) return;
                    const a = s.brightness * (0.5 + 0.5 * Math.sin(time * 1.5 + s.x * 10));
                    ctx.fillStyle = `rgba(180,200,255,${a})`;
                    ctx.beginPath();
                    ctx.arc(p.sx, p.sy, Math.max(0.1, s.size * p.scale), 0, Math.PI * 2);
                    ctx.fill();
                });

                // Project visible nodes
                const projected = [];
                this.visibleNodes.forEach(n => {
                    const p = this.project(n.x, n.y, n.z, this.rotationAngle);
                    if (p.behind) return;
                    n.screenX = p.sx; n.screenY = p.sy; n.screenScale = p.scale;
                    projected.push({ node: n, sx: p.sx, sy: p.sy, scale: p.scale, z: p.z });
                });
                projected.sort((a, b) => b.z - a.z);

                // Constellation lines (teacher-student connections)
                const nodeMap = {};
                this.visibleNodes.forEach(n => nodeMap[n.id] = n);
                const visIds = new Set(this.visibleNodes.map(n => n.id));

                const hasSelection = !!this.selectedNode;
                this.galaxyEdges.forEach(e => {
                    const src = nodeMap[e.source], tgt = nodeMap[e.target];
                    if (!src || !tgt) return;
                    if (!visIds.has(e.source) || !visIds.has(e.target)) return;
                    const isSel = hasSelection && (e.source === this.selectedNode.id || e.target === this.selectedNode.id);
                    const isConstellation = (e.type === 'has_student' || e.type === 'teaches');

                    if (isSel) {
                        // Highlighted connection line for selected node
                        ctx.strokeStyle = 'rgba(96,165,250,0.8)';
                        ctx.lineWidth = 2;
                        ctx.shadowBlur = 6;
                        ctx.shadowColor = 'rgba(96,165,250,0.4)';
                    } else if (hasSelection) {
                        // Dim all other edges when something is selected
                        ctx.strokeStyle = 'rgba(100,116,139,0.03)';
                        ctx.lineWidth = 0.2;
                        ctx.shadowBlur = 0;
                    } else if (isConstellation) {
                        ctx.strokeStyle = 'rgba(251,191,36,0.12)';
                        ctx.lineWidth = 0.5;
                        ctx.shadowBlur = 0;
                    } else {
                        ctx.strokeStyle = 'rgba(100,116,139,0.04)';
                        ctx.lineWidth = 0.3;
                        ctx.shadowBlur = 0;
                    }
                    ctx.beginPath();
                    ctx.moveTo(src.screenX, src.screenY);
                    ctx.lineTo(tgt.screenX, tgt.screenY);
                    ctx.stroke();
                    ctx.shadowBlur = 0;
                });

                // Draw nodes
                projected.forEach(p => this.drawNode(ctx, p.node, p.sx, p.sy, p.scale, time));
            },

            drawNode(ctx, node, sx, sy, scale, time) {
                if (scale <= 0.01) return;
                const color = this.getColor(node.type);
                const isSel = this.selectedNode && this.selectedNode.id === node.id;
                const isHov = this.hoveredNode && this.hoveredNode.id === node.id;
                const isConnected = this.connectedIds.size > 0 && this.connectedIds.has(node.id);
                const isDimmed = this.selectedNode && !isConnected && !isSel;
                const pulse = Math.sin(time * 2 + node.pulsePhase) * 0.3 + 0.7;

                // Save context for global alpha dimming
                ctx.save();
                if (isDimmed) ctx.globalAlpha = 0.15;

                if (node.type === 'student') {
                    const baseR = isSel ? 4.5 : (isConnected ? 3.2 : 2.5);
                    const r = (baseR + pulse * (isSel ? 1.8 : 1.2)) * scale;
                    // Glow halo
                    const grad = ctx.createRadialGradient(sx, sy, 0, sx, sy, r * 2.5);
                    grad.addColorStop(0, color + (isSel ? 'aa' : '66'));
                    grad.addColorStop(0.6, color + '11');
                    grad.addColorStop(1, 'transparent');
                    ctx.fillStyle = grad;
                    ctx.beginPath();
                    ctx.arc(sx, sy, r * 2.5, 0, Math.PI * 2);
                    ctx.fill();
                    // Core
                    ctx.fillStyle = color;
                    ctx.beginPath();
                    ctx.arc(sx, sy, r, 0, Math.PI * 2);
                    ctx.fill();
                    // Bright center
                    ctx.fillStyle = '#E0EAFF';
                    ctx.beginPath();
                    ctx.arc(sx, sy, r * 0.35, 0, Math.PI * 2);
                    ctx.fill();
                    // Label on hover/select/connected
                    if ((isSel || isHov || isConnected) && scale > 0.3) {
                        ctx.fillStyle = isSel ? 'white' : (isConnected ? 'rgba(255,255,255,0.85)' : 'rgba(255,255,255,0.6)');
                        ctx.font = (isSel || isHov) ? `bold ${Math.max(10, 12 * scale)}px sans-serif` : `${Math.max(9, 10 * scale)}px sans-serif`;
                        ctx.textAlign = 'center';
                        ctx.fillText(node.label, sx, sy + r + 12 * scale);
                    }
                } else if (node.type === 'teacher') {
                    const baseR = isConnected ? 5 : 4;
                    const r = (baseR + pulse) * scale;
                    const grad = ctx.createRadialGradient(sx, sy, 0, sx, sy, r * 2.2);
                    grad.addColorStop(0, color + (isConnected ? 'cc' : '99'));
                    grad.addColorStop(0.5, color + '22');
                    grad.addColorStop(1, 'transparent');
                    ctx.fillStyle = grad;
                    ctx.beginPath();
                    ctx.arc(sx, sy, r * 2.2, 0, Math.PI * 2);
                    ctx.fill();
                    ctx.fillStyle = color;
                    ctx.beginPath();
                    ctx.arc(sx, sy, r, 0, Math.PI * 2);
                    ctx.fill();
                    ctx.fillStyle = '#FFFDE7';
                    ctx.beginPath();
                    ctx.arc(sx, sy, r * 0.3, 0, Math.PI * 2);
                    ctx.fill();
                    if (scale > 0.4 || isConnected) {
                        ctx.fillStyle = isConnected ? 'rgba(251,191,36,0.95)' : 'rgba(251,191,36,0.7)';
                        ctx.font = isConnected ? `bold ${Math.max(9, 11 * scale)}px sans-serif` : `${Math.max(8, 9 * scale)}px sans-serif`;
                        ctx.textAlign = 'center';
                        const lbl = node.label.length > 15 ? node.label.substring(0,13) + '..' : node.label;
                        ctx.fillText(lbl, sx, sy + r + 10 * scale);
                    }
                } else if (node.type === 'room') {
                    const r = (5 + pulse * 0.5) * scale;
                    const grad = ctx.createRadialGradient(sx, sy, 0, sx, sy, r * 1.6);
                    grad.addColorStop(0, color + '88');
                    grad.addColorStop(1, 'transparent');
                    ctx.fillStyle = grad;
                    ctx.beginPath();
                    ctx.arc(sx, sy, r * 1.6, 0, Math.PI * 2);
                    ctx.fill();
                    ctx.fillStyle = color;
                    ctx.beginPath();
                    ctx.arc(sx, sy, r, 0, Math.PI * 2);
                    ctx.fill();
                    if (scale > 0.35 || isConnected) {
                        ctx.fillStyle = isConnected ? 'rgba(236,72,153,0.95)' : 'rgba(236,72,153,0.8)';
                        ctx.font = `bold ${Math.max(8, 10 * scale)}px sans-serif`;
                        ctx.textAlign = 'center';
                        ctx.fillText(node.label.substring(0, 12), sx, sy + r + 12 * scale);
                    }
                } else if (node.type === 'assignment') {
                    const r = (isConnected ? 2 : 1.2) * scale;
                    ctx.fillStyle = color + (isConnected ? 'cc' : '77');
                    ctx.beginPath();
                    ctx.arc(sx, sy, r, 0, Math.PI * 2);
                    ctx.fill();
                    if (isConnected && scale > 0.4) {
                        ctx.fillStyle = color;
                        ctx.font = `${Math.max(8, 9 * scale)}px sans-serif`;
                        ctx.textAlign = 'center';
                        ctx.fillText(node.label.substring(0, 20), sx, sy + r + 8 * scale);
                    }
                } else if (node.type === 'assessment') {
                    const r = (isConnected ? 3.5 : 2.5) * scale;
                    ctx.fillStyle = color;
                    ctx.beginPath();
                    ctx.moveTo(sx, sy - r); ctx.lineTo(sx - r*0.7, sy + r*0.6); ctx.lineTo(sx + r*0.7, sy + r*0.6);
                    ctx.closePath(); ctx.fill();
                    if (isConnected && scale > 0.4) {
                        ctx.fillStyle = color;
                        ctx.font = `${Math.max(8, 9 * scale)}px sans-serif`;
                        ctx.textAlign = 'center';
                        ctx.fillText(node.label.substring(0, 20), sx, sy + r + 10 * scale);
                    }
                } else if (node.type === 'interview') {
                    const r = (isConnected ? 3.5 : 2.5) * scale;
                    ctx.fillStyle = color;
                    ctx.beginPath();
                    ctx.moveTo(sx, sy-r); ctx.lineTo(sx+r*0.7, sy); ctx.lineTo(sx, sy+r); ctx.lineTo(sx-r*0.7, sy);
                    ctx.closePath(); ctx.fill();
                    if (isConnected && scale > 0.4) {
                        ctx.fillStyle = color;
                        ctx.font = `${Math.max(8, 9 * scale)}px sans-serif`;
                        ctx.textAlign = 'center';
                        ctx.fillText(node.label.substring(0, 20), sx, sy + r + 10 * scale);
                    }
                } else if (node.type === 'employee') {
                    const r = (isConnected ? 3.5 : 2.5) * scale;
                    ctx.fillStyle = color;
                    ctx.beginPath();
                    ctx.moveTo(sx, sy-r); ctx.lineTo(sx+r*0.7, sy+r*0.3); ctx.lineTo(sx, sy-r*0.1); ctx.lineTo(sx-r*0.7, sy+r*0.3);
                    ctx.closePath(); ctx.fill();
                    if (isConnected && scale > 0.4) {
                        ctx.fillStyle = color;
                        ctx.font = `${Math.max(8, 9 * scale)}px sans-serif`;
                        ctx.textAlign = 'center';
                        ctx.fillText(node.label.substring(0, 20), sx, sy + r + 10 * scale);
                    }
                } else if (node.type === 'schedule') {
                    const r = 2 * scale;
                    ctx.fillStyle = color;
                    ctx.fillRect(sx-r, sy-r, r*2, r*2);
                } else {
                    const r = 1.2 * scale;
                    ctx.fillStyle = color;
                    ctx.beginPath(); ctx.arc(sx, sy, r, 0, Math.PI*2); ctx.fill();
                }

                ctx.restore(); // restore globalAlpha

                // Selection / hover ring (not dimmed)
                if (isSel || isHov) {
                    const r = (node.type === 'room' ? 8 : node.type === 'teacher' ? 7 : node.type === 'student' ? 6 : 4) * scale;
                    ctx.strokeStyle = isSel ? '#60A5FA' : 'rgba(255,255,255,0.4)';
                    ctx.lineWidth = isSel ? 2 : 1;
                    ctx.setLineDash(isSel ? [3, 3] : []);
                    ctx.beginPath(); ctx.arc(sx, sy, r, 0, Math.PI * 2); ctx.stroke();
                    ctx.setLineDash([]);
                    // Glow ring for selected
                    if (isSel) {
                        ctx.shadowBlur = 15;
                        ctx.shadowColor = '#60A5FA';
                        ctx.strokeStyle = 'rgba(96,165,250,0.3)';
                        ctx.lineWidth = 3;
                        ctx.beginPath(); ctx.arc(sx, sy, r * 1.4, 0, Math.PI * 2); ctx.stroke();
                        ctx.shadowBlur = 0;
                    }
                }
            },

            onMouseMove(event) {
                const rect = this.canvas.getBoundingClientRect();
                const mx = event.clientX - rect.left, my = event.clientY - rect.top;
                let found = null, minDist = Infinity;
                this.visibleNodes.forEach(n => {
                    const d = Math.sqrt((n.screenX-mx)**2 + (n.screenY-my)**2);
                    if (d < 15 && d < minDist) { minDist = d; found = n; }
                });
                this.hoveredNode = found;
                this.canvas.style.cursor = found ? 'pointer' : 'default';
                this.tooltipX = mx + 15;
                this.tooltipY = my - 10;
            },

            onCanvasClick(event) {
                if (this.hoveredNode) {
                    this.selectedNode = this.selectedNode?.id === this.hoveredNode.id ? null : { ...this.hoveredNode };
                } else {
                    this.selectedNode = null;
                }
                this.applyFilters(); // reveal/hide connected nodes
            }
        };
    }
    </script>
    """
    return render_page("Space Waymaker", content, "galaxy")


@app.get("/view/schedules", response_class=HTMLResponse)
async def view_schedules(request: Request):
    """Schedules view."""
    if not check_auth(request):
        return RedirectResponse(url="/login", status_code=302)
    content = """
    <div x-data="schedulesPage()" x-init="loadSchedules()">
        <div class="flex justify-between items-center mb-6">
            <h1 class="text-3xl font-bold text-gray-800">Class Schedules</h1>
            <input type="date" x-model="date" @change="loadSchedules()" class="px-4 py-2 border rounded-lg">
        </div>

        <div class="bg-white rounded-lg shadow overflow-hidden">
            <table class="min-w-full divide-y divide-gray-200">
                <thead class="bg-gray-50">
                    <tr>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Time Slot</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Room</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Teacher(s)</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Students</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Notes</th>
                    </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-200">
                    <template x-for="schedule in schedules" :key="schedule.id">
                        <tr class="hover:bg-gray-50">
                            <td class="px-6 py-4 whitespace-nowrap font-medium" x-text="schedule.time_slot || '—'"></td>
                            <td class="px-6 py-4 whitespace-nowrap text-gray-500" x-text="schedule.room || '—'"></td>
                            <td class="px-6 py-4">
                                <template x-for="teacher in (schedule.teachers || [])" :key="teacher">
                                    <span class="inline-block px-2 py-1 text-xs rounded bg-blue-100 text-blue-800 mr-1 mb-1" x-text="teacher"></span>
                                </template>
                            </td>
                            <td class="px-6 py-4">
                                <span class="text-sm" x-text="(schedule.students || []).length + ' students'"></span>
                            </td>
                            <td class="px-6 py-4 text-gray-500 text-sm max-w-xs truncate" x-text="schedule.notes || '—'"></td>
                        </tr>
                    </template>
                </tbody>
            </table>

            <div x-show="schedules.length === 0" class="p-8 text-center text-gray-500">
                <i class="fas fa-calendar-alt text-4xl mb-4"></i>
                <p>No schedules found for this date.</p>
            </div>
        </div>
    </div>

    <script>
        function schedulesPage() {
            return {
                schedules: [],
                date: new Date().toISOString().split('T')[0],

                async loadSchedules() {
                    try {
                        const res = await fetch(`/api/schedules?date=${this.date}`);
                        this.schedules = await res.json();
                    } catch (e) {
                        console.error('Failed to load schedules:', e);
                        this.schedules = [];
                    }
                }
            }
        }
    </script>
    """
    return render_page("Schedules", content, "schedules")


@app.get("/view/coaching", response_class=HTMLResponse)
async def view_coaching(request: Request):
    """Coaching records view."""
    if not check_auth(request):
        return RedirectResponse(url="/login", status_code=302)
    content = """
    <div x-data="coachingPage()" x-init="loadRecords()">
        <h1 class="text-3xl font-bold text-gray-800 mb-6">Coaching Records</h1>

        <div class="bg-white rounded-lg shadow overflow-hidden">
            <table class="min-w-full divide-y divide-gray-200">
                <thead class="bg-gray-50">
                    <tr>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Employee</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Offense</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Severity</th>
                        <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                    </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-200">
                    <template x-for="record in records" :key="record.id">
                        <tr class="hover:bg-gray-50 cursor-pointer" @click="viewRecord(record)">
                            <td class="px-6 py-4 whitespace-nowrap font-medium" x-text="record.employee_name || '—'"></td>
                            <td class="px-6 py-4 whitespace-nowrap text-gray-500" x-text="record.date || '—'"></td>
                            <td class="px-6 py-4 whitespace-nowrap">
                                <span class="px-2 py-1 text-xs rounded-full"
                                    :class="{
                                        'bg-yellow-100 text-yellow-800': record.coaching_type === 'verbal',
                                        'bg-orange-100 text-orange-800': record.coaching_type === 'written',
                                        'bg-red-100 text-red-800': record.coaching_type === 'final'
                                    }"
                                    x-text="record.coaching_type || '—'"></span>
                            </td>
                            <td class="px-6 py-4 text-gray-500" x-text="record.offense_name || '—'"></td>
                            <td class="px-6 py-4">
                                <span class="px-2 py-1 text-xs rounded-full"
                                    :class="{
                                        'bg-green-100 text-green-800': record.offense_severity === 'minor',
                                        'bg-yellow-100 text-yellow-800': record.offense_severity === 'moderate',
                                        'bg-red-100 text-red-800': record.offense_severity === 'severe'
                                    }"
                                    x-text="record.offense_severity || '—'"></span>
                            </td>
                            <td class="px-6 py-4">
                                <span x-show="record.employee_acknowledged" class="text-green-600"><i class="fas fa-check"></i> Acknowledged</span>
                                <span x-show="!record.employee_acknowledged" class="text-gray-400"><i class="fas fa-clock"></i> Pending</span>
                            </td>
                        </tr>
                    </template>
                </tbody>
            </table>

            <div x-show="records.length === 0" class="p-8 text-center text-gray-500">
                <i class="fas fa-comments text-4xl mb-4"></i>
                <p>No coaching records found.</p>
            </div>
        </div>
    </div>

    <script>
        function coachingPage() {
            return {
                records: [],

                async loadRecords() {
                    try {
                        const res = await fetch('/api/coaching?limit=50');
                        this.records = await res.json();
                    } catch (e) {
                        console.error('Failed to load coaching records:', e);
                        this.records = [];
                    }
                },

                viewRecord(record) {
                    // Could open a modal with full details
                    console.log('View record:', record);
                }
            }
        }
    </script>
    """
    return render_page("Coaching", content, "coaching")


@app.get("/view/apps", response_class=HTMLResponse)
async def view_apps(request: Request):
    """App marketplace view."""
    if not check_auth(request):
        return RedirectResponse(url="/login", status_code=302)
    content = """
    <div x-data="appsPage()" x-init="loadApps()">
        <h1 class="text-3xl font-bold text-gray-800 mb-6">Educational Apps Marketplace</h1>

        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            <template x-for="app in apps" :key="app.id">
                <div class="bg-white rounded-lg shadow overflow-hidden hover:shadow-lg transition">
                    <div class="h-40 bg-gradient-to-br from-blue-400 to-purple-500 flex items-center justify-center">
                        <i class="fas fa-graduation-cap text-white text-5xl"></i>
                    </div>
                    <div class="p-6">
                        <div class="flex justify-between items-start mb-2">
                            <h3 class="font-semibold text-lg" x-text="app.title"></h3>
                            <div class="flex items-center text-yellow-500">
                                <i class="fas fa-star text-sm"></i>
                                <span class="ml-1 text-sm text-gray-600" x-text="app.rating?.toFixed(1) || '—'"></span>
                            </div>
                        </div>

                        <p class="text-gray-500 text-sm mb-3 line-clamp-2" x-text="app.description"></p>

                        <div class="flex flex-wrap gap-1 mb-3">
                            <span class="px-2 py-0.5 text-xs rounded bg-blue-100 text-blue-800" x-text="app.category"></span>
                            <span class="px-2 py-0.5 text-xs rounded bg-green-100 text-green-800" x-text="app.student_levels"></span>
                        </div>

                        <div class="flex justify-between items-center">
                            <span class="text-sm text-gray-500">By <span x-text="app.teacher_name"></span></span>
                            <a :href="app.app_link" target="_blank" class="text-blue-600 hover:text-blue-800 text-sm">
                                Open <i class="fas fa-external-link-alt ml-1"></i>
                            </a>
                        </div>
                    </div>
                </div>
            </template>
        </div>

        <div x-show="apps.length === 0" class="bg-white rounded-lg shadow p-8 text-center text-gray-500">
            <i class="fas fa-th-large text-4xl mb-4"></i>
            <p>No apps found in the marketplace.</p>
        </div>
    </div>

    <script>
        function appsPage() {
            return {
                apps: [],

                async loadApps() {
                    try {
                        const res = await fetch('/api/apps?limit=50');
                        this.apps = await res.json();
                    } catch (e) {
                        console.error('Failed to load apps:', e);
                        this.apps = [];
                    }
                }
            }
        }
    </script>
    """
    return render_page("App Marketplace", content, "apps")


@app.get("/view/databases", response_class=HTMLResponse)
async def view_databases(request: Request):
    """Database Explorer - View raw database tables."""
    if not check_auth(request):
        return RedirectResponse(url="/login", status_code=302)
    content = """
    <div x-data="databaseExplorer()" x-init="loadDatabases()">
        <div class="flex justify-between items-center mb-6">
            <h1 class="text-3xl font-bold text-gray-800">Database Explorer</h1>
            <button @click="loadDatabases()" class="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">
                <i class="fas fa-refresh mr-2"></i> Refresh
            </button>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-4 gap-6">
            <!-- Sidebar - Database List -->
            <div class="lg:col-span-1">
                <div class="bg-white rounded-lg shadow p-4">
                    <h2 class="font-semibold text-lg mb-4">Data Sources</h2>
                    <div class="space-y-2">
                        <template x-for="db in databases" :key="db.id">
                            <div class="border rounded-lg overflow-hidden">
                                <button @click="toggleDb(db.id)"
                                    class="w-full px-3 py-2 text-left text-sm font-medium flex justify-between items-center hover:bg-gray-50"
                                    :class="expandedDb === db.id ? 'bg-blue-50 text-blue-700' : 'bg-white'">
                                    <span class="flex items-center">
                                        <i class="fas fa-database mr-2" :class="db.type === 'postgresql' ? 'text-blue-500' : 'text-green-500'"></i>
                                        <span x-text="db.name"></span>
                                    </span>
                                    <i class="fas" :class="expandedDb === db.id ? 'fa-chevron-down' : 'fa-chevron-right'"></i>
                                </button>
                                <div x-show="expandedDb === db.id" x-collapse class="border-t bg-gray-50">
                                    <template x-for="table in db.tables" :key="table">
                                        <button @click="loadTable(db.id, table)"
                                            class="w-full px-4 py-2 text-left text-sm hover:bg-gray-100 flex items-center"
                                            :class="selectedTable === db.id + '.' + table ? 'bg-blue-100 text-blue-700 font-medium' : ''">
                                            <i class="fas fa-table mr-2 text-gray-400"></i>
                                            <span x-text="table"></span>
                                        </button>
                                    </template>
                                </div>
                            </div>
                        </template>
                    </div>

                    <div x-show="databases.length === 0" class="text-gray-500 text-sm text-center py-4">
                        <i class="fas fa-spinner fa-spin mr-2"></i> Loading databases...
                    </div>
                </div>
            </div>

            <!-- Main Content - Table Data -->
            <div class="lg:col-span-3">
                <div class="bg-white rounded-lg shadow">
                    <!-- Table Header -->
                    <div class="p-4 border-b flex justify-between items-center">
                        <div>
                            <h2 class="font-semibold text-lg" x-text="currentTableName || 'Select a table'"></h2>
                            <p class="text-sm text-gray-500" x-show="tableData.length > 0">
                                <span x-text="tableData.length"></span> rows
                                <span x-show="totalRows > tableData.length"> of <span x-text="totalRows"></span></span>
                            </p>
                        </div>
                        <div class="flex gap-2" x-show="currentTableName">
                            <input type="text" x-model="searchQuery" @input.debounce.300ms="filterTable()"
                                placeholder="Filter rows..."
                                class="px-3 py-1 text-sm border rounded focus:outline-none focus:ring-2 focus:ring-blue-500">
                            <select x-model="pageSize" @change="loadTable(currentDb, currentTable)" class="px-3 py-1 text-sm border rounded">
                                <option value="25">25 rows</option>
                                <option value="50">50 rows</option>
                                <option value="100">100 rows</option>
                                <option value="500">500 rows</option>
                            </select>
                        </div>
                    </div>

                    <!-- Table Content -->
                    <div class="overflow-x-auto">
                        <div x-show="loading" class="p-8 text-center">
                            <i class="fas fa-spinner fa-spin text-3xl text-blue-500 mb-4"></i>
                            <p class="text-gray-500">Loading table data...</p>
                        </div>

                        <div x-show="!loading && !currentTableName" class="p-8 text-center text-gray-500">
                            <i class="fas fa-arrow-left text-4xl mb-4"></i>
                            <p>Select a database and table from the sidebar to view its data</p>
                        </div>

                        <div x-show="!loading && currentTableName && tableData.length === 0" class="p-8 text-center text-gray-500">
                            <i class="fas fa-inbox text-4xl mb-4"></i>
                            <p>No data found in this table</p>
                        </div>

                        <table x-show="!loading && tableData.length > 0" class="min-w-full divide-y divide-gray-200">
                            <thead class="bg-gray-50 sticky top-0">
                                <tr>
                                    <template x-for="col in columns" :key="col">
                                        <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap cursor-pointer hover:bg-gray-100"
                                            @click="sortBy(col)">
                                            <span x-text="col"></span>
                                            <i x-show="sortColumn === col" class="fas ml-1"
                                                :class="sortDirection === 'asc' ? 'fa-sort-up' : 'fa-sort-down'"></i>
                                        </th>
                                    </template>
                                </tr>
                            </thead>
                            <tbody class="bg-white divide-y divide-gray-200">
                                <template x-for="(row, idx) in filteredData" :key="idx">
                                    <tr class="hover:bg-gray-50">
                                        <template x-for="col in columns" :key="col">
                                            <td class="px-4 py-3 text-sm text-gray-900 max-w-xs truncate" :title="String(row[col] ?? '')">
                                                <span x-text="formatValue(row[col])"></span>
                                            </td>
                                        </template>
                                    </tr>
                                </template>
                            </tbody>
                        </table>
                    </div>

                    <!-- Pagination -->
                    <div x-show="totalRows > tableData.length" class="p-4 border-t flex justify-between items-center">
                        <span class="text-sm text-gray-500">
                            Showing <span x-text="(currentPage - 1) * pageSize + 1"></span>-<span x-text="Math.min(currentPage * pageSize, totalRows)"></span> of <span x-text="totalRows"></span>
                        </span>
                        <div class="flex gap-2">
                            <button @click="prevPage()" :disabled="currentPage <= 1"
                                class="px-3 py-1 text-sm border rounded disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50">
                                <i class="fas fa-chevron-left"></i> Previous
                            </button>
                            <button @click="nextPage()" :disabled="currentPage * pageSize >= totalRows"
                                class="px-3 py-1 text-sm border rounded disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50">
                                Next <i class="fas fa-chevron-right"></i>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        function databaseExplorer() {
            return {
                databases: [],
                expandedDb: null,
                selectedTable: null,
                currentDb: null,
                currentTable: null,
                currentTableName: null,
                tableData: [],
                filteredData: [],
                columns: [],
                loading: false,
                searchQuery: '',
                sortColumn: null,
                sortDirection: 'asc',
                pageSize: 50,
                currentPage: 1,
                totalRows: 0,

                async loadDatabases() {
                    try {
                        const res = await fetch('/api/databases');
                        this.databases = await res.json();
                        if (this.databases.length > 0) {
                            this.expandedDb = this.databases[0].id;
                        }
                    } catch (e) {
                        console.error('Failed to load databases:', e);
                    }
                },

                toggleDb(dbId) {
                    this.expandedDb = this.expandedDb === dbId ? null : dbId;
                },

                async loadTable(dbId, tableName) {
                    this.loading = true;
                    this.currentDb = dbId;
                    this.currentTable = tableName;
                    this.selectedTable = dbId + '.' + tableName;
                    this.currentTableName = tableName;
                    this.searchQuery = '';
                    this.sortColumn = null;

                    try {
                        const res = await fetch(`/api/databases/${dbId}/tables/${tableName}?limit=${this.pageSize}&offset=${(this.currentPage - 1) * this.pageSize}`);
                        const data = await res.json();
                        this.tableData = data.rows || [];
                        this.columns = data.columns || [];
                        this.totalRows = data.total || this.tableData.length;
                        this.filteredData = [...this.tableData];
                    } catch (e) {
                        console.error('Failed to load table:', e);
                        this.tableData = [];
                        this.columns = [];
                    } finally {
                        this.loading = false;
                    }
                },

                filterTable() {
                    if (!this.searchQuery) {
                        this.filteredData = [...this.tableData];
                        return;
                    }
                    const query = this.searchQuery.toLowerCase();
                    this.filteredData = this.tableData.filter(row =>
                        this.columns.some(col =>
                            String(row[col] ?? '').toLowerCase().includes(query)
                        )
                    );
                },

                sortBy(col) {
                    if (this.sortColumn === col) {
                        this.sortDirection = this.sortDirection === 'asc' ? 'desc' : 'asc';
                    } else {
                        this.sortColumn = col;
                        this.sortDirection = 'asc';
                    }

                    this.filteredData.sort((a, b) => {
                        let valA = a[col] ?? '';
                        let valB = b[col] ?? '';

                        if (typeof valA === 'number' && typeof valB === 'number') {
                            return this.sortDirection === 'asc' ? valA - valB : valB - valA;
                        }

                        valA = String(valA).toLowerCase();
                        valB = String(valB).toLowerCase();

                        if (this.sortDirection === 'asc') {
                            return valA < valB ? -1 : valA > valB ? 1 : 0;
                        } else {
                            return valA > valB ? -1 : valA < valB ? 1 : 0;
                        }
                    });
                },

                formatValue(val) {
                    if (val === null || val === undefined) return '—';
                    if (typeof val === 'boolean') return val ? 'Yes' : 'No';
                    if (typeof val === 'object') return JSON.stringify(val);
                    const str = String(val);
                    return str.length > 100 ? str.substring(0, 100) + '...' : str;
                },

                prevPage() {
                    if (this.currentPage > 1) {
                        this.currentPage--;
                        this.loadTable(this.currentDb, this.currentTable);
                    }
                },

                nextPage() {
                    if (this.currentPage * this.pageSize < this.totalRows) {
                        this.currentPage++;
                        this.loadTable(this.currentDb, this.currentTable);
                    }
                }
            }
        }
    </script>
    """
    return render_page("Database Explorer", content, "databases")


# ============================================================================
# ONTOLOGY VIEW ROUTES
# ============================================================================

@app.get("/view/skills", response_class=HTMLResponse)
async def view_skills(request: Request):
    """Skills Taxonomy view - hierarchical view of all skills."""
    if not check_auth(request):
        return RedirectResponse(url="/login", status_code=302)

    content = """
    <div x-data="skillsView()" x-init="loadData()">
        <div class="flex justify-between items-center mb-6">
            <div>
                <h1 class="text-3xl font-bold text-gray-800">Skills Taxonomy</h1>
                <p class="text-gray-500 text-sm mt-1">Hierarchical view of all curriculum skills</p>
            </div>
            <div class="flex gap-2">
                <button @click="viewMode = 'tree'" :class="viewMode === 'tree' ? 'bg-blue-600 text-white' : 'bg-gray-200'" class="px-4 py-2 rounded">
                    <i class="fas fa-sitemap mr-2"></i>Tree View
                </button>
                <button @click="viewMode = 'list'" :class="viewMode === 'list' ? 'bg-blue-600 text-white' : 'bg-gray-200'" class="px-4 py-2 rounded">
                    <i class="fas fa-list mr-2"></i>List View
                </button>
            </div>
        </div>

        <!-- Stats Cards -->
        <div class="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
            <div class="bg-white rounded-lg shadow p-4">
                <p class="text-gray-500 text-sm">Domains</p>
                <p class="text-2xl font-bold" x-text="stats.total_domains || 0"></p>
            </div>
            <div class="bg-white rounded-lg shadow p-4">
                <p class="text-gray-500 text-sm">Categories</p>
                <p class="text-2xl font-bold" x-text="stats.total_categories || 0"></p>
            </div>
            <div class="bg-white rounded-lg shadow p-4">
                <p class="text-gray-500 text-sm">Total Skills</p>
                <p class="text-2xl font-bold" x-text="stats.total_skills || 0"></p>
            </div>
            <div class="bg-white rounded-lg shadow p-4">
                <p class="text-gray-500 text-sm">Core Skills</p>
                <p class="text-2xl font-bold text-blue-600" x-text="stats.core_skills || 0"></p>
            </div>
            <div class="bg-white rounded-lg shadow p-4">
                <p class="text-gray-500 text-sm">Content Links</p>
                <p class="text-2xl font-bold text-green-600" x-text="stats.content_links || 0"></p>
            </div>
        </div>

        <!-- Tree View -->
        <div x-show="viewMode === 'tree'" class="space-y-4">
            <template x-for="domain in tree" :key="domain.id">
                <div class="bg-white rounded-lg shadow overflow-hidden">
                    <div class="p-4 cursor-pointer flex items-center justify-between"
                         :style="'background-color: ' + (domain.color || '#1976d2') + '20'"
                         @click="domain.expanded = !domain.expanded">
                        <div class="flex items-center gap-3">
                            <i class="fas fa-layer-group text-xl" :style="'color: ' + (domain.color || '#1976d2')"></i>
                            <div>
                                <h3 class="font-semibold text-lg" x-text="domain.name"></h3>
                                <p class="text-sm text-gray-500" x-text="domain.description"></p>
                            </div>
                        </div>
                        <div class="flex items-center gap-4">
                            <span class="text-sm text-gray-500" x-text="(domain.categories?.length || 0) + ' categories'"></span>
                            <i class="fas" :class="domain.expanded ? 'fa-chevron-up' : 'fa-chevron-down'"></i>
                        </div>
                    </div>

                    <div x-show="domain.expanded" x-collapse class="border-t">
                        <template x-for="category in domain.categories" :key="category.id">
                            <div class="border-b last:border-b-0">
                                <div class="p-3 pl-8 cursor-pointer flex items-center justify-between bg-gray-50"
                                     @click="category.expanded = !category.expanded">
                                    <div class="flex items-center gap-2">
                                        <i class="fas fa-folder" :style="'color: ' + (category.color || '#666')"></i>
                                        <span class="font-medium" x-text="category.name"></span>
                                        <span class="text-xs bg-gray-200 px-2 py-1 rounded" x-text="category.skills?.length + ' skills'"></span>
                                    </div>
                                    <i class="fas" :class="category.expanded ? 'fa-chevron-up' : 'fa-chevron-down'"></i>
                                </div>

                                <div x-show="category.expanded" x-collapse class="bg-white">
                                    <template x-for="skill in category.skills" :key="skill.id">
                                        <div class="p-3 pl-16 border-t flex items-center justify-between hover:bg-blue-50">
                                            <div class="flex items-center gap-3">
                                                <i class="fas fa-check-circle" :class="skill.is_core_skill ? 'text-blue-500' : 'text-gray-300'"></i>
                                                <div>
                                                    <span class="font-medium" x-text="skill.name"></span>
                                                    <span class="text-xs text-gray-400 ml-2" x-text="skill.code"></span>
                                                    <p class="text-xs text-gray-500" x-text="skill.description?.substring(0, 80) + '...'"></p>
                                                </div>
                                            </div>
                                            <div class="flex items-center gap-2 text-xs">
                                                <span x-show="skill.cefr_level" class="bg-purple-100 text-purple-700 px-2 py-1 rounded" x-text="skill.cefr_level"></span>
                                                <span x-show="skill.estimated_hours" class="bg-gray-100 px-2 py-1 rounded" x-text="skill.estimated_hours + 'h'"></span>
                                            </div>
                                        </div>
                                    </template>
                                </div>
                            </div>
                        </template>
                    </div>
                </div>
            </template>
        </div>

        <!-- List View -->
        <div x-show="viewMode === 'list'" class="bg-white rounded-lg shadow overflow-hidden">
            <table class="w-full">
                <thead class="bg-gray-50">
                    <tr>
                        <th class="px-4 py-3 text-left text-sm font-medium text-gray-500">Skill</th>
                        <th class="px-4 py-3 text-left text-sm font-medium text-gray-500">Category</th>
                        <th class="px-4 py-3 text-left text-sm font-medium text-gray-500">Level</th>
                        <th class="px-4 py-3 text-left text-sm font-medium text-gray-500">Age Range</th>
                        <th class="px-4 py-3 text-left text-sm font-medium text-gray-500">Hours</th>
                        <th class="px-4 py-3 text-left text-sm font-medium text-gray-500">Core</th>
                    </tr>
                </thead>
                <tbody>
                    <template x-for="skill in skills" :key="skill.id">
                        <tr class="border-t hover:bg-gray-50">
                            <td class="px-4 py-3">
                                <div class="font-medium" x-text="skill.name"></div>
                                <div class="text-xs text-gray-400" x-text="skill.code"></div>
                            </td>
                            <td class="px-4 py-3 text-sm" x-text="skill.category_code"></td>
                            <td class="px-4 py-3">
                                <span x-show="skill.cefr_level" class="text-xs bg-purple-100 text-purple-700 px-2 py-1 rounded" x-text="skill.cefr_level"></span>
                            </td>
                            <td class="px-4 py-3 text-sm" x-text="skill.target_age_min && skill.target_age_max ? skill.target_age_min + '-' + skill.target_age_max : '-'"></td>
                            <td class="px-4 py-3 text-sm" x-text="skill.estimated_hours || '-'"></td>
                            <td class="px-4 py-3">
                                <i class="fas fa-star" :class="skill.is_core_skill ? 'text-yellow-500' : 'text-gray-200'"></i>
                            </td>
                        </tr>
                    </template>
                </tbody>
            </table>
        </div>
    </div>

    <script>
        function skillsView() {
            return {
                viewMode: 'tree',
                stats: {},
                tree: [],
                skills: [],

                async loadData() {
                    try {
                        const [statsRes, treeRes, skillsRes] = await Promise.all([
                            fetch('/api/skills/stats'),
                            fetch('/api/skills/tree'),
                            fetch('/api/skills/list')
                        ]);

                        this.stats = await statsRes.json();
                        this.tree = (await treeRes.json()).map(d => ({...d, expanded: false, categories: d.categories?.map(c => ({...c, expanded: false}))}));
                        this.skills = await skillsRes.json();
                    } catch (e) {
                        console.error('Failed to load skills data:', e);
                    }
                }
            }
        }
    </script>
    """
    return render_page("Skills Taxonomy", content, "skills")


@app.get("/view/progress", response_class=HTMLResponse)
async def view_progress(request: Request):
    """Learning Progress view - student skill progress tracking."""
    if not check_auth(request):
        return RedirectResponse(url="/login", status_code=302)

    content = """
    <div x-data="progressView()" x-init="loadData()">
        <div class="flex justify-between items-center mb-6">
            <div>
                <h1 class="text-3xl font-bold text-gray-800">Learning Progress</h1>
                <p class="text-gray-500 text-sm mt-1">Track student skill development and mastery</p>
            </div>
        </div>

        <!-- Student Selection -->
        <div class="bg-white rounded-lg shadow p-4 mb-6">
            <div class="flex flex-wrap items-center gap-4">
                <div class="flex-1 min-w-64">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Select Student</label>
                    <select x-model="selectedStudent" @change="loadStudentData()"
                            class="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
                        <option value="">All Students</option>
                        <template x-for="s in students" :key="s.student_id">
                            <option :value="s.student_id" x-text="s.student_name + ' (' + s.skill_count + ' skills, ' + s.avg_progress + '%)'"></option>
                        </template>
                    </select>
                </div>
                <div x-show="selectedStudent" class="flex items-center gap-2 mt-4 md:mt-0">
                    <a :href="'/view/profiles?student=' + encodeURIComponent(selectedStudent)"
                       class="text-sm bg-blue-100 text-blue-700 hover:bg-blue-200 px-3 py-1.5 rounded-lg flex items-center gap-1">
                        <i class="fas fa-user"></i> View Full Profile
                    </a>
                    <button @click="selectedStudent = ''; loadStudentData()"
                            class="text-sm bg-gray-100 text-gray-600 hover:bg-gray-200 px-3 py-1.5 rounded-lg">
                        <i class="fas fa-times"></i> Clear
                    </button>
                </div>
                <div x-show="loading" class="flex items-center text-gray-500 text-sm">
                    <i class="fas fa-spinner fa-spin mr-2"></i> Loading...
                </div>
            </div>

            <!-- Selected Student Summary -->
            <div x-show="selectedStudent && studentSummary.total_skills > 0" class="mt-4 pt-4 border-t">
                <div class="grid grid-cols-2 md:grid-cols-5 gap-4 text-center">
                    <div>
                        <p class="text-2xl font-bold text-gray-800" x-text="studentSummary.total_skills || 0"></p>
                        <p class="text-xs text-gray-500">Skills Tracked</p>
                    </div>
                    <div>
                        <p class="text-2xl font-bold text-green-600" x-text="studentSummary.mastered || 0"></p>
                        <p class="text-xs text-gray-500">Mastered</p>
                    </div>
                    <div>
                        <p class="text-2xl font-bold text-yellow-600" x-text="studentSummary.in_progress || 0"></p>
                        <p class="text-xs text-gray-500">In Progress</p>
                    </div>
                    <div>
                        <p class="text-2xl font-bold text-red-600" x-text="studentSummary.needs_work || 0"></p>
                        <p class="text-xs text-gray-500">Needs Work</p>
                    </div>
                    <div>
                        <p class="text-2xl font-bold text-blue-600" x-text="(studentSummary.avg_progress || 0).toFixed(1) + '%'"></p>
                        <p class="text-xs text-gray-500">Avg Progress</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- Stats -->
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div class="bg-white rounded-lg shadow p-4">
                <p class="text-gray-500 text-sm">Students Tracked</p>
                <p class="text-2xl font-bold" x-text="stats.students_with_progress || 0"></p>
            </div>
            <div class="bg-white rounded-lg shadow p-4">
                <p class="text-gray-500 text-sm">Skills Mastered</p>
                <p class="text-2xl font-bold text-green-600" x-text="stats.mastery_records || 0"></p>
            </div>
            <div class="bg-white rounded-lg shadow p-4">
                <p class="text-gray-500 text-sm">Recommendations</p>
                <p class="text-2xl font-bold text-blue-600" x-text="stats.active_recommendations || 0"></p>
            </div>
            <div class="bg-white rounded-lg shadow p-4">
                <p class="text-gray-500 text-sm">Achievements</p>
                <p class="text-2xl font-bold text-yellow-600" x-text="stats.total_achievements || 0"></p>
            </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <!-- Progress Records -->
            <div class="bg-white rounded-lg shadow">
                <div class="p-4 border-b flex justify-between items-center">
                    <h2 class="font-semibold">
                        <span x-show="!selectedStudent">Recent Skill Progress</span>
                        <span x-show="selectedStudent">Skill Progress for <span class="text-blue-600" x-text="students.find(s => s.student_id === selectedStudent)?.student_name || selectedStudent"></span></span>
                    </h2>
                    <span class="text-sm text-gray-500" x-text="progress.length + ' records'"></span>
                </div>
                <div class="divide-y max-h-96 overflow-y-auto">
                    <!-- Empty state -->
                    <div x-show="progress.length === 0 && !loading" class="p-8 text-center text-gray-500">
                        <i class="fas fa-chart-line text-4xl mb-3 text-gray-300"></i>
                        <p x-show="selectedStudent">No skill progress data found for this student.</p>
                        <p x-show="!selectedStudent">No skill progress data available.</p>
                    </div>
                    <template x-for="p in progress" :key="p.student_id + p.skill_code">
                        <div class="p-4 hover:bg-gray-50">
                            <div class="flex justify-between items-start mb-2">
                                <div>
                                    <span x-show="!selectedStudent" class="font-medium" x-text="p.student_name || p.student_id"></span>
                                    <span x-show="selectedStudent" class="font-medium" x-text="p.skill_name"></span>
                                    <span x-show="!selectedStudent" class="text-xs text-gray-400 ml-2" x-text="p.skill_name"></span>
                                    <span x-show="selectedStudent" class="text-xs text-gray-400 ml-2" x-text="p.domain_code + ' / ' + p.category_code"></span>
                                </div>
                                <span class="text-xs px-2 py-1 rounded"
                                      :class="p.trend_direction === 'improving' ? 'bg-green-100 text-green-700' :
                                              p.trend_direction === 'declining' ? 'bg-red-100 text-red-700' : 'bg-gray-100 text-gray-700'"
                                      x-text="p.trend_direction || 'stable'"></span>
                            </div>
                            <div class="flex items-center gap-2">
                                <div class="flex-1 bg-gray-200 rounded-full h-2">
                                    <div class="h-2 rounded-full"
                                         :class="p.progress_percentage >= 85 ? 'bg-green-500' :
                                                 p.progress_percentage >= 50 ? 'bg-yellow-500' : 'bg-red-500'"
                                         :style="'width: ' + p.progress_percentage + '%'"></div>
                                </div>
                                <span class="text-sm font-medium" x-text="Math.round(p.progress_percentage) + '%'"></span>
                            </div>
                            <div class="mt-1 text-xs text-gray-400" x-text="'Level: ' + (p.current_level || 'Not set')"></div>
                        </div>
                    </template>
                </div>
            </div>

            <!-- Recommendations -->
            <div class="bg-white rounded-lg shadow">
                <div class="p-4 border-b flex justify-between items-center">
                    <h2 class="font-semibold">
                        <span x-show="!selectedStudent">Learning Recommendations</span>
                        <span x-show="selectedStudent">Recommendations for <span class="text-blue-600" x-text="students.find(s => s.student_id === selectedStudent)?.student_name || selectedStudent"></span></span>
                    </h2>
                    <span class="text-sm text-gray-500" x-text="recommendations.length + ' active'"></span>
                </div>
                <div class="divide-y max-h-96 overflow-y-auto">
                    <!-- Empty state -->
                    <div x-show="recommendations.length === 0 && !loading" class="p-8 text-center text-gray-500">
                        <i class="fas fa-lightbulb text-4xl mb-3 text-gray-300"></i>
                        <p x-show="selectedStudent">No recommendations for this student.</p>
                        <p x-show="!selectedStudent">No active recommendations.</p>
                    </div>
                    <template x-for="r in recommendations" :key="r.id">
                        <div class="p-4 hover:bg-gray-50">
                            <div class="flex items-start gap-3">
                                <i class="fas mt-1"
                                   :class="r.recommendation_type === 'skill' ? 'fa-graduation-cap text-blue-500' :
                                           r.recommendation_type === 'class' ? 'fa-chalkboard text-green-500' :
                                           r.recommendation_type === 'book' ? 'fa-book text-purple-500' : 'fa-lightbulb text-yellow-500'"></i>
                                <div class="flex-1">
                                    <div class="font-medium" x-text="r.target_name || 'Recommendation'"></div>
                                    <div class="text-sm text-gray-500" x-text="r.reason"></div>
                                    <div class="text-xs text-gray-400 mt-1" x-show="!selectedStudent">
                                        Student: <span x-text="r.student_id"></span>
                                        | Priority: <span x-text="Math.round(r.priority_score)"></span>
                                    </div>
                                    <div class="text-xs text-gray-400 mt-1" x-show="selectedStudent">
                                        Priority: <span x-text="Math.round(r.priority_score)"></span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </template>
                </div>
            </div>
        </div>

        <!-- Achievements -->
        <div class="mt-6 bg-white rounded-lg shadow">
            <div class="p-4 border-b">
                <h2 class="font-semibold">Available Achievements</h2>
            </div>
            <div class="p-4 grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
                <template x-for="a in achievements" :key="a.id">
                    <div class="text-center p-3 rounded-lg hover:bg-gray-50">
                        <div class="w-12 h-12 mx-auto rounded-full flex items-center justify-center"
                             :style="'background-color: ' + (a.color || '#666') + '20'">
                            <i class="fas text-xl" :class="a.icon || 'fa-award'" :style="'color: ' + (a.color || '#666')"></i>
                        </div>
                        <div class="mt-2 font-medium text-sm" x-text="a.name"></div>
                        <div class="text-xs text-gray-400" x-text="a.points + ' pts'"></div>
                    </div>
                </template>
            </div>
        </div>
    </div>

    <script>
        function progressView() {
            return {
                stats: {},
                progress: [],
                recommendations: [],
                achievements: [],
                students: [],
                selectedStudent: '',
                studentSummary: {},
                loading: false,

                async loadData() {
                    this.loading = true;
                    try {
                        // Load students with skill data and general stats
                        const [studentsRes, statsRes, achieveRes] = await Promise.all([
                            fetch('/api/skills/students'),
                            fetch('/api/skills/stats'),
                            fetch('/api/skills/achievements')
                        ]);

                        this.students = await studentsRes.json();
                        this.stats = await statsRes.json();
                        this.achievements = await achieveRes.json();

                        console.log('Loaded students:', this.students.length);

                        // Load all progress initially
                        await this.loadStudentData();
                    } catch (e) {
                        console.error('Failed to load progress data:', e);
                    }
                    this.loading = false;
                },

                async loadStudentData() {
                    this.loading = true;
                    try {
                        const studentParam = this.selectedStudent ? `&student_id=${encodeURIComponent(this.selectedStudent)}` : '';

                        const [progressRes, recsRes] = await Promise.all([
                            fetch(`/api/skills/progress?limit=100${studentParam}`),
                            fetch(`/api/skills/recommendations?limit=20${studentParam}`)
                        ]);

                        this.progress = await progressRes.json();
                        this.recommendations = await recsRes.json();

                        // Calculate summary for selected student
                        if (this.selectedStudent && this.progress.length > 0) {
                            const mastered = this.progress.filter(p => p.progress_percentage >= 85).length;
                            const inProgress = this.progress.filter(p => p.progress_percentage >= 40 && p.progress_percentage < 85).length;
                            const needsWork = this.progress.filter(p => p.progress_percentage < 40).length;
                            const avgProgress = this.progress.reduce((sum, p) => sum + (p.progress_percentage || 0), 0) / this.progress.length;

                            this.studentSummary = {
                                total_skills: this.progress.length,
                                mastered: mastered,
                                in_progress: inProgress,
                                needs_work: needsWork,
                                avg_progress: avgProgress
                            };
                        } else {
                            this.studentSummary = {};
                        }
                    } catch (e) {
                        console.error('Failed to load student data:', e);
                    }
                    this.loading = false;
                }
            }
        }
    </script>
    """
    return render_page("Learning Progress", content, "progress")


@app.get("/view/interventions", response_class=HTMLResponse)
async def view_interventions(request: Request):
    """Interventions view - at-risk students and intervention tracking."""
    if not check_auth(request):
        return RedirectResponse(url="/login", status_code=302)

    content = """
    <div x-data="interventionsView()" x-init="loadData()">
        <div class="flex justify-between items-center mb-6">
            <div>
                <h1 class="text-3xl font-bold text-gray-800">Interventions</h1>
                <p class="text-gray-500 text-sm mt-1">Track at-risk students and intervention progress</p>
            </div>
        </div>

        <!-- Risk Level Stats -->
        <div class="grid grid-cols-4 gap-4 mb-6">
            <div class="bg-red-50 border border-red-200 rounded-lg p-4">
                <p class="text-red-600 text-sm font-medium">Critical</p>
                <p class="text-2xl font-bold text-red-700" x-text="interventions.filter(i => i.risk_level === 'critical').length"></p>
            </div>
            <div class="bg-orange-50 border border-orange-200 rounded-lg p-4">
                <p class="text-orange-600 text-sm font-medium">High Risk</p>
                <p class="text-2xl font-bold text-orange-700" x-text="interventions.filter(i => i.risk_level === 'high').length"></p>
            </div>
            <div class="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                <p class="text-yellow-600 text-sm font-medium">Medium Risk</p>
                <p class="text-2xl font-bold text-yellow-700" x-text="interventions.filter(i => i.risk_level === 'medium').length"></p>
            </div>
            <div class="bg-green-50 border border-green-200 rounded-lg p-4">
                <p class="text-green-600 text-sm font-medium">Low Risk</p>
                <p class="text-2xl font-bold text-green-700" x-text="interventions.filter(i => i.risk_level === 'low').length"></p>
            </div>
        </div>

        <!-- Interventions List -->
        <div class="bg-white rounded-lg shadow">
            <div class="p-4 border-b flex justify-between items-center">
                <h2 class="font-semibold">Active Interventions</h2>
                <select class="border rounded px-3 py-1 text-sm" @change="filterRisk = $event.target.value">
                    <option value="">All Risk Levels</option>
                    <option value="critical">Critical</option>
                    <option value="high">High</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low</option>
                </select>
            </div>
            <div class="divide-y">
                <template x-for="i in filteredInterventions" :key="i.id">
                    <div class="p-4 hover:bg-gray-50">
                        <div class="flex items-start gap-4">
                            <div class="w-10 h-10 rounded-full flex items-center justify-center"
                                 :class="i.risk_level === 'critical' ? 'bg-red-100' :
                                         i.risk_level === 'high' ? 'bg-orange-100' :
                                         i.risk_level === 'medium' ? 'bg-yellow-100' : 'bg-green-100'">
                                <i class="fas fa-exclamation-triangle"
                                   :class="i.risk_level === 'critical' ? 'text-red-600' :
                                           i.risk_level === 'high' ? 'text-orange-600' :
                                           i.risk_level === 'medium' ? 'text-yellow-600' : 'text-green-600'"></i>
                            </div>
                            <div class="flex-1">
                                <div class="flex justify-between items-start">
                                    <div>
                                        <span class="font-medium" x-text="i.student_name || i.student_id"></span>
                                        <span class="text-xs ml-2 px-2 py-1 rounded uppercase"
                                              :class="i.risk_level === 'critical' ? 'bg-red-100 text-red-700' :
                                                      i.risk_level === 'high' ? 'bg-orange-100 text-orange-700' :
                                                      i.risk_level === 'medium' ? 'bg-yellow-100 text-yellow-700' : 'bg-green-100 text-green-700'"
                                              x-text="i.risk_level"></span>
                                    </div>
                                    <span class="text-xs px-2 py-1 rounded"
                                          :class="i.status === 'pending' ? 'bg-gray-100 text-gray-600' :
                                                  i.status === 'in_progress' ? 'bg-blue-100 text-blue-600' : 'bg-green-100 text-green-600'"
                                          x-text="i.status"></span>
                                </div>
                                <p class="text-sm text-gray-600 mt-1" x-text="i.issue_description"></p>
                                <div class="mt-2 text-xs text-gray-400">
                                    Type: <span x-text="i.intervention_type || 'General'"></span>
                                </div>
                            </div>
                        </div>
                    </div>
                </template>
                <div x-show="filteredInterventions.length === 0" class="p-8 text-center text-gray-500">
                    <i class="fas fa-check-circle text-4xl text-green-500 mb-2"></i>
                    <p>No interventions matching the filter</p>
                </div>
            </div>
        </div>
    </div>

    <script>
        function interventionsView() {
            return {
                interventions: [],
                filterRisk: '',

                get filteredInterventions() {
                    if (!this.filterRisk) return this.interventions;
                    return this.interventions.filter(i => i.risk_level === this.filterRisk);
                },

                async loadData() {
                    try {
                        const res = await fetch('/api/skills/interventions');
                        this.interventions = await res.json();
                    } catch (e) {
                        console.error('Failed to load interventions:', e);
                    }
                }
            }
        }
    </script>
    """
    return render_page("Interventions", content, "interventions")


@app.get("/view/personas", response_class=HTMLResponse)
async def view_personas(request: Request):
    """Student Personas view - personality profiles and learning styles."""
    if not check_auth(request):
        return RedirectResponse(url="/login", status_code=302)

    content = """
    <div x-data="personasView()" x-init="loadData()">
        <div class="flex justify-between items-center mb-6">
            <div>
                <h1 class="text-3xl font-bold text-gray-800">Student Personas</h1>
                <p class="text-gray-500 text-sm mt-1">Personality profiles and learning style preferences</p>
            </div>
        </div>

        <!-- Stats Cards -->
        <div class="grid grid-cols-4 gap-4 mb-6">
            <div class="bg-purple-50 border border-purple-200 rounded-lg p-4">
                <p class="text-purple-600 text-sm font-medium">Total Personas</p>
                <p class="text-2xl font-bold text-purple-700" x-text="stats.total_personas || 0"></p>
            </div>
            <div class="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <p class="text-blue-600 text-sm font-medium">Total Reports</p>
                <p class="text-2xl font-bold text-blue-700" x-text="stats.total_reports || 0"></p>
            </div>
            <div class="bg-green-50 border border-green-200 rounded-lg p-4">
                <p class="text-green-600 text-sm font-medium">Students</p>
                <p class="text-2xl font-bold text-green-700" x-text="stats.total_students || 0"></p>
            </div>
            <div class="bg-orange-50 border border-orange-200 rounded-lg p-4">
                <p class="text-orange-600 text-sm font-medium">Teachers</p>
                <p class="text-2xl font-bold text-orange-700" x-text="stats.total_teachers || 0"></p>
            </div>
        </div>

        <!-- Personality Dimensions -->
        <div class="bg-white rounded-lg shadow mb-6">
            <div class="p-4 border-b">
                <h2 class="font-semibold">Personality Dimensions</h2>
                <p class="text-sm text-gray-500">The 6 dimensions used to assess learning preferences</p>
            </div>
            <div class="p-4 grid grid-cols-3 gap-4">
                <template x-for="dim in dimensions" :key="dim.code">
                    <div class="border rounded-lg p-4 hover:shadow-md transition-shadow">
                        <div class="flex items-center gap-2 mb-2">
                            <span class="text-lg font-bold text-purple-600" x-text="dim.code"></span>
                            <span class="text-sm text-gray-600" x-text="dim.name"></span>
                        </div>
                        <div class="flex justify-between text-xs">
                            <div class="text-left">
                                <span class="font-medium text-blue-600" x-text="dim.left_pole_name"></span>
                                <p class="text-gray-500" x-text="dim.left_pole_description"></p>
                            </div>
                            <div class="text-gray-400">↔</div>
                            <div class="text-right">
                                <span class="font-medium text-green-600" x-text="dim.right_pole_name"></span>
                                <p class="text-gray-500" x-text="dim.right_pole_description"></p>
                            </div>
                        </div>
                    </div>
                </template>
            </div>
        </div>

        <!-- Personas List -->
        <div class="bg-white rounded-lg shadow">
            <div class="p-4 border-b flex justify-between items-center">
                <h2 class="font-semibold">Student Personas</h2>
                <div class="text-sm text-gray-500">
                    <span x-text="personas.length"></span> students with personality profiles
                </div>
            </div>
            <div class="divide-y">
                <template x-for="p in personas" :key="p.student_name">
                    <div class="p-4 hover:bg-gray-50 cursor-pointer" @click="selectedPersona = p">
                        <div class="flex items-center justify-between">
                            <div class="flex items-center gap-4">
                                <div class="w-10 h-10 bg-purple-100 rounded-full flex items-center justify-center">
                                    <i class="fas fa-user text-purple-600"></i>
                                </div>
                                <div>
                                    <p class="font-medium" x-text="p.student_name"></p>
                                    <p class="text-xs text-gray-500">Type: <span class="font-mono" x-text="p.personality_type"></span></p>
                                </div>
                            </div>
                            <div class="flex gap-1">
                                <template x-for="(score, dim) in p.scores" :key="dim">
                                    <div class="w-8 h-8 rounded text-xs flex items-center justify-center font-medium"
                                         :class="score < 45 ? 'bg-blue-100 text-blue-700' :
                                                 score > 55 ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'"
                                         :title="dim + ': ' + score">
                                        <span x-text="dim"></span>
                                    </div>
                                </template>
                            </div>
                        </div>
                    </div>
                </template>
                <div x-show="personas.length === 0" class="p-8 text-center text-gray-500">
                    <i class="fas fa-user-circle text-4xl text-gray-300 mb-2"></i>
                    <p>No personality profiles found</p>
                    <p class="text-sm">Students need to complete the personality quiz</p>
                </div>
            </div>
        </div>

        <!-- Selected Persona Modal -->
        <div x-show="selectedPersona" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" @click.self="selectedPersona = null">
            <div class="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto" x-show="selectedPersona">
                <div class="p-4 border-b flex justify-between items-center sticky top-0 bg-white">
                    <h3 class="text-xl font-bold" x-text="selectedPersona?.student_name"></h3>
                    <button @click="selectedPersona = null" class="text-gray-500 hover:text-gray-700">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div class="p-6">
                    <div class="text-center mb-6">
                        <div class="inline-block px-4 py-2 bg-purple-100 rounded-lg">
                            <span class="text-2xl font-mono font-bold text-purple-700" x-text="selectedPersona?.personality_type"></span>
                        </div>
                        <p class="text-sm text-gray-500 mt-2">Personality Type Code</p>
                    </div>

                    <h4 class="font-semibold mb-4">Dimension Scores</h4>
                    <div class="space-y-4">
                        <template x-for="dim in dimensions" :key="dim.code">
                            <div class="border rounded-lg p-4">
                                <div class="flex justify-between items-center mb-2">
                                    <span class="font-medium" x-text="dim.name"></span>
                                    <span class="text-sm px-2 py-1 rounded"
                                          :class="selectedPersona?.tendencies[dim.code]?.includes('Strong') ? 'bg-purple-100 text-purple-700' :
                                                  selectedPersona?.tendencies[dim.code]?.includes('Moderate') ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600'"
                                          x-text="selectedPersona?.tendencies[dim.code]"></span>
                                </div>
                                <div class="relative h-4 bg-gray-200 rounded-full">
                                    <div class="absolute left-0 top-0 h-full bg-gradient-to-r from-blue-500 to-green-500 rounded-full"
                                         :style="'width: ' + (selectedPersona?.scores[dim.code] || 50) + '%'"></div>
                                    <div class="absolute top-0 h-full w-0.5 bg-gray-400" style="left: 50%"></div>
                                </div>
                                <div class="flex justify-between text-xs text-gray-500 mt-1">
                                    <span x-text="dim.left_pole_name"></span>
                                    <span x-text="dim.right_pole_name"></span>
                                </div>
                            </div>
                        </template>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        function personasView() {
            return {
                stats: {},
                dimensions: [],
                personas: [],
                selectedPersona: null,

                async loadData() {
                    try {
                        const [statsRes, dimsRes, personasRes] = await Promise.all([
                            fetch('/api/personas/stats'),
                            fetch('/api/personas/dimensions'),
                            fetch('/api/personas/list')
                        ]);
                        this.stats = await statsRes.json();
                        this.dimensions = await dimsRes.json();
                        this.personas = await personasRes.json();
                    } catch (e) {
                        console.error('Failed to load persona data:', e);
                    }
                }
            }
        }
    </script>
    """
    return render_page("Student Personas", content, "personas")


@app.get("/view/profiles", response_class=HTMLResponse)
async def view_profiles(request: Request):
    """Unified Student/Teacher Profile view with all related data."""
    if not check_auth(request):
        return RedirectResponse(url="/login", status_code=302)

    content = """
    <div x-data="profilesView()" x-init="loadLists()">
        <div class="flex justify-between items-center mb-6">
            <div>
                <h1 class="text-3xl font-bold text-gray-800">Student & Teacher Profiles</h1>
                <p class="text-gray-500 text-sm mt-1">Select a student or teacher to view their complete profile with skills, progress, and reports</p>
            </div>
        </div>

        <!-- Error Message -->
        <div x-show="error" class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-6">
            <i class="fas fa-exclamation-circle mr-2"></i>
            <span x-text="error"></span>
        </div>

        <!-- Selection Row -->
        <div class="grid grid-cols-2 gap-6 mb-6">
            <!-- Student Selection -->
            <div class="bg-white rounded-lg shadow p-4">
                <h2 class="font-semibold mb-3 flex items-center gap-2">
                    <i class="fas fa-user-graduate text-blue-500"></i> Select Student
                    <span x-show="!loadingLists" class="text-xs text-gray-400 font-normal">(<span x-text="students.length"></span> available)</span>
                    <i x-show="loadingLists" class="fas fa-spinner fa-spin text-gray-400 text-sm"></i>
                </h2>
                <select class="w-full border rounded px-3 py-2" @change="loadStudentProfile($event.target.value)" :disabled="loadingLists">
                    <option value="" x-text="loadingLists ? 'Loading students...' : '-- Select a student (' + students.length + ') --'"></option>
                    <template x-for="s in students" :key="s.student_id">
                        <option :value="s.student_id" x-text="s.student_name + (s.has_skills ? ' [Skills]' : '') + (s.has_persona ? ' [Persona]' : '') + (s.has_reports ? ' [Reports]' : '')"></option>
                    </template>
                </select>
            </div>

            <!-- Teacher Selection -->
            <div class="bg-white rounded-lg shadow p-4">
                <h2 class="font-semibold mb-3 flex items-center gap-2">
                    <i class="fas fa-chalkboard-teacher text-green-500"></i> Select Teacher
                    <span x-show="!loadingLists" class="text-xs text-gray-400 font-normal">(<span x-text="teachers.length"></span> available)</span>
                    <i x-show="loadingLists" class="fas fa-spinner fa-spin text-gray-400 text-sm"></i>
                </h2>
                <select class="w-full border rounded px-3 py-2" @change="loadTeacherProfile($event.target.value)" :disabled="loadingLists">
                    <option value="" x-text="loadingLists ? 'Loading teachers...' : '-- Select a teacher (' + teachers.length + ') --'"></option>
                    <template x-for="t in teachers" :key="t.teacher_id">
                        <option :value="t.teacher_id" x-text="t.teacher_name + ' (' + t.students_count + ' students, ' + t.reports_count + ' reports)'"></option>
                    </template>
                </select>
            </div>
        </div>

        <!-- Loading State -->
        <div x-show="loading" class="text-center py-12">
            <i class="fas fa-spinner fa-spin text-4xl text-blue-500"></i>
            <p class="mt-2 text-gray-500">Loading profile...</p>
        </div>

        <!-- Student Profile -->
        <div x-show="studentProfile && !loading" class="space-y-6">
            <!-- Header -->
            <div class="bg-gradient-to-r from-blue-500 to-blue-600 rounded-lg shadow p-6 text-white">
                <div class="flex items-center gap-4">
                    <div class="w-16 h-16 bg-white/20 rounded-full flex items-center justify-center">
                        <i class="fas fa-user-graduate text-3xl"></i>
                    </div>
                    <div>
                        <h2 class="text-2xl font-bold" x-text="studentProfile.student_name"></h2>
                        <div class="flex gap-4 mt-1 text-blue-100">
                            <span x-show="studentProfile.grade_level"><i class="fas fa-graduation-cap mr-1"></i> Grade <span x-text="studentProfile.grade_level"></span></span>
                            <span x-show="studentProfile.gender"><i class="fas fa-venus-mars mr-1"></i> <span x-text="studentProfile.gender"></span></span>
                            <span x-show="studentProfile.personality_type"><i class="fas fa-brain mr-1"></i> Type: <span class="font-mono" x-text="studentProfile.personality_type"></span></span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Stats Row -->
            <div class="grid grid-cols-4 gap-4">
                <div class="bg-white rounded-lg shadow p-4 text-center">
                    <p class="text-3xl font-bold text-blue-600" x-text="studentProfile.skills_summary?.total_skills || 0"></p>
                    <p class="text-sm text-gray-500">Skills Tracked</p>
                </div>
                <div class="bg-white rounded-lg shadow p-4 text-center">
                    <p class="text-3xl font-bold text-green-600" x-text="studentProfile.skills_summary?.mastered || 0"></p>
                    <p class="text-sm text-gray-500">Skills Mastered</p>
                </div>
                <div class="bg-white rounded-lg shadow p-4 text-center">
                    <p class="text-3xl font-bold text-purple-600" x-text="studentProfile.reports_summary?.total_reports || 0"></p>
                    <p class="text-sm text-gray-500">Total Reports</p>
                </div>
                <div class="bg-white rounded-lg shadow p-4 text-center">
                    <p class="text-3xl font-bold text-orange-600" x-text="(studentProfile.skills_summary?.avg_progress || 0) + '%'"></p>
                    <p class="text-sm text-gray-500">Avg Progress</p>
                </div>
            </div>

            <!-- Tabs -->
            <div class="bg-white rounded-lg shadow">
                <div class="border-b flex">
                    <button @click="activeTab = 'skills'" class="px-6 py-3 font-medium" :class="activeTab === 'skills' ? 'border-b-2 border-blue-500 text-blue-600' : 'text-gray-500'">
                        <i class="fas fa-chart-bar mr-2"></i> Skills Progress
                    </button>
                    <button @click="activeTab = 'persona'" class="px-6 py-3 font-medium" :class="activeTab === 'persona' ? 'border-b-2 border-blue-500 text-blue-600' : 'text-gray-500'">
                        <i class="fas fa-brain mr-2"></i> Persona
                    </button>
                    <button @click="activeTab = 'reports'" class="px-6 py-3 font-medium" :class="activeTab === 'reports' ? 'border-b-2 border-blue-500 text-blue-600' : 'text-gray-500'">
                        <i class="fas fa-file-alt mr-2"></i> Reports
                    </button>
                    <button @click="activeTab = 'recommendations'" class="px-6 py-3 font-medium" :class="activeTab === 'recommendations' ? 'border-b-2 border-blue-500 text-blue-600' : 'text-gray-500'">
                        <i class="fas fa-lightbulb mr-2"></i> Recommendations
                    </button>
                </div>

                <!-- Skills Tab -->
                <div x-show="activeTab === 'skills'" class="p-4">
                    <div x-show="studentProfile.skills_progress?.length === 0" class="text-center py-8 text-gray-500">
                        <i class="fas fa-chart-bar text-4xl mb-2 opacity-30"></i>
                        <p>No skills progress data available</p>
                    </div>
                    <div class="grid gap-3" x-show="studentProfile.skills_progress?.length > 0">
                        <template x-for="skill in studentProfile.skills_progress" :key="skill.skill_code">
                            <div class="border rounded-lg p-3">
                                <div class="flex justify-between items-center mb-2">
                                    <div>
                                        <span class="font-medium" x-text="skill.skill_name"></span>
                                        <span class="text-xs text-gray-400 ml-2 font-mono" x-text="skill.skill_code"></span>
                                    </div>
                                    <div class="flex items-center gap-2">
                                        <span class="text-sm" x-text="skill.progress_percentage + '%'"></span>
                                        <span class="text-xs px-2 py-1 rounded"
                                              :class="skill.progress_percentage >= 85 ? 'bg-green-100 text-green-700' :
                                                      skill.progress_percentage >= 40 ? 'bg-yellow-100 text-yellow-700' : 'bg-red-100 text-red-700'"
                                              x-text="skill.current_level || (skill.progress_percentage >= 85 ? 'Mastered' : skill.progress_percentage >= 40 ? 'In Progress' : 'Needs Work')"></span>
                                    </div>
                                </div>
                                <div class="h-2 bg-gray-200 rounded-full overflow-hidden">
                                    <div class="h-full rounded-full transition-all"
                                         :class="skill.progress_percentage >= 85 ? 'bg-green-500' :
                                                 skill.progress_percentage >= 40 ? 'bg-yellow-500' : 'bg-red-500'"
                                         :style="'width: ' + skill.progress_percentage + '%'"></div>
                                </div>
                                <div class="flex justify-between text-xs text-gray-400 mt-1">
                                    <span x-text="skill.domain_code + ' > ' + skill.category_code"></span>
                                    <span x-show="skill.last_practiced" x-text="'Last: ' + skill.last_practiced"></span>
                                </div>
                            </div>
                        </template>
                    </div>
                </div>

                <!-- Persona Tab -->
                <div x-show="activeTab === 'persona'" class="p-4">
                    <div x-show="!studentProfile.personality_type" class="text-center py-8 text-gray-500">
                        <i class="fas fa-brain text-4xl mb-2 opacity-30"></i>
                        <p>No personality assessment data available</p>
                        <p class="text-sm">Student needs to complete the personality quiz</p>
                    </div>
                    <div x-show="studentProfile.personality_type" class="space-y-4">
                        <div class="text-center mb-6">
                            <div class="inline-block px-6 py-3 bg-purple-100 rounded-lg">
                                <span class="text-3xl font-mono font-bold text-purple-700" x-text="studentProfile.personality_type"></span>
                            </div>
                        </div>
                        <template x-for="dim in studentProfile.persona_dimensions" :key="dim.code">
                            <div class="border rounded-lg p-4">
                                <div class="flex justify-between items-center mb-2">
                                    <span class="font-medium" x-text="dim.name"></span>
                                    <span class="text-sm px-2 py-1 rounded"
                                          :class="dim.tendency.includes('Strong') ? 'bg-purple-100 text-purple-700' : dim.tendency === 'Balanced' ? 'bg-gray-100 text-gray-600' : 'bg-blue-100 text-blue-700'"
                                          x-text="dim.tendency"></span>
                                </div>
                                <div class="relative h-3 bg-gray-200 rounded-full">
                                    <div class="absolute left-0 top-0 h-full bg-gradient-to-r from-blue-500 to-green-500 rounded-full transition-all"
                                         :style="'width: ' + dim.score + '%'"></div>
                                    <div class="absolute top-0 h-full w-0.5 bg-gray-400" style="left: 50%"></div>
                                </div>
                                <div class="flex justify-between text-xs text-gray-500 mt-1">
                                    <span x-text="dim.code.charAt(0) === 'E' ? 'Explorer' : dim.code.charAt(0) === 'S' ? 'Social' : dim.code.charAt(0) === 'P' ? 'Practical' : dim.code.charAt(0) === 'R' ? 'Routine' : dim.code.charAt(0) === 'A' ? 'Analytical' : 'Local'"></span>
                                    <span x-text="dim.code.charAt(1) === 'I' ? 'Investigator' : dim.code.charAt(1) === 'C' ? 'Concentrated' : dim.code.charAt(1) === 'T' ? 'Theoretical' : dim.code.charAt(1) === 'N' ? 'Novel' : dim.code.charAt(1) === 'D' ? 'Decisive' : 'Global'"></span>
                                </div>
                            </div>
                        </template>
                    </div>
                </div>

                <!-- Reports Tab -->
                <div x-show="activeTab === 'reports'" class="p-4">
                    <div x-show="studentProfile.recent_reports?.length === 0" class="text-center py-8 text-gray-500">
                        <i class="fas fa-file-alt text-4xl mb-2 opacity-30"></i>
                        <p>No reports available</p>
                    </div>
                    <div class="space-y-3" x-show="studentProfile.recent_reports?.length > 0">
                        <div class="text-sm text-gray-500 mb-4">
                            Showing <span x-text="studentProfile.recent_reports?.length"></span> most recent reports
                            (Total: <span x-text="studentProfile.reports_summary?.total_reports"></span>)
                        </div>
                        <template x-for="(report, idx) in studentProfile.recent_reports" :key="idx">
                            <div class="border rounded-lg p-3 hover:bg-gray-50">
                                <div class="flex justify-between items-start">
                                    <div>
                                        <span class="font-medium" x-text="report.subject"></span>
                                        <span class="text-xs text-gray-400 ml-2" x-text="report.date"></span>
                                    </div>
                                    <span class="text-xs px-2 py-1 rounded"
                                          :class="report.skill_focus_met === 'YES' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'"
                                          x-text="report.skill_focus_met === 'YES' ? 'Met' : 'Not Met'"></span>
                                </div>
                                <div class="text-sm text-gray-600 mt-1">
                                    Teacher: <span x-text="report.teacher_name"></span>
                                    <span x-show="report.skill_focus" class="ml-2">| Focus: <span x-text="report.skill_focus"></span></span>
                                </div>
                                <div class="flex gap-4 mt-2 text-xs">
                                    <span :class="report.attention >= 4 ? 'text-green-600' : report.attention >= 3 ? 'text-yellow-600' : 'text-red-600'">
                                        Attention: <span x-text="report.attention"></span>/5
                                    </span>
                                    <span :class="report.comprehension >= 4 ? 'text-green-600' : report.comprehension >= 3 ? 'text-yellow-600' : 'text-red-600'">
                                        Comprehension: <span x-text="report.comprehension"></span>/5
                                    </span>
                                    <span :class="report.retention >= 4 ? 'text-green-600' : report.retention >= 3 ? 'text-yellow-600' : 'text-red-600'">
                                        Retention: <span x-text="report.retention"></span>/5
                                    </span>
                                    <span :class="report.behavior >= 4 ? 'text-green-600' : report.behavior >= 3 ? 'text-yellow-600' : 'text-red-600'">
                                        Behavior: <span x-text="report.behavior"></span>/5
                                    </span>
                                </div>
                            </div>
                        </template>
                    </div>
                </div>

                <!-- Recommendations Tab -->
                <div x-show="activeTab === 'recommendations'" class="p-4">
                    <div class="grid grid-cols-2 gap-6">
                        <!-- Recommendations -->
                        <div>
                            <h3 class="font-semibold mb-3 text-blue-600"><i class="fas fa-lightbulb mr-2"></i>Learning Recommendations</h3>
                            <div x-show="studentProfile.recommendations?.length === 0" class="text-gray-500 text-sm">No active recommendations</div>
                            <div class="space-y-2">
                                <template x-for="rec in studentProfile.recommendations" :key="rec.target">
                                    <div class="border-l-4 border-blue-400 pl-3 py-2">
                                        <p class="font-medium text-sm" x-text="rec.target"></p>
                                        <p class="text-xs text-gray-500" x-text="rec.reason"></p>
                                    </div>
                                </template>
                            </div>
                        </div>
                        <!-- Interventions -->
                        <div>
                            <h3 class="font-semibold mb-3 text-red-600"><i class="fas fa-exclamation-triangle mr-2"></i>Active Interventions</h3>
                            <div x-show="studentProfile.interventions?.length === 0" class="text-gray-500 text-sm">No active interventions</div>
                            <div class="space-y-2">
                                <template x-for="int in studentProfile.interventions" :key="int.issue">
                                    <div class="border-l-4 pl-3 py-2"
                                         :class="int.risk_level === 'critical' ? 'border-red-500' : int.risk_level === 'high' ? 'border-orange-500' : 'border-yellow-500'">
                                        <div class="flex items-center gap-2">
                                            <span class="text-xs uppercase px-2 py-0.5 rounded"
                                                  :class="int.risk_level === 'critical' ? 'bg-red-100 text-red-700' : int.risk_level === 'high' ? 'bg-orange-100 text-orange-700' : 'bg-yellow-100 text-yellow-700'"
                                                  x-text="int.risk_level"></span>
                                            <span class="text-xs text-gray-400" x-text="int.type"></span>
                                        </div>
                                        <p class="text-sm mt-1" x-text="int.issue"></p>
                                    </div>
                                </template>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Teacher Profile -->
        <div x-show="teacherProfile && !loading" class="space-y-6">
            <!-- Header -->
            <div class="bg-gradient-to-r from-green-500 to-green-600 rounded-lg shadow p-6 text-white">
                <div class="flex items-center gap-4">
                    <div class="w-16 h-16 bg-white/20 rounded-full flex items-center justify-center">
                        <i class="fas fa-chalkboard-teacher text-3xl"></i>
                    </div>
                    <div>
                        <h2 class="text-2xl font-bold" x-text="teacherProfile.teacher_name"></h2>
                        <div class="flex gap-4 mt-1 text-green-100">
                            <span><i class="fas fa-users mr-1"></i> <span x-text="teacherProfile.student_count"></span> Students</span>
                            <span><i class="fas fa-file-alt mr-1"></i> <span x-text="teacherProfile.reports_count"></span> Reports</span>
                            <span x-show="teacherProfile.subjects_taught?.length"><i class="fas fa-book mr-1"></i> <span x-text="teacherProfile.subjects_taught?.join(', ')"></span></span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Effectiveness Metrics -->
            <div class="bg-white rounded-lg shadow p-4" x-show="teacherProfile.effectiveness">
                <h3 class="font-semibold mb-4">Teaching Effectiveness</h3>
                <div class="grid grid-cols-5 gap-4">
                    <div class="text-center">
                        <div class="text-2xl font-bold" :class="teacherProfile.effectiveness?.avg_attention >= 4 ? 'text-green-600' : teacherProfile.effectiveness?.avg_attention >= 3 ? 'text-yellow-600' : 'text-red-600'" x-text="teacherProfile.effectiveness?.avg_attention?.toFixed(1)"></div>
                        <div class="text-xs text-gray-500">Avg Attention</div>
                    </div>
                    <div class="text-center">
                        <div class="text-2xl font-bold" :class="teacherProfile.effectiveness?.avg_retention >= 4 ? 'text-green-600' : teacherProfile.effectiveness?.avg_retention >= 3 ? 'text-yellow-600' : 'text-red-600'" x-text="teacherProfile.effectiveness?.avg_retention?.toFixed(1)"></div>
                        <div class="text-xs text-gray-500">Avg Retention</div>
                    </div>
                    <div class="text-center">
                        <div class="text-2xl font-bold" :class="teacherProfile.effectiveness?.avg_comprehension >= 4 ? 'text-green-600' : teacherProfile.effectiveness?.avg_comprehension >= 3 ? 'text-yellow-600' : 'text-red-600'" x-text="teacherProfile.effectiveness?.avg_comprehension?.toFixed(1)"></div>
                        <div class="text-xs text-gray-500">Avg Comprehension</div>
                    </div>
                    <div class="text-center">
                        <div class="text-2xl font-bold" :class="teacherProfile.effectiveness?.avg_behavior >= 4 ? 'text-green-600' : teacherProfile.effectiveness?.avg_behavior >= 3 ? 'text-yellow-600' : 'text-red-600'" x-text="teacherProfile.effectiveness?.avg_behavior?.toFixed(1)"></div>
                        <div class="text-xs text-gray-500">Avg Behavior</div>
                    </div>
                    <div class="text-center">
                        <div class="text-2xl font-bold text-blue-600" x-text="teacherProfile.effectiveness?.skill_met_rate?.toFixed(0) + '%'"></div>
                        <div class="text-xs text-gray-500">Skill Focus Met</div>
                    </div>
                </div>
            </div>

            <!-- Students List -->
            <div class="bg-white rounded-lg shadow">
                <div class="p-4 border-b flex justify-between items-center">
                    <h3 class="font-semibold">Students (<span x-text="teacherProfile.students?.length"></span>)</h3>
                    <input type="text" placeholder="Search students..." class="border rounded px-3 py-1 text-sm" x-model="studentSearch">
                </div>
                <div class="max-h-96 overflow-y-auto">
                    <table class="w-full">
                        <thead class="bg-gray-50 sticky top-0">
                            <tr>
                                <th class="text-left p-3 text-sm font-medium text-gray-600">Student</th>
                                <th class="text-center p-3 text-sm font-medium text-gray-600">Reports</th>
                                <th class="text-center p-3 text-sm font-medium text-gray-600">Attention</th>
                                <th class="text-center p-3 text-sm font-medium text-gray-600">Comprehension</th>
                                <th class="text-center p-3 text-sm font-medium text-gray-600">Skill Met</th>
                                <th class="text-center p-3 text-sm font-medium text-gray-600">Last Report</th>
                                <th class="text-center p-3 text-sm font-medium text-gray-600">Action</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y">
                            <template x-for="student in filteredTeacherStudents" :key="student.student_name">
                                <tr class="hover:bg-gray-50">
                                    <td class="p-3" x-text="student.student_name"></td>
                                    <td class="p-3 text-center" x-text="student.reports_count"></td>
                                    <td class="p-3 text-center" :class="student.avg_attention >= 4 ? 'text-green-600' : student.avg_attention >= 3 ? 'text-yellow-600' : 'text-red-600'" x-text="student.avg_attention?.toFixed(1)"></td>
                                    <td class="p-3 text-center" :class="student.avg_comprehension >= 4 ? 'text-green-600' : student.avg_comprehension >= 3 ? 'text-yellow-600' : 'text-red-600'" x-text="student.avg_comprehension?.toFixed(1)"></td>
                                    <td class="p-3 text-center" x-text="student.skill_met_rate?.toFixed(0) + '%'"></td>
                                    <td class="p-3 text-center text-xs text-gray-500" x-text="student.last_report"></td>
                                    <td class="p-3 text-center">
                                        <button @click="loadStudentProfile(student.student_name)" class="text-blue-500 hover:text-blue-700 text-sm">
                                            <i class="fas fa-eye"></i> View
                                        </button>
                                    </td>
                                </tr>
                            </template>
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Specializations -->
            <div x-show="teacherProfile.specializations?.length > 0" class="bg-white rounded-lg shadow p-4">
                <h3 class="font-semibold mb-4">Skill Specializations</h3>
                <div class="grid grid-cols-3 gap-4">
                    <template x-for="spec in teacherProfile.specializations" :key="spec.skill_code">
                        <div class="border rounded-lg p-3">
                            <div class="font-medium" x-text="spec.skill_name"></div>
                            <div class="text-xs text-gray-500 font-mono" x-text="spec.skill_code"></div>
                            <div class="mt-2 grid grid-cols-2 gap-2 text-xs">
                                <div>Proficiency: <span class="font-medium" x-text="spec.proficiency"></span></div>
                                <div>Effectiveness: <span class="font-medium" x-text="(spec.effectiveness * 100).toFixed(0) + '%'"></span></div>
                                <div>Students: <span class="font-medium" x-text="spec.students_taught"></span></div>
                                <div>Avg Improvement: <span class="font-medium" x-text="spec.avg_improvement?.toFixed(1) + '%'"></span></div>
                            </div>
                        </div>
                    </template>
                </div>
            </div>
        </div>

        <!-- Empty State -->
        <div x-show="!studentProfile && !teacherProfile && !loading" class="bg-white rounded-lg shadow p-12 text-center">
            <i class="fas fa-users text-6xl text-gray-300 mb-4"></i>
            <h3 class="text-xl font-semibold text-gray-600">Select a Student or Teacher</h3>
            <p class="text-gray-500 mt-2">Choose from the dropdowns above to view their complete profile with skills, persona, and reports</p>
        </div>
    </div>

    <script>
        function profilesView() {
            return {
                students: [],
                teachers: [],
                studentProfile: null,
                teacherProfile: null,
                loading: false,
                loadingLists: true,
                activeTab: 'skills',
                studentSearch: '',
                error: null,

                get filteredTeacherStudents() {
                    if (!this.teacherProfile?.students) return [];
                    if (!this.studentSearch) return this.teacherProfile.students;
                    const search = this.studentSearch.toLowerCase();
                    return this.teacherProfile.students.filter(s => s.student_name.toLowerCase().includes(search));
                },

                async loadLists() {
                    this.loadingLists = true;
                    this.error = null;
                    try {
                        console.log('Loading students and teachers...');
                        const [studentsRes, teachersRes] = await Promise.all([
                            fetch('/api/profiles/students'),
                            fetch('/api/profiles/teachers')
                        ]);

                        if (!studentsRes.ok) {
                            throw new Error('Students API returned ' + studentsRes.status);
                        }
                        if (!teachersRes.ok) {
                            throw new Error('Teachers API returned ' + teachersRes.status);
                        }

                        const studentsData = await studentsRes.json();
                        const teachersData = await teachersRes.json();

                        console.log('Loaded', studentsData.length, 'students and', teachersData.length, 'teachers');

                        this.students = studentsData;
                        this.teachers = teachersData;
                    } catch (e) {
                        console.error('Failed to load lists:', e);
                        this.error = 'Failed to load data: ' + e.message;
                    }
                    this.loadingLists = false;
                },

                async loadStudentProfile(studentId) {
                    if (!studentId) {
                        this.studentProfile = null;
                        return;
                    }
                    this.loading = true;
                    this.teacherProfile = null;
                    this.activeTab = 'skills';
                    this.error = null;
                    try {
                        const res = await fetch('/api/profiles/student/' + encodeURIComponent(studentId));
                        if (!res.ok) throw new Error('API returned ' + res.status);
                        this.studentProfile = await res.json();
                    } catch (e) {
                        console.error('Failed to load student profile:', e);
                        this.error = 'Failed to load student: ' + e.message;
                    }
                    this.loading = false;
                },

                async loadTeacherProfile(teacherId) {
                    if (!teacherId) {
                        this.teacherProfile = null;
                        return;
                    }
                    this.loading = true;
                    this.studentProfile = null;
                    this.error = null;
                    try {
                        const res = await fetch('/api/profiles/teacher/' + encodeURIComponent(teacherId));
                        if (!res.ok) throw new Error('API returned ' + res.status);
                        this.teacherProfile = await res.json();
                    } catch (e) {
                        console.error('Failed to load teacher profile:', e);
                        this.error = 'Failed to load teacher: ' + e.message;
                    }
                    this.loading = false;
                }
            }
        }
    </script>
    """
    return render_page("Student & Teacher Profiles", content, "profiles")


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/health")
async def health_check():
    """Check API and TypeDB health."""
    return {
        "status": "healthy",
        "typedb_connected": loader is not None and loader.driver is not None,
        "last_sync": last_sync,
    }


@app.get("/api/stats", response_model=StatsResponse)
async def get_stats():
    """Get dashboard statistics from all connected databases."""
    from ..extractors import PostgreSQLExtractor
    import sqlite3

    stats = {}
    total_teachers = 0
    total_students = 0
    total_assignments = 0
    total_assessments = 0

    try:
        # Get counts from PostgreSQL
        extractor = PostgreSQLExtractor()
        if extractor.connect():
            # Count distinct teachers (RealDictCursor returns dict, use 'count' key)
            extractor.cursor.execute("SELECT COUNT(DISTINCT name) as count FROM teachers")
            result = extractor.cursor.fetchone()
            total_teachers = result["count"] if result else 0
            stats["teachers"] = total_teachers

            # Count distinct students
            extractor.cursor.execute("SELECT COUNT(DISTINCT name) as count FROM students")
            result = extractor.cursor.fetchone()
            total_students = result["count"] if result else 0
            stats["students"] = total_students

            # Count active assignments
            extractor.cursor.execute("SELECT COUNT(*) as count FROM assignments WHERE is_active = true")
            result = extractor.cursor.fetchone()
            total_assignments = result["count"] if result else 0
            stats["assignments"] = total_assignments

            # Count attendance records
            extractor.cursor.execute("SELECT COUNT(*) as count FROM teacher_attendance")
            result = extractor.cursor.fetchone()
            stats["pg_attendance"] = result["count"] if result else 0

            extractor.disconnect()

        # Get counts from SQLite databases
        # Teacher Attendance
        attendance_db = Path.home() / "attendance-checker" / "attendance.db"
        if attendance_db.exists():
            conn = sqlite3.connect(str(attendance_db))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM attendance")
            stats["teacher_attendance"] = cursor.fetchone()[0] or 0
            conn.close()

        # Student Attendance
        student_att_db = Path.home() / "student-attendance-checker" / "student-attendance.db"
        if student_att_db.exists():
            conn = sqlite3.connect(str(student_att_db))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM attendance")
            stats["student_attendance"] = cursor.fetchone()[0] or 0
            conn.close()

        # Coaching Records
        coaching_db = Path.home() / "academy-coaching-app" / "coaching.db"
        if coaching_db.exists():
            conn = sqlite3.connect(str(coaching_db))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM coaching_records")
            stats["coaching_records"] = cursor.fetchone()[0] or 0
            cursor.execute("SELECT COUNT(*) FROM employees")
            stats["employees"] = cursor.fetchone()[0] or 0
            conn.close()

        # App Marketplace
        marketplace_db = Path.home() / "ican-app-marketplace" / "marketplace.db"
        if marketplace_db.exists():
            conn = sqlite3.connect(str(marketplace_db))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM apps")
            stats["apps"] = cursor.fetchone()[0] or 0
            conn.close()

        # Demo Assessments
        demo_db = Path.home() / "ican-demo-assessment" / "demo_assessments.db"
        if demo_db.exists():
            conn = sqlite3.connect(str(demo_db))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM assessments")
            demo_count = cursor.fetchone()[0] or 0
            stats["demo_assessments"] = demo_count
            total_assessments += demo_count
            conn.close()

        # Interviews
        interviews_db = Path.home() / "interview-sheet-generator" / "server" / "interviews.db"
        if interviews_db.exists():
            conn = sqlite3.connect(str(interviews_db))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM interviews")
            interview_count = cursor.fetchone()[0] or 0
            stats["interviews"] = interview_count
            total_assessments += interview_count
            conn.close()

        # Student Reports
        reports_db = Path.home() / "student-report-app" / "student_reports.db"
        if reports_db.exists():
            conn = sqlite3.connect(str(reports_db))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM student_reports")
            report_count = cursor.fetchone()[0] or 0
            stats["student_reports"] = report_count
            total_assessments += report_count
            conn.close()

        # Student Analytics (Unified Ontology Platform)
        analytics_db = Path.home() / "unified-ontology-platform" / "backend" / "databases" / "student_analytics.db"
        if analytics_db.exists():
            conn = sqlite3.connect(str(analytics_db))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM students")
            stats["analytics_students"] = cursor.fetchone()[0] or 0
            cursor.execute("SELECT COUNT(*) FROM assessments")
            stats["analytics_assessments"] = cursor.fetchone()[0] or 0
            cursor.execute("SELECT COUNT(*) FROM skill_progressions")
            stats["skill_progressions"] = cursor.fetchone()[0] or 0
            conn.close()

        # ICAN Classes
        classes_db = Path.home() / "unified-ontology-platform" / "backend" / "databases" / "ican_classes.db"
        if classes_db.exists():
            conn = sqlite3.connect(str(classes_db))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM classes")
            stats["ican_classes"] = cursor.fetchone()[0] or 0
            cursor.execute("SELECT COUNT(*) FROM learning_paths")
            stats["learning_paths"] = cursor.fetchone()[0] or 0
            conn.close()

        # Books Library
        books_db = Path.home() / "unified-ontology-platform" / "backend" / "databases" / "books_library.db"
        if books_db.exists():
            conn = sqlite3.connect(str(books_db))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM books")
            stats["books"] = cursor.fetchone()[0] or 0
            cursor.execute("SELECT COUNT(*) FROM authors")
            stats["authors"] = cursor.fetchone()[0] or 0
            conn.close()

        # Eduspace / ICANX Academy
        eduspace_db = Path.home() / "Downloads" / "eduspace app" / "icanx-academy.db"
        if eduspace_db.exists():
            conn = sqlite3.connect(str(eduspace_db))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM programs")
            stats["programs"] = cursor.fetchone()[0] or 0
            cursor.execute("SELECT COUNT(*) FROM testimonials")
            stats["testimonials"] = cursor.fetchone()[0] or 0
            conn.close()

        # Face Attendance (JSON)
        import json
        face_attendance_json = Path.home() / "face-attendance-app" / "attendance.json"
        if face_attendance_json.exists():
            with open(face_attendance_json, "r") as f:
                face_records = json.load(f)
                stats["face_attendance"] = len(face_records)
        face_users_json = Path.home() / "face-attendance-app" / "users.json"
        if face_users_json.exists():
            with open(face_users_json, "r") as f:
                face_users = json.load(f)
                stats["face_users"] = len(face_users)

        # Skills Taxonomy (Ontology)
        skills_db = Path.home() / "data-pipeline" / "databases" / "skills_taxonomy.db"
        if skills_db.exists():
            conn = sqlite3.connect(str(skills_db))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM skill_domains")
            stats["skill_domains"] = cursor.fetchone()[0] or 0
            cursor.execute("SELECT COUNT(*) FROM skill_categories")
            stats["skill_categories"] = cursor.fetchone()[0] or 0
            cursor.execute("SELECT COUNT(*) FROM skills")
            stats["skills"] = cursor.fetchone()[0] or 0
            cursor.execute("SELECT COUNT(*) FROM skill_prerequisites")
            stats["skill_prerequisites"] = cursor.fetchone()[0] or 0
            cursor.execute("SELECT COUNT(*) FROM achievements")
            stats["achievements"] = cursor.fetchone()[0] or 0
            cursor.execute("SELECT COUNT(*) FROM student_skill_progress")
            stats["student_skill_progress"] = cursor.fetchone()[0] or 0
            cursor.execute("SELECT COUNT(*) FROM interventions WHERE status != 'resolved'")
            stats["active_interventions"] = cursor.fetchone()[0] or 0
            conn.close()

        # Notion connection status (just track if configured, not in counts)
        # We don't add to stats dict since it expects integers

    except Exception as e:
        logger.error(f"Failed to get stats: {e}")

    return StatsResponse(
        total_teachers=total_teachers,
        total_students=total_students,
        total_assignments=total_assignments,
        total_assessments=total_assessments,
        last_sync=last_sync,
        entity_counts=stats,
    )


@app.get("/api/teachers")
async def list_teachers(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    active_only: bool = True,
    search: Optional[str] = None,
    source: Optional[str] = None,  # "postgres", "notion", or None for all
):
    """List all teachers (deduplicated by name) with pagination metadata."""
    from ..extractors import PostgreSQLExtractor
    from ..config import settings

    all_teachers = {}  # Use dict to deduplicate by name

    # Fetch from PostgreSQL
    if source is None or source == "postgres":
        try:
            extractor = PostgreSQLExtractor()
            if extractor.connect():
                conditions = []
                params = []
                if active_only:
                    conditions.append("is_active = true")
                if search:
                    conditions.append("name ILIKE %s")
                    params.append(f"%{search}%")

                where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

                extractor.cursor.execute(
                    f"""
                    SELECT DISTINCT ON (name) id, name, is_active
                    FROM teachers
                    {where_clause}
                    ORDER BY name, created_at DESC
                    """,
                    params if params else None
                )
                for row in extractor.cursor.fetchall():
                    name = row.get("name")
                    if name and name not in all_teachers:
                        all_teachers[name] = {
                            "id": f"pg_teacher_{row['id']}",
                            "pg_id": row['id'],
                            "name": name,
                            "email": None,
                            "position": None,
                            "department": None,
                            "is_active": row.get("is_active", True),
                            "sources": ["postgres"]
                        }
                extractor.disconnect()
        except Exception as e:
            logger.error(f"Failed to fetch PostgreSQL teachers: {e}")

    # Fetch from Notion
    if source is None or source == "notion":
        try:
            from notion_client import Client
            if settings.notion_api_key:
                client = Client(auth=settings.notion_api_key)

                # Fetch from both teacher databases
                db_ids = []
                if settings.notion_teachers_db_id:
                    db_ids.append(("notion", settings.notion_teachers_db_id))
                if getattr(settings, 'notion_online_teachers_db_id', None):
                    db_ids.append(("notion_online", settings.notion_online_teachers_db_id))

                for source_name, db_id in db_ids:
                    try:
                        has_more = True
                        start_cursor = None
                        while has_more:
                            params = {}
                            if start_cursor:
                                params["start_cursor"] = start_cursor

                            response = client.databases.query(database_id=db_id, **params)

                            for page in response.get("results", []):
                                props = page.get("properties", {})

                                # Get name from Full Name or Name title property
                                name = None
                                for key in ["Full Name", "Name"]:
                                    if key in props and props[key].get("title"):
                                        title_list = props[key]["title"]
                                        if title_list:
                                            name = title_list[0].get("plain_text", "")
                                            break

                                if not name:
                                    continue

                                # Apply search filter
                                if search and search.lower() not in name.lower():
                                    continue

                                # Get status
                                status = None
                                if "Status" in props and props["Status"].get("select"):
                                    status = props["Status"]["select"].get("name")

                                is_active = status == "Active" if status else True
                                if active_only and not is_active:
                                    continue

                                # Get email
                                email = props.get("Email", {}).get("email")

                                # Get position (multi-select)
                                position = None
                                if "Position" in props and props["Position"].get("multi_select"):
                                    positions = [p.get("name") for p in props["Position"]["multi_select"]]
                                    position = ", ".join(positions) if positions else None

                                # Merge or add
                                if name in all_teachers:
                                    all_teachers[name]["sources"].append(source_name)
                                    if email:
                                        all_teachers[name]["email"] = email
                                    if position:
                                        all_teachers[name]["position"] = position
                                    all_teachers[name]["notion_id"] = page["id"]
                                else:
                                    all_teachers[name] = {
                                        "id": f"notion_teacher_{page['id'].replace('-', '')}",
                                        "notion_id": page["id"],
                                        "name": name,
                                        "email": email,
                                        "position": position,
                                        "department": None,
                                        "is_active": is_active,
                                        "sources": [source_name]
                                    }

                            has_more = response.get("has_more", False)
                            start_cursor = response.get("next_cursor")
                    except Exception as e:
                        logger.warning(f"Failed to fetch from Notion database {db_id}: {e}")

        except ImportError:
            logger.warning("notion-client not installed")
        except Exception as e:
            logger.error(f"Failed to fetch Notion teachers: {e}")

    # Sort by name and paginate
    sorted_teachers = sorted(all_teachers.values(), key=lambda x: x.get("name", "").lower())
    total = len(sorted_teachers)
    paginated = sorted_teachers[offset:offset + limit]

    return {
        "data": paginated,
        "pagination": {
            "total": total,
            "limit": limit,
            "offset": offset,
            "page": (offset // limit) + 1,
            "total_pages": (total + limit - 1) // limit if total > 0 else 0
        }
    }


@app.get("/api/teachers/{teacher_id}/profile")
async def get_teacher_profile(teacher_id: str):
    """Get comprehensive teacher profile with all connected data from all apps."""
    from ..extractors import PostgreSQLExtractor
    import sqlite3

    # Check if it's a numeric ID (PostgreSQL) or UUID (Notion)
    is_notion_id = "-" in teacher_id or len(teacher_id) > 10

    profile = {
        "id": teacher_id,
        "name": None,
        "email": None,
        "phone": None,
        "position": None,
        "department": None,
        "is_active": True,
        "notion_data": None,
        "data_sources": [],
        "students": [],
        "assignments": [],
        "attendance": [],
        "pg_attendance": [],  # PostgreSQL teacher_attendance
        "coaching": [],
        "apps": [],
        "demo_assessments": [],
        "interviews_conducted": [],  # Interviews where this teacher was interviewer
    }

    pg_teacher_id = None  # Will be set if we find a matching PostgreSQL teacher

    try:
        # 1. Get basic teacher info from PostgreSQL (if numeric ID)
        extractor = PostgreSQLExtractor()
        if extractor.connect():
            if not is_notion_id and teacher_id.isdigit():
                # Direct PostgreSQL lookup by ID
                pg_teacher_id = int(teacher_id)
                extractor.cursor.execute("SELECT * FROM teachers WHERE id = %s", (pg_teacher_id,))
                teacher = extractor.cursor.fetchone()
                if teacher:
                    profile["name"] = teacher.get("name")
                    profile["email"] = teacher.get("email")
                    profile["position"] = teacher.get("position")
                    profile["department"] = teacher.get("department")
                    profile["is_active"] = teacher.get("is_active", True)
                    profile["data_sources"].append("Scheduling DB")
            else:
                # This is a Notion teacher - fetch from Notion first
                try:
                    from notion_client import Client
                    notion = Client(auth=settings.notion_api_key)
                    page = notion.pages.retrieve(page_id=teacher_id)
                    props = page.get("properties", {})

                    # Extract name from Notion (try different property names)
                    name_prop = props.get("Full Name", {}) or props.get("Name", {})
                    if name_prop.get("title") and name_prop["title"]:
                        profile["name"] = name_prop["title"][0]["plain_text"]

                    # Extract email
                    email_prop = props.get("Email", {}) or props.get("email", {})
                    if email_prop.get("email"):
                        profile["email"] = email_prop["email"]

                    profile["notion_data"] = {"page_id": teacher_id}
                    profile["data_sources"].append("Notion Teachers")

                    # Try to find matching PostgreSQL teacher by name
                    if profile["name"]:
                        extractor.cursor.execute(
                            "SELECT id FROM teachers WHERE name ILIKE %s OR name ILIKE %s LIMIT 1",
                            (profile["name"], f"%{profile['name'].split()[-1]}%")
                        )
                        match = extractor.cursor.fetchone()
                        if match:
                            pg_teacher_id = match["id"]
                            profile["data_sources"].append("Scheduling DB")
                except Exception as e:
                    logger.warning(f"Failed to fetch Notion teacher: {e}")

            # Get students this teacher teaches (via assignments) - only if we have a PG teacher ID
            if pg_teacher_id:
                extractor.cursor.execute("""
                    SELECT DISTINCT s.id, s.name, s.student_id, s.grade, s.school
                    FROM students s
                    JOIN assignment_students ast ON s.id = ast.student_id
                    JOIN assignments a ON ast.assignment_id = a.id
                    JOIN assignment_teachers at ON a.id = at.assignment_id
                    WHERE at.teacher_id = %s AND a.is_active = true AND s.is_active = true
                    ORDER BY s.name
                    LIMIT 100
                """, (pg_teacher_id,))
                for row in extractor.cursor.fetchall():
                    profile["students"].append({
                        "id": row["id"],
                        "name": row["name"],
                        "student_id": row["student_id"],
                        "grade": row["grade"],
                        "school": row["school"]
                    })

                # Get assignments
                extractor.cursor.execute("""
                    SELECT a.id, a.date, a.notes, ts.name as time_slot, r.name as room,
                        (SELECT COUNT(*) FROM assignment_students WHERE assignment_id = a.id) as student_count
                    FROM assignments a
                    JOIN assignment_teachers at ON a.id = at.assignment_id
                    LEFT JOIN time_slots ts ON a.time_slot_id = ts.id
                    LEFT JOIN rooms r ON a.room_id = r.id
                    WHERE at.teacher_id = %s AND a.is_active = true
                    ORDER BY a.date DESC
                    LIMIT 50
                """, (pg_teacher_id,))
                for row in extractor.cursor.fetchall():
                    profile["assignments"].append({
                        "id": row["id"],
                        "date": str(row["date"]) if row["date"] else None,
                        "time_slot": row["time_slot"],
                        "room": row["room"],
                        "student_count": row["student_count"],
                        "notes": row["notes"]
                    })

            # Get PostgreSQL teacher_attendance records
            teacher_name = profile.get("name")
            if teacher_name:
                extractor.cursor.execute("""
                    SELECT id, date, status, check_in_time, check_out_time, notes
                    FROM teacher_attendance
                    WHERE teacher_name = %s OR teacher_name LIKE %s
                    ORDER BY date DESC
                    LIMIT 50
                """, (teacher_name, f"%{teacher_name}%"))
                for row in extractor.cursor.fetchall():
                    profile["pg_attendance"].append({
                        "id": row["id"],
                        "date": str(row["date"]) if row["date"] else None,
                        "status": row["status"],
                        "check_in_time": row["check_in_time"],
                        "check_out_time": row["check_out_time"],
                        "notes": row["notes"]
                    })
                if profile["pg_attendance"]:
                    profile["data_sources"].append("Scheduling Attendance")

            extractor.disconnect()

        # 2. Get attendance from SQLite (attendance-checker)
        teacher_name = profile.get("name")
        if teacher_name:
            try:
                attendance_db = Path.home() / "attendance-checker" / "attendance.db"
                if attendance_db.exists():
                    conn = sqlite3.connect(str(attendance_db))
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()

                    # Query attendance table directly - teacher_name format is "[Nickname] Full Name"
                    # Match by nickname in brackets or by full name
                    cursor.execute("""
                        SELECT id, date, start_time, status, minutes_late, late_reason,
                               has_undertime, undertime_minutes, undertime_reason
                        FROM attendance
                        WHERE teacher_name LIKE ? OR teacher_name LIKE ? OR teacher_name LIKE ?
                        ORDER BY date DESC
                        LIMIT 50
                    """, (f"[{teacher_name}]%", f"%{teacher_name}%", f"{teacher_name.split()[0]}%"))
                    for row in cursor.fetchall():
                        profile["attendance"].append({
                            "id": row["id"],
                            "date": row["date"],
                            "start_time": row["start_time"],
                            "status": row["status"],
                            "minutes_late": row["minutes_late"],
                            "late_reason": row["late_reason"],
                            "has_undertime": bool(row["has_undertime"]) if row["has_undertime"] else False,
                            "undertime_minutes": row["undertime_minutes"],
                            "undertime_reason": row["undertime_reason"]
                        })
                    if profile["attendance"]:
                        profile["data_sources"].append("Attendance Tracker")

                    conn.close()
            except Exception as e:
                logger.debug(f"Could not load attendance data: {e}")

        # 3. Get coaching records from SQLite (academy-coaching-app)
        if teacher_name:
            try:
                coaching_db = Path.home() / "academy-coaching-app" / "coaching.db"
                if coaching_db.exists():
                    conn = sqlite3.connect(str(coaching_db))
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()

                    # Find matching employee in coaching db - uses first_name/last_name columns
                    cursor.execute("""
                        SELECT id, first_name, last_name, email, position
                        FROM employees
                        WHERE first_name LIKE ? OR last_name LIKE ?
                              OR (first_name || ' ' || last_name) LIKE ?
                    """, (f"%{teacher_name}%", f"%{teacher_name}%", f"%{teacher_name}%"))
                    emp = cursor.fetchone()

                    if emp:
                        # Store employee info for enrichment
                        if emp["email"] and not profile.get("email"):
                            profile["email"] = emp["email"]
                        if emp["position"] and not profile.get("position"):
                            profile["position"] = emp["position"]

                        cursor.execute("""
                            SELECT cr.id, cr.coaching_date, cr.coaching_type, cr.issue_description,
                                   cr.employee_acknowledged, cr.expected_improvement, cr.follow_up_date,
                                   ot.offense_name, ot.offense_severity
                            FROM coaching_records cr
                            LEFT JOIN offense_types ot ON cr.offense_id = ot.id
                            WHERE cr.employee_id = ?
                            ORDER BY cr.coaching_date DESC
                            LIMIT 20
                        """, (emp["id"],))
                        for row in cursor.fetchall():
                            profile["coaching"].append({
                                "id": row["id"],
                                "date": row["coaching_date"],
                                "coaching_type": row["coaching_type"],
                                "issue_description": row["issue_description"],
                                "employee_acknowledged": bool(row["employee_acknowledged"]),
                                "expected_improvement": row["expected_improvement"],
                                "follow_up_date": row["follow_up_date"],
                                "offense_name": row["offense_name"],
                                "offense_severity": row["offense_severity"]
                            })
                        if profile["coaching"]:
                            profile["data_sources"].append("Coaching App")

                    conn.close()
            except Exception as e:
                logger.debug(f"Could not load coaching data: {e}")

        # 4. Get marketplace apps from SQLite (ican-app-marketplace)
        if teacher_name:
            try:
                marketplace_db = Path.home() / "ican-app-marketplace" / "marketplace.db"
                if marketplace_db.exists():
                    conn = sqlite3.connect(str(marketplace_db))
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()

                    cursor.execute("""
                        SELECT id, title, description, category, student_levels, app_link
                        FROM apps WHERE teacher_name LIKE ? OR teacher_name LIKE ?
                    """, (f"%{teacher_name}%", f"{teacher_name.split()[0]}%"))
                    for row in cursor.fetchall():
                        profile["apps"].append({
                            "id": row["id"],
                            "title": row["title"],
                            "description": row["description"],
                            "category": row["category"],
                            "student_levels": row["student_levels"],
                            "app_link": row["app_link"]
                        })
                    if profile["apps"]:
                        profile["data_sources"].append("App Marketplace")

                    conn.close()
            except Exception as e:
                logger.debug(f"Could not load marketplace data: {e}")

        # 5. Get demo assessments where this teacher was the assessor
        if teacher_name:
            try:
                demo_db = Path.home() / "ican-demo-assessment" / "demo_assessments.db"
                if demo_db.exists():
                    conn = sqlite3.connect(str(demo_db))
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()

                    # Correct column names: demo_date, final_result, additional_comments
                    cursor.execute("""
                        SELECT id, applicant_name, demo_date, topic, level_targeted,
                               assessment_score, final_result, additional_comments, ai_feedback,
                               met_total, ni_total, fail_total
                        FROM assessments WHERE assessor_name LIKE ? OR assessor_name LIKE ?
                        ORDER BY demo_date DESC LIMIT 20
                    """, (f"%{teacher_name}%", f"{teacher_name.split()[0]}%"))
                    for row in cursor.fetchall():
                        profile["demo_assessments"].append({
                            "id": row["id"],
                            "applicant_name": row["applicant_name"],
                            "date": row["demo_date"],
                            "topic": row["topic"],
                            "level_targeted": row["level_targeted"],
                            "score": row["assessment_score"],
                            "result": row["final_result"],
                            "comments": row["additional_comments"],
                            "ai_feedback": row["ai_feedback"],
                            "met_count": row["met_total"],
                            "needs_improvement_count": row["ni_total"],
                            "fail_count": row["fail_total"]
                        })
                    if profile["demo_assessments"]:
                        profile["data_sources"].append("Demo Assessments")

                    conn.close()
            except Exception as e:
                logger.debug(f"Could not load demo assessments data: {e}")

        # 6. Get interviews conducted by this teacher
        if teacher_name:
            try:
                interviews_db = Path.home() / "interview-sheet-generator" / "server" / "interviews.db"
                if interviews_db.exists():
                    conn = sqlite3.connect(str(interviews_db))
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()

                    cursor.execute("""
                        SELECT id, student_name, student_id, interview_type, date, grade, age,
                               pronunciation, fluency, comprehension, insight, vocab, knowledge_level,
                               report_text
                        FROM interviews WHERE interviewer LIKE ? OR interviewer LIKE ?
                        ORDER BY date DESC LIMIT 20
                    """, (f"%{teacher_name}%", f"{teacher_name.split()[0]}%"))
                    for row in cursor.fetchall():
                        profile["interviews_conducted"].append({
                            "id": row["id"],
                            "student_name": row["student_name"],
                            "student_id": row["student_id"],
                            "interview_type": row["interview_type"],
                            "date": row["date"],
                            "grade": row["grade"],
                            "age": row["age"],
                            "scores": {
                                "pronunciation": row["pronunciation"],
                                "fluency": row["fluency"],
                                "comprehension": row["comprehension"],
                                "insight": row["insight"],
                                "vocab": row["vocab"],
                                "knowledge_level": row["knowledge_level"]
                            },
                            "report_text": row["report_text"]
                        })
                    if profile["interviews_conducted"]:
                        profile["data_sources"].append("Interviews")

                    conn.close()
            except Exception as e:
                logger.debug(f"Could not load interviews data: {e}")

        # 7. Search Notion for this teacher
        if teacher_name and settings.notion_teachers_db_id:
            notion_data = search_notion_by_name(settings.notion_teachers_db_id, teacher_name)
            if notion_data:
                profile["notion_data"] = notion_data
                profile["data_sources"].append("Notion")
                # Enrich profile with Notion data
                if notion_data.get("Email") and not profile.get("email"):
                    profile["email"] = notion_data.get("Email")
                if notion_data.get("Contact Number"):
                    profile["phone"] = notion_data.get("Contact Number")
                if notion_data.get("Position"):
                    positions = notion_data.get("Position")
                    profile["position"] = positions if isinstance(positions, str) else ", ".join(positions) if positions else None

    except Exception as e:
        logger.error(f"Failed to load teacher profile: {e}")

    return profile


@app.get("/api/students")
async def list_students(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    active_only: bool = True,
    grade: Optional[str] = None,
    search: Optional[str] = None,
):
    """List all students (deduplicated by name) with pagination metadata."""
    from ..extractors import PostgreSQLExtractor

    try:
        extractor = PostgreSQLExtractor()
        if extractor.connect():
            conditions = []
            params = []

            if active_only:
                conditions.append("is_active = true")
            if grade:
                conditions.append("grade = %s")
                params.append(grade)
            if search:
                conditions.append("(name ILIKE %s OR student_id ILIKE %s)")
                params.extend([f"%{search}%", f"%{search}%"])

            where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

            # Get total count first
            extractor.cursor.execute(f"""
                SELECT COUNT(DISTINCT name) as count FROM students {where}
            """, params if params else None)
            total = extractor.cursor.fetchone()["count"]

            # Get distinct students by name, taking the most recent record for each
            extractor.cursor.execute(
                f"""
                SELECT DISTINCT ON (name) id, name, student_id, grade, school, is_active
                FROM students
                {where}
                ORDER BY name, created_at DESC
                LIMIT %s OFFSET %s
                """,
                (*params, limit, offset) if params else (limit, offset)
            )
            rows = extractor.cursor.fetchall()
            extractor.disconnect()

            students = [
                {
                    "id": f"pg_student_{row['id']}",
                    "pg_id": row['id'],
                    "name": row.get("name"),
                    "student_id": row.get("student_id"),
                    "grade": row.get("grade"),
                    "school": row.get("school"),
                    "is_active": row.get("is_active", True),
                    "sources": ["postgres"]
                }
                for row in rows
            ]

            return {
                "data": students,
                "pagination": {
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "page": (offset // limit) + 1,
                    "total_pages": (total + limit - 1) // limit
                }
            }
    except Exception as e:
        logger.error(f"Failed to list students: {e}")

    return {"data": [], "pagination": {"total": 0, "limit": limit, "offset": offset, "page": 1, "total_pages": 0}}


@app.get("/api/students/{student_id}/profile")
async def get_student_profile(student_id: int):
    """Get comprehensive student profile with all connected data from all apps."""
    from ..extractors import PostgreSQLExtractor
    import sqlite3

    profile = {
        "id": student_id,
        "name": None,
        "student_id": None,
        "grade": None,
        "school": None,
        "is_active": True,
        "notion_data": None,
        "data_sources": [],
        "teachers": [],
        "assignments": [],
        "attendance": [],
        "interviews": [],
        "reports": [],
    }

    try:
        # 1. Get basic student info from PostgreSQL
        extractor = PostgreSQLExtractor()
        if extractor.connect():
            # Basic info
            extractor.cursor.execute("SELECT * FROM students WHERE id = %s", (student_id,))
            student = extractor.cursor.fetchone()
            if student:
                profile["name"] = student.get("name")
                profile["student_id"] = student.get("student_id")
                profile["grade"] = student.get("grade")
                profile["school"] = student.get("school")
                profile["is_active"] = student.get("is_active", True)
                profile["data_sources"].append("Scheduling DB")

            # Get teachers for this student (via assignments)
            extractor.cursor.execute("""
                SELECT DISTINCT t.id, t.name, t.is_active
                FROM teachers t
                JOIN assignment_teachers at ON t.id = at.teacher_id
                JOIN assignments a ON at.assignment_id = a.id
                JOIN assignment_students ast ON a.id = ast.assignment_id
                WHERE ast.student_id = %s AND a.is_active = true AND t.is_active = true
                ORDER BY t.name
                LIMIT 50
            """, (student_id,))
            for row in extractor.cursor.fetchall():
                profile["teachers"].append({
                    "id": row["id"],
                    "name": row["name"],
                    "is_active": row["is_active"]
                })

            # Get assignments for this student
            extractor.cursor.execute("""
                SELECT a.id, a.date, a.notes, ts.name as time_slot, r.name as room,
                    array_agg(DISTINCT t.name) as teacher_names
                FROM assignments a
                JOIN assignment_students ast ON a.id = ast.assignment_id
                LEFT JOIN time_slots ts ON a.time_slot_id = ts.id
                LEFT JOIN rooms r ON a.room_id = r.id
                LEFT JOIN assignment_teachers at ON a.id = at.assignment_id
                LEFT JOIN teachers t ON at.teacher_id = t.id
                WHERE ast.student_id = %s AND a.is_active = true
                GROUP BY a.id, ts.name, r.name
                ORDER BY a.date DESC
                LIMIT 50
            """, (student_id,))
            for row in extractor.cursor.fetchall():
                teacher_names = [n for n in (row["teacher_names"] or []) if n]
                profile["assignments"].append({
                    "id": row["id"],
                    "date": str(row["date"]) if row["date"] else None,
                    "time_slot": row["time_slot"],
                    "room": row["room"],
                    "teacher_names": ", ".join(teacher_names) if teacher_names else None,
                    "notes": row["notes"]
                })

            extractor.disconnect()

        # 2. Get student attendance from SQLite (student-attendance-checker)
        student_name = profile.get("name")
        if student_name:
            try:
                attendance_db = Path.home() / "student-attendance-checker" / "student-attendance.db"
                if attendance_db.exists():
                    conn = sqlite3.connect(str(attendance_db))
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()

                    # Query attendance table directly by student_name
                    cursor.execute("""
                        SELECT id, date, status, start_time, end_time, minutes_late, late_reason, absent_reason,
                               has_undertime, undertime_minutes, undertime_reason
                        FROM attendance
                        WHERE student_name LIKE ? OR student_name LIKE ?
                        ORDER BY date DESC
                        LIMIT 50
                    """, (f"%{student_name}%", f"{student_name.split()[0]}%"))
                    for row in cursor.fetchall():
                        profile["attendance"].append({
                            "id": row["id"],
                            "date": row["date"],
                            "status": row["status"],
                            "start_time": row["start_time"],
                            "end_time": row["end_time"],
                            "minutes_late": row["minutes_late"],
                            "late_reason": row["late_reason"],
                            "absent_reason": row["absent_reason"],
                            "has_undertime": bool(row["has_undertime"]) if row["has_undertime"] else False,
                            "undertime_minutes": row["undertime_minutes"],
                            "undertime_reason": row["undertime_reason"]
                        })
                    if profile["attendance"]:
                        profile["data_sources"].append("Student Attendance")

                    conn.close()
            except Exception as e:
                logger.debug(f"Could not load student attendance data: {e}")

        # 3. Get interview records from SQLite (interview-sheet-generator)
        if student_name:
            try:
                interviews_db = Path.home() / "interview-sheet-generator" / "server" / "interviews.db"
                if interviews_db.exists():
                    conn = sqlite3.connect(str(interviews_db))
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()

                    # Correct columns: interviewer (not assessor_name), report_text (not notes)
                    cursor.execute("""
                        SELECT id, date, interview_type, interviewer, grade, age,
                               pronunciation, fluency, comprehension, insight, vocab, knowledge_level,
                               report_text
                        FROM interviews WHERE student_name LIKE ? OR student_name LIKE ?
                        ORDER BY date DESC LIMIT 20
                    """, (f"%{student_name}%", f"{student_name.split()[0]}%"))
                    for row in cursor.fetchall():
                        profile["interviews"].append({
                            "id": row["id"],
                            "date": row["date"],
                            "interview_type": row["interview_type"],
                            "interviewer": row["interviewer"],
                            "grade": row["grade"],
                            "age": row["age"],
                            "scores": {
                                "pronunciation": row["pronunciation"],
                                "fluency": row["fluency"],
                                "comprehension": row["comprehension"],
                                "insight": row["insight"],
                                "vocab": row["vocab"],
                                "knowledge_level": row["knowledge_level"]
                            },
                            "report_text": row["report_text"]
                        })
                    if profile["interviews"]:
                        profile["data_sources"].append("Interview Records")

                    conn.close()
            except Exception as e:
                logger.debug(f"Could not load interview data: {e}")

        # 4. Get student reports from SQLite (student-report-app)
        if student_name:
            try:
                reports_db = Path.home() / "student-report-app" / "student_reports.db"
                if reports_db.exists():
                    conn = sqlite3.connect(str(reports_db))
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()

                    # Correct table: student_reports, correct columns: report_date, subject, attendance, homework, participation, behavior, notes
                    cursor.execute("""
                        SELECT id, report_date, grade, subject, attendance, homework,
                               participation, behavior, notes
                        FROM student_reports WHERE student_name LIKE ? OR student_name LIKE ?
                        ORDER BY report_date DESC LIMIT 20
                    """, (f"%{student_name}%", f"{student_name.split()[0]}%"))
                    for row in cursor.fetchall():
                        profile["reports"].append({
                            "id": row["id"],
                            "date": row["report_date"],
                            "grade": row["grade"],
                            "subject": row["subject"],
                            "attendance": row["attendance"],
                            "homework": row["homework"],
                            "participation": row["participation"],
                            "behavior": row["behavior"],
                            "notes": row["notes"]
                        })
                    if profile["reports"]:
                        profile["data_sources"].append("Student Reports")

                    conn.close()
            except Exception as e:
                logger.debug(f"Could not load student reports data: {e}")

        # 5. Search Notion for this student
        if student_name and settings.notion_students_db_id:
            notion_data = search_notion_by_name(settings.notion_students_db_id, student_name)
            if notion_data:
                profile["notion_data"] = notion_data
                profile["data_sources"].append("Notion")
                # Enrich profile with Notion data
                if notion_data.get("Grade") and not profile.get("grade"):
                    profile["grade"] = notion_data.get("Grade")
                if notion_data.get("School") and not profile.get("school"):
                    profile["school"] = notion_data.get("School")
                if notion_data.get("English Name"):
                    profile["english_name"] = notion_data.get("English Name")

    except Exception as e:
        logger.error(f"Failed to load student profile: {e}")

    return profile


@app.get("/api/students/{student_id}/assessments")
async def get_student_assessments(student_id: str):
    """Get assessments for a student."""
    # This would query TypeDB for assessments linked to the student
    return []


@app.get("/api/attendance")
async def get_attendance(
    type: str = "teacher",
    date: Optional[str] = None,
    limit: int = 100
):
    """Get attendance records."""
    if type == "teacher":
        from ..extractors.sqlite import TeacherAttendanceExtractor
        extractor = TeacherAttendanceExtractor()
    else:
        from ..extractors.sqlite import StudentAttendanceExtractor
        extractor = StudentAttendanceExtractor()

    try:
        result = extractor.extract_all()
        records = [
            {
                "id": e.external_id,
                "name": e.data.get("teacher_name") or e.data.get("student_name"),
                "teacher_name": e.data.get("teacher_name"),
                "student_name": e.data.get("student_name"),
                "date": e.data.get("date"),
                "status": e.data.get("attendance_status"),
                "start_time": e.data.get("start_time"),
                "minutes_late": e.data.get("minutes_late"),
                "late_reason": e.data.get("late_reason"),
                "absent_reason": e.data.get("absent_reason"),
            }
            for e in result.entities
            if e.entity_type in ("attendance", "student_attendance")
        ]

        if date:
            records = [r for r in records if r.get("date") == date]

        return records[:limit]
    except Exception as e:
        logger.error(f"Failed to get attendance: {e}")
        return []


@app.get("/api/assessments")
async def get_assessments(type: str = "all", limit: int = 50):
    """Get assessment records."""
    assessments = []

    try:
        if type in ("all", "demo"):
            from ..extractors.sqlite import DemoAssessmentExtractor
            extractor = DemoAssessmentExtractor()
            result = extractor.extract_all()
            for e in result.entities:
                assessments.append({
                    "id": e.external_id,
                    "type": "Demo Assessment",
                    "name": e.data.get("applicant_name"),
                    "applicant_name": e.data.get("applicant_name"),
                    "date": e.data.get("date"),
                    "score": e.data.get("assessment_score"),
                    "result": e.data.get("assessment_result"),
                    "assessor": e.data.get("assessor_name"),
                    "feedback": e.data.get("feedback"),
                })

        if type in ("all", "interview"):
            from ..extractors.sqlite import InterviewExtractor
            extractor = InterviewExtractor()
            result = extractor.extract_all()
            for e in result.entities:
                assessments.append({
                    "id": e.external_id,
                    "type": "Interview",
                    "name": e.data.get("student_name"),
                    "student_name": e.data.get("student_name"),
                    "date": e.data.get("date"),
                    "score": None,
                    "result": None,
                    "assessor": e.data.get("assessor_name"),
                    "feedback": e.data.get("feedback"),
                })

        if type in ("all", "report"):
            from ..extractors.sqlite import StudentReportExtractor
            extractor = StudentReportExtractor()
            result = extractor.extract_all()
            for e in result.entities:
                assessments.append({
                    "id": e.external_id,
                    "type": "Student Report",
                    "name": e.data.get("student_name"),
                    "student_name": e.data.get("student_name"),
                    "date": e.data.get("date"),
                    "score": None,
                    "result": None,
                    "assessor": None,
                    "feedback": e.data.get("notes"),
                })
    except Exception as e:
        logger.error(f"Failed to get assessments: {e}")

    return assessments[:limit]


@app.get("/api/coaching")
async def get_coaching(limit: int = 50):
    """Get coaching records."""
    try:
        from ..extractors.sqlite import CoachingExtractor
        extractor = CoachingExtractor()
        result = extractor.extract_all()

        records = []
        employees = {e.external_id: e.data for e in result.entities if e.entity_type == "employee"}
        offenses = {e.external_id: e.data for e in result.entities if e.entity_type == "offense_type"}

        for e in result.entities:
            if e.entity_type == "coaching_record":
                emp_id = f"coaching_employee_{e.data.get('employee_id')}"
                offense_id = f"coaching_offense_{e.data.get('offense_id')}"

                records.append({
                    "id": e.external_id,
                    "employee_name": employees.get(emp_id, {}).get("name", "Unknown"),
                    "date": e.data.get("date"),
                    "coaching_type": e.data.get("coaching_type"),
                    "offense_name": offenses.get(offense_id, {}).get("offense_name"),
                    "offense_severity": e.data.get("offense_severity") or offenses.get(offense_id, {}).get("offense_severity"),
                    "employee_acknowledged": e.data.get("employee_acknowledged", False),
                    "issue_description": e.data.get("issue_description"),
                })

        return records[:limit]
    except Exception as e:
        logger.error(f"Failed to get coaching records: {e}")
        return []


@app.get("/api/apps")
async def get_apps(limit: int = 50):
    """Get educational apps."""
    try:
        from ..extractors.sqlite import MarketplaceExtractor
        extractor = MarketplaceExtractor()
        result = extractor.extract_all()

        return [
            {
                "id": e.external_id,
                "title": e.data.get("title"),
                "description": e.data.get("description"),
                "category": e.data.get("category"),
                "student_levels": e.data.get("student_levels"),
                "app_link": e.data.get("app_link"),
                "image_url": e.data.get("image_url"),
                "teacher_name": e.data.get("teacher_name"),
                "rating": e.data.get("rating"),
            }
            for e in result.entities
            if e.entity_type == "educational_app"
        ][:limit]
    except Exception as e:
        logger.error(f"Failed to get apps: {e}")
        return []


# ==================== Student Analytics & Classes ====================

@app.get("/api/level-tests")
async def get_level_tests(limit: int = 50, student_name: Optional[str] = None):
    """Get level test assessments with AI analysis from student_analytics database."""
    import sqlite3
    from ..config import settings

    try:
        db_path = settings.sqlite_student_analytics_db
        if not db_path.exists():
            return {"data": [], "error": "Student analytics database not found"}

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = """
            SELECT id, student_name, student_id, grade, test_level, test_date,
                   grammar_score, grammar_total, reading_score, reading_total,
                   vocabulary_score, vocabulary_total, listening_score, listening_total,
                   writing_score, writing_total, total_score, total_possible,
                   ai_recommendation, writing_response, writing_analysis,
                   strengths, weaknesses, created_at
            FROM level_tests
        """
        params = []
        if student_name:
            query += " WHERE student_name LIKE ?"
            params.append(f"%{student_name}%")
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        tests = []
        for row in rows:
            tests.append({
                "id": row["id"],
                "student_name": row["student_name"],
                "student_id": row["student_id"],
                "grade": row["grade"],
                "test_level": row["test_level"],
                "test_date": row["test_date"],
                "scores": {
                    "grammar": {"score": row["grammar_score"], "total": row["grammar_total"]},
                    "reading": {"score": row["reading_score"], "total": row["reading_total"]},
                    "vocabulary": {"score": row["vocabulary_score"], "total": row["vocabulary_total"]},
                    "listening": {"score": row["listening_score"], "total": row["listening_total"]},
                    "writing": {"score": row["writing_score"], "total": row["writing_total"]},
                    "total": {"score": row["total_score"], "total": row["total_possible"]},
                },
                "ai_recommendation": row["ai_recommendation"],
                "writing_response": row["writing_response"][:500] if row["writing_response"] else None,
                "writing_analysis": row["writing_analysis"][:500] if row["writing_analysis"] else None,
                "created_at": row["created_at"],
            })

        return {"data": tests, "count": len(tests)}
    except Exception as e:
        logger.error(f"Failed to get level tests: {e}")
        return {"data": [], "error": str(e)}


@app.get("/api/classes")
async def get_classes(
    limit: int = 50,
    category_id: Optional[int] = None,
    search: Optional[str] = None
):
    """Get ICAN classes from ican_classes database."""
    import sqlite3
    from ..config import settings

    try:
        db_path = settings.sqlite_ican_classes_db
        if not db_path.exists():
            return {"data": [], "error": "ICAN classes database not found"}

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = """
            SELECT c.id, c.name, c.description, c.category_id,
                   c.min_grade_level, c.max_grade_level, c.difficulty_level,
                   c.duration_weeks, c.skills_focus, c.learning_objectives,
                   c.materials_needed, c.assessment_methods, c.is_active,
                   cc.name as category_name, cc.color as category_color
            FROM classes c
            LEFT JOIN class_categories cc ON c.category_id = cc.id
            WHERE 1=1
        """
        params = []
        if category_id:
            query += " AND c.category_id = ?"
            params.append(category_id)
        if search:
            query += " AND (c.name LIKE ? OR c.description LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])
        query += " ORDER BY c.name LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        classes = []
        for row in rows:
            classes.append({
                "id": row["id"],
                "name": row["name"],
                "description": row["description"],
                "category_id": row["category_id"],
                "category_name": row["category_name"],
                "category_color": row["category_color"],
                "grade_range": f"{row['min_grade_level']} - {row['max_grade_level']}",
                "min_grade_level": row["min_grade_level"],
                "max_grade_level": row["max_grade_level"],
                "difficulty_level": row["difficulty_level"],
                "duration_weeks": row["duration_weeks"],
                "skills_focus": row["skills_focus"],
                "learning_objectives": row["learning_objectives"],
                "materials_needed": row["materials_needed"],
                "assessment_methods": row["assessment_methods"],
                "is_active": bool(row["is_active"]),
            })

        return {"data": classes, "count": len(classes)}
    except Exception as e:
        logger.error(f"Failed to get classes: {e}")
        return {"data": [], "error": str(e)}


@app.get("/api/class-categories")
async def get_class_categories():
    """Get class categories from ican_classes database."""
    import sqlite3
    from ..config import settings

    try:
        db_path = settings.sqlite_ican_classes_db
        if not db_path.exists():
            return {"data": [], "error": "ICAN classes database not found"}

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT cc.*, COUNT(c.id) as class_count
            FROM class_categories cc
            LEFT JOIN classes c ON cc.id = c.category_id
            GROUP BY cc.id
            ORDER BY cc.name
        """)
        rows = cursor.fetchall()
        conn.close()

        return {
            "data": [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "description": row["description"],
                    "color": row["color"],
                    "class_count": row["class_count"],
                }
                for row in rows
            ]
        }
    except Exception as e:
        logger.error(f"Failed to get class categories: {e}")
        return {"data": [], "error": str(e)}


@app.get("/api/class-schedules")
async def get_class_schedules(class_id: Optional[int] = None, day: Optional[str] = None):
    """Get class schedules from ican_classes database."""
    import sqlite3
    from ..config import settings

    try:
        db_path = settings.sqlite_ican_classes_db
        if not db_path.exists():
            return {"data": [], "error": "ICAN classes database not found"}

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = """
            SELECT cs.*, c.name as class_name, c.description as class_description
            FROM class_schedules cs
            LEFT JOIN classes c ON cs.class_id = c.id
            WHERE 1=1
        """
        params = []
        if class_id:
            query += " AND cs.class_id = ?"
            params.append(class_id)
        if day:
            query += " AND cs.day_of_week = ?"
            params.append(day)
        query += " ORDER BY cs.day_of_week, cs.start_time"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return {
            "data": [
                {
                    "id": row["id"],
                    "class_id": row["class_id"],
                    "class_name": row["class_name"],
                    "class_description": row["class_description"],
                    "teacher_name": row["teacher_name"],
                    "day_of_week": row["day_of_week"],
                    "start_time": row["start_time"],
                    "end_time": row["end_time"],
                    "room": row["room"],
                    "max_students": row["max_students"],
                    "current_enrollment": row["current_enrollment"],
                }
                for row in rows
            ]
        }
    except Exception as e:
        logger.error(f"Failed to get class schedules: {e}")
        return {"data": [], "error": str(e)}


@app.get("/api/schedules")
async def get_schedules(date: Optional[str] = None):
    """Get class schedules."""
    from ..extractors import PostgreSQLExtractor

    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    try:
        extractor = PostgreSQLExtractor()
        if extractor.connect():
            extractor.cursor.execute("""
                SELECT a.id, a.date, a.notes, ts.name as time_slot, r.name as room,
                    array_agg(DISTINCT t.name) as teachers,
                    array_agg(DISTINCT s.name) as students
                FROM assignments a
                LEFT JOIN time_slots ts ON a.time_slot_id = ts.id
                LEFT JOIN rooms r ON a.room_id = r.id
                LEFT JOIN assignment_teachers at ON a.id = at.assignment_id
                LEFT JOIN teachers t ON at.teacher_id = t.id
                LEFT JOIN assignment_students ast ON a.id = ast.assignment_id
                LEFT JOIN students s ON ast.student_id = s.id
                WHERE a.date = %s AND a.is_active = true
                GROUP BY a.id, ts.name, r.name
                ORDER BY ts.name
            """, (date,))

            rows = extractor.cursor.fetchall()
            extractor.disconnect()

            return [
                {
                    "id": row["id"],
                    "date": str(row["date"]),
                    "time_slot": row["time_slot"],
                    "room": row["room"],
                    "teachers": [t for t in (row["teachers"] or []) if t],
                    "students": [s for s in (row["students"] or []) if s],
                    "notes": row["notes"],
                }
                for row in rows
            ]
    except Exception as e:
        logger.error(f"Failed to get schedules: {e}")

    return []


@app.get("/api/search")
async def search(
    q: str = Query(..., min_length=2),
    entity_types: Optional[str] = None,
    limit: int = 50,
    semantic: bool = False,
):
    """Search across all entities in all databases."""
    # If semantic search is enabled and vector store is ready, use it
    vs = get_vector_store()
    if semantic and vs.is_ready():
        vector_results = vs.search(q, n_results=limit)
        formatted = []
        for r in vector_results:
            meta = r.get("metadata", {})
            formatted.append({
                "type": meta.get("type", "unknown"),
                "id": meta.get("pg_id") or r.get("id"),
                "name": meta.get("name", ""),
                "description": meta.get("description", ""),
                "source": meta.get("source", "vector"),
                "url": meta.get("url", ""),
                "similarity": r.get("similarity", 0),
            })
        return {"query": q, "results": formatted, "count": len(formatted), "search_type": "semantic"}

    results = []
    import sqlite3

    from ..extractors import PostgreSQLExtractor

    try:
        extractor = PostgreSQLExtractor()
        if extractor.connect():
            # Search teachers (deduplicated)
            if not entity_types or "teacher" in entity_types:
                extractor.cursor.execute(
                    """SELECT DISTINCT ON (name) id, name
                       FROM teachers WHERE name ILIKE %s
                       ORDER BY name, created_at DESC LIMIT %s""",
                    (f"%{q}%", limit)
                )
                for row in extractor.cursor.fetchall():
                    results.append({
                        "type": "teacher",
                        "id": row['id'],
                        "name": row["name"],
                        "source": "postgres",
                        "url": f"/view/teacher/{row['id']}"
                    })

            # Search students (deduplicated)
            if not entity_types or "student" in entity_types:
                extractor.cursor.execute(
                    """SELECT DISTINCT ON (name) id, name, student_id, grade, school
                       FROM students WHERE name ILIKE %s OR student_id ILIKE %s
                       ORDER BY name, created_at DESC LIMIT %s""",
                    (f"%{q}%", f"%{q}%", limit)
                )
                for row in extractor.cursor.fetchall():
                    results.append({
                        "type": "student",
                        "id": row['id'],
                        "name": row["name"],
                        "student_id": row.get("student_id"),
                        "grade": row.get("grade"),
                        "source": "postgres",
                        "url": f"/view/student/{row['id']}"
                    })

            extractor.disconnect()

        # Search coaching/employees database
        if not entity_types or "employee" in entity_types:
            coaching_db = Path.home() / "academy-coaching-app" / "coaching.db"
            if coaching_db.exists():
                conn = sqlite3.connect(str(coaching_db))
                cursor = conn.cursor()
                cursor.execute(
                    """SELECT id, first_name, last_name, email, position
                       FROM employees WHERE first_name LIKE ? OR last_name LIKE ? OR email LIKE ?
                       LIMIT ?""",
                    (f"%{q}%", f"%{q}%", f"%{q}%", limit)
                )
                for row in cursor.fetchall():
                    results.append({
                        "type": "employee",
                        "id": row[0],
                        "name": f"{row[1]} {row[2]}",
                        "email": row[3],
                        "position": row[4],
                        "source": "coaching"
                    })
                conn.close()

        # Search interviews
        if not entity_types or "interview" in entity_types:
            interviews_db = Path.home() / "interview-sheet-generator" / "server" / "interviews.db"
            if interviews_db.exists():
                conn = sqlite3.connect(str(interviews_db))
                cursor = conn.cursor()
                cursor.execute(
                    """SELECT id, student_name, interviewer, date, interview_type
                       FROM interviews WHERE student_name LIKE ? OR interviewer LIKE ?
                       ORDER BY date DESC LIMIT ?""",
                    (f"%{q}%", f"%{q}%", limit)
                )
                for row in cursor.fetchall():
                    results.append({
                        "type": "interview",
                        "id": row[0],
                        "name": row[1],
                        "interviewer": row[2],
                        "date": row[3],
                        "interview_type": row[4],
                        "source": "interviews"
                    })
                conn.close()

        # Search demo assessments
        if not entity_types or "assessment" in entity_types:
            demo_db = Path.home() / "ican-demo-assessment" / "demo_assessments.db"
            if demo_db.exists():
                conn = sqlite3.connect(str(demo_db))
                cursor = conn.cursor()
                cursor.execute(
                    """SELECT id, applicant_name, assessor_name, demo_date, final_result
                       FROM assessments WHERE applicant_name LIKE ? OR assessor_name LIKE ?
                       ORDER BY demo_date DESC LIMIT ?""",
                    (f"%{q}%", f"%{q}%", limit)
                )
                for row in cursor.fetchall():
                    results.append({
                        "type": "assessment",
                        "id": row[0],
                        "name": row[1],
                        "assessor": row[2],
                        "date": row[3],
                        "result": row[4],
                        "source": "demo_assessments"
                    })
                conn.close()

        # Search apps
        if not entity_types or "app" in entity_types:
            marketplace_db = Path.home() / "ican-app-marketplace" / "marketplace.db"
            if marketplace_db.exists():
                conn = sqlite3.connect(str(marketplace_db))
                cursor = conn.cursor()
                cursor.execute(
                    """SELECT id, title, description, category, teacher_name
                       FROM apps WHERE title LIKE ? OR description LIKE ? OR teacher_name LIKE ?
                       LIMIT ?""",
                    (f"%{q}%", f"%{q}%", f"%{q}%", limit)
                )
                for row in cursor.fetchall():
                    results.append({
                        "type": "app",
                        "id": row[0],
                        "name": row[1],
                        "description": row[2][:100] if row[2] else None,
                        "category": row[3],
                        "teacher": row[4],
                        "source": "marketplace"
                    })
                conn.close()

    except Exception as e:
        logger.error(f"Search failed: {e}")

    return {"query": q, "results": results, "count": len(results)}


# ============================================================================
# EXPORT ENDPOINTS
# ============================================================================

@app.get("/api/export/teachers")
async def export_teachers(format: str = "csv"):
    """Export all teachers as CSV or JSON."""
    from fastapi.responses import StreamingResponse
    import csv
    import io

    from ..extractors import PostgreSQLExtractor

    teachers = []
    try:
        extractor = PostgreSQLExtractor()
        if extractor.connect():
            extractor.cursor.execute("""
                SELECT DISTINCT ON (name) id, name, is_active, created_at
                FROM teachers
                ORDER BY name, created_at DESC
            """)
            teachers = [dict(row) for row in extractor.cursor.fetchall()]
            extractor.disconnect()
    except Exception as e:
        logger.error(f"Export teachers failed: {e}")
        return {"error": str(e)}

    if format == "json":
        return {"data": teachers, "count": len(teachers)}

    # CSV format
    output = io.StringIO()
    if teachers:
        writer = csv.DictWriter(output, fieldnames=teachers[0].keys())
        writer.writeheader()
        writer.writerows(teachers)

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=teachers.csv"}
    )


@app.get("/api/export/students")
async def export_students(format: str = "csv"):
    """Export all students as CSV or JSON."""
    from fastapi.responses import StreamingResponse
    import csv
    import io

    from ..extractors import PostgreSQLExtractor

    students = []
    try:
        extractor = PostgreSQLExtractor()
        if extractor.connect():
            extractor.cursor.execute("""
                SELECT DISTINCT ON (name) id, name, student_id, grade, school, is_active, created_at
                FROM students
                ORDER BY name, created_at DESC
            """)
            students = [dict(row) for row in extractor.cursor.fetchall()]
            extractor.disconnect()
    except Exception as e:
        logger.error(f"Export students failed: {e}")
        return {"error": str(e)}

    if format == "json":
        return {"data": students, "count": len(students)}

    # CSV format
    output = io.StringIO()
    if students:
        writer = csv.DictWriter(output, fieldnames=students[0].keys())
        writer.writeheader()
        writer.writerows(students)

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=students.csv"}
    )


@app.get("/api/export/attendance")
async def export_attendance(
    type: str = "teacher",
    format: str = "csv",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
):
    """Export attendance records as CSV or JSON."""
    from fastapi.responses import StreamingResponse
    import csv
    import io
    import sqlite3

    records = []
    try:
        if type == "teacher":
            db_path = Path.home() / "attendance-checker" / "attendance.db"
        else:
            db_path = Path.home() / "student-attendance-checker" / "student-attendance.db"

        if db_path.exists():
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = "SELECT * FROM attendance"
            params = []

            if date_from or date_to:
                conditions = []
                if date_from:
                    conditions.append("date >= ?")
                    params.append(date_from)
                if date_to:
                    conditions.append("date <= ?")
                    params.append(date_to)
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY date DESC"
            cursor.execute(query, params)
            records = [dict(row) for row in cursor.fetchall()]
            conn.close()

    except Exception as e:
        logger.error(f"Export attendance failed: {e}")
        return {"error": str(e)}

    if format == "json":
        return {"data": records, "count": len(records)}

    # CSV format
    output = io.StringIO()
    if records:
        writer = csv.DictWriter(output, fieldnames=records[0].keys())
        writer.writeheader()
        writer.writerows(records)

    output.seek(0)
    filename = f"{type}_attendance.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ============================================================================
# VECTOR SEARCH ENDPOINTS (Semantic/AI-powered search)
# ============================================================================

# Global vector store instance
_vector_store = None


def get_vector_store():
    """Get or initialize the vector store."""
    global _vector_store
    if _vector_store is None:
        from ..services.vector_store import VectorStore
        _vector_store = VectorStore()
    return _vector_store


@app.get("/api/vector/status")
async def vector_status():
    """Get vector store status and statistics."""
    try:
        vs = get_vector_store()
        if not vs.is_ready():
            return {
                "status": "not_initialized",
                "message": "Vector store not initialized. Call POST /api/vector/index to initialize.",
                "count": 0
            }
        return vs.get_stats()
    except Exception as e:
        return {"status": "error", "message": str(e), "count": 0}


@app.post("/api/vector/index")
async def vector_index():
    """
    Index all data for semantic search.
    This embeds all teachers, students, employees, apps, interviews, and assessments.
    Takes 1-2 minutes on first run (downloads AI model).
    """
    try:
        vs = get_vector_store()

        # Initialize if needed
        if not vs.is_ready():
            logger.info("Initializing vector store for the first time...")
            if not vs.initialize():
                raise HTTPException(500, "Failed to initialize vector store")

        # Index all data
        logger.info("Starting vector indexing...")
        counts = vs.index_all_data()

        return {
            "status": "success",
            "message": "Vector indexing complete",
            "indexed": counts,
            "total": sum(counts.values())
        }
    except Exception as e:
        logger.error(f"Vector indexing failed: {e}")
        raise HTTPException(500, f"Indexing failed: {str(e)}")


@app.get("/api/vector/search")
async def vector_search(
    q: str = Query(..., min_length=2, description="Search query (natural language)"),
    limit: int = Query(10, ge=1, le=50, description="Number of results"),
    type: Optional[str] = Query(None, description="Filter by type: teacher, student, employee, app, interview, assessment")
):
    """
    Semantic search across all indexed data.

    Unlike keyword search, this understands meaning:
    - "math teachers" finds teachers even if "math" isn't in their name
    - "struggling students" finds relevant student records
    - "reading apps for beginners" finds matching educational apps

    Returns results ranked by semantic similarity.
    """
    try:
        vs = get_vector_store()

        if not vs.is_ready():
            # Try to initialize
            if not vs.initialize():
                raise HTTPException(503, "Vector store not available. Run POST /api/vector/index first.")

        # Check if we have indexed data
        stats = vs.get_stats()
        if stats.get("count", 0) == 0:
            return {
                "query": q,
                "results": [],
                "count": 0,
                "message": "No data indexed. Run POST /api/vector/index first."
            }

        # Perform semantic search
        results = vs.search(query=q, n_results=limit, filter_type=type)

        # Format results for frontend
        formatted_results = []
        for r in results:
            meta = r.get("metadata", {})
            formatted_results.append({
                "id": r["id"],
                "name": meta.get("name", ""),
                "type": meta.get("type", ""),
                "source": meta.get("source", "postgres"),
                "url": meta.get("url", ""),
                "similarity": r["similarity"],
                "preview": r["text"][:150] if r.get("text") else "",
                "metadata": meta
            })

        return {
            "query": q,
            "results": formatted_results,
            "count": len(formatted_results),
            "search_type": "semantic"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Vector search failed: {e}")
        raise HTTPException(500, f"Search failed: {str(e)}")


@app.delete("/api/vector/clear")
async def vector_clear():
    """Clear all indexed vectors. Requires re-indexing after."""
    try:
        vs = get_vector_store()
        if vs.is_ready():
            vs.clear()
            return {"status": "success", "message": "Vector store cleared"}
        return {"status": "not_initialized", "message": "Nothing to clear"}
    except Exception as e:
        raise HTTPException(500, f"Failed to clear: {str(e)}")


@app.post("/api/sync", response_model=SyncResponse)
async def trigger_sync(request: SyncRequest):
    """Trigger a data sync from all sources."""
    global last_sync

    start_time = datetime.now()
    response = SyncResponse(status="running", started_at=start_time)

    all_entities = []
    all_relations = []

    try:
        # PostgreSQL
        if not request.sources or "postgres" in request.sources:
            pg_extractor = PostgreSQLExtractor()
            result = pg_extractor.extract_all()
            all_entities.extend(result.entities)
            all_relations.extend(result.relations)
            response.errors.extend(result.errors)

        # SQLite databases
        sqlite_extractors = [
            ("teacher_attendance", TeacherAttendanceExtractor),
            ("student_attendance", StudentAttendanceExtractor),
            ("coaching", CoachingExtractor),
            ("demo_assessment", DemoAssessmentExtractor),
            ("interviews", InterviewExtractor),
            ("student_reports", StudentReportExtractor),
            ("marketplace", MarketplaceExtractor),
        ]

        for name, ExtractorClass in sqlite_extractors:
            if not request.sources or name in request.sources:
                try:
                    extractor = ExtractorClass()
                    result = extractor.extract_all()
                    all_entities.extend(result.entities)
                    all_relations.extend(result.relations)
                    response.errors.extend(result.errors)
                except Exception as e:
                    response.errors.append(f"{name}: {str(e)}")

        # Notion
        if not request.sources or "notion" in request.sources:
            if settings.notion_api_key:
                notion_extractor = NotionExtractor()
                result = notion_extractor.extract_all()
                all_entities.extend(result.entities)
                all_relations.extend(result.relations)
                response.errors.extend(result.errors)

        # Entity resolution
        resolver = EntityResolver()
        resolved_teachers = resolver.resolve_teachers(all_entities)
        resolved_students = resolver.resolve_students(all_entities)

        # Load into TypeDB if connected
        if loader and loader.driver:
            loader.load_resolved_entities(resolved_teachers)
            loader.load_resolved_entities(resolved_students)

            other_entities = [
                e for e in all_entities
                if e.entity_type not in ("teacher", "employee", "student")
            ]
            loader.load_entities(other_entities)
            loader.load_relations(all_relations)

        response.entities_processed = len(all_entities)
        response.relations_processed = len(all_relations)
        response.status = "completed"
        response.completed_at = datetime.now()
        last_sync = datetime.now()
        save_last_sync(last_sync)
        logger.info(f"Sync completed: {len(all_entities)} entities, {len(all_relations)} relations")

    except Exception as e:
        logger.error(f"Sync failed: {e}")
        response.status = "failed"
        response.errors.append(str(e))
        response.completed_at = datetime.now()

    return response


@app.post("/api/query", response_model=QueryResponse)
async def execute_query(request: QueryRequest):
    """Execute a custom TypeQL query."""
    if not loader or not loader.driver:
        raise HTTPException(503, "TypeDB not connected")

    start = time.time()

    try:
        results = loader.query(request.query)
        execution_time = (time.time() - start) * 1000

        return QueryResponse(
            results=results,
            count=len(results),
            execution_time_ms=execution_time,
        )
    except Exception as e:
        raise HTTPException(400, f"Query failed: {str(e)}")


@app.get("/api/graph", response_model=GraphResponse)
async def get_graph(limit: int = 100, include_assignments: bool = True, include_schedules: bool = True):
    """Get comprehensive graph data for visualization with all relationships."""
    from ..extractors import PostgreSQLExtractor
    import sqlite3

    nodes = []
    edges = []
    seen_nodes = set()
    seen_edges = set()

    def add_node(node_id: str, label: str, node_type: str, group: str = None, metadata: dict = None):
        if node_id not in seen_nodes:
            nodes.append(GraphNode(
                id=node_id,
                label=label or "Unknown",
                type=node_type,
                group=group,
                metadata=metadata or {}
            ))
            seen_nodes.add(node_id)

    def add_edge(source: str, target: str, edge_type: str, weight: int = 1):
        edge_key = f"{source}-{target}-{edge_type}"
        if edge_key not in seen_edges and source in seen_nodes and target in seen_nodes:
            edges.append(GraphEdge(
                source=source,
                target=target,
                type=edge_type,
                weight=weight
            ))
            seen_edges.add(edge_key)

    try:
        extractor = PostgreSQLExtractor()
        if extractor.connect():
            # ============================================
            # CORE ENTITIES: Teachers, Students, Assignments
            # ============================================

            # Get assignments first (as central connecting nodes)
            assignment_ids = {}
            teacher_ids_to_fetch = set()
            student_ids_to_fetch = set()

            if include_assignments:
                extractor.cursor.execute("""
                    SELECT a.id, a.date, ts.name as time_slot, ts.start_time, ts.end_time,
                           r.name as room, a.room_id
                    FROM assignments a
                    JOIN time_slots ts ON a.time_slot_id = ts.id
                    JOIN rooms r ON a.room_id = r.id
                    WHERE a.is_active = true
                    ORDER BY a.date DESC
                    LIMIT %s
                """, (limit,))
                for row in extractor.cursor.fetchall():
                    node_id = f"assignment_{row['id']}"
                    label = f"{row['room']} ({row['time_slot']})"
                    add_node(node_id, label, "assignment", "assignments", {
                        "pg_id": row["id"],
                        "date": str(row.get("date")),
                        "room": row.get("room"),
                        "time_slot": row.get("time_slot"),
                        "time": f"{row.get('start_time')}-{row.get('end_time')}"
                    })
                    assignment_ids[row["id"]] = node_id

                # Get teachers linked to these specific assignments
                if assignment_ids:
                    extractor.cursor.execute("""
                        SELECT DISTINCT at.teacher_id
                        FROM assignment_teachers at
                        WHERE at.assignment_id = ANY(%s)
                    """, (list(assignment_ids.keys()),))
                    for row in extractor.cursor.fetchall():
                        teacher_ids_to_fetch.add(row["teacher_id"])

                # Get students linked to these specific assignments
                if assignment_ids:
                    extractor.cursor.execute("""
                        SELECT DISTINCT ast.student_id
                        FROM assignment_students ast
                        WHERE ast.assignment_id = ANY(%s)
                    """, (list(assignment_ids.keys()),))
                    for row in extractor.cursor.fetchall():
                        student_ids_to_fetch.add(row["student_id"])

            # Get teachers (connected ones first, then fill with others)
            teacher_ids = {}
            if teacher_ids_to_fetch:
                extractor.cursor.execute("""
                    SELECT id, name, is_active FROM teachers WHERE id = ANY(%s)
                """, (list(teacher_ids_to_fetch),))
                for row in extractor.cursor.fetchall():
                    node_id = f"teacher_{row['id']}"
                    add_node(node_id, row["name"], "teacher", "teachers", {"pg_id": row["id"]})
                    teacher_ids[row["id"]] = node_id

            # Fill remaining slots with other active teachers
            remaining = limit - len(teacher_ids)
            if remaining > 0:
                extractor.cursor.execute("""
                    SELECT DISTINCT ON (name) id, name, is_active
                    FROM teachers WHERE is_active = true AND id != ALL(%s)
                    ORDER BY name, created_at DESC LIMIT %s
                """, (list(teacher_ids.keys()) if teacher_ids else [], remaining))
                for row in extractor.cursor.fetchall():
                    node_id = f"teacher_{row['id']}"
                    add_node(node_id, row["name"], "teacher", "teachers", {"pg_id": row["id"]})
                    teacher_ids[row["id"]] = node_id

            # Get students (connected ones first, then fill with others)
            student_ids = {}
            if student_ids_to_fetch:
                extractor.cursor.execute("""
                    SELECT id, name, grade, school, is_active FROM students WHERE id = ANY(%s)
                """, (list(student_ids_to_fetch),))
                for row in extractor.cursor.fetchall():
                    node_id = f"student_{row['id']}"
                    add_node(node_id, row["name"], "student", "students", {
                        "pg_id": row["id"],
                        "grade": row.get("grade"),
                        "school": row.get("school")
                    })
                    student_ids[row["id"]] = node_id

            # Fill remaining slots with other active students
            remaining = limit - len(student_ids)
            if remaining > 0:
                extractor.cursor.execute("""
                    SELECT DISTINCT ON (name) id, name, grade, school, is_active
                    FROM students WHERE is_active = true AND id != ALL(%s)
                    ORDER BY name, created_at DESC LIMIT %s
                """, (list(student_ids.keys()) if student_ids else [], remaining))
                for row in extractor.cursor.fetchall():
                    node_id = f"student_{row['id']}"
                    add_node(node_id, row["name"], "student", "students", {
                        "pg_id": row["id"],
                        "grade": row.get("grade"),
                        "school": row.get("school")
                    })
                    student_ids[row["id"]] = node_id

            # Connect teachers to assignments
            if include_assignments and assignment_ids:
                extractor.cursor.execute("""
                    SELECT at.assignment_id, at.teacher_id
                    FROM assignment_teachers at
                    WHERE at.assignment_id = ANY(%s)
                """, (list(assignment_ids.keys()),))
                for row in extractor.cursor.fetchall():
                    teacher_node = teacher_ids.get(row["teacher_id"])
                    assignment_node = assignment_ids.get(row["assignment_id"])
                    if teacher_node and assignment_node:
                        add_edge(teacher_node, assignment_node, "teaches_in")

                # Connect students to assignments
                extractor.cursor.execute("""
                    SELECT ast.assignment_id, ast.student_id
                    FROM assignment_students ast
                    WHERE ast.assignment_id = ANY(%s)
                """, (list(assignment_ids.keys()),))
                for row in extractor.cursor.fetchall():
                    student_node = student_ids.get(row["student_id"])
                    assignment_node = assignment_ids.get(row["assignment_id"])
                    if student_node and assignment_node:
                        add_edge(assignment_node, student_node, "has_student")

            # Get schedules: time slots and rooms as organizational nodes
            if include_schedules:
                # Add time slots as schedule nodes
                extractor.cursor.execute("SELECT id, name, start_time, end_time FROM time_slots ORDER BY display_order")
                for row in extractor.cursor.fetchall():
                    slot_node = f"timeslot_{row['id']}"
                    add_node(slot_node, row["name"], "schedule", "schedule", {
                        "time": f"{row['start_time']}-{row['end_time']}"
                    })

                # Add rooms as location nodes
                extractor.cursor.execute("SELECT id, name FROM rooms ORDER BY display_order")
                room_ids = {}
                for row in extractor.cursor.fetchall():
                    room_node = f"room_{row['id']}"
                    add_node(room_node, row["name"], "room", "rooms")
                    room_ids[row["id"]] = room_node

                # Link assignments to rooms
                if include_assignments:
                    extractor.cursor.execute("""
                        SELECT id, room_id, time_slot_id FROM assignments WHERE is_active = true
                    """)
                    for row in extractor.cursor.fetchall():
                        assignment_node = assignment_ids.get(row["id"])
                        room_node = room_ids.get(row["room_id"])
                        if assignment_node and room_node:
                            add_edge(room_node, assignment_node, "location")

            extractor.disconnect()

        # ============================================
        # CROSS-DATABASE CONNECTIONS
        # ============================================

        # Connect to coaching database for employee relationships
        coaching_db = Path.home() / "academy-coaching-app" / "coaching.db"
        if coaching_db.exists():
            conn = sqlite3.connect(str(coaching_db))
            cursor = conn.cursor()

            # Get recent coaching records to show coaching relationships
            cursor.execute("""
                SELECT DISTINCT e.id, e.first_name, e.last_name, e.position
                FROM employees e
                JOIN coaching_records cr ON e.id = cr.employee_id
                ORDER BY cr.created_at DESC LIMIT 20
            """)
            for row in cursor.fetchall():
                emp_name = f"{row[1]} {row[2]}"
                emp_node = f"employee_{row[0]}"
                add_node(emp_node, emp_name, "employee", "coaching", {
                    "position": row[3]
                })

                # Try to link employee to teacher by name matching
                for tid, tnode in teacher_ids.items():
                    teacher_label = next((n.label for n in nodes if n.id == tnode), "")
                    if teacher_label and (emp_name.lower() in teacher_label.lower() or
                                          teacher_label.lower() in emp_name.lower() or
                                          row[1].lower() in teacher_label.lower()):
                        add_edge(tnode, emp_node, "coaching_profile")
                        break

            conn.close()

        # Connect to demo assessments
        demo_db = Path.home() / "ican-demo-assessment" / "demo_assessments.db"
        if demo_db.exists():
            conn = sqlite3.connect(str(demo_db))
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, applicant_name, assessor_name, final_result
                FROM assessments ORDER BY demo_date DESC LIMIT 15
            """)
            for row in cursor.fetchall():
                assess_node = f"demo_{row[0]}"
                add_node(assess_node, f"Demo: {row[1][:20]}", "assessment", "assessments", {
                    "applicant": row[1],
                    "assessor": row[2],
                    "result": row[3]
                })

                # Link assessor (teacher) to assessment
                if row[2]:
                    for tid, tnode in teacher_ids.items():
                        teacher_label = next((n.label for n in nodes if n.id == tnode), "")
                        if teacher_label and (row[2].lower() in teacher_label.lower() or
                                              teacher_label.split()[0].lower() in row[2].lower()):
                            add_edge(tnode, assess_node, "assessed")
                            break

            conn.close()

        # Connect to interviews
        interviews_db = Path.home() / "interview-sheet-generator" / "server" / "interviews.db"
        if interviews_db.exists():
            conn = sqlite3.connect(str(interviews_db))
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, student_name, interviewer, interview_type
                FROM interviews ORDER BY date DESC LIMIT 20
            """)
            for row in cursor.fetchall():
                interview_node = f"interview_{row[0]}"
                add_node(interview_node, f"Interview: {row[1][:15]}", "interview", "interviews", {
                    "student": row[1],
                    "interviewer": row[2],
                    "type": row[3]
                })

                # Link to student by name
                if row[1]:
                    for sid, snode in student_ids.items():
                        student_label = next((n.label for n in nodes if n.id == snode), "")
                        if student_label and (row[1].lower() in student_label.lower() or
                                              student_label.lower() in row[1].lower()):
                            add_edge(snode, interview_node, "interviewed")
                            break

                # Link interviewer to interview
                if row[2]:
                    for tid, tnode in teacher_ids.items():
                        teacher_label = next((n.label for n in nodes if n.id == tnode), "")
                        if teacher_label and (row[2].lower() in teacher_label.lower() or
                                              teacher_label.split()[0].lower() in row[2].lower()):
                            add_edge(tnode, interview_node, "conducted")
                            break

            conn.close()

    except Exception as e:
        logger.error(f"Failed to build graph: {e}")

    return GraphResponse(nodes=nodes, edges=edges)


# ============================================================================
# DATABASE EXPLORER API ENDPOINTS
# ============================================================================

# SQLite database paths
SQLITE_DATABASES = {
    "attendance": {
        "name": "Teacher Attendance",
        "path": Path.home() / "attendance-checker" / "attendance.db",
        "type": "sqlite"
    },
    "student_attendance": {
        "name": "Student Attendance",
        "path": Path.home() / "student-attendance-checker" / "student-attendance.db",
        "type": "sqlite"
    },
    "coaching": {
        "name": "Coaching Records",
        "path": Path.home() / "academy-coaching-app" / "coaching.db",
        "type": "sqlite"
    },
    "marketplace": {
        "name": "App Marketplace",
        "path": Path.home() / "ican-app-marketplace" / "marketplace.db",
        "type": "sqlite"
    },
    "demo_assessments": {
        "name": "Demo Assessments",
        "path": Path.home() / "ican-demo-assessment" / "demo_assessments.db",
        "type": "sqlite"
    },
    "interviews": {
        "name": "Interviews",
        "path": Path.home() / "interview-sheet-generator" / "server" / "interviews.db",
        "type": "sqlite"
    },
    "student_reports": {
        "name": "Student Reports",
        "path": Path.home() / "student-report-app" / "student_reports.db",
        "type": "sqlite"
    },
    "n8n": {
        "name": "n8n Workflows",
        "path": Path.home() / ".n8n" / "database.sqlite",
        "type": "sqlite"
    },
}


def get_sqlite_tables(db_path: Path) -> List[str]:
    """Get list of tables from a SQLite database."""
    import sqlite3
    if not db_path.exists():
        return []
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall() if not row[0].startswith('sqlite_')]
        conn.close()
        return tables
    except Exception as e:
        logger.error(f"Failed to get tables from {db_path}: {e}")
        return []


def get_sqlite_table_data(db_path: Path, table_name: str, limit: int = 50, offset: int = 0):
    """Get data from a SQLite table."""
    import sqlite3
    if not db_path.exists():
        return {"columns": [], "rows": [], "total": 0}

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Validate table name to prevent SQL injection
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        if not cursor.fetchone():
            conn.close()
            return {"columns": [], "rows": [], "total": 0}

        # Get total count
        cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
        total = cursor.fetchone()[0]

        # Get column info
        cursor.execute(f'PRAGMA table_info("{table_name}")')
        columns = [row[1] for row in cursor.fetchall()]

        # Get rows
        cursor.execute(f'SELECT * FROM "{table_name}" LIMIT ? OFFSET ?', (limit, offset))
        rows = [dict(row) for row in cursor.fetchall()]

        conn.close()
        return {"columns": columns, "rows": rows, "total": total}
    except Exception as e:
        logger.error(f"Failed to get data from {db_path}.{table_name}: {e}")
        return {"columns": [], "rows": [], "total": 0, "error": str(e)}


def get_postgres_tables() -> List[str]:
    """Get list of tables from PostgreSQL database."""
    from ..extractors import PostgreSQLExtractor

    try:
        extractor = PostgreSQLExtractor()
        if extractor.connect():
            extractor.cursor.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """)
            tables = [row["table_name"] for row in extractor.cursor.fetchall()]
            extractor.disconnect()
            return tables
    except Exception as e:
        logger.error(f"Failed to get PostgreSQL tables: {e}")
    return []


def get_postgres_table_data(table_name: str, limit: int = 50, offset: int = 0):
    """Get data from a PostgreSQL table."""
    from ..extractors import PostgreSQLExtractor

    # Whitelist of allowed table names to prevent SQL injection
    allowed_tables = get_postgres_tables()
    if table_name not in allowed_tables:
        return {"columns": [], "rows": [], "total": 0, "error": "Invalid table name"}

    try:
        extractor = PostgreSQLExtractor()
        if extractor.connect():
            # Get total count
            extractor.cursor.execute(f'SELECT COUNT(*) as cnt FROM "{table_name}"')
            total = extractor.cursor.fetchone()["cnt"]

            # Get column info
            extractor.cursor.execute(f"""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = %s ORDER BY ordinal_position
            """, (table_name,))
            columns = [row["column_name"] for row in extractor.cursor.fetchall()]

            # Get rows
            extractor.cursor.execute(f'SELECT * FROM "{table_name}" LIMIT %s OFFSET %s', (limit, offset))
            rows = []
            for row in extractor.cursor.fetchall():
                row_dict = {}
                for col in columns:
                    val = row.get(col)
                    # Convert non-JSON-serializable types
                    if isinstance(val, (datetime,)):
                        val = val.isoformat()
                    elif hasattr(val, '__str__') and not isinstance(val, (str, int, float, bool, type(None), list, dict)):
                        val = str(val)
                    row_dict[col] = val
                rows.append(row_dict)

            extractor.disconnect()
            return {"columns": columns, "rows": rows, "total": total}
    except Exception as e:
        logger.error(f"Failed to get PostgreSQL data from {table_name}: {e}")
        return {"columns": [], "rows": [], "total": 0, "error": str(e)}

    return {"columns": [], "rows": [], "total": 0}


def get_notion_databases() -> List[dict]:
    """Get list of available Notion databases."""
    import requests

    if not settings.notion_api_key:
        return []

    databases = []
    headers = {
        'Authorization': f'Bearer {settings.notion_api_key}',
        'Notion-Version': '2022-06-28',
        'Content-Type': 'application/json'
    }

    if settings.notion_teachers_db_id:
        databases.append({
            "id": "notion_teachers",
            "name": "Notion Teachers",
            "type": "notion",
            "notion_db_id": settings.notion_teachers_db_id,
            "tables": ["teachers"]
        })

    if settings.notion_students_db_id:
        databases.append({
            "id": "notion_students",
            "name": "Notion Students",
            "type": "notion",
            "notion_db_id": settings.notion_students_db_id,
            "tables": ["students"]
        })

    return databases


def get_notion_table_data(notion_db_id: str, limit: int = 50, offset: int = 0) -> dict:
    """Fetch data from a Notion database."""
    import requests

    if not settings.notion_api_key:
        return {"columns": [], "rows": [], "total": 0, "error": "No Notion API key configured"}

    headers = {
        'Authorization': f'Bearer {settings.notion_api_key}',
        'Notion-Version': '2022-06-28',
        'Content-Type': 'application/json'
    }

    try:
        # Query the database
        response = requests.post(
            f'https://api.notion.com/v1/databases/{notion_db_id}/query',
            headers=headers,
            json={'page_size': min(limit, 100)}  # Notion max is 100
        )

        if response.status_code != 200:
            return {"columns": [], "rows": [], "total": 0, "error": response.text}

        data = response.json()
        results = data.get('results', [])

        if not results:
            return {"columns": [], "rows": [], "total": 0}

        # Extract columns from first result's properties
        first_page = results[0]
        columns = list(first_page.get('properties', {}).keys())

        # Extract row data
        rows = []
        for page in results:
            row = {"notion_id": page.get("id")}
            props = page.get('properties', {})

            for col_name, prop in props.items():
                prop_type = prop.get('type')
                value = None

                if prop_type == 'title':
                    title_list = prop.get('title', [])
                    value = title_list[0].get('plain_text', '') if title_list else ''
                elif prop_type == 'rich_text':
                    text_list = prop.get('rich_text', [])
                    value = text_list[0].get('plain_text', '') if text_list else ''
                elif prop_type == 'email':
                    value = prop.get('email', '')
                elif prop_type == 'phone_number':
                    value = prop.get('phone_number', '')
                elif prop_type == 'select':
                    select = prop.get('select')
                    value = select.get('name', '') if select else ''
                elif prop_type == 'multi_select':
                    multi = prop.get('multi_select', [])
                    value = ', '.join([m.get('name', '') for m in multi])
                elif prop_type == 'number':
                    value = prop.get('number')
                elif prop_type == 'date':
                    date_obj = prop.get('date')
                    value = date_obj.get('start', '') if date_obj else ''
                elif prop_type == 'unique_id':
                    uid = prop.get('unique_id', {})
                    value = f"{uid.get('prefix', '')}{uid.get('number', '')}"
                elif prop_type == 'files':
                    files = prop.get('files', [])
                    value = files[0].get('name', '') if files else ''
                elif prop_type == 'created_time':
                    value = prop.get('created_time', '')
                elif prop_type == 'last_edited_time':
                    value = prop.get('last_edited_time', '')
                else:
                    value = str(prop)[:100]

                row[col_name] = value

            rows.append(row)

        # Add notion_id to columns
        columns = ["notion_id"] + columns

        return {
            "columns": columns,
            "rows": rows,
            "total": len(rows),
            "has_more": data.get('has_more', False)
        }

    except Exception as e:
        logger.error(f"Failed to fetch Notion data: {e}")
        return {"columns": [], "rows": [], "total": 0, "error": str(e)}


def search_notion_by_name(notion_db_id: str, name: str) -> Optional[dict]:
    """Search Notion database for a person by name."""
    import requests

    if not settings.notion_api_key or not notion_db_id:
        return None

    headers = {
        'Authorization': f'Bearer {settings.notion_api_key}',
        'Notion-Version': '2022-06-28',
        'Content-Type': 'application/json'
    }

    try:
        search_name = name.strip() if name else ''
        if not search_name:
            return None

        # Search by Nickname first (more reliable for matching scheduling DB names)
        response = requests.post(
            f'https://api.notion.com/v1/databases/{notion_db_id}/query',
            headers=headers,
            json={
                'filter': {
                    'or': [
                        {
                            'property': 'Nickname',
                            'rich_text': {
                                'equals': search_name
                            }
                        },
                        {
                            'property': 'Full Name',
                            'title': {
                                'contains': search_name
                            }
                        }
                    ]
                },
                'page_size': 10
            }
        )

        if response.status_code != 200:
            logger.warning(f"Notion search failed: {response.status_code} - {response.text}")
            return None

        data = response.json()
        results = data.get('results', [])

        # Find best match
        name_lower = search_name.lower()
        for page in results:
            props = page.get('properties', {})

            # Get nickname
            nickname_prop = props.get('Nickname', {}).get('rich_text', [])
            nickname = nickname_prop[0].get('plain_text', '') if nickname_prop else ''

            # Get full name
            full_name_prop = props.get('Full Name', {}).get('title', [])
            full_name = full_name_prop[0].get('plain_text', '') if full_name_prop else ''

            # Check if names match - prioritize exact nickname match
            nickname_lower = nickname.lower()
            full_name_lower = full_name.lower()

            if (name_lower == nickname_lower or
                name_lower in full_name_lower or
                full_name_lower in name_lower or
                f"[{name_lower}]" in full_name_lower):
                # Extract all properties
                result = {"notion_id": page.get("id"), "notion_url": page.get("url")}

                for col_name, prop in props.items():
                    prop_type = prop.get('type')
                    value = None

                    if prop_type == 'title':
                        title_list = prop.get('title', [])
                        value = title_list[0].get('plain_text', '') if title_list else ''
                    elif prop_type == 'rich_text':
                        text_list = prop.get('rich_text', [])
                        value = text_list[0].get('plain_text', '') if text_list else ''
                    elif prop_type == 'email':
                        value = prop.get('email', '')
                    elif prop_type == 'phone_number':
                        value = prop.get('phone_number', '')
                    elif prop_type == 'select':
                        select = prop.get('select')
                        value = select.get('name', '') if select else ''
                    elif prop_type == 'multi_select':
                        multi = prop.get('multi_select', [])
                        value = ', '.join([m.get('name', '') for m in multi])
                    elif prop_type == 'number':
                        value = prop.get('number')
                    elif prop_type == 'date':
                        date_obj = prop.get('date')
                        value = date_obj.get('start', '') if date_obj else ''
                    elif prop_type == 'unique_id':
                        uid = prop.get('unique_id', {})
                        value = f"{uid.get('prefix', '')}{uid.get('number', '')}"

                    result[col_name] = value

                return result

        return None

    except Exception as e:
        logger.error(f"Failed to search Notion: {e}")
        return None


@app.get("/api/databases")
async def list_databases():
    """List all available databases and their tables."""
    databases = []

    # PostgreSQL
    pg_tables = get_postgres_tables()
    if pg_tables:
        databases.append({
            "id": "postgresql",
            "name": "PostgreSQL (scheduling_db)",
            "type": "postgresql",
            "tables": pg_tables
        })

    # SQLite databases
    for db_id, db_info in SQLITE_DATABASES.items():
        tables = get_sqlite_tables(db_info["path"])
        if tables:
            databases.append({
                "id": db_id,
                "name": db_info["name"],
                "type": "sqlite",
                "tables": tables
            })

    # Notion databases
    databases.extend(get_notion_databases())

    return databases


@app.get("/api/databases/{db_id}/tables/{table_name}")
async def get_table_data(
    db_id: str,
    table_name: str,
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """Get data from a specific database table."""
    if db_id == "postgresql":
        return get_postgres_table_data(table_name, limit, offset)
    elif db_id in SQLITE_DATABASES:
        db_path = SQLITE_DATABASES[db_id]["path"]
        return get_sqlite_table_data(db_path, table_name, limit, offset)
    elif db_id == "notion_teachers" and settings.notion_teachers_db_id:
        return get_notion_table_data(settings.notion_teachers_db_id, limit, offset)
    elif db_id == "notion_students" and settings.notion_students_db_id:
        return get_notion_table_data(settings.notion_students_db_id, limit, offset)
    else:
        raise HTTPException(404, f"Database '{db_id}' not found")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
