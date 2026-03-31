"""Thread suggestion and management — auto-extract topics from sessions."""

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from pathlib import Path
from config import PROJECTS_DIR
from services.topic_extractor import extract_topics_from_sessions, generate_thread_content

router = APIRouter(prefix="/api/threads", tags=["threads"])


@router.get("/suggest")
def suggest_threads(
    project: str = Query(..., description="Encoded project path"),
    min_sessions: int = Query(2, ge=2, le=10),
):
    """Analyze sessions and suggest meta-threads based on recurring topics.

    Scans all indexed sessions for a project, extracts keywords,
    clusters by co-occurrence, and returns suggested thread groupings.
    """
    clusters = extract_topics_from_sessions(project)

    # Filter by minimum session count
    clusters = [c for c in clusters if c["session_count"] >= min_sessions]

    return {
        "suggestions": clusters,
        "total": len(clusters),
        "project": project,
    }


class CreateThreadFromSuggestion(BaseModel):
    topic: str
    suggested_title: str
    keywords: list[str]
    sessions: list[dict]
    session_count: int
    total_messages: int
    total_importance: float
    date_range: dict


@router.post("/create-from-suggestion")
def create_thread_from_suggestion(
    project: str = Query(...),
    body: CreateThreadFromSuggestion = ...,
):
    """Create a thread file from a suggested topic cluster."""
    cluster = {
        "topic": body.topic,
        "keywords": body.keywords,
        "sessions": body.sessions,
        "session_count": body.session_count,
        "total_messages": body.total_messages,
        "total_importance": body.total_importance,
        "suggested_title": body.suggested_title,
        "date_range": body.date_range,
    }

    content = generate_thread_content(cluster)

    memory_dir = PROJECTS_DIR / project / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)

    # Sanitize filename
    safe_topic = body.topic.replace(" ", "_").replace("/", "_")[:30]
    filename = f"meta_thread_{safe_topic}.md"
    filepath = memory_dir / filename

    if filepath.exists():
        raise HTTPException(409, f"Thread already exists: {filename}")

    filepath.write_text(content, encoding="utf-8")

    return {
        "filename": filename,
        "path": str(filepath),
        "created": True,
        "topic": body.topic,
        "session_count": body.session_count,
    }
