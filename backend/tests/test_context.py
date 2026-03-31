"""Tests for the context router — full CRUD on context branches."""


class TestContextCRUD:
    def test_create_and_list(self, client):
        # Create
        r = client.post("/api/context", json={
            "type": "formula",
            "content": "E = mc^2",
            "summary": "Energy-mass equivalence",
            "tags": ["physics", "relativity"],
            "project": "test-project",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["created"] is True
        assert data["type"] == "formula"
        entry_id = data["id"]

        # List
        r = client.get("/api/context?project=test-project")
        assert r.status_code == 200
        results = r.json()["results"]
        assert len(results) >= 1
        found = next((b for b in results if b["id"] == entry_id), None)
        assert found is not None
        assert found["content"] == "E = mc^2"
        assert found["tags"] == ["physics", "relativity"]

    def test_update(self, client):
        # Create first
        r = client.post("/api/context", json={
            "type": "pattern",
            "content": "Original content",
        })
        entry_id = r.json()["id"]

        # Update
        r = client.patch(f"/api/context/{entry_id}", json={
            "content": "Updated content",
            "summary": "Now with summary",
        })
        assert r.status_code == 200
        assert r.json()["updated"] == entry_id

        # Verify
        r = client.get("/api/context")
        found = next(b for b in r.json()["results"] if b["id"] == entry_id)
        assert found["content"] == "Updated content"
        assert found["summary"] == "Now with summary"

    def test_delete(self, client):
        # Create
        r = client.post("/api/context", json={
            "type": "insight",
            "content": "To be deleted",
        })
        entry_id = r.json()["id"]

        # Delete
        r = client.delete(f"/api/context/{entry_id}")
        assert r.status_code == 200
        assert r.json()["deleted"] == entry_id

        # Verify gone
        r = client.get("/api/context")
        ids = [b["id"] for b in r.json()["results"]]
        assert entry_id not in ids

    def test_update_nonexistent_returns_404(self, client):
        r = client.patch("/api/context/nonexistent-id", json={"content": "x"})
        assert r.status_code == 404


class TestContextFilters:
    def test_filter_by_type(self, client):
        client.post("/api/context", json={"type": "clause", "content": "clause1"})
        client.post("/api/context", json={"type": "substrate", "content": "sub1"})

        r = client.get("/api/context?type=clause")
        assert r.status_code == 200
        types = {b["type"] for b in r.json()["results"]}
        assert types == {"clause"}

    def test_filter_by_search(self, client):
        client.post("/api/context", json={"type": "formula", "content": "unique_search_term_xyz"})
        r = client.get("/api/context?q=unique_search_term_xyz")
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    def test_filter_by_tag(self, client):
        client.post("/api/context", json={
            "type": "pattern",
            "content": "tagged content",
            "tags": ["special_tag_42"],
        })
        r = client.get('/api/context?tag=special_tag_42')
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    def test_limit(self, client):
        for i in range(5):
            client.post("/api/context", json={"type": "insight", "content": f"item {i}"})
        r = client.get("/api/context?type=insight&limit=2")
        assert len(r.json()["results"]) <= 2


class TestContextStats:
    def test_returns_counts_by_type(self, client):
        client.post("/api/context", json={"type": "formula", "content": "f1", "project": "stats-test"})
        client.post("/api/context", json={"type": "formula", "content": "f2", "project": "stats-test"})
        client.post("/api/context", json={"type": "clause", "content": "c1", "project": "stats-test"})

        r = client.get("/api/context/stats?project=stats-test")
        assert r.status_code == 200
        stats = r.json()["stats"]
        assert stats.get("formula", 0) >= 2
        assert stats.get("clause", 0) >= 1
        assert r.json()["total"] >= 3

    def test_global_stats(self, client):
        r = client.get("/api/context/stats")
        assert r.status_code == 200
        assert "stats" in r.json()
