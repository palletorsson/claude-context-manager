"""Variety engineering — content hashing, memory temperature, reference counting.

Implements Ashby's Law of Requisite Variety: attenuate incoming variety at layer
boundaries using content hashes as cheap control signals, and amplify regulatory
capacity through reference counting and temperature-based prioritization.

Three subsystems:
1. Content hashing — gate expensive recomputation when input is unchanged
2. Memory temperature — classify memories as hot/warm/cold/frozen
3. Reference counting — track concept frequency across sessions
"""

import hashlib
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from db import db_connection


# ── Hashing utilities ─────────────────────────────────────────


def file_content_hash(path: Path) -> str:
    """SHA-256 of file content, streamed in 64KB chunks. Platform-independent."""
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
    except (OSError, IOError):
        return ""
    return h.hexdigest()


def composite_hash(*values: str) -> str:
    """SHA-256 of null-separated string values. Deterministic and order-sensitive."""
    combined = "\x00".join(str(v) for v in values)
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


# ── Session hash for topic cache ──────────────────────────────


def compute_sessions_hash(project_path: str) -> str:
    """Hash all session metadata for a project. Used to gate topic extraction."""
    with db_connection() as db:
        rows = db.execute("""
            SELECT session_id, first_message, last_message, importance
            FROM sessions
            WHERE project_path = ? AND archived = 0 AND category != 'minor'
            ORDER BY session_id
        """, (project_path,)).fetchall()

    if not rows:
        return composite_hash("empty", project_path)

    parts = []
    for r in rows:
        parts.append(composite_hash(
            r["session_id"],
            r["first_message"] or "",
            r["last_message"] or "",
            str(r["importance"] or 0),
        ))
    return composite_hash(*parts)


# ── Topic cache gate ──────────────────────────────────────────


def get_cached_topics(project_path: str) -> list[dict] | None:
    """Return cached topic clusters if sessions_hash matches, else None."""
    current_hash = compute_sessions_hash(project_path)
    with db_connection() as db:
        row = db.execute(
            "SELECT sessions_hash, clusters_json FROM topic_cache WHERE project_path = ?",
            (project_path,)
        ).fetchone()

    if row and row["sessions_hash"] == current_hash:
        try:
            return json.loads(row["clusters_json"])
        except (json.JSONDecodeError, TypeError):
            return None
    return None


def cache_topics(project_path: str, clusters: list[dict]):
    """Store computed topic clusters with current sessions_hash."""
    current_hash = compute_sessions_hash(project_path)
    now = datetime.now(timezone.utc).isoformat()
    with db_connection() as db:
        db.execute("""
            INSERT OR REPLACE INTO topic_cache (project_path, sessions_hash, clusters_json, computed_at)
            VALUES (?, ?, ?, ?)
        """, (project_path, current_hash, json.dumps(clusters), now))
        db.commit()


# ── Memory temperature ────────────────────────────────────────


def compute_temperature(
    last_referenced_at: str | None,
    reference_count: int,
    importance: float,
    modified_at: str | None,
) -> tuple[str, float]:
    """Compute memory temperature from recency, connectivity, and importance.

    Returns (label, score) where label is hot/warm/cold/frozen and score is 0-100.

    Score formula:
      recency_score (0-40)  × 0.4 weight — decays 1.5 pts/day from 40
      connectivity  (0-30)  × 0.3 weight — 3 pts per reference, caps at 30
      importance    (0-30)  × 0.3 weight — 30% of raw importance, caps at 30
    """
    now = datetime.now(timezone.utc)

    # Recency: days since last reference or modification
    ref_date = None
    for ts_str in (last_referenced_at, modified_at):
        if ts_str:
            try:
                ts = datetime.fromisoformat(ts_str)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ref_date is None or ts > ref_date:
                    ref_date = ts
            except (ValueError, TypeError):
                pass

    if ref_date:
        days_ago = max(0, (now - ref_date).total_seconds() / 86400)
    else:
        days_ago = 90  # default: old

    recency_score = max(0, 40 - days_ago * 1.5)

    # Connectivity: references from other sessions/reads
    connectivity_score = min(30, reference_count * 3)

    # Importance: percentage of raw importance
    importance_score = min(30, importance * 0.3)

    score = recency_score + connectivity_score + importance_score
    score = round(min(100, max(0, score)), 1)

    # Thresholds
    if score >= 75 or days_ago <= 7:
        label = "hot"
    elif score >= 40 or days_ago <= 30:
        label = "warm"
    elif score >= 15 or days_ago <= 60:
        label = "cold"
    else:
        label = "frozen"

    return label, score


# ── Memory metadata cache ─────────────────────────────────────


def get_cached_memory_meta(project_path: str, filename: str, current_hash: str) -> dict | None:
    """Return cached metadata if file_hash matches, else None."""
    with db_connection() as db:
        row = db.execute(
            "SELECT * FROM memory_meta WHERE project_path = ? AND filename = ?",
            (project_path, filename)
        ).fetchone()

    if row and row["file_hash"] == current_hash:
        return dict(row)
    return None


def upsert_memory_meta(
    project_path: str,
    filename: str,
    file_hash: str,
    file_size: int,
    modified_at: str,
    status: str,
    summary: str,
    importance: float = 50.0,
):
    """Insert or update memory metadata. Preserves ref_count on update."""
    now = datetime.now(timezone.utc).isoformat()

    with db_connection() as db:
        existing = db.execute(
            "SELECT reference_count, last_referenced_at FROM memory_meta WHERE project_path = ? AND filename = ?",
            (project_path, filename)
        ).fetchone()

        ref_count = existing["reference_count"] if existing else 0
        last_ref = existing["last_referenced_at"] if existing else None

        temp_label, temp_score = compute_temperature(last_ref, ref_count, importance, modified_at)

        db.execute("""
            INSERT OR REPLACE INTO memory_meta
            (project_path, filename, file_hash, file_size, modified_at, status, summary,
             temperature, temperature_score, last_referenced_at, reference_count, cached_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            project_path, filename, file_hash, file_size, modified_at, status, summary,
            temp_label, temp_score, last_ref, ref_count, now,
        ))
        db.commit()


def record_memory_reference(project_path: str, filename: str):
    """Increment reference count and update last_referenced_at."""
    now = datetime.now(timezone.utc).isoformat()
    with db_connection() as db:
        db.execute("""
            UPDATE memory_meta
            SET reference_count = reference_count + 1,
                last_referenced_at = ?
            WHERE project_path = ? AND filename = ?
        """, (now, project_path, filename))
        db.commit()


# ── Concept reference counting ────────────────────────────────


def extract_and_count_concepts(
    session_id: str,
    project_path: str,
    first_message: str,
    tools_json: str,
):
    """Extract concepts from a session and upsert reference counts."""
    from services.topic_extractor import extract_keywords

    now = datetime.now(timezone.utc).isoformat()
    concepts = []

    # Keywords from first message
    keywords = extract_keywords(first_message or "", max_keywords=10)
    for kw in keywords:
        h = composite_hash("keyword", project_path, kw)
        concepts.append((h, "keyword", kw))

    # Tools used
    try:
        tools = json.loads(tools_json) if tools_json else []
    except (json.JSONDecodeError, TypeError):
        tools = []
    for tool in tools:
        if tool:
            h = composite_hash("tool", project_path, tool)
            concepts.append((h, "tool", tool))

    if not concepts:
        return

    with db_connection() as db:
        for concept_hash, concept_type, concept_value in concepts:
            existing = db.execute(
                "SELECT ref_count FROM concept_refs WHERE concept_hash = ?",
                (concept_hash,)
            ).fetchone()

            if existing:
                db.execute("""
                    UPDATE concept_refs SET ref_count = ref_count + 1, last_seen_at = ?
                    WHERE concept_hash = ?
                """, (now, concept_hash))
            else:
                db.execute("""
                    INSERT INTO concept_refs (concept_hash, concept_type, concept_value, project_path, ref_count, first_seen_at, last_seen_at)
                    VALUES (?, ?, ?, ?, 1, ?, ?)
                """, (concept_hash, concept_type, concept_value, project_path, now, now))

        db.commit()


def get_top_concepts(project_path: str, concept_type: str | None = None, limit: int = 20) -> list[dict]:
    """Return highest-ref-count concepts for a project."""
    with db_connection() as db:
        if concept_type:
            rows = db.execute("""
                SELECT concept_type, concept_value, ref_count, first_seen_at, last_seen_at
                FROM concept_refs WHERE project_path = ? AND concept_type = ?
                ORDER BY ref_count DESC LIMIT ?
            """, (project_path, concept_type, limit)).fetchall()
        else:
            rows = db.execute("""
                SELECT concept_type, concept_value, ref_count, first_seen_at, last_seen_at
                FROM concept_refs WHERE project_path = ?
                ORDER BY ref_count DESC LIMIT ?
            """, (project_path, limit)).fetchall()

    return [dict(r) for r in rows]


def get_temperature_summary(project_path: str = "") -> dict:
    """Count memories by temperature label."""
    with db_connection() as db:
        if project_path:
            rows = db.execute("""
                SELECT temperature, COUNT(*) as count FROM memory_meta
                WHERE project_path = ? GROUP BY temperature
            """, (project_path,)).fetchall()
        else:
            rows = db.execute("""
                SELECT temperature, COUNT(*) as count FROM memory_meta
                GROUP BY temperature
            """).fetchall()

    result = {"hot": 0, "warm": 0, "cold": 0, "frozen": 0}
    for r in rows:
        result[r["temperature"]] = r["count"]
    return result


# ── Startup backfill ──────────────────────────────────────────


def backfill_content_hashes() -> int:
    """Fill content_hash for sessions where it is empty and the file exists."""
    count = 0
    with db_connection() as db:
        rows = db.execute(
            "SELECT session_id, file_path FROM sessions WHERE content_hash = '' OR content_hash IS NULL"
        ).fetchall()

        for row in rows:
            path = Path(row["file_path"])
            if path.exists():
                h = file_content_hash(path)
                if h:
                    db.execute(
                        "UPDATE sessions SET content_hash = ? WHERE session_id = ?",
                        (h, row["session_id"])
                    )
                    count += 1

        if count:
            db.commit()

    return count
