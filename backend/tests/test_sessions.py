"""Tests for the sessions router — list, detail, update, messages."""

from tests.conftest import TEST_PROJECT


class TestListSessions:
    def test_lists_sessions(self, client, seeded_session):
        r = client.get(f"/api/sessions?project={TEST_PROJECT}")
        assert r.status_code == 200
        data = r.json()
        assert "sessions" in data
        assert "total" in data
        assert "counts" in data
        assert data["total"] >= 1

    def test_pagination(self, client, seeded_session):
        r = client.get(f"/api/sessions?project={TEST_PROJECT}&page=1&per_page=1")
        assert r.status_code == 200
        data = r.json()
        assert data["page"] == 1
        assert data["per_page"] == 1
        assert len(data["sessions"]) <= 1

    def test_filter_starred(self, client, seeded_session):
        r = client.get(f"/api/sessions?project={TEST_PROJECT}&starred=true")
        assert r.status_code == 200
        # Our seeded session is not starred, so it shouldn't appear
        for s in r.json()["sessions"]:
            assert s["starred"] == 1

    def test_filter_category(self, client, seeded_session):
        r = client.get(f"/api/sessions?project={TEST_PROJECT}&category=standard")
        assert r.status_code == 200

    def test_search(self, client, seeded_session):
        r = client.get(f"/api/sessions?project={TEST_PROJECT}&q=refactor")
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    def test_sort_options(self, client, seeded_session):
        for sort in ("newest", "oldest", "importance", "rating", "size"):
            r = client.get(f"/api/sessions?project={TEST_PROJECT}&sort={sort}")
            assert r.status_code == 200, f"Sort '{sort}' failed"

    def test_counts_include_starred_and_archived(self, client, seeded_session):
        r = client.get(f"/api/sessions?project={TEST_PROJECT}")
        counts = r.json()["counts"]
        assert "starred" in counts
        assert "archived" in counts
        assert "all" in counts


class TestGetSession:
    def test_returns_session(self, client, seeded_session):
        r = client.get(f"/api/sessions/{seeded_session}")
        assert r.status_code == 200
        data = r.json()
        assert data["session_id"] == seeded_session
        assert data["model"] == "claude-sonnet-4-20250514"
        assert isinstance(data["tools_used"], list)  # parsed from JSON string

    def test_404_on_missing(self, client):
        r = client.get("/api/sessions/nonexistent-session-id")
        assert r.status_code == 404


class TestUpdateSession:
    def test_star_session(self, client, seeded_session):
        r = client.patch(f"/api/sessions/{seeded_session}", json={"starred": True})
        assert r.status_code == 200
        assert "starred" in r.json()["fields"]

        # Verify
        r2 = client.get(f"/api/sessions/{seeded_session}")
        assert r2.json()["starred"] == 1

    def test_archive_session(self, client, seeded_session):
        r = client.patch(f"/api/sessions/{seeded_session}", json={"archived": True})
        assert r.status_code == 200

    def test_rate_session(self, client, seeded_session):
        r = client.patch(f"/api/sessions/{seeded_session}", json={"rating": 4})
        assert r.status_code == 200
        r2 = client.get(f"/api/sessions/{seeded_session}")
        assert r2.json()["rating"] == 4

    def test_rating_clamped(self, client, seeded_session):
        r = client.patch(f"/api/sessions/{seeded_session}", json={"rating": 99})
        assert r.status_code == 200
        r2 = client.get(f"/api/sessions/{seeded_session}")
        assert r2.json()["rating"] == 5  # clamped to max

    def test_set_custom_title(self, client, seeded_session):
        r = client.patch(f"/api/sessions/{seeded_session}", json={"custom_title": "Auth Refactor"})
        assert r.status_code == 200
        r2 = client.get(f"/api/sessions/{seeded_session}")
        assert r2.json()["custom_title"] == "Auth Refactor"

    def test_set_tags(self, client, seeded_session):
        r = client.patch(f"/api/sessions/{seeded_session}", json={"tags": ["auth", "refactor"]})
        assert r.status_code == 200
        r2 = client.get(f"/api/sessions/{seeded_session}")
        assert r2.json()["tags"] == ["auth", "refactor"]

    def test_404_on_missing(self, client):
        r = client.patch("/api/sessions/nonexistent", json={"starred": True})
        assert r.status_code == 404


class TestBatchUpdate:
    def test_batch_star(self, client, seeded_session):
        r = client.patch("/api/sessions/batch/update", json={
            "session_ids": [seeded_session],
            "starred": True,
        })
        assert r.status_code == 200
        assert r.json()["updated"] == 1


class TestMessages:
    def test_get_messages_paginated(self, client, seeded_session):
        r = client.get(f"/api/sessions/{seeded_session}/messages?page=1&per_page=10")
        assert r.status_code == 200
        data = r.json()
        assert "messages" in data
        assert "total" in data
        assert data["total"] >= 1
        # Check message structure
        msg = data["messages"][0]
        assert "type" in msg
        assert "preview" in msg
        assert msg["type"] in ("user", "assistant")

    def test_messages_404_on_missing_session(self, client):
        r = client.get("/api/sessions/nonexistent/messages")
        assert r.status_code == 404
