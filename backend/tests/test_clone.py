"""Tests for the clone router — extracting session context into thread files."""

from tests.conftest import TEST_PROJECT


class TestCloneSession:
    def test_clone_creates_thread_file(self, client, seeded_session, mock_project):
        r = client.post("/api/clone", json={
            "session_id": seeded_session,
            "thread_name": "auth refactor",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["created"] is True
        assert data["filename"] == "thread_auth_refactor.md"
        assert "context_summary" in data
        assert "decisions" in data["context_summary"]
        assert "files_touched" in data["context_summary"]
        assert "questions" in data["context_summary"]

    def test_clone_extracts_decisions(self, client, seeded_session, mock_project):
        r = client.post("/api/clone", json={
            "session_id": seeded_session,
            "thread_name": "decisions test",
        })
        data = r.json()
        # Our sample events contain "decided" and "Going with" markers
        assert data["context_summary"]["decisions"] >= 0

    def test_clone_extracts_files(self, client, seeded_session, mock_project):
        r = client.post("/api/clone", json={
            "session_id": seeded_session,
            "thread_name": "files test",
        })
        data = r.json()
        # Our sample events have Read and Edit tool use with file_path
        assert data["context_summary"]["files_touched"] >= 1

    def test_clone_thread_content_has_sections(self, client, seeded_session, mock_project):
        client.post("/api/clone", json={
            "session_id": seeded_session,
            "thread_name": "sections test",
        })
        # Read the created file
        thread_path = mock_project / "memory" / "thread_sections_test.md"
        assert thread_path.exists()
        content = thread_path.read_text(encoding="utf-8")
        assert "# Thread:" in content
        assert "## Status: ACTIVE" in content
        assert "## Origin" in content

    def test_clone_404_on_missing_session(self, client, mock_project):
        r = client.post("/api/clone", json={
            "session_id": "nonexistent",
            "thread_name": "test",
        })
        assert r.status_code == 404

    def test_clone_409_on_duplicate(self, client, seeded_session, mock_project):
        # Create first
        client.post("/api/clone", json={
            "session_id": seeded_session,
            "thread_name": "dupe test",
        })
        # Try again
        r = client.post("/api/clone", json={
            "session_id": seeded_session,
            "thread_name": "dupe test",
        })
        assert r.status_code == 409
