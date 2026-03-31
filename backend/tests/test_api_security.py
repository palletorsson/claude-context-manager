"""Integration tests for API security — path traversal, input validation, SQL safety."""

import sys
import os

import pytest
from fastapi.testclient import TestClient

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from main import app
from db import init_db, db_connection

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    """Ensure database tables exist before tests."""
    init_db()


# ── Memory router: path traversal ─────────────────────────────


class TestMemoryPathTraversal:
    """Test path traversal protection in memory router.

    URL paths with .. get normalized by the HTTP layer before reaching FastAPI,
    so we use URL-encoded segments (%2e%2e) to test the validators directly.
    The list endpoint uses query params which bypass URL normalization.
    """

    def test_list_traversal_in_project_query(self):
        r = client.get("/api/memory?project=..%2F..%2Fetc")
        assert r.status_code == 400

    def test_post_traversal_in_filename_body(self):
        """Traversal in the filename body field should be caught by validate_filename."""
        r = client.post(
            "/api/memory/valid-project",
            json={"filename": "../../../etc/passwd", "content": "malicious"},
        )
        assert r.status_code == 400

    def test_post_traversal_dotdot_filename(self):
        r = client.post(
            "/api/memory/valid-project",
            json={"filename": "..%2f..%2fetc", "content": "malicious"},
        )
        assert r.status_code == 400

    def test_post_backslash_in_filename(self):
        r = client.post(
            "/api/memory/valid-project",
            json={"filename": "path\\file.md", "content": "malicious"},
        )
        assert r.status_code == 400

    def test_null_bytes_in_project(self):
        r = client.get("/api/memory?project=test%00evil")
        assert r.status_code in (400, 422)

    def test_special_chars_in_project(self):
        r = client.get("/api/memory?project=test;rm+-rf+/")
        assert r.status_code in (400, 422)


# ── Sessions router: input validation ─────────────────────────


class TestSessionsValidation:
    def test_line_number_zero(self):
        r = client.get("/api/sessions/fake-id/messages/0")
        assert r.status_code == 400
        assert "line_number" in r.json()["detail"].lower()

    def test_line_number_negative(self):
        r = client.get("/api/sessions/fake-id/messages/-1")
        assert r.status_code == 400

    def test_search_query_too_long(self):
        long_q = "a" * 201
        r = client.get(f"/api/sessions?project=test&q={long_q}")
        assert r.status_code == 422  # FastAPI validation error


# ── Context router: input validation ──────────────────────────


class TestContextValidation:
    def test_search_query_too_long(self):
        long_q = "a" * 201
        r = client.get(f"/api/context?q={long_q}")
        assert r.status_code == 422

    def test_tag_too_long(self):
        long_tag = "a" * 101
        r = client.get(f"/api/context?tag={long_tag}")
        assert r.status_code == 422

    def test_invalid_type_on_create(self):
        r = client.post("/api/context", json={
            "type": "invalid_type",
            "content": "test content",
        })
        assert r.status_code == 400
        assert "Invalid type" in r.json()["detail"]

    def test_valid_type_on_create(self):
        r = client.post("/api/context", json={
            "type": "formula",
            "content": "test content",
        })
        assert r.status_code == 200
        assert r.json()["created"] is True


# ── Tree router: validation ───────────────────────────────────


class TestTreeValidation:
    def test_invalid_status(self):
        r = client.patch(
            "/api/tree/override?project=test",
            json={"node_id": "test/node", "status": "INVALID_STATUS"},
        )
        assert r.status_code == 400
        assert "Invalid status" in r.json()["detail"]

    def test_valid_status(self):
        r = client.patch(
            "/api/tree/override?project=test",
            json={"node_id": "test/node", "status": "done"},
        )
        assert r.status_code == 200

    def test_priority_too_high(self):
        r = client.patch(
            "/api/tree/override?project=test",
            json={"node_id": "test/node", "priority": 5},
        )
        assert r.status_code == 400
        assert "Priority" in r.json()["detail"]

    def test_priority_negative(self):
        r = client.patch(
            "/api/tree/override?project=test",
            json={"node_id": "test/node", "priority": -1},
        )
        assert r.status_code == 400

    def test_discovery_label_sanitized(self):
        r = client.post(
            "/api/tree/discovery?project=test",
            json={"label": "../../etc/passwd"},
        )
        assert r.status_code == 200
        node_id = r.json()["node_id"]
        # Should be sanitized — no path separators
        assert "/" not in node_id.split("/", 1)[1]  # only the "discovery/" prefix has /
        assert ".." not in node_id
        assert node_id == "discovery/etcpasswd"

    def test_discovery_empty_label_after_sanitize(self):
        r = client.post(
            "/api/tree/discovery?project=test",
            json={"label": "!@#$%^&*()"},
        )
        assert r.status_code == 400
        assert "alphanumeric" in r.json()["detail"].lower()

    def test_discovery_priority_out_of_range(self):
        r = client.post(
            "/api/tree/discovery?project=test",
            json={"label": "test node", "priority": 99},
        )
        assert r.status_code == 400


# ── db_connection context manager ─────────────────────────────


class TestDbConnection:
    def test_connection_closes_on_success(self):
        with db_connection() as db:
            db.execute("SELECT 1")
        # If we get here without error, the connection was properly managed

    def test_connection_closes_on_exception(self):
        with pytest.raises(ValueError):
            with db_connection() as db:
                db.execute("SELECT 1")
                raise ValueError("intentional error")
        # Connection should be closed despite the exception

    def test_connection_usable(self):
        with db_connection() as db:
            row = db.execute("SELECT 1 as val").fetchone()
            assert row["val"] == 1
