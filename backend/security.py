"""Shared security validators for path traversal, input sanitization, and SQL safety."""

import re
from pathlib import Path
from fastapi import HTTPException
from config import PROJECTS_DIR


def safe_resolve(base_dir: Path, *segments: str) -> Path:
    """Resolve a path and verify it stays within base_dir.

    Raises HTTPException(400) if the resolved path escapes base_dir.
    """
    for seg in segments:
        if "\x00" in seg:
            raise HTTPException(400, "Invalid path: null bytes not allowed")

    constructed = base_dir.joinpath(*segments)
    resolved = constructed.resolve()
    base_resolved = base_dir.resolve()

    if not str(resolved).startswith(str(base_resolved)):
        raise HTTPException(400, "Invalid path: directory traversal not allowed")

    return resolved


def validate_filename(name: str) -> str:
    """Validate a filename is safe (no path separators, no traversal).

    Returns the stripped name. Raises HTTPException(400) on invalid input.
    """
    name = name.strip()
    if not name:
        raise HTTPException(400, "Filename cannot be empty")
    if "\x00" in name:
        raise HTTPException(400, "Invalid filename: null bytes not allowed")
    if ".." in name:
        raise HTTPException(400, "Invalid filename: '..' not allowed")
    if "/" in name or "\\" in name:
        raise HTTPException(400, "Invalid filename: path separators not allowed")
    return name


def validate_project(name: str) -> str:
    """Validate a project directory name is safe.

    Returns the stripped name. Raises HTTPException(400) on invalid input.
    """
    name = validate_filename(name)
    # Project names from Claude Code are encoded paths like "C--Users-palle-Documents-..."
    # Allow alphanumeric, dash, underscore, dot, tilde
    if not re.match(r'^[a-zA-Z0-9\-_.~]+$', name):
        raise HTTPException(400, "Invalid project name: contains disallowed characters")
    return name


def sanitize_node_id(label: str) -> str:
    """Sanitize a label into a safe node ID component.

    Strips everything except lowercase alphanumeric and underscores.
    """
    return re.sub(r'[^a-z0-9_]', '', label.lower().replace(" ", "_"))[:40]
