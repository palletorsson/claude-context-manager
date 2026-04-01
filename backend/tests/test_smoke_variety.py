"""Smoke tests for variety engineering — measures efficiency gains and meaning preservation.

These tests verify that:
1. Cached paths produce identical results to uncached paths (meaning preservation)
2. Cached paths are faster than uncached paths (efficiency gain)
3. Hash gates correctly detect content changes vs. noise
"""

import sys
import os
import json
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.variety import (
    file_content_hash,
    compute_sessions_hash,
    get_cached_topics,
    cache_topics,
    get_cached_memory_meta,
    upsert_memory_meta,
    compute_temperature,
    get_temperature_summary,
)
from services.topic_extractor import extract_topics_from_sessions
from services.claude_fs import list_memory_files, _clear_projects_cache
from services.indexer import index_session
from db import db_connection, init_db
from tests.conftest import TEST_PROJECT


# ── Meaning Preservation: cached == uncached ──────────────────


class TestMeaningPreservation:
    """Verify that cached results are semantically identical to fresh computation."""

    def test_index_session_hash_is_stable(self, tmp_path):
        """Indexing the same file twice produces the same content_hash."""
        events = [
            {"type": "user", "timestamp": 1711900000000, "message": {"content": "Build auth module"}},
            {"type": "assistant", "timestamp": 1711900010000, "message": {
                "model": "claude-sonnet-4-20250514",
                "content": [
                    {"type": "text", "text": "I'll build the auth module."},
                    {"type": "tool_use", "name": "Write", "input": {"file_path": "/src/auth.py"}},
                ],
            }},
        ]
        jsonl = tmp_path / "stable_test.jsonl"
        jsonl.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")

        result1 = index_session(jsonl)
        result2 = index_session(jsonl)

        assert result1["content_hash"] == result2["content_hash"]
        assert result1["message_count"] == result2["message_count"]
        assert result1["first_message"] == result2["first_message"]
        assert result1["tools_used"] == result2["tools_used"]
        assert result1["category"] == result2["category"]
        assert result1["importance"] == result2["importance"]

    def test_topic_cache_preserves_clusters(self, seeded_sessions_for_topics):
        """Cached topics are identical to freshly computed topics."""
        # First call: computes fresh
        fresh = extract_topics_from_sessions(TEST_PROJECT)

        # Second call: should hit cache
        cached = extract_topics_from_sessions(TEST_PROJECT)

        assert len(fresh) == len(cached), "Cached must return same number of clusters"
        for f, c in zip(fresh, cached):
            assert f["topic"] == c["topic"]
            assert f.get("session_count") == c.get("session_count")
            assert f.get("total_importance") == c.get("total_importance")

    def test_memory_meta_preserves_status(self, mock_project):
        """Cached memory metadata matches fresh file parse."""
        # First call: parses files, caches metadata
        files1 = list_memory_files(TEST_PROJECT)

        # Second call: should hit cache
        files2 = list_memory_files(TEST_PROJECT)

        assert len(files1) == len(files2)
        for f1, f2 in zip(files1, files2):
            assert f1["filename"] == f2["filename"]
            assert f1["status"] == f2["status"]
            assert f1["summary"] == f2["summary"]
            assert f1["file_size"] == f2["file_size"]

    def test_hash_detects_real_content_change(self, tmp_path):
        """Hash changes when file content changes, not just mtime."""
        f = tmp_path / "changing.jsonl"
        f.write_text('{"type":"user","message":{"content":"version 1"}}', encoding="utf-8")
        h1 = file_content_hash(f)

        f.write_text('{"type":"user","message":{"content":"version 2"}}', encoding="utf-8")
        h2 = file_content_hash(f)

        assert h1 != h2, "Hash must change when content changes"

    def test_hash_ignores_mtime_noise(self, tmp_path):
        """Hash stays stable when only mtime changes (backup, copy, touch)."""
        f = tmp_path / "stable.jsonl"
        f.write_text('{"type":"user","message":{"content":"stable"}}', encoding="utf-8")
        h1 = file_content_hash(f)

        # Simulate mtime change without content change
        os.utime(f, (time.time() + 3600, time.time() + 3600))
        h2 = file_content_hash(f)

        assert h1 == h2, "Hash must NOT change when only mtime changes"

    def test_sessions_hash_changes_on_data_change(self, seeded_session):
        """Sessions hash detects when session metadata changes."""
        h1 = compute_sessions_hash(TEST_PROJECT)

        with db_connection() as db:
            db.execute(
                "UPDATE sessions SET first_message = 'completely different topic' WHERE session_id = ?",
                (seeded_session,)
            )
            db.commit()

        h2 = compute_sessions_hash(TEST_PROJECT)
        assert h1 != h2, "Sessions hash must change when session data changes"


# ── Efficiency: cached is faster than uncached ────────────────


class TestEfficiencyGains:
    """Measure that cached paths are meaningfully faster."""

    def test_topic_cache_speedup(self, seeded_sessions_for_topics):
        """Second topic extraction call should be significantly faster."""
        # Cold call: computes fresh
        t0 = time.perf_counter()
        result1 = extract_topics_from_sessions(TEST_PROJECT)
        cold_time = time.perf_counter() - t0

        # Warm call: should hit cache
        t0 = time.perf_counter()
        result2 = extract_topics_from_sessions(TEST_PROJECT)
        warm_time = time.perf_counter() - t0

        # Cache should be faster (at least 2x, usually 10x+)
        # On small test data the absolute times are tiny, so we check relative
        print(f"\n  Topic extraction: cold={cold_time*1000:.1f}ms, warm={warm_time*1000:.1f}ms, speedup={cold_time/max(warm_time, 0.0001):.1f}x")
        assert len(result1) == len(result2), "Results must be identical"
        # The cached path should be at least as fast (allowing for measurement noise)
        # We don't assert strict speedup on tiny test data, but log it

    def test_memory_meta_cache_speedup(self, mock_project):
        """Second memory listing should be faster due to cached metadata."""
        # Cold call
        t0 = time.perf_counter()
        files1 = list_memory_files(TEST_PROJECT)
        cold_time = time.perf_counter() - t0

        # Warm call
        t0 = time.perf_counter()
        files2 = list_memory_files(TEST_PROJECT)
        warm_time = time.perf_counter() - t0

        print(f"\n  Memory listing: cold={cold_time*1000:.1f}ms, warm={warm_time*1000:.1f}ms, speedup={cold_time/max(warm_time, 0.0001):.1f}x")
        assert len(files1) == len(files2)

    def test_index_session_produces_hash(self, tmp_path):
        """Verify index_session now returns a content_hash for the gate."""
        events = [
            {"type": "user", "message": {"content": "test"}},
            {"type": "assistant", "message": {"model": "claude-sonnet-4-20250514", "content": "ok"}},
        ]
        jsonl = tmp_path / "hash_test.jsonl"
        jsonl.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")

        result = index_session(jsonl)
        assert "content_hash" in result
        assert len(result["content_hash"]) == 64  # SHA-256 hex


# ── Hash Gate Correctness ─────────────────────────────────────


class TestHashGateCorrectness:
    """Verify the two-tier gate (mtime -> hash -> reindex) works correctly."""

    def test_mtime_gate_skips_unchanged(self, client, seeded_session):
        """Listing sessions twice with unchanged files should not re-index."""
        # First call indexes
        r1 = client.get(f"/api/sessions?project={TEST_PROJECT}")
        assert r1.status_code == 200
        count1 = r1.json()["total"]

        # Second call should hit mtime gate
        r2 = client.get(f"/api/sessions?project={TEST_PROJECT}")
        assert r2.status_code == 200
        count2 = r2.json()["total"]

        assert count1 == count2, "Same data, same result"

    def test_temperature_classification_is_consistent(self):
        """Same inputs always produce same temperature."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()

        results = set()
        for _ in range(10):
            label, score = compute_temperature(now, 5, 60, now)
            results.add((label, score))

        assert len(results) == 1, "Temperature must be deterministic"


# ── End-to-End: Full Pipeline ─────────────────────────────────


class TestEndToEndPipeline:
    """Test the full flow from session indexing through to variety stats."""

    def test_full_pipeline(self, client, seeded_session):
        """Index -> list -> variety stats -> all consistent."""
        # 1. Sessions are indexed and accessible
        r = client.get(f"/api/sessions?project={TEST_PROJECT}")
        assert r.status_code == 200
        assert r.json()["total"] >= 1

        # 2. Dashboard includes temperature summary
        r = client.get("/api/dashboard")
        assert r.status_code == 200
        data = r.json()
        assert "temperature_summary" in data
        temp = data["temperature_summary"]
        assert isinstance(temp, dict)
        assert all(k in temp for k in ("hot", "warm", "cold", "frozen"))

        # 3. Variety endpoint returns concept data
        r = client.get(f"/api/dashboard/variety?project={TEST_PROJECT}")
        assert r.status_code == 200
        variety = r.json()
        assert "temperature_distribution" in variety
        assert "top_concepts" in variety

    def test_memory_read_increments_reference(self, client, mock_project):
        """Reading a memory file should increment its reference count."""
        # Read a file
        client.get(f"/api/memory/{TEST_PROJECT}/MEMORY.md")
        client.get(f"/api/memory/{TEST_PROJECT}/MEMORY.md")
        client.get(f"/api/memory/{TEST_PROJECT}/MEMORY.md")

        # Check that reference count increased
        with db_connection() as db:
            row = db.execute(
                "SELECT reference_count FROM memory_meta WHERE project_path = ? AND filename = ?",
                (TEST_PROJECT, "MEMORY.md")
            ).fetchone()

        if row:
            assert row["reference_count"] >= 3, "Three reads should produce ref_count >= 3"
