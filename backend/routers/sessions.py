from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
import json
from db import db_connection
from config import PROJECTS_DIR
from services.claude_fs import list_session_files
from services.indexer import index_session, read_messages_page, read_single_message
from services.variety import file_content_hash, extract_and_count_concepts

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def _ensure_indexed(project_path: str, limit: int = 200):
    """Index recent sessions for a project if not already cached."""
    with db_connection() as db:
        files = list_session_files(project_path)[:limit]

        for f in files:
            session_id = f.stem
            row = db.execute(
                "SELECT file_mtime, content_hash FROM sessions WHERE session_id = ?",
                (session_id,)
            ).fetchone()

            current_mtime = f.stat().st_mtime

            # Fast path: mtime unchanged → skip
            if row and abs(row["file_mtime"] - current_mtime) < 1.0:
                continue

            # Hash gate: if mtime changed but content identical, just update mtime
            if row and row["content_hash"]:
                new_hash = file_content_hash(f)
                if new_hash == row["content_hash"]:
                    db.execute(
                        "UPDATE sessions SET file_mtime = ? WHERE session_id = ?",
                        (current_mtime, session_id)
                    )
                    continue

            meta = index_session(f)
            meta["project_path"] = project_path
            meta["indexed_at"] = datetime.now(timezone.utc).isoformat()

            db.execute("""
                INSERT OR REPLACE INTO sessions
                (session_id, project_path, file_path, file_size, file_mtime,
                 message_count, user_count, assistant_count,
                 first_message, last_message, started_at, model, indexed_at,
                 tools_used, category, importance, duration_mins, content_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                meta["session_id"], project_path, meta["file_path"],
                meta["file_size"], meta["file_mtime"],
                meta["message_count"], meta["user_count"], meta["assistant_count"],
                meta["first_message"], meta["last_message"],
                meta["started_at"], meta["model"], meta["indexed_at"],
                meta.get("tools_used", "[]"),
                meta.get("category", "standard"),
                meta.get("importance", 0),
                meta.get("duration_mins", 0),
                meta.get("content_hash", ""),
            ))

            # Update concept reference counts
            extract_and_count_concepts(
                session_id, project_path,
                meta.get("first_message", ""),
                meta.get("tools_used", "[]"),
            )

        db.commit()


# ── List sessions with filters ─────────────────────────────

@router.get("")
def list_sessions(
    project: str = Query(..., description="Encoded project path"),
    page: int = Query(1, ge=1),
    per_page: int = Query(30, ge=1, le=100),
    q: str = Query("", max_length=200, description="Search in messages or custom title"),
    sort: str = Query("newest", description="newest|oldest|importance|rating|size"),
    category: str = Query("", description="major|standard|minor|automated"),
    starred: Optional[bool] = Query(None),
    archived: Optional[bool] = Query(None, description="Include archived (default: exclude)"),
):
    """List sessions with filtering, sorting, and metadata."""
    _ensure_indexed(project, limit=500)

    with db_connection() as db:
        offset = (page - 1) * per_page

        # Build WHERE clause — all conditions are hardcoded strings or use ? params
        conditions = ["project_path = ?"]
        params: list = [project]

        # Default: hide archived unless explicitly requested
        if archived is None or archived is False:
            conditions.append("archived = 0")
        elif archived is True:
            conditions.append("archived = 1")

        if starred is not None:
            conditions.append("starred = ?")
            params.append(1 if starred else 0)

        if category:
            conditions.append("category = ?")
            params.append(category)

        if q:
            conditions.append("(first_message LIKE ? OR last_message LIKE ? OR custom_title LIKE ? OR tags LIKE ?)")
            params.extend([f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%"])

        where = " AND ".join(conditions)

        # Sort — whitelist ensures no user input is interpolated into SQL
        order_map = {
            "newest": "started_at DESC",
            "oldest": "started_at ASC",
            "importance": "importance DESC, started_at DESC",
            "rating": "rating DESC, importance DESC",
            "size": "message_count DESC",
        }
        order = order_map.get(sort, "started_at DESC")

        rows = db.execute(
            f"SELECT * FROM sessions WHERE {where} ORDER BY {order} LIMIT ? OFFSET ?",
            params + [per_page, offset]
        ).fetchall()

        total = db.execute(
            f"SELECT COUNT(*) as c FROM sessions WHERE {where}",
            params
        ).fetchone()["c"]

        # Category counts for the filter bar
        counts = {}
        for row in db.execute(
            "SELECT category, COUNT(*) as c FROM sessions WHERE project_path = ? AND archived = 0 GROUP BY category",
            (project,)
        ).fetchall():
            counts[row["category"]] = row["c"]

        starred_count = db.execute(
            "SELECT COUNT(*) as c FROM sessions WHERE project_path = ? AND starred = 1",
            (project,)
        ).fetchone()["c"]

        archived_count = db.execute(
            "SELECT COUNT(*) as c FROM sessions WHERE project_path = ? AND archived = 1",
            (project,)
        ).fetchone()["c"]

    sessions = [dict(r) for r in rows]
    return {
        "sessions": sessions,
        "total": total,
        "page": page,
        "per_page": per_page,
        "counts": {
            **counts,
            "starred": starred_count,
            "archived": archived_count,
            "all": sum(counts.values()),
        },
    }


# ── Session detail ──────────────────────────────────────────

@router.get("/{session_id}")
def get_session(session_id: str):
    with db_connection() as db:
        row = db.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Session not found")
    result = dict(row)
    # Parse JSON fields
    for field in ("tools_used", "tags"):
        if result.get(field):
            try:
                result[field] = json.loads(result[field])
            except Exception:
                pass
    return result


# ── Update session metadata ─────────────────────────────────

class SessionUpdate(BaseModel):
    starred: Optional[bool] = None
    archived: Optional[bool] = None
    rating: Optional[int] = None
    custom_title: Optional[str] = None
    tags: Optional[list[str]] = None
    notes: Optional[str] = None
    category: Optional[str] = None


@router.patch("/{session_id}")
def update_session(session_id: str, body: SessionUpdate):
    """Update session metadata (star, archive, rate, title, tags, notes)."""
    with db_connection() as db:
        row = db.execute("SELECT session_id FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Session not found")

        # All update column names are hardcoded, not user-controlled
        updates = []
        params = []

        if body.starred is not None:
            updates.append("starred = ?")
            params.append(1 if body.starred else 0)
        if body.archived is not None:
            updates.append("archived = ?")
            params.append(1 if body.archived else 0)
        if body.rating is not None:
            updates.append("rating = ?")
            params.append(max(0, min(5, body.rating)))
        if body.custom_title is not None:
            updates.append("custom_title = ?")
            params.append(body.custom_title)
        if body.tags is not None:
            updates.append("tags = ?")
            params.append(json.dumps(body.tags))
        if body.notes is not None:
            updates.append("notes = ?")
            params.append(body.notes)
        if body.category is not None:
            updates.append("category = ?")
            params.append(body.category)

        if updates:
            params.append(session_id)
            db.execute(f"UPDATE sessions SET {', '.join(updates)} WHERE session_id = ?", params)
            db.commit()

    return {"updated": session_id, "fields": [u.split(" = ")[0] for u in updates]}


# ── Batch operations ────────────────────────────────────────

class BatchUpdate(BaseModel):
    session_ids: list[str]
    starred: Optional[bool] = None
    archived: Optional[bool] = None
    category: Optional[str] = None


@router.patch("/batch/update")
def batch_update(body: BatchUpdate):
    """Batch update multiple sessions (star, archive, categorize)."""
    with db_connection() as db:
        # All update column names are hardcoded, not user-controlled
        updates = []
        params_base = []

        if body.starred is not None:
            updates.append("starred = ?")
            params_base.append(1 if body.starred else 0)
        if body.archived is not None:
            updates.append("archived = ?")
            params_base.append(1 if body.archived else 0)
        if body.category is not None:
            updates.append("category = ?")
            params_base.append(body.category)

        if updates:
            placeholders = ",".join("?" * len(body.session_ids))
            db.execute(
                f"UPDATE sessions SET {', '.join(updates)} WHERE session_id IN ({placeholders})",
                params_base + body.session_ids
            )
            db.commit()

    return {"updated": len(body.session_ids)}


# ── Messages ────────────────────────────────────────────────

@router.get("/{session_id}/messages")
def get_messages(
    session_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
):
    with db_connection() as db:
        row = db.execute("SELECT file_path FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Session not found")
    jsonl_path = Path(row["file_path"])
    if not jsonl_path.exists():
        raise HTTPException(404, "Session file not found on disk")
    return read_messages_page(jsonl_path, page=page, per_page=per_page)


@router.get("/{session_id}/messages/{line_number}")
def get_message(session_id: str, line_number: int):
    if line_number < 1:
        raise HTTPException(400, "line_number must be >= 1")
    with db_connection() as db:
        row = db.execute("SELECT file_path FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Session not found")
    result = read_single_message(Path(row["file_path"]), line_number)
    if not result:
        raise HTTPException(404, "Message not found")
    return result
