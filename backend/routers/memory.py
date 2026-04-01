from fastapi import APIRouter, Query, HTTPException, Body
from pathlib import Path
from config import PROJECTS_DIR
from services.claude_fs import list_memory_files
from security import safe_resolve, validate_filename, validate_project
from services.variety import record_memory_reference

router = APIRouter(prefix="/api/memory", tags=["memory"])


def _memory_dir(project: str) -> Path:
    project = validate_project(project)
    d = safe_resolve(PROJECTS_DIR, project, "memory")
    d.mkdir(parents=True, exist_ok=True)
    return d


@router.get("")
def list_files(project: str = Query(...)):
    """List all memory files for a project."""
    validate_project(project)
    files = list_memory_files(project)
    return {"files": files, "total": len(files)}


@router.get("/{project}/{filename}")
def read_file(project: str, filename: str):
    """Read full content of a memory file."""
    filename = validate_filename(filename)
    mem_dir = _memory_dir(project)
    path = safe_resolve(PROJECTS_DIR, validate_project(project), "memory", filename)
    if not path.exists():
        raise HTTPException(404, f"File not found: {filename}")
    content = path.read_text(encoding="utf-8")
    # Track reference for temperature computation
    record_memory_reference(validate_project(project), filename)
    return {"filename": filename, "content": content, "size": len(content)}


@router.put("/{project}/{filename}")
def update_file(project: str, filename: str, content: str = Body(..., embed=True)):
    """Update a memory file's content."""
    filename = validate_filename(filename)
    path = safe_resolve(PROJECTS_DIR, validate_project(project), "memory", filename)
    if not path.exists():
        raise HTTPException(404, f"File not found: {filename}")
    path.write_text(content, encoding="utf-8")
    return {"filename": filename, "updated": True, "size": len(content)}


@router.post("/{project}")
def create_file(project: str, filename: str = Body(...), content: str = Body(...)):
    """Create a new memory file."""
    filename = validate_filename(filename)
    if not filename.endswith(".md"):
        filename += ".md"
    # Re-validate after suffix append
    filename = validate_filename(filename)
    mem_dir = _memory_dir(project)
    path = safe_resolve(PROJECTS_DIR, validate_project(project), "memory", filename)
    if path.exists():
        raise HTTPException(409, f"File already exists: {filename}")
    path.write_text(content, encoding="utf-8")
    return {"filename": filename, "created": True}


@router.delete("/{project}/{filename}")
def delete_file(project: str, filename: str):
    """Delete a memory file (moves to .archived suffix)."""
    filename = validate_filename(filename)
    path = safe_resolve(PROJECTS_DIR, validate_project(project), "memory", filename)
    if not path.exists():
        raise HTTPException(404, f"File not found: {filename}")
    # Archive instead of delete
    archived = path.with_suffix(".md.archived")
    path.rename(archived)
    return {"filename": filename, "archived": True}
