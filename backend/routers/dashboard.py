from fastapi import APIRouter
from services.claude_fs import discover_projects, list_memory_files
from db import get_db

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
def dashboard():
    """Aggregate stats across all projects."""
    projects = discover_projects()

    # Get recent sessions from cache
    db = get_db()
    recent = db.execute("""
        SELECT session_id, project_path, first_message, started_at, model, message_count
        FROM sessions ORDER BY started_at DESC LIMIT 20
    """).fetchall()

    total_sessions = db.execute("SELECT COUNT(*) as c FROM sessions").fetchone()["c"]
    db.close()

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
    }
