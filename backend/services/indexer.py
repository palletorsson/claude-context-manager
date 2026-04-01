"""Stream JSONL session files and extract metadata for the cache."""

import json
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
from services.variety import file_content_hash


def index_session(jsonl_path: Path) -> dict:
    """Stream a JSONL session file and extract metadata.

    Returns a dict with session metadata suitable for cache.db insertion.
    Does NOT load the entire file into memory.
    """
    session_id = jsonl_path.stem
    stat = jsonl_path.stat()

    first_user_msg = None
    last_user_msg = None
    user_count = 0
    assistant_count = 0
    started_at = None
    ended_at = None
    model = None
    tools = set()

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

                # Extract timestamps
                ts = event.get("timestamp")
                if ts:
                    try:
                        if isinstance(ts, (int, float)):
                            ts_iso = datetime.fromtimestamp(
                                ts / 1000 if ts > 1e12 else ts,
                                tz=timezone.utc
                            ).isoformat()
                        else:
                            ts_iso = str(ts)
                        if started_at is None:
                            started_at = ts_iso
                        ended_at = ts_iso
                    except Exception:
                        pass

                # Count and extract user messages
                if event_type == "user":
                    user_count += 1
                    msg = event.get("message", {})
                    content = msg.get("content", "")
                    if isinstance(content, str):
                        text = content[:500]
                    elif isinstance(content, list):
                        texts = []
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                texts.append(block.get("text", ""))
                            elif isinstance(block, str):
                                texts.append(block)
                        text = " ".join(texts)[:500]
                    else:
                        text = str(content)[:500]

                    if first_user_msg is None:
                        first_user_msg = text
                    last_user_msg = text

                # Count assistant messages, extract model + tools
                elif event_type == "assistant":
                    assistant_count += 1
                    msg = event.get("message", {})
                    if model is None:
                        model = msg.get("model")
                    # Extract tool names
                    content = msg.get("content", [])
                    if isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "tool_use":
                                tools.add(block.get("name", ""))

    except Exception as e:
        print(f"Error indexing {jsonl_path}: {e}")

    total_msgs = user_count + assistant_count
    first = first_user_msg or ""
    last = last_user_msg or ""

    # Auto-classify
    category = classify_session(first, total_msgs, user_count, stat.st_size)
    importance = compute_importance(
        total_msgs, user_count, assistant_count, stat.st_size, tools, first
    )

    # Estimate duration from timestamps
    duration_mins = 0.0
    if started_at and ended_at and started_at != ended_at:
        try:
            t0 = datetime.fromisoformat(started_at)
            t1 = datetime.fromisoformat(ended_at)
            duration_mins = max(0, (t1 - t0).total_seconds() / 60)
        except Exception:
            pass

    content_hash = file_content_hash(jsonl_path)

    return {
        "session_id": session_id,
        "file_path": str(jsonl_path),
        "content_hash": content_hash,
        "file_size": stat.st_size,
        "file_mtime": stat.st_mtime,
        "message_count": total_msgs,
        "user_count": user_count,
        "assistant_count": assistant_count,
        "first_message": first,
        "last_message": last,
        "started_at": started_at or "",
        "model": model or "",
        "tools_used": json.dumps(sorted(tools - {""})),
        "category": category,
        "importance": importance,
        "duration_mins": duration_mins,
    }


def classify_session(first_msg: str, total_msgs: int, user_msgs: int, file_size: int) -> str:
    """Auto-classify session into: major, standard, minor, automated."""
    # Automated tasks (oversight batch jobs)
    if "Take your time and do excellent work" in first_msg:
        return "automated"
    if first_msg.startswith("You are working on"):
        return "automated"
    if first_msg.startswith("You are a screenshot"):
        return "automated"

    # Minor: very short conversations
    if user_msgs <= 2 and total_msgs <= 6:
        return "minor"
    if total_msgs <= 10 and file_size < 20_000:
        return "minor"

    # Major: long deep sessions
    if total_msgs >= 200 or file_size >= 1_000_000:
        return "major"
    if user_msgs >= 30:
        return "major"

    return "standard"


def compute_importance(
    total_msgs: int,
    user_msgs: int,
    assistant_msgs: int,
    file_size: int,
    tools: set,
    first_msg: str,
) -> float:
    """Compute importance score 0-100 based on session signals."""
    score = 0.0

    # Message volume (0-30 points)
    score += min(30, total_msgs * 0.05)

    # User engagement — more user messages = more interactive (0-20)
    score += min(20, user_msgs * 0.5)

    # Tool diversity — more tools = deeper work (0-15)
    score += min(15, len(tools) * 1.5)

    # File operations signal real work (0-10)
    file_tools = tools & {"Edit", "Write", "Read", "Bash"}
    score += len(file_tools) * 2.5

    # Size signal (0-10)
    score += min(10, file_size / 500_000)

    # Continuation sessions are important (0-5)
    if "continue" in first_msg.lower() or "handoff" in first_msg.lower():
        score += 5

    # Automated sessions get reduced score
    if "Take your time and do excellent work" in first_msg:
        score *= 0.3

    # Minor questions get reduced
    if total_msgs <= 6:
        score *= 0.2

    return round(min(100, score), 1)


def read_messages_page(
    jsonl_path: Path,
    page: int = 1,
    per_page: int = 50,
    types: Optional[set] = None,
) -> dict:
    """Read a page of messages from a JSONL file.

    Returns {messages: [...], total: int, page: int, per_page: int}
    """
    if types is None:
        types = {"user", "assistant"}

    messages = []
    total = 0
    skip = (page - 1) * per_page
    collected = 0

    try:
        with open(jsonl_path, "r", encoding="utf-8") as f:
            line_num = 0
            for line in f:
                line = line.strip()
                if not line:
                    line_num += 1
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    line_num += 1
                    continue

                event_type = event.get("type")
                if event_type not in types:
                    line_num += 1
                    continue

                total += 1

                if total <= skip:
                    line_num += 1
                    continue

                if collected >= per_page:
                    line_num += 1
                    continue

                # Extract content preview
                msg = event.get("message", {})
                content = msg.get("content", "")

                if isinstance(content, str):
                    preview = content[:300]
                    has_tool = False
                    has_thinking = False
                elif isinstance(content, list):
                    texts = []
                    has_tool = False
                    has_thinking = False
                    for block in content:
                        if isinstance(block, dict):
                            if block.get("type") == "text":
                                texts.append(block.get("text", ""))
                            elif block.get("type") == "tool_use":
                                has_tool = True
                            elif block.get("type") == "thinking":
                                has_thinking = True
                    preview = " ".join(texts)[:300]
                else:
                    preview = str(content)[:300]
                    has_tool = False
                    has_thinking = False

                messages.append({
                    "line": line_num,
                    "type": event_type,
                    "timestamp": event.get("timestamp"),
                    "preview": preview,
                    "has_tool_use": has_tool,
                    "has_thinking": has_thinking,
                    "model": msg.get("model"),
                })
                collected += 1
                line_num += 1

    except Exception as e:
        print(f"Error reading messages from {jsonl_path}: {e}")

    # We need to count remaining after we stopped collecting
    # For efficiency, if we hit per_page, continue counting total
    if collected >= per_page:
        try:
            with open(jsonl_path, "r", encoding="utf-8") as f:
                total = sum(
                    1 for line in f
                    if line.strip() and _is_message_type(line, types)
                )
        except Exception:
            pass

    return {
        "messages": messages,
        "total": total,
        "page": page,
        "per_page": per_page,
    }


def _is_message_type(line: str, types: set) -> bool:
    """Quick check if a JSONL line is a message type we care about."""
    for t in types:
        if f'"type":"{t}"' in line or f'"type": "{t}"' in line:
            return True
    return False


def read_single_message(jsonl_path: Path, line_number: int) -> Optional[dict]:
    """Read a single message at a specific line number."""
    try:
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i == line_number:
                    event = json.loads(line.strip())
                    return {
                        "line": line_number,
                        "type": event.get("type"),
                        "timestamp": event.get("timestamp"),
                        "message": event.get("message", {}),
                    }
    except Exception:
        pass
    return None
