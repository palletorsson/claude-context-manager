from fastapi import APIRouter
from services.claude_fs import discover_projects

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("")
def list_projects():
    """List all discovered Claude Code projects with stats."""
    projects = discover_projects()
    return {"projects": projects, "total": len(projects)}
