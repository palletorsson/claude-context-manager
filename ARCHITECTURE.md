# Architecture

This document explains how Claude Context Manager works internally: the indexing pipeline, cache lifecycle, data flow, and how the components relate.

## Overview

The system reads Claude Code's session logs (`~/.claude/projects/`) in **read-only mode** and maintains a local SQLite cache with indexed metadata. It never writes to your Claude Code data.

```
~/.claude/projects/                     backend/data/cache.db
  <project>/                              sessions table
    *.jsonl  ──── index ──────────────>   (metadata, importance, hash)
    memory/*.md ── scan ──────────────>   memory_meta table
                                          (temperature, status, refs)
                                          topic_cache table
                                          concept_refs table
                                          context_branches table
                                          tree_overrides table
```

## Indexing Pipeline

When a project's sessions are requested via the API, the system runs `_ensure_indexed()` which processes each JSONL file through a three-tier gate:

### Three-Tier Hash Gate

```
For each session file:

  1. Mtime check (O(1))
     Compare file.stat().st_mtime against cached mtime.
     If within 1s tolerance → SKIP (most common path)

  2. Hash check (O(file_size))
     Compute SHA-256 of file content.
     If hash matches cached hash → update mtime only, SKIP
     (Catches: file copied, backed up, or touched without content change)

  3. Full re-index (O(file_size + events))
     Stream JSONL line by line. Extract:
       - Message counts (user, assistant)
       - Timestamps (start, end, duration)
       - Model name
       - Tools used (from tool_use content blocks)
       - First/last user messages
     Compute classification and importance score.
     Store in sessions table with new content hash.
```

This pipeline is in `routers/sessions.py:_ensure_indexed()`. The hash utility is in `services/variety.py:file_content_hash()`. The JSONL parser is in `services/indexer.py:index_session()`.

## Data Flow

### Request: List sessions for a project

```
GET /api/sessions?project=<encoded_path>
  → routers/sessions.py:list_sessions()
    → _ensure_indexed(project_path)     # runs three-tier gate
    → SQL query with filters/sort       # from cache.db
    → return JSON response
```

### Request: Clone a session to thread

```
POST /api/clone {session_id, thread_name}
  → routers/clone.py:clone_session()
    → _extract_context(jsonl_path)      # streams JSONL, extracts:
        - decisions (keyword markers in assistant messages)
        - turning points: pivots + breakthroughs
        - files touched (from tool_use blocks)
        - questions (sentences ending with ?)
    → _generate_thread(name, session, context)
        - writes thread_*.md to project's memory/ directory
    → return summary counts
```

### Request: Topic suggestions

```
GET /api/threads/suggest?project=<encoded_path>
  → routers/threads.py
    → variety.get_cached_topics(project_path)
        - computes sessions_hash from all session metadata
        - if hash matches cached → return cached clusters
    → topic_extractor.extract_topics_from_sessions(project_path)
        - TF-IDF keyword extraction from first messages
        - Jaccard similarity clustering (O(n^2))
    → variety.cache_topics(project_path, clusters)
    → return clusters
```

## Database Schema

All tables live in `backend/data/cache.db` (SQLite, WAL mode). Defined in `db.py`.

### Core Tables

| Table | Purpose | Key fields |
|-------|---------|-----------|
| `projects` | Discovered projects | encoded_path, display_name, session_count |
| `sessions` | Indexed session metadata | session_id, content_hash, importance, category, starred, archived, rating |
| `context_branches` | Stored knowledge | type (formula/clause/pattern/insight/substrate), content, tags |
| `tree_overrides` | Manual annotations on working tree | node_id, status, note, priority |

### Variety Engineering Tables

| Table | Purpose | Cache key |
|-------|---------|----------|
| `topic_cache` | Cached topic clusters | sessions_hash (composite of all session metadata) |
| `memory_meta` | Memory file metadata + temperature | file_hash (SHA-256 of file content) |
| `concept_refs` | Keyword/tool frequency tracking | concept_hash (type + project + value) |

### Cache Invalidation

Each cache layer has its own invalidation mechanism:

- **Sessions**: mtime → content_hash → full re-index
- **Topics**: sessions_hash changes when any session is added/modified
- **Memory metadata**: file_hash changes when memory file content changes
- **Projects**: directory mtime changes when projects are added/removed

The entire cache database is safe to delete. It rebuilds on the next startup or API request.

## Memory Temperature

Computed in `services/variety.py:compute_temperature()`:

```
score = recency_decay + connectivity + importance

  recency_decay = max(0, 40 - days_since_reference * 1.5)    [0-40]
  connectivity  = min(30, reference_count * 3)                 [0-30]
  importance    = min(30, raw_importance * 0.3)                 [0-30]
```

Labels: hot (>=75), warm (>=40), cold (>=15), frozen (<15).

Current purpose: **browsing triage** in the memory UI. Hot items surface first; frozen items can be ignored.

## Session Classification

Computed in `services/indexer.py:classify_session()`:

- **Automated**: detected by known prompt patterns ("Take your time and do excellent work", "You are working on")
- **Minor**: <=2 user messages and <=6 total, or <=10 total and <20KB
- **Major**: >=200 messages, >=1MB, or >=30 user messages
- **Standard**: everything else

## Turning-Point Extraction

Computed in `routers/clone.py:_extract_context()` during clone operations:

- **Pivots**: user messages after message #2 containing redirect markers ("actually,", "scratch that", "instead,", "different approach")
- **Breakthroughs**: assistant messages containing discovery markers ("the issue was", "root cause", "found it", "turns out")

This is an explicitly heuristic approach. See the paper (`docs/variety-engineering.tex`) for discussion of limitations and the ablation study.

## Router / Service Relationship

```
routers/           services/              db.py
  projects.py   →  claude_fs.py          ← discover_projects, decode paths
  sessions.py   →  indexer.py            ← stream JSONL, classify, score
                →  variety.py            ← hash, temperature, concept refs
  memory.py     →  variety.py            ← memory metadata cache
  clone.py      →  (inline extraction)   ← stream JSONL for context
  threads.py    →  topic_extractor.py    ← TF-IDF, Jaccard clustering
                →  variety.py            ← topic cache gate
  tree.py       →  tree_builder.py       ← generate project tree
  context.py    →  (direct DB)           ← CRUD on context_branches
  dashboard.py  →  (direct DB)           ← aggregate stats
```

Routers handle HTTP concerns (validation, response formatting). Services handle business logic (parsing, scoring, clustering). `db.py` manages the connection pool and schema.

## Security

Handled in `security.py`:

- **Path traversal prevention**: `safe_resolve()` ensures resolved paths stay within `PROJECTS_DIR`
- **Filename validation**: rejects null bytes, path separators, `.` / `..`
- **Node ID sanitization**: strips unsafe characters for tree override keys
- **SQL injection prevention**: all queries use parameterized statements
- **Connection leak prevention**: all DB access uses context managers

## Key Design Decisions

**Read-only access to Claude Code data.** The system never writes to `~/.claude/projects/*/` except into the `memory/` subdirectory during clone operations. This is critical for trust.

**No LLM dependencies.** All analysis (classification, importance scoring, topic clustering, turning-point detection) uses lightweight heuristics. This keeps the system fast, deterministic, and dependency-free.

**SQLite with WAL mode.** A single-file database is appropriate for a local developer tool. WAL mode allows concurrent reads during writes.

**Content hashing as the primary optimization.** Rather than time-based TTLs or polling, the system uses content hashes to make exact "changed/not changed" decisions. This is the core architectural idea, discussed in detail in the paper.
