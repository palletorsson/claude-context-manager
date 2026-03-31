"""Extract topics from sessions and suggest meta-threads.

Scans indexed sessions, extracts keywords from first/last messages,
clusters sessions by shared topics, and suggests thread groupings.
No LLM needed — uses TF-IDF-like keyword extraction and co-occurrence.
"""

import re
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from db import get_db

# Common words to ignore
STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "as", "into", "through", "during", "before", "after", "above", "below",
    "between", "out", "off", "over", "under", "again", "further", "then",
    "once", "here", "there", "when", "where", "why", "how", "all", "both",
    "each", "few", "more", "most", "other", "some", "such", "no", "nor",
    "not", "only", "own", "same", "so", "than", "too", "very", "just",
    "don", "now", "and", "but", "or", "if", "while", "that", "this",
    "what", "which", "who", "whom", "these", "those", "am", "it", "its",
    "i", "me", "my", "we", "our", "you", "your", "he", "him", "his",
    "she", "her", "they", "them", "their", "up", "about", "also",
    # Claude/AI specific stops
    "claude", "please", "help", "want", "make", "let", "think", "know",
    "like", "get", "use", "using", "work", "working", "take", "time",
    "look", "see", "read", "file", "files", "code", "run", "project",
    "yes", "no", "ok", "sure", "thanks", "good", "well", "still",
    "one", "two", "three", "new", "first", "last", "next", "current",
    "start", "continue", "done", "check", "try", "add", "create",
    "update", "change", "move", "keep", "put", "set", "give", "show",
    # Task automation stops
    "excellent", "task", "batch", "readme", "zero",
    # Project name stops (too common to be useful topics)
    "ada", "research", "project", "session", "commit",
    "uncommited", "uncommitted",
    # Technical noise
    "res", "commons", "algorithms", "artifacts", "registry",
    "maps", "sequences", "map", "sequence", "artifact",
    "description", "priority", "medium", "high", "low",
    "missing", "status", "write", "implement",
    "json", "script", "function", "class", "extends",
    "node", "path", "directory", "directories", "folder",
    "functional", "bearing", "modules",
}

# Minimum keyword length
MIN_WORD_LEN = 3


def extract_keywords(text: str, max_keywords: int = 15) -> list[str]:
    """Extract meaningful keywords from text."""
    if not text:
        return []
    # Normalize
    text = text.lower()
    # Extract words (keep underscores for identifiers like map_data)
    words = re.findall(r'[a-z][a-z0-9_]+', text)
    # Filter
    words = [w for w in words if len(w) >= MIN_WORD_LEN and w not in STOP_WORDS]
    # Count and return top N
    counts = Counter(words)
    return [w for w, _ in counts.most_common(max_keywords)]


def extract_topics_from_sessions(project_path: str) -> list[dict]:
    """Extract topic clusters from all indexed sessions for a project.

    Returns a list of topic clusters, each with:
    - topic: the primary keyword
    - keywords: related keywords
    - sessions: list of session_ids that discuss this topic
    - suggested_title: a suggested thread title
    - importance: weighted by session importance scores
    """
    db = get_db()

    # Get all non-archived, non-minor sessions
    rows = db.execute("""
        SELECT session_id, first_message, last_message, importance, category,
               message_count, custom_title, started_at
        FROM sessions
        WHERE project_path = ? AND archived = 0 AND category != 'minor'
        ORDER BY started_at DESC
    """, (project_path,)).fetchall()
    db.close()

    if not rows:
        return []

    # Step 1: Extract keywords per session
    session_keywords: dict[str, list[str]] = {}
    session_meta: dict[str, dict] = {}

    for row in rows:
        sid = row["session_id"]
        text = f"{row['first_message'] or ''} {row['last_message'] or ''} {row['custom_title'] or ''}"
        keywords = extract_keywords(text)
        if keywords:
            session_keywords[sid] = keywords
            session_meta[sid] = {
                "session_id": sid,
                "first_message": (row["first_message"] or "")[:150],
                "custom_title": row["custom_title"] or "",
                "importance": row["importance"] or 0,
                "category": row["category"] or "standard",
                "message_count": row["message_count"] or 0,
                "started_at": row["started_at"] or "",
            }

    # Step 2: Build keyword → sessions index
    keyword_sessions: dict[str, set[str]] = defaultdict(set)
    for sid, keywords in session_keywords.items():
        for kw in keywords:
            keyword_sessions[kw].add(sid)

    # Step 3: Find keywords that appear in 2+ sessions (potential topics)
    topic_candidates = {
        kw: sids for kw, sids in keyword_sessions.items()
        if len(sids) >= 2
    }

    # Step 4: Cluster topics by co-occurrence
    # If two keywords appear in mostly the same sessions, merge them
    clusters: list[dict] = []
    used_keywords: set[str] = set()

    # Sort by how many sessions the keyword appears in (descending)
    sorted_topics = sorted(topic_candidates.items(), key=lambda x: -len(x[1]))

    for primary_kw, primary_sids in sorted_topics:
        if primary_kw in used_keywords:
            continue

        # Find related keywords (high overlap with this one)
        related = [primary_kw]
        used_keywords.add(primary_kw)

        for other_kw, other_sids in sorted_topics:
            if other_kw in used_keywords:
                continue
            # Jaccard similarity
            intersection = len(primary_sids & other_sids)
            union = len(primary_sids | other_sids)
            if union > 0 and intersection / union > 0.5:
                related.append(other_kw)
                used_keywords.add(other_kw)
                primary_sids = primary_sids | other_sids

        # Build cluster
        sessions_in_cluster = sorted(
            [session_meta[sid] for sid in primary_sids if sid in session_meta],
            key=lambda s: s["importance"],
            reverse=True,
        )

        if len(sessions_in_cluster) < 2:
            continue

        total_importance = sum(s["importance"] for s in sessions_in_cluster)
        total_messages = sum(s["message_count"] for s in sessions_in_cluster)

        clusters.append({
            "topic": primary_kw,
            "keywords": related[:8],
            "session_count": len(sessions_in_cluster),
            "sessions": sessions_in_cluster[:10],  # Top 10 by importance
            "total_importance": round(total_importance, 1),
            "total_messages": total_messages,
            "suggested_title": _suggest_title(primary_kw, related, sessions_in_cluster),
            "date_range": {
                "first": sessions_in_cluster[-1]["started_at"][:10] if sessions_in_cluster else "",
                "last": sessions_in_cluster[0]["started_at"][:10] if sessions_in_cluster else "",
            },
        })

    # Sort clusters by total importance
    clusters.sort(key=lambda c: -c["total_importance"])

    return clusters[:30]  # Top 30 topics


def _suggest_title(primary: str, related: list[str], sessions: list[dict]) -> str:
    """Generate a suggested thread title from topic keywords."""
    # If any session has a custom title, use its keywords
    titled = [s for s in sessions if s.get("custom_title")]
    if titled:
        return f"Meta: {titled[0]['custom_title']}"

    # Otherwise build from keywords
    keywords = [kw.replace("_", " ").title() for kw in related[:3]]
    return f"Meta: {', '.join(keywords)}"


def generate_thread_content(cluster: dict) -> str:
    """Generate a thread markdown file from a topic cluster."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    lines = [
        f"# Meta-Thread: {cluster['suggested_title']} (auto-generated {now})",
        "",
        "## Status: SUGGESTED — review and activate if useful",
        "",
        f"## Topic: {cluster['topic']}",
        f"Keywords: {', '.join(cluster['keywords'])}",
        f"Sessions: {cluster['session_count']} | Messages: {cluster['total_messages']} | "
        f"Date range: {cluster['date_range']['first']} to {cluster['date_range']['last']}",
        "",
        "## Sessions in this thread",
    ]

    for s in cluster["sessions"]:
        title = s.get("custom_title") or s.get("first_message", "")[:80]
        cat = s.get("category", "?")
        imp = s.get("importance", 0)
        lines.append(f"- [{cat}] imp={imp:.0f} | {s['session_id'][:12]}... | {title}")

    lines.extend([
        "",
        "## Open Questions",
        "- What are the key decisions made across these sessions?",
        "- What patterns or insights recur?",
        "- What's still unresolved?",
        "",
        "## How to Resume",
        "```",
        f"Read this thread file and continue the {cluster['topic']} discussion",
        "```",
    ])

    return "\n".join(lines)
