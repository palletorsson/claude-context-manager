"""Build a project working tree from live data + manual overrides.

The tree combines auto-scanned state (sequences, maps, artifacts, encyclopedia pages)
with manual annotations (notes, status overrides, priorities, discoveries).
Auto-generated nodes get a status from the data. Manual overrides win.
"""

import json
import os
from pathlib import Path
from datetime import datetime, timezone
from db import db_connection
from config import CLAUDE_DIR


def build_tree(project_path: str, repo_path: str = "") -> dict:
    """Build the full working tree for a project.

    Combines:
    - Auto-scanned game state (sequences, maps from LOD/spine)
    - Encyclopedia state (from search API stats if available)
    - Context manager state (sessions, threads, branches)
    - Manual overrides from tree_overrides in cache.db
    """
    with db_connection() as db:
        # Load manual overrides
        overrides = {}
        try:
            rows = db.execute(
                "SELECT node_id, status, note, priority FROM tree_overrides WHERE project = ?",
                (project_path,)
            ).fetchall()
            overrides = {r["node_id"]: dict(r) for r in rows}
        except Exception:
            pass

        tree = {
            "generated": datetime.now(timezone.utc).isoformat(),
            "project": project_path,
            "children": [],
        }

        # ── Game branch ──
        game = _build_game_branch(repo_path, overrides)
        tree["children"].append(game)

        # ── Encyclopedia branch ──
        encyclopedia = _build_encyclopedia_branch(overrides)
        tree["children"].append(encyclopedia)

        # ── Context Manager branch ──
        context = _build_context_branch(project_path, db, overrides)
        tree["children"].append(context)

        # ── Writer branch ──
        writer = _build_writer_branch(overrides)
        tree["children"].append(writer)

        # ── Discoveries (manual nodes added by user) ──
        discovery_rows = db.execute(
            "SELECT node_id, status, note, priority FROM tree_overrides WHERE project = ? AND node_id LIKE 'discovery/%'",
            (project_path,)
        ).fetchall()
        if discovery_rows:
            discoveries = {
                "id": "discoveries",
                "label": "Discoveries",
                "type": "branch",
                "status": "active",
                "children": [
                    {
                        "id": r["node_id"],
                        "label": r["note"] or r["node_id"].split("/")[-1],
                        "type": "leaf",
                        "status": r["status"] or "noted",
                        "priority": r["priority"] or 0,
                        "note": r["note"] or "",
                    }
                    for r in discovery_rows
                ],
            }
            tree["children"].append(discoveries)

    # Compute summary stats
    tree["stats"] = _compute_stats(tree)

    return tree


def _apply_override(node: dict, overrides: dict) -> dict:
    """Apply manual override to a node if one exists."""
    override = overrides.get(node.get("id", ""))
    if override:
        if override.get("status"):
            node["status"] = override["status"]
            node["overridden"] = True
        if override.get("note"):
            node["note"] = override["note"]
        if override.get("priority"):
            node["priority"] = override["priority"]
    return node


def _build_game_branch(repo_path: str, overrides: dict) -> dict:
    """Build game tree from sequences/maps on disk."""
    game = {
        "id": "game",
        "label": "VR Game",
        "type": "branch",
        "status": "active",
        "children": [],
    }

    # Try to read curriculum spine
    spine_path = Path(repo_path) / "commons" / "maps" / "curriculum_spine.json" if repo_path else None
    spine_sequences = []

    if spine_path and spine_path.exists():
        try:
            with open(spine_path) as f:
                spine_data = json.load(f)
            spine_sequences = spine_data.get("spine", {}).get("sequences", [])
        except Exception:
            pass

    # Try to read sequence files
    seq_dir = Path(repo_path) / "commons" / "maps" / "sequences" if repo_path else None
    all_sequences = {}

    if seq_dir and seq_dir.exists():
        for f in sorted(seq_dir.glob("*.json")):
            try:
                with open(f) as fh:
                    data = json.load(fh)
                if "sequences" in data and isinstance(data["sequences"], dict):
                    for sid, sdata in data["sequences"].items():
                        maps = sdata.get("maps", [])
                        all_sequences[sid] = {
                            "name": sdata.get("name", sid),
                            "maps": maps,
                            "map_count": len(maps),
                            "description": (sdata.get("description") or "")[:100],
                        }
            except Exception:
                continue

    # Build spine sequences first
    spine_ids = set()
    for entry in spine_sequences:
        sid = entry.get("name", "")
        spine_ids.add(sid)
        seq_data = all_sequences.get(sid, {})
        maps = seq_data.get("maps", [])

        # Determine status
        if not maps:
            status = "empty"
        elif len(maps) >= 5:
            status = "complete"
        else:
            status = "partial"

        seq_node = {
            "id": f"game/spine/{sid}",
            "label": f"{seq_data.get('name', sid)}",
            "type": "branch",
            "status": status,
            "phase": entry.get("phase", ""),
            "order": entry.get("order", 99),
            "map_count": len(maps),
            "children": [
                _apply_override({
                    "id": f"game/spine/{sid}/{m}",
                    "label": m,
                    "type": "leaf",
                    "status": "exists",
                }, overrides)
                for m in maps[:20]  # Limit to avoid huge trees
            ],
        }
        game["children"].append(_apply_override(seq_node, overrides))

    # Branch sequences
    for sid, sdata in sorted(all_sequences.items()):
        if sid in spine_ids:
            continue
        maps = sdata.get("maps", [])
        if not maps:
            status = "empty"
        elif len(maps) >= 3:
            status = "complete"
        else:
            status = "partial"

        seq_node = {
            "id": f"game/branch/{sid}",
            "label": sdata.get("name", sid),
            "type": "branch",
            "status": status,
            "map_count": len(maps),
            "children": [],  # Don't expand branch sequences to keep tree manageable
        }
        game["children"].append(_apply_override(seq_node, overrides))

    return _apply_override(game, overrides)


def _build_encyclopedia_branch(overrides: dict) -> dict:
    """Build encyclopedia tree."""
    enc = {
        "id": "encyclopedia",
        "label": "Encyclopedia",
        "type": "branch",
        "status": "active",
        "children": [
            _apply_override({"id": "encyclopedia/search", "label": "Search Engine (3,261 items)", "type": "leaf", "status": "done"}, overrides),
            _apply_override({"id": "encyclopedia/substrates", "label": "Substrates Page", "type": "leaf", "status": "done"}, overrides),
            _apply_override({"id": "encyclopedia/map-builder", "label": "Map Builder", "type": "leaf", "status": "done"}, overrides),
            _apply_override({"id": "encyclopedia/map-studio", "label": "Map Studio", "type": "leaf", "status": "done"}, overrides),
            _apply_override({"id": "encyclopedia/voxel-editor", "label": "Voxel Editor", "type": "leaf", "status": "done"}, overrides),
            _apply_override({"id": "encyclopedia/pattern-maker", "label": "Pattern Maker", "type": "leaf", "status": "done"}, overrides),
            _apply_override({"id": "encyclopedia/facade-builder", "label": "Facade Builder", "type": "leaf", "status": "done"}, overrides),
            _apply_override({"id": "encyclopedia/mosaic-editor", "label": "Mosaic Editor", "type": "leaf", "status": "done"}, overrides),
            _apply_override({"id": "encyclopedia/floor-plan-editor", "label": "Floor Plan Editor", "type": "leaf", "status": "done"}, overrides),
            _apply_override({"id": "encyclopedia/onboarding", "label": "Onboarding Page", "type": "leaf", "status": "done"}, overrides),
            _apply_override({"id": "encyclopedia/motif-catalog", "label": "Motif Catalog Page", "type": "leaf", "status": "todo"}, overrides),
            _apply_override({"id": "encyclopedia/primitives", "label": "Primitive Editors (16/20)", "type": "leaf", "status": "partial"}, overrides),
        ],
    }
    return _apply_override(enc, overrides)


def _build_context_branch(project_path: str, db, overrides: dict) -> dict:
    """Build context manager tree from live data."""
    # Count sessions, threads, branches
    session_count = 0
    try:
        row = db.execute("SELECT COUNT(*) as c FROM sessions WHERE project_path = ?", (project_path,)).fetchone()
        session_count = row["c"] if row else 0
    except Exception:
        pass

    branch_count = 0
    try:
        row = db.execute("SELECT COUNT(*) as c FROM context_branches").fetchone()
        branch_count = row["c"] if row else 0
    except Exception:
        pass

    ctx = {
        "id": "context",
        "label": "Context Manager",
        "type": "branch",
        "status": "active",
        "children": [
            _apply_override({"id": "context/app", "label": f"App v0.2.0 (light theme)", "type": "leaf", "status": "done"}, overrides),
            _apply_override({"id": "context/sessions", "label": f"Sessions ({session_count} indexed)", "type": "leaf", "status": "done"}, overrides),
            _apply_override({"id": "context/branches", "label": f"Context Branches ({branch_count})", "type": "leaf", "status": "done"}, overrides),
            _apply_override({"id": "context/threads", "label": "Meta-Thread Suggestions", "type": "leaf", "status": "done"}, overrides),
            _apply_override({"id": "context/tree", "label": "Working Tree (this)", "type": "leaf", "status": "active"}, overrides),
            _apply_override({"id": "context/github", "label": "Push to GitHub", "type": "leaf", "status": "todo"}, overrides),
            _apply_override({"id": "context/mcp", "label": "MCP Server Integration", "type": "leaf", "status": "todo"}, overrides),
        ],
    }
    return _apply_override(ctx, overrides)


def _build_writer_branch(overrides: dict) -> dict:
    """Build writer tree."""
    writer = {
        "id": "writer",
        "label": "Ada Writer (Book)",
        "type": "branch",
        "status": "todo",
        "children": [
            _apply_override({"id": "writer/structure", "label": "Chapter Structure", "type": "leaf", "status": "todo"}, overrides),
            _apply_override({"id": "writer/qfep-chapter", "label": "QFEP Methodology Chapter", "type": "leaf", "status": "todo"}, overrides),
            _apply_override({"id": "writer/primitives-chapter", "label": "Primitives Chapter", "type": "leaf", "status": "todo"}, overrides),
        ],
    }
    return _apply_override(writer, overrides)


def _compute_stats(tree: dict) -> dict:
    """Count nodes by status."""
    counts = {"done": 0, "active": 0, "partial": 0, "todo": 0, "empty": 0, "exists": 0, "noted": 0, "total": 0}

    def walk(node):
        if node.get("type") == "leaf":
            status = node.get("status", "todo")
            counts[status] = counts.get(status, 0) + 1
            counts["total"] += 1
        for child in node.get("children", []):
            walk(child)

    for child in tree.get("children", []):
        walk(child)

    return counts
