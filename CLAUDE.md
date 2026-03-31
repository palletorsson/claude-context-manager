# Claude Context Manager

> A memory operations layer for long-running AI work. Browse, star, clone, and manage Claude Code session history.

## Quick Start

```bash
# Backend
cd backend && pip install -r requirements.txt && uvicorn main:app --port 8000

# Frontend (separate terminal)
cd frontend && npm install && npm run dev

# Open http://localhost:3001
```

## Architecture

```
backend/ (FastAPI, Python 3.10+)
├── main.py              # App entry, CORS, startup
├── config.py            # Auto-detect ~/.claude, env vars
├── db.py                # SQLite cache (sessions + context_branches + tree_overrides)
├── routers/
│   ├── projects.py      # GET /api/projects
│   ├── sessions.py      # GET/PATCH /api/sessions (star, archive, rate, filter, sort)
│   ├── memory.py        # GET/PUT/POST/DELETE /api/memory (CRUD on .md files)
│   ├── context.py       # GET/POST/PATCH/DELETE /api/context (knowledge branches)
│   ├── clone.py         # POST /api/clone (extract session → thread file)
│   ├── threads.py       # GET /api/threads/suggest (auto-cluster topics)
│   ├── tree.py          # GET/PATCH /api/tree (working tree + overrides)
│   └── dashboard.py     # GET /api/dashboard (aggregate stats)
└── services/
    ├── claude_fs.py     # Cross-platform ~/.claude reader
    ├── indexer.py       # JSONL streaming + auto-classification + importance scoring
    └── topic_extractor.py # TF-IDF keyword extraction + Jaccard clustering

frontend/ (Next.js, TypeScript)
├── src/app/
│   ├── page.tsx         # Dashboard
│   ├── tree/page.tsx    # Working tree (auto + manual overrides)
│   ├── sessions/page.tsx       # Session browser (filter, sort, star, archive)
│   ├── sessions/[id]/page.tsx  # Session detail + Clone button
│   ├── memory/page.tsx         # Memory file editor
│   └── context/page.tsx        # Context branches viewer
└── src/components/
    └── Sidebar.tsx      # Navigation
```

## Data Sources (read-only, never modifies Claude Code data)

| Source | Path | What |
|--------|------|------|
| Session logs | `~/.claude/projects/<encoded>/*.jsonl` | Full conversation events |
| Memory files | `~/.claude/projects/<encoded>/memory/*.md` | MEMORY.md + thread files |
| Active sessions | `~/.claude/sessions/*.json` | Currently running |
| History | `~/.claude/history.jsonl` | Command prompts |

## Cache Database (backend/data/cache.db)

Tables: `sessions` (with star/archive/rating/importance/category/custom_title/tags), `context_branches` (formula/clause/pattern/insight/substrate), `tree_overrides` (manual annotations on working tree nodes). Safe to delete — rebuilds on startup.

## Key Features

- **Auto-classification**: major (200+ msgs), standard, minor (<6), automated (batch jobs)
- **Importance scoring**: 0-100 from message count, tool diversity, file operations
- **Clone to thread**: extracts decisions/files/questions from JSONL → thread_*.md
- **Meta-thread suggestions**: clusters sessions by recurring keywords (Jaccard similarity)
- **Working tree**: auto-generated project tree + manual overrides that survive regeneration
- **Context branches**: persistent knowledge store (formula, clause, pattern, insight, substrate)

## Current State (v0.2.0)

- 4 commits on master, MIT license, public at github.com/palletorsson/claude-context-manager
- Issue #1: "v0.3: Legibility before features" — screenshots, GIF, before/after needed
- Light GitHub-style UI (white bg, bordered cards, blue accents)
- Cross-platform, zero config, no external dependencies

## What Needs Doing (from Issue #1)

1. **Screenshots in README** — dashboard, sessions, memory, tree pages
2. **Demo GIF** — star a session → clone → see thread file (10 seconds)
3. **Before/after workflow** — concrete example of context loss → context preserved
4. **Scoring transparency** — show breakdown (messages: +X, tools: +Y) not just the number
5. **Clone quality validation** — test against 5 real sessions, check if extracted decisions are useful
6. **Taxonomy examples** — add example per context branch type so users know which to pick

## Environment Variables (.env)

```
CLAUDE_DIR=~/.claude          # auto-detected
BACKEND_PORT=8000             # default
CORS_ORIGINS=http://localhost:3000,http://localhost:3001
```
