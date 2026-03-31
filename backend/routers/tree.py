"""Working tree — auto-generated + manual overrides. The steering mechanism."""

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
from db import db_connection
from services.tree_builder import build_tree
from security import sanitize_node_id

router = APIRouter(prefix="/api/tree", tags=["tree"])

VALID_STATUSES = {"done", "active", "partial", "todo", "empty", "blocked", "noted", ""}


# ── Ensure overrides table exists ────────────────────────────

def _ensure_table():
    with db_connection() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS tree_overrides (
                node_id TEXT NOT NULL,
                project TEXT NOT NULL,
                status TEXT DEFAULT '',
                note TEXT DEFAULT '',
                priority INTEGER DEFAULT 0,
                updated_at TEXT,
                PRIMARY KEY (node_id, project)
            )
        """)
        db.commit()


_ensure_table()


# ── Get full tree ────────────────────────────────────────────

@router.get("")
def get_tree(
    project: str = Query(..., description="Encoded project path"),
    repo: str = Query("", description="Absolute path to the project repo on disk"),
):
    """Get the full working tree for a project.

    The tree is auto-generated from live data (sequences, maps, sessions,
    context branches) and enriched with manual overrides (status, notes, priority).
    """
    tree = build_tree(project, repo)
    return tree


# ── Override a node ──────────────────────────────────────────

class NodeOverride(BaseModel):
    node_id: str
    status: Optional[str] = None  # done, active, partial, todo, empty, blocked, noted
    note: Optional[str] = None
    priority: Optional[int] = None  # 0=normal, 1=high, 2=critical


@router.patch("/override")
def set_override(
    project: str = Query(...),
    body: NodeOverride = ...,
):
    """Set a manual override on a tree node. Overrides survive regeneration."""
    if body.status is not None and body.status not in VALID_STATUSES:
        raise HTTPException(400, f"Invalid status. Must be one of: {', '.join(s or '(empty)' for s in VALID_STATUSES)}")
    if body.priority is not None and not (0 <= body.priority <= 2):
        raise HTTPException(400, "Priority must be 0 (normal), 1 (high), or 2 (critical)")

    with db_connection() as db:
        now = datetime.now(timezone.utc).isoformat()

        # Upsert
        existing = db.execute(
            "SELECT node_id FROM tree_overrides WHERE node_id = ? AND project = ?",
            (body.node_id, project)
        ).fetchone()

        if existing:
            # All update column names are hardcoded, not user-controlled
            updates = []
            params = []
            if body.status is not None:
                updates.append("status = ?")
                params.append(body.status)
            if body.note is not None:
                updates.append("note = ?")
                params.append(body.note)
            if body.priority is not None:
                updates.append("priority = ?")
                params.append(body.priority)
            updates.append("updated_at = ?")
            params.append(now)
            params.extend([body.node_id, project])
            db.execute(f"UPDATE tree_overrides SET {', '.join(updates)} WHERE node_id = ? AND project = ?", params)
        else:
            db.execute(
                "INSERT INTO tree_overrides (node_id, project, status, note, priority, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (body.node_id, project, body.status or "", body.note or "", body.priority or 0, now)
            )

        db.commit()
    return {"node_id": body.node_id, "updated": True}


# ── Add a discovery node ─────────────────────────────────────

class DiscoveryNode(BaseModel):
    label: str
    note: str = ""
    priority: int = 0


@router.post("/discovery")
def add_discovery(
    project: str = Query(...),
    body: DiscoveryNode = ...,
):
    """Add a manual discovery node to the tree. For things learned along the way."""
    if not (0 <= body.priority <= 2):
        raise HTTPException(400, "Priority must be 0 (normal), 1 (high), or 2 (critical)")

    safe_id = sanitize_node_id(body.label)
    if not safe_id:
        raise HTTPException(400, "Label must contain at least one alphanumeric character")
    node_id = f"discovery/{safe_id}"

    with db_connection() as db:
        now = datetime.now(timezone.utc).isoformat()
        db.execute(
            "INSERT OR REPLACE INTO tree_overrides (node_id, project, status, note, priority, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (node_id, project, "noted", body.note or body.label, body.priority, now)
        )
        db.commit()
    return {"node_id": node_id, "created": True}


# ── List all overrides ───────────────────────────────────────

@router.get("/overrides")
def list_overrides(project: str = Query(...)):
    """List all manual overrides for a project."""
    with db_connection() as db:
        rows = db.execute(
            "SELECT * FROM tree_overrides WHERE project = ? ORDER BY updated_at DESC",
            (project,)
        ).fetchall()
    return {"overrides": [dict(r) for r in rows], "total": len(rows)}
