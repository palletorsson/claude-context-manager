"""Unit tests for service layer — indexer, topic_extractor, claude_fs."""

import json
import time
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.indexer import classify_session, compute_importance, index_session, read_messages_page, read_single_message
from services.topic_extractor import extract_keywords
from services.claude_fs import decode_project_path


# ── classify_session ──────────────────────────────────────────


class TestClassifySession:
    def test_automated_take_your_time(self):
        assert classify_session("Take your time and do excellent work on this.", 50, 10, 100000) == "automated"

    def test_automated_you_are_working_on(self):
        assert classify_session("You are working on task #42", 20, 5, 50000) == "automated"

    def test_automated_screenshot(self):
        assert classify_session("You are a screenshot analyzer", 10, 3, 20000) == "automated"

    def test_minor_short_conversation(self):
        assert classify_session("Quick question", 4, 2, 5000) == "minor"

    def test_minor_low_messages_small_file(self):
        assert classify_session("Small task", 8, 3, 15000) == "minor"

    def test_major_high_message_count(self):
        assert classify_session("Big refactor", 250, 50, 500000) == "major"

    def test_major_large_file(self):
        assert classify_session("Work session", 100, 20, 2_000_000) == "major"

    def test_major_many_user_messages(self):
        assert classify_session("Long conversation", 80, 35, 300000) == "major"

    def test_standard_default(self):
        assert classify_session("Normal task", 30, 10, 100000) == "standard"


# ── compute_importance ────────────────────────────────────────


class TestComputeImportance:
    def test_returns_float(self):
        score = compute_importance(50, 20, 30, 200000, {"Edit", "Read"}, "task")
        assert isinstance(score, float)

    def test_score_range(self):
        score = compute_importance(50, 20, 30, 200000, {"Edit", "Read", "Bash"}, "task")
        assert 0 <= score <= 100

    def test_higher_messages_higher_score(self):
        low = compute_importance(10, 5, 5, 50000, set(), "task")
        high = compute_importance(100, 50, 50, 50000, set(), "task")
        assert high > low

    def test_tool_diversity_boosts_score(self):
        no_tools = compute_importance(50, 20, 30, 100000, set(), "task")
        many_tools = compute_importance(50, 20, 30, 100000, {"Edit", "Write", "Read", "Bash", "Grep"}, "task")
        assert many_tools > no_tools

    def test_automated_penalty(self):
        normal = compute_importance(50, 20, 30, 100000, set(), "Normal task")
        automated = compute_importance(50, 20, 30, 100000, set(), "Take your time and do excellent work")
        assert automated < normal

    def test_short_session_penalty(self):
        short = compute_importance(4, 2, 2, 5000, set(), "Quick")
        normal = compute_importance(50, 20, 30, 100000, set(), "Normal")
        assert short < normal

    def test_continuation_bonus(self):
        normal = compute_importance(50, 20, 30, 100000, set(), "Fix the bug")
        continuation = compute_importance(50, 20, 30, 100000, set(), "Continue the refactor from yesterday")
        assert continuation > normal

    def test_max_100(self):
        score = compute_importance(1000, 500, 500, 10_000_000, {"Edit", "Write", "Read", "Bash", "Grep", "Glob"}, "Continue this handoff")
        assert score <= 100


# ── index_session ─────────────────────────────────────────────


class TestIndexSession:
    def test_indexes_jsonl_file(self, tmp_path):
        events = [
            {"type": "user", "timestamp": int(time.time() * 1000), "message": {"content": "Hello world"}},
            {"type": "assistant", "timestamp": int(time.time() * 1000) + 5000, "message": {"model": "claude-sonnet-4-20250514", "content": "Hi there!"}},
            {"type": "user", "timestamp": int(time.time() * 1000) + 10000, "message": {"content": "Thanks"}},
        ]
        jsonl = tmp_path / "test_session.jsonl"
        jsonl.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")

        result = index_session(jsonl)
        assert result["session_id"] == "test_session"
        assert result["user_count"] == 2
        assert result["assistant_count"] == 1
        assert result["message_count"] == 3
        assert result["model"] == "claude-sonnet-4-20250514"
        assert result["first_message"] == "Hello world"
        assert result["last_message"] == "Thanks"
        assert result["category"] in ("minor", "standard", "major", "automated")
        assert 0 <= result["importance"] <= 100

    def test_extracts_tools(self, tmp_path):
        events = [
            {"type": "user", "message": {"content": "Read a file"}},
            {"type": "assistant", "message": {
                "model": "claude-sonnet-4-20250514",
                "content": [
                    {"type": "tool_use", "name": "Read", "input": {"file_path": "/test.py"}},
                    {"type": "tool_use", "name": "Edit", "input": {}},
                ],
            }},
        ]
        jsonl = tmp_path / "tools_session.jsonl"
        jsonl.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")

        result = index_session(jsonl)
        tools = json.loads(result["tools_used"])
        assert "Read" in tools
        assert "Edit" in tools

    def test_handles_empty_file(self, tmp_path):
        jsonl = tmp_path / "empty.jsonl"
        jsonl.write_text("", encoding="utf-8")
        result = index_session(jsonl)
        assert result["message_count"] == 0


# ── read_messages_page ────────────────────────────────────────


class TestReadMessagesPage:
    def _make_jsonl(self, tmp_path, n_messages=10):
        events = []
        for i in range(n_messages):
            t = "user" if i % 2 == 0 else "assistant"
            events.append({"type": t, "message": {"content": f"Message {i}"}})
        path = tmp_path / "paged.jsonl"
        path.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
        return path

    def test_returns_page(self, tmp_path):
        path = self._make_jsonl(tmp_path, 10)
        result = read_messages_page(path, page=1, per_page=5)
        assert len(result["messages"]) == 5
        assert result["page"] == 1
        assert result["per_page"] == 5
        assert result["total"] == 10

    def test_second_page(self, tmp_path):
        path = self._make_jsonl(tmp_path, 10)
        result = read_messages_page(path, page=2, per_page=5)
        assert len(result["messages"]) == 5

    def test_partial_last_page(self, tmp_path):
        path = self._make_jsonl(tmp_path, 7)
        result = read_messages_page(path, page=2, per_page=5)
        assert len(result["messages"]) == 2

    def test_message_has_preview(self, tmp_path):
        path = self._make_jsonl(tmp_path, 2)
        result = read_messages_page(path, page=1, per_page=10)
        assert "preview" in result["messages"][0]


# ── read_single_message ───────────────────────────────────────


class TestReadSingleMessage:
    def test_reads_message_at_line(self, tmp_path):
        events = [
            {"type": "user", "message": {"content": "Line zero"}},
            {"type": "assistant", "message": {"content": "Line one"}},
        ]
        path = tmp_path / "single.jsonl"
        path.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")

        result = read_single_message(path, 0)
        assert result is not None
        assert result["type"] == "user"
        assert result["line"] == 0

        result1 = read_single_message(path, 1)
        assert result1["type"] == "assistant"

    def test_returns_none_for_out_of_range(self, tmp_path):
        path = tmp_path / "short.jsonl"
        path.write_text('{"type":"user","message":{"content":"only one"}}', encoding="utf-8")
        assert read_single_message(path, 999) is None


# ── extract_keywords ──────────────────────────────────────────


class TestExtractKeywords:
    def test_extracts_meaningful_words(self):
        keywords = extract_keywords("Refactor authentication module with JWT tokens")
        assert "authentication" in keywords or "refactor" in keywords
        assert "jwt" in keywords or "tokens" in keywords

    def test_filters_stop_words(self):
        keywords = extract_keywords("the quick brown fox and the lazy dog")
        assert "the" not in keywords
        assert "and" not in keywords

    def test_filters_short_words(self):
        keywords = extract_keywords("I am a go to do an if or")
        # All words are <= 2 chars or stop words
        assert len(keywords) == 0

    def test_empty_string(self):
        assert extract_keywords("") == []

    def test_respects_max_keywords(self):
        text = " ".join(f"word{i}" for i in range(100))
        keywords = extract_keywords(text, max_keywords=5)
        assert len(keywords) <= 5

    def test_deduplicates_by_frequency(self):
        keywords = extract_keywords("database database database schema schema migration")
        assert keywords[0] == "database"  # most frequent first


# ── decode_project_path ───────────────────────────────────────


class TestDecodeProjectPath:
    def test_returns_tuple(self):
        display, path = decode_project_path("some-encoded-path")
        assert isinstance(display, str)
        assert isinstance(path, str)

    def test_empty_string(self):
        display, path = decode_project_path("")
        assert display == ""
        assert path == ""

    def test_extracts_last_segment_as_fallback(self):
        display, path = decode_project_path("some-project-name")
        # When path can't be resolved, display should be the last segment
        assert len(display) > 0
