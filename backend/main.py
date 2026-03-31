"""Claude Context Manager — Browse, star, clone, and manage Claude Code sessions."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import CORS_ORIGINS, validate_config
from db import init_db
from routers import projects, sessions, memory, context, clone, dashboard

app = FastAPI(
    title="Claude Context Manager",
    description="Browse, clone, and manage Claude Code session memory. "
                "Star important sessions, archive noise, clone context into resumable threads.",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router)
app.include_router(sessions.router)
app.include_router(memory.router)
app.include_router(context.router)
app.include_router(clone.router)
app.include_router(dashboard.router)


@app.on_event("startup")
def startup():
    init_db()
    warnings = validate_config()
    for w in warnings:
        print(f"  WARNING: {w}")
    if not warnings:
        from services.claude_fs import discover_projects
        projects = discover_projects()
        total_sessions = sum(p["session_count"] for p in projects)
        print(f"  Found {len(projects)} projects, {total_sessions} sessions")


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "claude-context-manager", "version": "0.2.0"}
