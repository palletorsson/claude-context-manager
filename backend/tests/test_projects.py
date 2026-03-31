"""Tests for the projects router."""

from tests.conftest import TEST_PROJECT


class TestListProjects:
    def test_returns_projects(self, client, mock_project):
        r = client.get("/api/projects")
        assert r.status_code == 200
        data = r.json()
        assert "projects" in data
        assert "total" in data
        assert data["total"] >= 1
        # Our mock project should appear
        names = [p["encoded_path"] for p in data["projects"]]
        assert TEST_PROJECT in names

    def test_project_has_expected_fields(self, client, mock_project):
        r = client.get("/api/projects")
        project = next(p for p in r.json()["projects"] if p["encoded_path"] == TEST_PROJECT)
        assert "display_name" in project
        assert "full_path" in project
        assert "session_count" in project
        assert "memory_count" in project
        assert project["session_count"] >= 1  # we created a .jsonl file
        assert project["memory_count"] >= 1  # we created .md files

    def test_empty_projects_dir(self, client, mock_projects_dir):
        """No project directories → empty list."""
        r = client.get("/api/projects")
        assert r.status_code == 200
        assert r.json()["total"] == 0
