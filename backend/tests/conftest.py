"""Shared fixtures for all backend tests."""

import sys
import os
import json
import time

import pytest

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from main import app
from db import init_db, db_connection


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    """Ensure database tables exist before every test."""
    init_db()


# ── Mock project directory structure ──────────────────────────

TEST_PROJECT = "test--mock-project"


@pytest.fixture
def mock_projects_dir(tmp_path, monkeypatch):
    """Create a temporary projects directory and monkeypatch config.PROJECTS_DIR.

    Structure:
        tmp_path/
            test--mock-project/
                session_abc123.jsonl
                memory/
                    MEMORY.md
                    thread_test.md
    """
    import config
    import services.claude_fs as claude_fs
    import security as sec

    # Clear projects discovery cache to prevent leaks between tests
    claude_fs._clear_projects_cache()

    projects_dir = tmp_path / "projects"
    projects_dir.mkdir()

    # Patch everywhere PROJECTS_DIR is imported
    monkeypatch.setattr(config, "PROJECTS_DIR", projects_dir)
    monkeypatch.setattr(claude_fs, "PROJECTS_DIR", projects_dir)
    monkeypatch.setattr(sec, "PROJECTS_DIR", projects_dir)

    # Also patch in routers that import PROJECTS_DIR directly
    from routers import memory, clone, threads
    monkeypatch.setattr(memory, "PROJECTS_DIR", projects_dir)
    monkeypatch.setattr(clone, "PROJECTS_DIR", projects_dir)
    monkeypatch.setattr(threads, "PROJECTS_DIR", projects_dir)

    return projects_dir


@pytest.fixture
def mock_project(mock_projects_dir):
    """Create a mock project directory with sample data."""
    project_dir = mock_projects_dir / TEST_PROJECT
    project_dir.mkdir()

    # Create a sample JSONL session file
    jsonl_path = project_dir / "session_abc123.jsonl"
    events = _make_sample_events()
    jsonl_path.write_text(
        "\n".join(json.dumps(e) for e in events),
        encoding="utf-8",
    )

    # Create memory directory with files
    memory_dir = project_dir / "memory"
    memory_dir.mkdir()

    (memory_dir / "MEMORY.md").write_text(
        "# Project Memory\n\n- [Test thread](thread_test.md) — a test thread\n",
        encoding="utf-8",
    )
    (memory_dir / "thread_test.md").write_text(
        "# Thread: Test\n\n## Status: ACTIVE\n\nSome context here.\n",
        encoding="utf-8",
    )

    return project_dir


def _make_sample_events():
    """Generate minimal JSONL events for testing."""
    now = time.time()
    return [
        {
            "type": "user",
            "timestamp": int(now * 1000),
            "message": {
                "content": "Help me refactor the authentication module",
            },
        },
        {
            "type": "assistant",
            "timestamp": int((now + 10) * 1000),
            "message": {
                "model": "claude-sonnet-4-20250514",
                "content": [
                    {"type": "text", "text": "I'll help you refactor the auth module. The approach: we decided to use JWT tokens instead of sessions."},
                    {"type": "tool_use", "name": "Read", "input": {"file_path": "/src/auth.py"}},
                ],
            },
        },
        {
            "type": "user",
            "timestamp": int((now + 60) * 1000),
            "message": {
                "content": "Good, now update the middleware too",
            },
        },
        {
            "type": "assistant",
            "timestamp": int((now + 70) * 1000),
            "message": {
                "model": "claude-sonnet-4-20250514",
                "content": [
                    {"type": "text", "text": "I'll update the middleware. Going with the decorator pattern for consistency."},
                    {"type": "tool_use", "name": "Edit", "input": {"file_path": "/src/middleware.py", "old_string": "old", "new_string": "new"}},
                ],
            },
        },
        {
            "type": "user",
            "timestamp": int((now + 120) * 1000),
            "message": {
                "content": "What about the database migration? Is there a risk?",
            },
        },
        {
            "type": "assistant",
            "timestamp": int((now + 130) * 1000),
            "message": {
                "model": "claude-sonnet-4-20250514",
                "content": "The migration is straightforward — just adding a token_hash column. No data loss risk.",
            },
        },
    ]


# ── Database seeding ──────────────────────────────────────────

@pytest.fixture
def seeded_session(mock_project):
    """Insert a test session into cache.db and return its ID."""
    session_id = "session_abc123"
    jsonl_path = mock_project / f"{session_id}.jsonl"

    with db_connection() as db:
        db.execute("""
            INSERT OR REPLACE INTO sessions
            (session_id, project_path, file_path, file_size, file_mtime,
             message_count, user_count, assistant_count,
             first_message, last_message, started_at, model, indexed_at,
             tools_used, category, importance, duration_mins,
             starred, archived, rating, custom_title, tags, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id, TEST_PROJECT, str(jsonl_path),
            jsonl_path.stat().st_size, jsonl_path.stat().st_mtime,
            6, 3, 3,
            "Help me refactor the authentication module",
            "What about the database migration?",
            "2026-03-31T10:00:00+00:00",
            "claude-sonnet-4-20250514",
            "2026-03-31T10:05:00+00:00",
            '["Edit", "Read"]',
            "standard", 45.0, 2.0,
            0, 0, 0, "", "[]", "",
        ))
        db.commit()

    return session_id


@pytest.fixture
def seeded_sessions_for_topics(mock_projects_dir):
    """Insert multiple sessions with overlapping keywords for topic extraction."""
    project_dir = mock_projects_dir / TEST_PROJECT
    project_dir.mkdir(exist_ok=True)

    sessions = [
        ("sess_auth_1", "Refactor authentication module with JWT tokens", "standard", 50.0, 20),
        ("sess_auth_2", "Fix authentication bug in JWT token validation", "standard", 40.0, 15),
        ("sess_auth_3", "Add authentication tests for JWT middleware", "standard", 35.0, 12),
        ("sess_db_1", "Database migration for user table schema", "standard", 30.0, 10),
        ("sess_db_2", "Database performance tuning and index optimization", "major", 60.0, 50),
    ]

    with db_connection() as db:
        for sid, first_msg, category, importance, msg_count in sessions:
            # Create empty jsonl file
            jsonl_path = project_dir / f"{sid}.jsonl"
            jsonl_path.write_text("", encoding="utf-8")

            db.execute("""
                INSERT OR REPLACE INTO sessions
                (session_id, project_path, file_path, file_size, file_mtime,
                 message_count, user_count, assistant_count,
                 first_message, last_message, started_at, model, indexed_at,
                 tools_used, category, importance, duration_mins,
                 starred, archived, rating, custom_title, tags, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sid, TEST_PROJECT, str(jsonl_path),
                100, time.time(),
                msg_count, msg_count // 2, msg_count // 2,
                first_msg, first_msg,
                "2026-03-31T10:00:00+00:00",
                "claude-sonnet-4-20250514",
                "2026-03-31T10:05:00+00:00",
                "[]", category, importance, 5.0,
                0, 0, 0, "", "[]", "",
            ))
        db.commit()
