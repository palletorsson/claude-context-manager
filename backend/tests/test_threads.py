"""Tests for the threads router — topic suggestion and thread creation."""

from tests.conftest import TEST_PROJECT


class TestSuggestThreads:
    def test_suggest_returns_clusters(self, client, seeded_sessions_for_topics):
        r = client.get(f"/api/threads/suggest?project={TEST_PROJECT}")
        assert r.status_code == 200
        data = r.json()
        assert "suggestions" in data
        assert "total" in data
        assert data["project"] == TEST_PROJECT

    def test_suggestions_have_expected_fields(self, client, seeded_sessions_for_topics):
        r = client.get(f"/api/threads/suggest?project={TEST_PROJECT}")
        suggestions = r.json()["suggestions"]
        if suggestions:
            s = suggestions[0]
            assert "topic" in s
            assert "keywords" in s
            assert "session_count" in s
            assert "sessions" in s
            assert "suggested_title" in s
            assert "date_range" in s
            assert s["session_count"] >= 2

    def test_min_sessions_filter(self, client, seeded_sessions_for_topics):
        r = client.get(f"/api/threads/suggest?project={TEST_PROJECT}&min_sessions=5")
        assert r.status_code == 200
        # With min_sessions=5, fewer clusters should qualify
        for s in r.json()["suggestions"]:
            assert s["session_count"] >= 5

    def test_empty_project_returns_no_suggestions(self, client, mock_projects_dir):
        r = client.get("/api/threads/suggest?project=empty-project")
        assert r.status_code == 200
        assert r.json()["total"] == 0


class TestCreateThreadFromSuggestion:
    def test_creates_thread_file(self, client, mock_project):
        r = client.post(
            f"/api/threads/create-from-suggestion?project={TEST_PROJECT}",
            json={
                "topic": "authentication",
                "suggested_title": "Meta: Authentication",
                "keywords": ["authentication", "jwt", "tokens"],
                "sessions": [{"session_id": "s1", "first_message": "test", "importance": 50}],
                "session_count": 3,
                "total_messages": 100,
                "total_importance": 150.0,
                "date_range": {"first": "2026-03-01", "last": "2026-03-31"},
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["created"] is True
        assert data["topic"] == "authentication"
        assert "meta_thread_" in data["filename"]

    def test_409_on_duplicate_thread(self, client, mock_project):
        body = {
            "topic": "duplicate_topic",
            "suggested_title": "Meta: Duplicate",
            "keywords": ["dup"],
            "sessions": [],
            "session_count": 2,
            "total_messages": 10,
            "total_importance": 20.0,
            "date_range": {"first": "2026-03-01", "last": "2026-03-31"},
        }
        client.post(f"/api/threads/create-from-suggestion?project={TEST_PROJECT}", json=body)
        r = client.post(f"/api/threads/create-from-suggestion?project={TEST_PROJECT}", json=body)
        assert r.status_code == 409
