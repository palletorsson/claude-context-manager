"""Tests for the memory router — CRUD operations on .md files."""

from tests.conftest import TEST_PROJECT


class TestListMemoryFiles:
    def test_lists_files(self, client, mock_project):
        r = client.get(f"/api/memory?project={TEST_PROJECT}")
        assert r.status_code == 200
        data = r.json()
        assert "files" in data
        assert data["total"] >= 2  # MEMORY.md + thread_test.md
        filenames = [f["filename"] for f in data["files"]]
        assert "MEMORY.md" in filenames

    def test_file_has_metadata(self, client, mock_project):
        r = client.get(f"/api/memory?project={TEST_PROJECT}")
        f = r.json()["files"][0]
        assert "filename" in f
        assert "file_size" in f
        assert "modified_at" in f
        assert "status" in f
        assert "summary" in f


class TestReadMemoryFile:
    def test_reads_content(self, client, mock_project):
        r = client.get(f"/api/memory/{TEST_PROJECT}/MEMORY.md")
        assert r.status_code == 200
        data = r.json()
        assert data["filename"] == "MEMORY.md"
        assert "Project Memory" in data["content"]
        assert data["size"] > 0

    def test_404_on_missing_file(self, client, mock_project):
        r = client.get(f"/api/memory/{TEST_PROJECT}/nonexistent.md")
        assert r.status_code == 404


class TestCreateMemoryFile:
    def test_creates_file(self, client, mock_project):
        r = client.post(
            f"/api/memory/{TEST_PROJECT}",
            json={"filename": "new_thread", "content": "# New Thread\n\nContent here."},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["created"] is True
        assert data["filename"] == "new_thread.md"  # auto-appends .md

    def test_creates_file_with_md_suffix(self, client, mock_project):
        r = client.post(
            f"/api/memory/{TEST_PROJECT}",
            json={"filename": "already.md", "content": "Content"},
        )
        assert r.status_code == 200
        assert r.json()["filename"] == "already.md"  # doesn't double-append

    def test_409_on_duplicate(self, client, mock_project):
        r = client.post(
            f"/api/memory/{TEST_PROJECT}",
            json={"filename": "MEMORY.md", "content": "duplicate"},
        )
        assert r.status_code == 409


class TestUpdateMemoryFile:
    def test_updates_content(self, client, mock_project):
        r = client.put(
            f"/api/memory/{TEST_PROJECT}/MEMORY.md",
            json={"content": "# Updated\n\nNew content."},
        )
        assert r.status_code == 200
        assert r.json()["updated"] is True

        # Verify content changed
        r2 = client.get(f"/api/memory/{TEST_PROJECT}/MEMORY.md")
        assert "Updated" in r2.json()["content"]

    def test_404_on_missing_file(self, client, mock_project):
        r = client.put(
            f"/api/memory/{TEST_PROJECT}/nonexistent.md",
            json={"content": "nope"},
        )
        assert r.status_code == 404


class TestDeleteMemoryFile:
    def test_archives_file(self, client, mock_project):
        r = client.delete(f"/api/memory/{TEST_PROJECT}/thread_test.md")
        assert r.status_code == 200
        assert r.json()["archived"] is True

        # Original file should be gone
        r2 = client.get(f"/api/memory/{TEST_PROJECT}/thread_test.md")
        assert r2.status_code == 404

        # Archived file should exist on disk
        archived = mock_project / "memory" / "thread_test.md.archived"
        assert archived.exists()

    def test_404_on_missing_file(self, client, mock_project):
        r = client.delete(f"/api/memory/{TEST_PROJECT}/nonexistent.md")
        assert r.status_code == 404
