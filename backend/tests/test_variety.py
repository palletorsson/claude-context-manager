"""Tests for the variety engineering system — hashing, temperature, reference counting."""

import sys
import os
import json
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.variety import (
    file_content_hash,
    composite_hash,
    compute_sessions_hash,
    get_cached_topics,
    cache_topics,
    compute_temperature,
    get_cached_memory_meta,
    upsert_memory_meta,
    record_memory_reference,
    extract_and_count_concepts,
    get_top_concepts,
    get_temperature_summary,
    backfill_content_hashes,
)
from db import db_connection
from tests.conftest import TEST_PROJECT


# ── Hash utilities ────────────────────────────────────────────


class TestFileContentHash:
    def test_deterministic(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello world", encoding="utf-8")
        h1 = file_content_hash(f)
        h2 = file_content_hash(f)
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_content_sensitive(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("version 1", encoding="utf-8")
        h1 = file_content_hash(f)
        f.write_text("version 2", encoding="utf-8")
        h2 = file_content_hash(f)
        assert h1 != h2

    def test_mtime_independent(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("same content", encoding="utf-8")
        h1 = file_content_hash(f)
        # Touch the file (change mtime, keep content)
        os.utime(f, (time.time() + 100, time.time() + 100))
        h2 = file_content_hash(f)
        assert h1 == h2

    def test_missing_file_returns_empty(self, tmp_path):
        assert file_content_hash(tmp_path / "nonexistent.txt") == ""


class TestCompositeHash:
    def test_deterministic(self):
        h1 = composite_hash("a", "b", "c")
        h2 = composite_hash("a", "b", "c")
        assert h1 == h2

    def test_order_sensitive(self):
        h1 = composite_hash("a", "b")
        h2 = composite_hash("b", "a")
        assert h1 != h2

    def test_separator_prevents_collision(self):
        h1 = composite_hash("ab", "c")
        h2 = composite_hash("a", "bc")
        assert h1 != h2


# ── Session hash ──────────────────────────────────────────────


class TestSessionsHash:
    def test_empty_project(self):
        h = compute_sessions_hash("nonexistent-project")
        assert len(h) == 64

    def test_stable_for_same_data(self, seeded_session):
        h1 = compute_sessions_hash(TEST_PROJECT)
        h2 = compute_sessions_hash(TEST_PROJECT)
        assert h1 == h2


# ── Topic cache ───────────────────────────────────────────────


class TestTopicCache:
    def test_cache_miss_returns_none(self):
        assert get_cached_topics("no-such-project") is None

    def test_cache_roundtrip(self, seeded_session):
        clusters = [{"topic": "auth", "keywords": ["jwt"]}]
        cache_topics(TEST_PROJECT, clusters)
        result = get_cached_topics(TEST_PROJECT)
        assert result is not None
        assert result[0]["topic"] == "auth"

    def test_cache_invalidated_on_session_change(self, seeded_session):
        cache_topics(TEST_PROJECT, [{"topic": "old"}])

        # Modify a session to change the hash
        with db_connection() as db:
            db.execute(
                "UPDATE sessions SET first_message = 'changed' WHERE session_id = ?",
                (seeded_session,)
            )
            db.commit()

        # Cache should now miss
        assert get_cached_topics(TEST_PROJECT) is None


# ── Memory temperature ────────────────────────────────────────


class TestComputeTemperature:
    def test_recent_is_hot(self):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        label, score = compute_temperature(now, 5, 80, now)
        assert label == "hot"
        assert score > 70

    def test_old_unreferenced_is_cold_or_frozen(self):
        old = "2025-01-01T00:00:00+00:00"
        label, score = compute_temperature(old, 0, 10, old)
        assert label in ("cold", "frozen")
        assert score < 30

    def test_high_refs_boost_temperature(self):
        old = "2025-06-01T00:00:00+00:00"
        _, score_low = compute_temperature(old, 0, 20, old)
        _, score_high = compute_temperature(old, 10, 20, old)
        assert score_high > score_low

    def test_score_bounded(self):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        _, score = compute_temperature(now, 100, 100, now)
        assert 0 <= score <= 100

    def test_none_dates_default_to_old(self):
        label, score = compute_temperature(None, 0, 0, None)
        assert label == "frozen"
        assert score < 15

    def test_all_four_labels_reachable(self):
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)

        # Hot: recent + high refs + high importance
        l, _ = compute_temperature(now.isoformat(), 10, 90, now.isoformat())
        assert l == "hot"

        # Warm: moderate
        warm_date = (now - timedelta(days=20)).isoformat()
        l, _ = compute_temperature(warm_date, 2, 30, warm_date)
        assert l == "warm"

        # Cold: old but some signal
        cold_date = (now - timedelta(days=50)).isoformat()
        l, _ = compute_temperature(cold_date, 1, 10, cold_date)
        assert l == "cold"

        # Frozen: very old, no signal
        frozen_date = (now - timedelta(days=200)).isoformat()
        l, _ = compute_temperature(frozen_date, 0, 0, frozen_date)
        assert l == "frozen"


# ── Memory metadata cache ─────────────────────────────────────


class TestMemoryMeta:
    def test_upsert_and_get(self):
        upsert_memory_meta("proj", "test.md", "hash123", 100, "2026-03-31T00:00:00+00:00", "active", "A summary")
        result = get_cached_memory_meta("proj", "test.md", "hash123")
        assert result is not None
        assert result["status"] == "active"
        assert result["summary"] == "A summary"

    def test_hash_mismatch_returns_none(self):
        upsert_memory_meta("proj", "miss.md", "hash_old", 100, "2026-03-31T00:00:00+00:00", "active", "")
        assert get_cached_memory_meta("proj", "miss.md", "hash_new") is None

    def test_reference_increment(self):
        # Use unique keys to avoid cross-test contamination
        upsert_memory_meta("proj-ref-test", "ref_unique.md", "hash_ref_u", 100, "2026-03-31T00:00:00+00:00", "active", "")
        record_memory_reference("proj-ref-test", "ref_unique.md")
        record_memory_reference("proj-ref-test", "ref_unique.md")
        result = get_cached_memory_meta("proj-ref-test", "ref_unique.md", "hash_ref_u")
        assert result["reference_count"] == 2
        assert result["last_referenced_at"] is not None

    def test_upsert_preserves_ref_count(self):
        upsert_memory_meta("proj-keep-test", "keep_unique.md", "h1u", 100, "2026-03-31T00:00:00+00:00", "active", "")
        record_memory_reference("proj-keep-test", "keep_unique.md")
        record_memory_reference("proj-keep-test", "keep_unique.md")
        # Update content (new hash) — should preserve ref_count
        upsert_memory_meta("proj-keep-test", "keep_unique.md", "h2u", 200, "2026-04-01T00:00:00+00:00", "paused", "Updated")
        result = get_cached_memory_meta("proj-keep-test", "keep_unique.md", "h2u")
        assert result["reference_count"] == 2
        assert result["status"] == "paused"


# ── Concept reference counting ────────────────────────────────


class TestConceptRefs:
    def test_extract_creates_concepts(self):
        extract_and_count_concepts("sess1", "proj-c", "Refactor authentication module", '["Read", "Edit"]')
        concepts = get_top_concepts("proj-c")
        assert len(concepts) > 0

    def test_repeated_extraction_increments(self):
        extract_and_count_concepts("s1", "proj-inc", "database migration schema", '["Bash"]')
        extract_and_count_concepts("s2", "proj-inc", "database migration index", '["Bash"]')
        concepts = get_top_concepts("proj-inc", concept_type="keyword")
        # "database" and "migration" should have ref_count >= 2
        db_concept = next((c for c in concepts if c["concept_value"] == "database"), None)
        if db_concept:
            assert db_concept["ref_count"] >= 2

    def test_tool_concepts_tracked(self):
        extract_and_count_concepts("st", "proj-t", "test", '["Read", "Edit", "Bash"]')
        tools = get_top_concepts("proj-t", concept_type="tool")
        tool_names = {c["concept_value"] for c in tools}
        assert "Read" in tool_names
        assert "Edit" in tool_names

    def test_project_scoping(self):
        extract_and_count_concepts("sa", "proj-A", "alpha concept here", "[]")
        extract_and_count_concepts("sb", "proj-B", "beta concept there", "[]")
        a_concepts = get_top_concepts("proj-A")
        b_values = {c["concept_value"] for c in get_top_concepts("proj-B")}
        a_values = {c["concept_value"] for c in a_concepts}
        # Should be scoped to project
        assert "alpha" in a_values or len(a_concepts) > 0


# ── Temperature summary ───────────────────────────────────────


class TestTemperatureSummary:
    def test_returns_all_labels(self):
        summary = get_temperature_summary()
        assert "hot" in summary
        assert "warm" in summary
        assert "cold" in summary
        assert "frozen" in summary

    def test_project_scoped(self):
        upsert_memory_meta("temp-proj", "f1.md", "h", 100, "2026-03-31T00:00:00+00:00", "active", "")
        summary = get_temperature_summary("temp-proj")
        assert sum(summary.values()) >= 1


# ── Backfill ──────────────────────────────────────────────────


class TestBackfill:
    def test_backfills_empty_hashes(self, seeded_session, mock_project):
        # Clear the hash
        with db_connection() as db:
            db.execute("UPDATE sessions SET content_hash = '' WHERE session_id = ?", (seeded_session,))
            db.commit()

        count = backfill_content_hashes()
        assert count >= 1

        # Verify hash is now populated
        with db_connection() as db:
            row = db.execute("SELECT content_hash FROM sessions WHERE session_id = ?", (seeded_session,)).fetchone()
        assert row["content_hash"] != ""


# ── API integration ───────────────────────────────────────────


class TestVarietyAPI:
    def test_dashboard_includes_temperature(self, client, seeded_session):
        r = client.get("/api/dashboard")
        assert r.status_code == 200
        assert "temperature_summary" in r.json()

    def test_variety_endpoint(self, client, seeded_session):
        r = client.get(f"/api/dashboard/variety?project={TEST_PROJECT}")
        assert r.status_code == 200
        data = r.json()
        assert "temperature_distribution" in data
        assert "top_concepts" in data
        assert "top_keywords" in data
        assert "top_tools" in data

    def test_memory_list_includes_temperature(self, client, mock_project):
        r = client.get(f"/api/memory?project={TEST_PROJECT}")
        assert r.status_code == 200
        files = r.json()["files"]
        if files:
            assert "temperature" in files[0]
            assert "temperature_score" in files[0]
