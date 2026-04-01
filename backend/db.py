"""SQLite cache database for session index and context branches."""

import sqlite3
from contextlib import contextmanager
from config import CACHE_DB, DATA_DIR


def get_db() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(CACHE_DB))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def db_connection():
    """Context manager that guarantees connection cleanup on exceptions."""
    conn = get_db()
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    conn = get_db()
    conn.executescript("""
        -- Projects discovered from ~/.claude/projects/
        CREATE TABLE IF NOT EXISTS projects (
            encoded_path TEXT PRIMARY KEY,
            display_name TEXT,
            full_path TEXT,
            session_count INTEGER DEFAULT 0,
            memory_count INTEGER DEFAULT 0,
            last_activity TEXT
        );

        -- Session index built by scanning JSONL files
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            project_path TEXT,
            file_path TEXT,
            file_size INTEGER,
            file_mtime REAL,
            message_count INTEGER DEFAULT 0,
            user_count INTEGER DEFAULT 0,
            assistant_count INTEGER DEFAULT 0,
            first_message TEXT,
            last_message TEXT,
            started_at TEXT,
            model TEXT,
            indexed_at TEXT
        );

        -- Context branches (formulas, clauses, patterns, insights)
        CREATE TABLE IF NOT EXISTS context_branches (
            id TEXT PRIMARY KEY,
            project TEXT DEFAULT '',
            type TEXT NOT NULL,
            content TEXT NOT NULL,
            summary TEXT DEFAULT '',
            tags TEXT DEFAULT '[]',
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_sessions_project
            ON sessions(project_path);
        CREATE INDEX IF NOT EXISTS idx_sessions_started
            ON sessions(started_at DESC);
        CREATE INDEX IF NOT EXISTS idx_context_project
            ON context_branches(project);
        CREATE INDEX IF NOT EXISTS idx_context_type
            ON context_branches(type);

        -- Variety engineering: topic cluster cache
        CREATE TABLE IF NOT EXISTS topic_cache (
            project_path TEXT PRIMARY KEY,
            sessions_hash TEXT NOT NULL,
            clusters_json TEXT NOT NULL,
            computed_at TEXT NOT NULL
        );

        -- Variety engineering: memory file metadata + temperature
        CREATE TABLE IF NOT EXISTS memory_meta (
            project_path TEXT NOT NULL,
            filename TEXT NOT NULL,
            file_hash TEXT NOT NULL,
            file_size INTEGER DEFAULT 0,
            modified_at TEXT,
            status TEXT DEFAULT 'active',
            summary TEXT DEFAULT '',
            temperature TEXT DEFAULT 'warm',
            temperature_score REAL DEFAULT 50.0,
            last_referenced_at TEXT,
            reference_count INTEGER DEFAULT 0,
            cached_at TEXT NOT NULL,
            PRIMARY KEY (project_path, filename)
        );

        CREATE INDEX IF NOT EXISTS idx_memory_meta_project
            ON memory_meta(project_path);
        CREATE INDEX IF NOT EXISTS idx_memory_meta_temperature
            ON memory_meta(temperature);

        -- Variety engineering: concept reference counting
        CREATE TABLE IF NOT EXISTS concept_refs (
            concept_hash TEXT PRIMARY KEY,
            concept_type TEXT NOT NULL,
            concept_value TEXT NOT NULL,
            project_path TEXT NOT NULL,
            ref_count INTEGER DEFAULT 1,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_concept_refs_project
            ON concept_refs(project_path);
        CREATE INDEX IF NOT EXISTS idx_concept_refs_type_project
            ON concept_refs(concept_type, project_path);
    """)
    conn.commit()

    # Migration: add metadata columns if missing
    _migrate_sessions(conn)
    conn.close()


def _migrate_sessions(conn: sqlite3.Connection):
    """Add metadata columns to sessions table if they don't exist."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()}
    migrations = {
        "starred":       "INTEGER DEFAULT 0",
        "archived":      "INTEGER DEFAULT 0",
        "rating":        "INTEGER DEFAULT 0",
        "importance":    "REAL DEFAULT 0",
        "category":      "TEXT DEFAULT ''",
        "custom_title":  "TEXT DEFAULT ''",
        "tags":          "TEXT DEFAULT ''",
        "notes":         "TEXT DEFAULT ''",
        "tools_used":    "TEXT DEFAULT ''",
        "duration_mins": "REAL DEFAULT 0",
        "content_hash":  "TEXT DEFAULT ''",
    }
    for col, definition in migrations.items():
        if col not in existing:
            conn.execute(f"ALTER TABLE sessions ADD COLUMN {col} {definition}")
    conn.commit()
