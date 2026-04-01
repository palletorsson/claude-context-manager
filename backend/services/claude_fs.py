"""Filesystem operations for reading Claude Code data. Cross-platform."""

import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
from config import PROJECTS_DIR


def decode_project_path(encoded: str) -> tuple[str, str]:
    """Decode an encoded project path to (display_name, full_path).

    Claude Code encodes paths differently by platform:
    - Windows: C--Users-palle-Documents-GitHub-AdaResearch_46
              (drive letter, double-dash, then single-dash separators)
    - macOS/Linux: -Users-palle-Documents-GitHub-project
              (leading dash, no drive letter)

    Returns (display_name, best_guess_full_path).
    """
    if not encoded:
        return encoded, encoded

    # Try to reconstruct and validate against filesystem
    if sys.platform == "win32":
        path = _decode_windows(encoded)
    else:
        path = _decode_unix(encoded)

    if path and Path(path).exists():
        return Path(path).name, path

    # Fallback: extract last meaningful segment as display name
    parts = encoded.replace("--", "/").replace("-", "/").split("/")
    display = parts[-1] if parts else encoded
    return display, encoded


def _decode_windows(encoded: str) -> Optional[str]:
    """Decode Windows-style encoded path: C--Users-palle-..."""
    if "--" not in encoded:
        return None

    drive_part, rest = encoded.split("--", 1)
    if len(drive_part) != 1:
        return None

    drive = drive_part + ":\\"
    segments = rest.split("-")

    # Greedy reconstruction: try combining segments to find real dirs
    return _reconstruct_path(drive, segments)


def _decode_unix(encoded: str) -> Optional[str]:
    """Decode Unix-style encoded path: -Users-palle-... or Users-palle-..."""
    # Strip leading dash if present
    if encoded.startswith("-"):
        encoded = encoded[1:]

    segments = encoded.split("-")
    return _reconstruct_path("/", segments)


def _reconstruct_path(base: str, segments: list[str]) -> Optional[str]:
    """Greedily reconstruct a real path by combining segments."""
    if not segments:
        return base if Path(base).exists() else None

    current = Path(base)
    i = 0

    while i < len(segments):
        # Try single segment
        candidate = current / segments[i]
        if candidate.exists():
            current = candidate
            i += 1
            continue

        # Try combining 2-4 segments (handles names with dashes/underscores)
        found = False
        for j in range(i + 2, min(i + 6, len(segments) + 1)):
            # Try with dash
            combined_dash = "-".join(segments[i:j])
            if (current / combined_dash).exists():
                current = current / combined_dash
                i = j
                found = True
                break
            # Try with underscore
            combined_under = "_".join(segments[i:j])
            if (current / combined_under).exists():
                current = current / combined_under
                i = j
                found = True
                break

        if not found:
            # Can't resolve further — join remaining with original separators
            remaining = "-".join(segments[i:])
            return str(current / remaining)

    return str(current)


def discover_projects() -> list[dict]:
    """Discover all Claude Code projects from the projects directory."""
    if not PROJECTS_DIR.exists():
        return []

    # Cache by directory mtime
    try:
        current_mtime = PROJECTS_DIR.stat().st_mtime
        if abs(current_mtime - _projects_cache["mtime"]) < 0.5 and _projects_cache["data"]:
            return _projects_cache["data"]
    except OSError:
        pass

    projects = []
    for entry in sorted(PROJECTS_DIR.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name.startswith("."):
            continue

        display_name, full_path = decode_project_path(entry.name)

        # Count sessions (JSONL files)
        jsonl_files = list(entry.glob("*.jsonl"))
        session_count = len(jsonl_files)

        # Count memory files
        memory_dir = entry / "memory"
        memory_count = len(list(memory_dir.glob("*.md"))) if memory_dir.exists() else 0

        # Last activity: most recent JSONL file mtime
        last_activity = None
        if jsonl_files:
            latest = max(jsonl_files, key=lambda f: f.stat().st_mtime)
            last_activity = datetime.fromtimestamp(
                latest.stat().st_mtime, tz=timezone.utc
            ).isoformat()

        projects.append({
            "encoded_path": entry.name,
            "display_name": display_name,
            "full_path": full_path,
            "session_count": session_count,
            "memory_count": memory_count,
            "last_activity": last_activity,
        })

    # Update cache
    try:
        _projects_cache["mtime"] = PROJECTS_DIR.stat().st_mtime
        _projects_cache["data"] = projects
    except OSError:
        pass

    return projects


def list_session_files(encoded_path: str) -> list[Path]:
    """List all JSONL session files for a project, newest first."""
    project_dir = PROJECTS_DIR / encoded_path
    # Defense in depth: verify resolved path stays within PROJECTS_DIR
    if not str(project_dir.resolve()).startswith(str(PROJECTS_DIR.resolve())):
        return []
    if not project_dir.exists():
        return []
    files = list(project_dir.glob("*.jsonl"))
    files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    return files


def list_memory_files(encoded_path: str) -> list[dict]:
    """List all memory files for a project, with temperature metadata."""
    from services.variety import file_content_hash, get_cached_memory_meta, upsert_memory_meta

    memory_dir = PROJECTS_DIR / encoded_path / "memory"
    # Defense in depth: verify resolved path stays within PROJECTS_DIR
    if not str(memory_dir.resolve()).startswith(str(PROJECTS_DIR.resolve())):
        return []
    if not memory_dir.exists():
        return []

    files = []
    for f in sorted(memory_dir.glob("*.md")):
        stat = f.stat()
        modified_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()

        # Check cached metadata by content hash
        current_hash = file_content_hash(f)
        cached = get_cached_memory_meta(encoded_path, f.name, current_hash)

        if cached:
            files.append({
                "filename": f.name,
                "file_path": str(f),
                "file_size": stat.st_size,
                "modified_at": modified_at,
                "status": cached["status"],
                "summary": cached["summary"],
                "temperature": cached["temperature"],
                "temperature_score": cached["temperature_score"],
            })
            continue

        # Cache miss — parse file content
        summary = ""
        status = "active"
        try:
            content = f.read_text(encoding="utf-8")
            for line in content.split("\n"):
                line = line.strip()
                if line and not line.startswith("#") and not line.startswith("---"):
                    summary = line[:200]
                    break
            upper = content.upper()
            if "PAUSED" in upper:
                status = "paused"
            elif "MERGED" in upper:
                status = "merged"
            elif "ARCHIVED" in upper:
                status = "archived"
        except Exception:
            pass

        # Cache the metadata
        upsert_memory_meta(
            project_path=encoded_path,
            filename=f.name,
            file_hash=current_hash,
            file_size=stat.st_size,
            modified_at=modified_at,
            status=status,
            summary=summary,
        )

        # Re-read cached meta to get computed temperature
        cached = get_cached_memory_meta(encoded_path, f.name, current_hash)
        temperature = cached["temperature"] if cached else "warm"
        temperature_score = cached["temperature_score"] if cached else 50.0

        files.append({
            "filename": f.name,
            "file_path": str(f),
            "file_size": stat.st_size,
            "modified_at": modified_at,
            "status": status,
            "summary": summary,
            "temperature": temperature,
            "temperature_score": temperature_score,
        })

    return files


# ── Projects discovery cache ──────────────────────────────────

_projects_cache: dict = {"mtime": 0.0, "data": []}


def _clear_projects_cache():
    """Clear the projects discovery cache. Used in tests."""
    _projects_cache["mtime"] = 0.0
    _projects_cache["data"] = []
