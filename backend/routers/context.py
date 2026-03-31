"""Context branches — stored locally in cache.db. No external dependencies."""

import json
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import Optional
from db import get_db

router = APIRouter(prefix="/api/context", tags=["context"])

VALID_TYPES = ["formula", "clause", "pattern", "insight", "substrate"]


def _format_entry(row) -> dict:
    d = dict(row)
    if d.get("tags"):
        try:
            d["tags"] = json.loads(d["tags"])
        except Exception:
            d["tags"] = []
    else:
        d["tags"] = []
    return d


# ── List / search ────────────────────────────────────────────

@router.get("")
def list_context(
    project: str = Query("", description="Filter by project (empty = all)"),
    type: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    """List context branches with optional filters."""
    db = get_db()

    query = "SELECT * FROM context_branches WHERE 1=1"
    params: list = []

    if project:
        query += " AND project = ?"
        params.append(project)

    if type:
        query += " AND type = ?"
        params.append(type)

    if q:
        query += " AND (content LIKE ? OR summary LIKE ? OR tags LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])

    if tag:
        query += ' AND tags LIKE ?'
        params.append(f'%"{tag}"%')

    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    rows = db.execute(query, params).fetchall()
    db.close()

    return {"results": [_format_entry(r) for r in rows], "total": len(rows)}


# ── Stats ────────────────────────────────────────────────────

@router.get("/stats")
def context_stats(project: str = Query("", description="Filter by project")):
    """Get counts by type."""
    db = get_db()

    if project:
        rows = db.execute(
            "SELECT type, COUNT(*) as count FROM context_branches WHERE project = ? GROUP BY type",
            (project,)
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT type, COUNT(*) as count FROM context_branches GROUP BY type"
        ).fetchall()

    db.close()
    stats = {r["type"]: r["count"] for r in rows}
    return {"stats": stats, "total": sum(stats.values())}


# ── Create ───────────────────────────────────────────────────

class ContextCreate(BaseModel):
    type: str
    content: str
    summary: Optional[str] = None
    tags: Optional[list[str]] = None
    project: Optional[str] = ""


@router.post("")
def create_context(body: ContextCreate):
    """Store a new context branch."""
    if body.type not in VALID_TYPES:
        raise HTTPException(400, f"Invalid type. Must be: {', '.join(VALID_TYPES)}")

    db = get_db()
    entry_id = str(uuid.uuid4())[:21]
    now = datetime.now(timezone.utc).isoformat()

    db.execute(
        "INSERT INTO context_branches (id, project, type, content, summary, tags, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (entry_id, body.project or "", body.type, body.content, body.summary or "",
         json.dumps(body.tags) if body.tags else "[]", now)
    )
    db.commit()
    db.close()

    return {"id": entry_id, "type": body.type, "created": True}


# ── Delete ───────────────────────────────────────────────────

@router.delete("/{entry_id}")
def delete_context(entry_id: str):
    """Delete a context branch."""
    db = get_db()
    db.execute("DELETE FROM context_branches WHERE id = ?", (entry_id,))
    db.commit()
    db.close()
    return {"deleted": entry_id}


# ── Update ───────────────────────────────────────────────────

class ContextUpdate(BaseModel):
    content: Optional[str] = None
    summary: Optional[str] = None
    tags: Optional[list[str]] = None
    type: Optional[str] = None


@router.patch("/{entry_id}")
def update_context(entry_id: str, body: ContextUpdate):
    """Update a context branch."""
    db = get_db()
    row = db.execute("SELECT id FROM context_branches WHERE id = ?", (entry_id,)).fetchone()
    if not row:
        db.close()
        raise HTTPException(404, "Context branch not found")

    updates = []
    params = []

    if body.content is not None:
        updates.append("content = ?")
        params.append(body.content)
    if body.summary is not None:
        updates.append("summary = ?")
        params.append(body.summary)
    if body.tags is not None:
        updates.append("tags = ?")
        params.append(json.dumps(body.tags))
    if body.type is not None and body.type in VALID_TYPES:
        updates.append("type = ?")
        params.append(body.type)

    if updates:
        params.append(entry_id)
        db.execute(f"UPDATE context_branches SET {', '.join(updates)} WHERE id = ?", params)
        db.commit()

    db.close()
    return {"updated": entry_id}
