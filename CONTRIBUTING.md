# Contributing to Claude Context Manager

Thank you for your interest in contributing. This document covers setup, conventions, and how to submit changes.

## Development Setup

### Prerequisites

- Python 3.10+
- Node.js 18+
- A `~/.claude` directory with at least one project (from using Claude Code)

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --port 8000 --reload
```

The `--reload` flag enables hot-reloading during development.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Opens on `http://localhost:3001` by default.

### Running Tests

```bash
cd backend
python -m pytest tests/ -v          # full suite with details
python -m pytest tests/ -q          # quick summary (199 tests, ~2.4s)
python -m pytest tests/test_clone.py -v   # single file
```

All tests must pass before submitting a PR.

## Project Structure

```
backend/
  main.py              # FastAPI app entry point
  config.py            # Environment variables, path auto-detection
  db.py                # SQLite schema, migrations, connection pooling
  security.py          # Input sanitization, path traversal prevention
  routers/             # HTTP route handlers (one file per resource)
  services/            # Business logic (indexing, clustering, temperature)
  tests/               # Pytest test suite
  data/                # SQLite cache database (gitignored)

frontend/
  src/app/             # Next.js pages (App Router)
  src/components/      # Shared React components
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for a deeper walkthrough of the indexing pipeline, cache lifecycle, and how routers relate to services.

## Coding Conventions

### Python (backend)

- Follow PEP 8. No linter is enforced yet, but keep it clean.
- Use type hints for function signatures.
- All database access goes through `db_connection()` context manager (from `db.py`).
- All user-facing input must be validated or sanitized using utilities in `security.py`.
- SQL queries use parameterized statements (`?` placeholders). Never interpolate user input.
- New endpoints go in `routers/`. Business logic goes in `services/`.

### TypeScript (frontend)

- All pages use `"use client"` (client-side rendering).
- Tailwind CSS for styling. No CSS modules.
- API calls go to `NEXT_PUBLIC_API_URL` (defaults to `http://localhost:8000`).

### Tests

- Every new endpoint needs at least one happy-path and one error-path test.
- Security-sensitive code (file paths, user input) needs explicit security tests.
- Tests use an in-memory SQLite database via the `conftest.py` fixtures.

## Submitting Changes

1. Fork the repo and create a feature branch from `master`.
2. Make your changes. Keep commits focused.
3. Run the test suite: `python -m pytest tests/ -q`
4. Open a PR with:
   - A clear title describing what changed
   - A brief description of why
   - Any testing you did beyond the automated suite

## Areas Where Help is Welcome

See the GitHub issues for current priorities. Some standing opportunities:

- **Screenshots / demo GIF** -- Capture the UI for the README
- **Summarization** -- Use an LLM to generate session summaries instead of first-message extraction
- **Diff view** -- Show what files changed during a session
- **Timeline** -- Visual timeline of sessions across projects
- **Export** -- Export starred sessions as markdown reports
- **MCP integration** -- Expose as an MCP server so Claude can query its own history
- **Turning-point precision** -- Evaluate false positive/negative rates of the keyword-based detector

## Questions?

Open an issue. There is no chat channel yet.
