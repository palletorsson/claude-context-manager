"""Tests for the tree router — overrides, discoveries, tree structure."""

from tests.conftest import TEST_PROJECT


class TestTreeOverrides:
    def test_set_override_creates_new(self, client):
        r = client.patch("/api/tree/override?project=test-proj", json={
            "node_id": "game/spine/test",
            "status": "done",
            "note": "Completed this node",
            "priority": 1,
        })
        assert r.status_code == 200
        assert r.json()["updated"] is True

    def test_set_override_upserts(self, client):
        # Create
        client.patch("/api/tree/override?project=test-proj", json={
            "node_id": "game/upsert",
            "status": "todo",
        })
        # Update same node
        r = client.patch("/api/tree/override?project=test-proj", json={
            "node_id": "game/upsert",
            "status": "done",
            "note": "Now done",
        })
        assert r.status_code == 200

        # Verify final state
        r = client.get("/api/tree/overrides?project=test-proj")
        found = next(o for o in r.json()["overrides"] if o["node_id"] == "game/upsert")
        assert found["status"] == "done"
        assert found["note"] == "Now done"

    def test_empty_status_allowed(self, client):
        r = client.patch("/api/tree/override?project=test-proj", json={
            "node_id": "game/empty",
            "status": "",
        })
        assert r.status_code == 200


class TestDiscoveryNodes:
    def test_add_discovery(self, client):
        r = client.post("/api/tree/discovery?project=test-proj", json={
            "label": "Found interesting pattern",
            "note": "The auth module uses a decorator pattern",
            "priority": 1,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["created"] is True
        assert data["node_id"].startswith("discovery/")
        assert "found_interesting_pattern" in data["node_id"]

    def test_discovery_appears_in_overrides(self, client):
        client.post("/api/tree/discovery?project=disc-proj", json={
            "label": "My Discovery",
        })
        r = client.get("/api/tree/overrides?project=disc-proj")
        nodes = [o["node_id"] for o in r.json()["overrides"]]
        assert any("discovery/" in n for n in nodes)


class TestListOverrides:
    def test_returns_overrides(self, client):
        # Create some overrides
        client.patch("/api/tree/override?project=list-proj", json={
            "node_id": "node/a", "status": "done",
        })
        client.patch("/api/tree/override?project=list-proj", json={
            "node_id": "node/b", "status": "active",
        })

        r = client.get("/api/tree/overrides?project=list-proj")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 2
        assert len(data["overrides"]) >= 2

    def test_overrides_are_project_scoped(self, client):
        client.patch("/api/tree/override?project=proj-A", json={
            "node_id": "x", "status": "done",
        })
        client.patch("/api/tree/override?project=proj-B", json={
            "node_id": "y", "status": "todo",
        })

        r = client.get("/api/tree/overrides?project=proj-A")
        ids = [o["node_id"] for o in r.json()["overrides"]]
        assert "x" in ids
        assert "y" not in ids


class TestGetTree:
    def test_returns_tree_structure(self, client, mock_project):
        r = client.get(f"/api/tree?project={TEST_PROJECT}")
        assert r.status_code == 200
        tree = r.json()
        assert "children" in tree
        assert "stats" in tree
        assert "generated" in tree
        assert len(tree["children"]) >= 1

    def test_tree_stats_have_counts(self, client, mock_project):
        r = client.get(f"/api/tree?project={TEST_PROJECT}")
        stats = r.json()["stats"]
        assert "total" in stats
        assert "done" in stats
        assert "todo" in stats
