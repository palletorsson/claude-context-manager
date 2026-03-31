from fastapi import APIRouter, Query, HTTPException, Body
from pathlib import Path
from config import PROJECTS_DIR
from services.claude_fs import list_memory_files

router = APIRouter(prefix="/api/memory", tags=["memory"])


def _memory_dir(project: str) -> Path:
    d = PROJECTS_DIR / project / "memory"
    d.mkdir(parents=True, exist_ok=True)
    return d


@router.get("")
def list_files(project: str = Query(...)):
    """List all memory files for a project."""
    files = list_memory_files(project)
    return {"files": files, "total": len(files)}


@router.get("/{project}/{filename}")
def read_file(project: str, filename: str):
    """Read full content of a memory file."""
    path = _memory_dir(project) / filename
    if not path.exists():
        raise HTTPException(404, f"File not found: {filename}")
    content = path.read_text(encoding="utf-8")
    return {"filename": filename, "content": content, "size": len(content)}


@router.put("/{project}/{filename}")
def update_file(project: str, filename: str, content: str = Body(..., embed=True)):
    """Update a memory file's content."""
    path = _memory_dir(project) / filename
    if not path.exists():
        raise HTTPException(404, f"File not found: {filename}")
    path.write_text(content, encoding="utf-8")
    return {"filename": filename, "updated": True, "size": len(content)}


@router.post("/{project}")
def create_file(project: str, filename: str = Body(...), content: str = Body(...)):
    """Create a new memory file."""
    if not filename.endswith(".md"):
        filename += ".md"
    path = _memory_dir(project) / filename
    if path.exists():
        raise HTTPException(409, f"File already exists: {filename}")
    path.write_text(content, encoding="utf-8")
    return {"filename": filename, "created": True}


@router.delete("/{project}/{filename}")
def delete_file(project: str, filename: str):
    """Delete a memory file (moves to .archived suffix)."""
    path = _memory_dir(project) / filename
    if not path.exists():
        raise HTTPException(404, f"File not found: {filename}")
    # Archive instead of delete
    archived = path.with_suffix(".md.archived")
    path.rename(archived)
    return {"filename": filename, "archived": True}
