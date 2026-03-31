"""Configuration — auto-detects Claude Code paths, configurable via env vars."""

import os
import sys
from pathlib import Path

# Load .env if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── Claude Code directory ────────────────────────────────────
# Auto-detect: ~/.claude on all platforms
# Override: set CLAUDE_DIR env var
_default_claude = Path.home() / ".claude"
CLAUDE_DIR = Path(os.environ.get("CLAUDE_DIR", str(_default_claude)))
PROJECTS_DIR = CLAUDE_DIR / "projects"
SESSIONS_DIR = CLAUDE_DIR / "sessions"
HISTORY_FILE = CLAUDE_DIR / "history.jsonl"
PLANS_DIR = CLAUDE_DIR / "plans"
TODOS_DIR = CLAUDE_DIR / "todos"

# ── Cache database ───────────────────────────────────────────
DATA_DIR = Path(os.environ.get("DATA_DIR", str(Path(__file__).parent / "data")))
CACHE_DB = DATA_DIR / "cache.db"

# ── Server ───────────────────────────────────────────────────
BACKEND_PORT = int(os.environ.get("BACKEND_PORT", "8000"))
CORS_ORIGINS = os.environ.get(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:3001"
).split(",")

# ── Validation ───────────────────────────────────────────────
def validate_config():
    """Check that Claude Code directory exists. Returns warnings."""
    warnings = []
    if not CLAUDE_DIR.exists():
        warnings.append(f"Claude Code directory not found: {CLAUDE_DIR}")
        warnings.append("Install Claude Code or set CLAUDE_DIR env var")
    elif not PROJECTS_DIR.exists():
        warnings.append(f"No projects directory at {PROJECTS_DIR}")
        warnings.append("Have you used Claude Code at least once?")
    return warnings
