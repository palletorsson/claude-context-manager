# Claude Context Manager

Browse, star, clone, and manage your Claude Code session history. Stop losing context between sessions.

## The Problem

Claude Code accumulates thousands of conversations across projects. The built-in `--resume` shows recent sessions, but there's no way to:

- **Find** the session where you made that key decision
- **Triage** — separate the 7 breakthrough sessions from 490 automated batch jobs
- **Clone** a conversation's context into a resumable thread file
- **Star** and **rate** important sessions so they surface first
- **Browse** memory files and context branches from a UI

73% of developers cite lack of context retention as their primary frustration with AI assistants ([ContextBranch, 2024](https://arxiv.org/pdf/2512.13914)). This tool fixes that.

## What It Does

**Sessions** — Browse all your Claude Code conversations with auto-classification (major/standard/minor/automated), importance scoring, star/archive/rate, custom titles, search, and filtering.

**Clone** — Extract key decisions, files touched, and open questions from any session into a `thread_*.md` file that future sessions can resume from.

**Memory** — View and edit your project memory files (`MEMORY.md`, thread files) from a web UI. Create new threads, track status (active/paused/merged).

**Context Branches** — Store and retrieve working knowledge: formulas, proven rules (clauses), working patterns, insights, and substrate definitions. Searchable by type, tag, and full text.

**Dashboard** — Project overview with starred sessions, active threads, and context branch counts.

## Quick Start

```bash
# 1. Clone
git clone https://github.com/your-username/claude-context-manager.git
cd claude-context-manager

# 2. Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --port 8000

# 3. Frontend (new terminal)
cd frontend
npm install
npm run dev

# 4. Open http://localhost:3001
```

## Requirements

- **Python 3.10+** with pip
- **Node.js 18+** with npm
- **Claude Code** installed (`~/.claude` directory must exist)

## Configuration

Copy `.env.example` to `.env` and adjust:

```bash
# Path to Claude Code directory (auto-detected as ~/.claude)
CLAUDE_DIR=/home/user/.claude

# Backend port (default: 8000)
BACKEND_PORT=8000

# Frontend API URL (set in frontend/.env.local)
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Most users need zero configuration — it auto-detects `~/.claude`.

## Architecture

```
Backend (FastAPI, Python)          Frontend (Next.js)
  /api/projects                      /              Dashboard
  /api/sessions                      /sessions      Session browser
  /api/sessions/:id/messages         /sessions/:id  Conversation viewer + Clone
  /api/sessions/:id (PATCH)          /memory        Memory file editor
  /api/memory                        /context       Context branches
  /api/context
  /api/clone
  /api/dashboard
```

**Data sources** (read-only, never modifies your Claude Code data):
- `~/.claude/projects/<project>/*.jsonl` — session conversation logs
- `~/.claude/projects/<project>/memory/*.md` — memory and thread files
- `~/.claude/sessions/*.json` — active session metadata
- `~/.claude/history.jsonl` — command history

**Cache** (`backend/data/cache.db`):
- Session index with metadata, importance scores, stars, ratings
- Context branches (formulas, clauses, patterns, insights)
- Safe to delete — rebuilds automatically on next startup

## Features

### Auto-Classification

Sessions are automatically classified on indexing:

| Category | Criteria | Example |
|----------|----------|---------|
| **Major** | 200+ messages or 1MB+ | Deep creative sessions, multi-hour work |
| **Standard** | 10-200 messages | Normal coding sessions |
| **Minor** | < 6 messages | Quick questions |
| **Automated** | Starts with task prompt | Batch jobs, CI/CD runs |

### Importance Scoring (0-100)

Computed from: message volume, user engagement, tool diversity, file operations, session size. Major sessions score 50-90. Automated tasks score 5-15.

### Clone to Thread

Click "Clone" on any session to extract:
- First user message (the task)
- Key decisions made during the conversation
- Files touched (from Edit/Write/Read operations)
- Open questions
- Last assistant summary

This creates a `thread_*.md` file in your project's memory directory that any future Claude session can load with: "Read thread_my_topic.md and continue."

### Context Branches

Five types of persistent knowledge:

| Type | Purpose | Example |
|------|---------|---------|
| `formula` | Equations, scales | Scoring algorithms, temperature scales |
| `clause` | Proven rules | "Teleporter must be on void tile" |
| `pattern` | Working recipes | Artifact creation steps |
| `insight` | Discoveries | "Tiles repeat, mosaics don't" |
| `substrate` | Material definitions | Shader properties |

## API Documentation

Start the backend and visit `http://localhost:8000/docs` for interactive Swagger UI.

## Contributing

Issues and PRs welcome. The biggest opportunities:

1. **Summarization** — Use an LLM to generate session summaries instead of first-message extraction
2. **Diff view** — Show what files changed during a session
3. **Timeline** — Visual timeline of sessions across projects
4. **Export** — Export starred sessions as markdown reports
5. **MCP integration** — Expose as an MCP server so Claude can query its own history

## License

MIT
