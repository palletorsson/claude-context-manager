"""Clone a session's context into a resumable thread file."""

import json
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from db import get_db
from config import PROJECTS_DIR

router = APIRouter(prefix="/api/clone", tags=["clone"])


class CloneRequest(BaseModel):
    session_id: str
    thread_name: str


@router.post("")
def clone_session(body: CloneRequest):
    """Extract context from a session and create a thread file."""
    db = get_db()
    row = db.execute(
        "SELECT * FROM sessions WHERE session_id = ?", (body.session_id,)
    ).fetchone()
    db.close()

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
        },
    }


def _extract_context(jsonl_path: Path) -> dict:
    """Stream a JSONL file and extract cloneable context."""
    decisions = []
    files = set()
    questions = []
    last_summary = ""
    user_messages = []

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

                elif event_type == "assistant" and text:
                    # Look for decisions
                    for marker in ["decided", "chose", "approach:", "decision:", "going with", "the plan is"]:
                        if marker.lower() in text.lower():
                            # Extract the sentence containing the marker
                            for sentence in text.split(". "):
                                if marker.lower() in sentence.lower():
                                    decisions.append(sentence.strip()[:200])
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

    except Exception as e:
        print(f"Error extracting context: {e}")

    return {
        "decisions": decisions[:20],
        "files": sorted(files)[:30],
        "questions": questions[:15],
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
