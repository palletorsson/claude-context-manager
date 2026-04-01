from fastapi import APIRouter, Query
from services.claude_fs import discover_projects, list_memory_files
from services.variety import get_temperature_summary, get_top_concepts
from db import db_connection

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
def dashboard():
    """Aggregate stats across all projects."""
    projects = discover_projects()

    # Get recent sessions from cache
    with db_connection() as db:
        recent = db.execute("""
            SELECT session_id, project_path, first_message, started_at, model, message_count
            FROM sessions ORDER BY started_at DESC LIMIT 20
        """).fetchall()

        total_sessions = db.execute("SELECT COUNT(*) as c FROM sessions").fetchone()["c"]

    # Active threads across all projects
    active_threads = []
    for p in projects:
        for f in list_memory_files(p["encoded_path"]):
            if f["status"] in ("active", "paused") and f["filename"].startswith("thread_"):
                active_threads.append({
                    "project": p["display_name"],
                    "project_path": p["encoded_path"],
                    **f,
                })

    return {
        "projects": projects,
        "recent_sessions": [dict(r) for r in recent],
        "total_sessions": total_sessions,
        "active_threads": active_threads,
        "total_memory_files": sum(p["memory_count"] for p in projects),
        "temperature_summary": get_temperature_summary(),
    }


@router.get("/variety")
def variety_stats(project: str = Query("", description="Filter by project (empty = all)")):
    """Variety engineering stats — temperature distribution and top concepts."""
    return {
        "temperature_distribution": get_temperature_summary(project),
        "top_concepts": get_top_concepts(project, limit=20),
        "top_keywords": get_top_concepts(project, concept_type="keyword", limit=15),
        "top_tools": get_top_concepts(project, concept_type="tool", limit=10),
    }
