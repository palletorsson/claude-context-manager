"""Tests for the dashboard router."""

from tests.conftest import TEST_PROJECT


class TestDashboard:
    def test_returns_dashboard_data(self, client, seeded_session):
        r = client.get("/api/dashboard")
        assert r.status_code == 200
        data = r.json()
        assert "projects" in data
        assert "recent_sessions" in data
        assert "total_sessions" in data
        assert "active_threads" in data
        assert "total_memory_files" in data

    def test_total_sessions_count(self, client, seeded_session):
        r = client.get("/api/dashboard")
        assert r.json()["total_sessions"] >= 1

    def test_recent_sessions_have_fields(self, client, seeded_session):
        r = client.get("/api/dashboard")
        recent = r.json()["recent_sessions"]
        if recent:
            s = recent[0]
            assert "session_id" in s
            assert "first_message" in s
            assert "started_at" in s

    def test_empty_dashboard(self, client, mock_projects_dir):
        """Dashboard works even with no projects."""
        r = client.get("/api/dashboard")
        assert r.status_code == 200
        assert r.json()["total_sessions"] >= 0
