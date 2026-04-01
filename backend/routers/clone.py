"""Clone a session's context into a resumable thread file."""

import json
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from db import db_connection
from config import PROJECTS_DIR

router = APIRouter(prefix="/api/clone", tags=["clone"])


class CloneRequest(BaseModel):
    session_id: str
    thread_name: str


@router.post("")
def clone_session(body: CloneRequest):
    """Extract context from a session and create a thread file."""
    with db_connection() as db:
        row = db.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (body.session_id,)
        ).fetchone()

    if not row:
        raise HTTPException(404, "Session not found")

    session = dict(row)
    jsonl_path = Path(session["file_path"])
    if not jsonl_path.exists():
        raise HTTPException(404, "Session file not found on disk")

    # Extract context from the session log
    context = _extract_context(jsonl_path)

    # Generate thread file content
    thread_content = _generate_thread(body.thread_name, session, context)

    # Write to project's memory directory
    project_path = session["project_path"]
    memory_dir = PROJECTS_DIR / project_path / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)

    filename = f"thread_{body.thread_name.lower().replace(' ', '_')}.md"
    filepath = memory_dir / filename

    if filepath.exists():
        raise HTTPException(409, f"Thread file already exists: {filename}")

    filepath.write_text(thread_content, encoding="utf-8")

    return {
        "filename": filename,
        "path": str(filepath),
        "created": True,
        "context_summary": {
            "decisions": len(context["decisions"]),
            "files_touched": len(context["files"]),
            "questions": len(context["questions"]),
            "turning_points": len(context["turning_points"]),
        },
    }


def _extract_context(jsonl_path: Path) -> dict:
    """Stream a JSONL file and extract cloneable context."""
    decisions = []
    files = set()
    questions = []
    turning_points = []
    last_summary = ""
    user_messages = []
    msg_index = 0
    prev_assistant_text = ""

    # Markers for mid-session pivots, breakthroughs, and root-cause discoveries
    pivot_markers = [
        "actually,", "wait,", "scratch that", "instead,", "let's change",
        "on second thought", "different approach", "won't work", "doesn't work",
        "let me try", "better approach", "I was wrong",
    ]
    breakthrough_markers = [
        "the issue was", "the problem was", "root cause", "found it",
        "that fixed it", "now it works", "the fix is", "turns out",
        "the real issue", "the bug was", "aha,", "the key insight",
        "mystery solved", "that explains",
    ]

    try:
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                event_type = event.get("type")
                msg = event.get("message", {})
                content = msg.get("content", "")

                # Extract text from content blocks
                if isinstance(content, list):
                    texts = []
                    for block in content:
                        if isinstance(block, dict):
                            if block.get("type") == "text":
                                texts.append(block.get("text", ""))
                            elif block.get("type") == "tool_use":
                                name = block.get("name", "")
                                inp = block.get("input", {})
                                # Track files from edit/write/read operations
                                if name in ("Edit", "Write", "Read"):
                                    fp = inp.get("file_path", "")
                                    if fp:
                                        files.add(fp)
                    text = "\n".join(texts)
                elif isinstance(content, str):
                    text = content
                else:
                    text = ""

                if event_type == "user":
                    user_messages.append(text[:300])
                    msg_index += 1

                    # Detect user-initiated pivots (redirections mid-session)
                    if msg_index > 2:
                        text_lower = text.lower()
                        for marker in pivot_markers:
                            if marker in text_lower:
                                turning_points.append({
                                    "type": "pivot",
                                    "position": msg_index,
                                    "text": text.strip()[:200],
                                })
                                break

                elif event_type == "assistant" and text:
                    msg_index += 1
                    text_lower = text.lower()

                    # Look for decisions
                    for marker in ["decided", "chose", "approach:", "decision:", "going with", "the plan is"]:
                        if marker in text_lower:
                            # Extract the sentence containing the marker
                            for sentence in text.split(". "):
                                if marker in sentence.lower():
                                    decisions.append(sentence.strip()[:200])
                                    break
                            break

                    # Look for breakthroughs and root-cause discoveries
                    for marker in breakthrough_markers:
                        if marker in text_lower:
                            for sentence in text.split(". "):
                                if marker in sentence.lower():
                                    turning_points.append({
                                        "type": "breakthrough",
                                        "position": msg_index,
                                        "text": sentence.strip()[:200],
                                    })
                                    break
                            break

                    # Look for questions
                    for sentence in text.split(". "):
                        s = sentence.strip()
                        if s.endswith("?") and len(s) > 20:
                            questions.append(s[:200])

                    # Keep last substantial text as summary
                    if len(text) > 100:
                        last_summary = text[:500]

                    prev_assistant_text = text

    except Exception as e:
        print(f"Error extracting context: {e}")

    # Deduplicate turning points by text similarity
    seen_tp = set()
    unique_tp = []
    for tp in turning_points:
        key = tp["text"][:80].lower()
        if key not in seen_tp:
            seen_tp.add(key)
            unique_tp.append(tp)

    return {
        "decisions": decisions[:20],
        "files": sorted(files)[:30],
        "questions": questions[:15],
        "turning_points": unique_tp[:15],
        "last_summary": last_summary,
        "user_messages": user_messages[:5],
    }


def _generate_thread(name: str, session: dict, context: dict) -> str:
    """Generate a thread markdown file from extracted context."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    lines = [
        f"# Thread: {name} (cloned {now})",
        "",
        f"## Status: ACTIVE",
        "",
        f"## Origin",
        f"Cloned from session `{session['session_id']}` ({session.get('started_at', 'unknown date')})",
        f"Model: {session.get('model', 'unknown')} | Messages: {session.get('message_count', 0)}",
        "",
    ]

    # First user messages (the task)
    if context["user_messages"]:
        lines.append("## What This Session Was About")
        for msg in context["user_messages"][:3]:
            lines.append(f"- {msg}")
        lines.append("")

    # Turning points (pivots and breakthroughs from mid-session)
    if context["turning_points"]:
        lines.append("## Turning Points")
        for tp in context["turning_points"]:
            label = "\U0001f504" if tp["type"] == "pivot" else "\U0001f4a1"
            lines.append(f"- {label} [{tp['type']}] {tp['text']}")
        lines.append("")

    # Decisions
    if context["decisions"]:
        lines.append("## Key Decisions")
        for d in context["decisions"]:
            lines.append(f"- {d}")
        lines.append("")

    # Files
    if context["files"]:
        lines.append("## Files Touched")
        for f in context["files"]:
            lines.append(f"- `{f}`")
        lines.append("")

    # Open questions
    if context["questions"]:
        lines.append("## Open Questions")
        for q in context["questions"]:
            lines.append(f"- {q}")
        lines.append("")

    # Resume point
    lines.append("## How to Resume")
    lines.append("```")
    lines.append(f'Read .claude/memory/thread_{name.lower().replace(" ", "_")}.md and continue')
    lines.append("```")
    lines.append("")

    if context["last_summary"]:
        lines.append("## Last Context")
        lines.append(context["last_summary"])
        lines.append("")

    return "\n".join(lines)
