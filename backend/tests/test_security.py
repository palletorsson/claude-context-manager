"""Unit tests for backend/security.py validators."""

import sys
import os
import tempfile
from pathlib import Path

import pytest

# Add backend to path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from security import safe_resolve, validate_filename, validate_project, sanitize_node_id


# ── safe_resolve ──────────────────────────────────────────────


class TestSafeResolve:
    def setup_method(self):
        self.base = Path(tempfile.gettempdir()) / "test_safe_resolve"
        self.base.mkdir(exist_ok=True)

    def test_valid_path(self):
        result = safe_resolve(self.base, "subdir", "file.txt")
        assert str(result).startswith(str(self.base.resolve()))

    def test_blocks_dotdot_traversal(self):
        with pytest.raises(Exception) as exc_info:
            safe_resolve(self.base, "..", "..", "etc", "passwd")
        assert exc_info.value.status_code == 400
        assert "traversal" in exc_info.value.detail.lower()

    def test_blocks_null_bytes(self):
        with pytest.raises(Exception) as exc_info:
            safe_resolve(self.base, "file\x00.txt")
        assert exc_info.value.status_code == 400
        assert "null" in exc_info.value.detail.lower()

    def test_blocks_absolute_escape(self):
        """Even if segment looks like an absolute path, it should be relative to base."""
        result = safe_resolve(self.base, "normal_segment")
        assert str(result).startswith(str(self.base.resolve()))

    def test_single_segment(self):
        result = safe_resolve(self.base, "myfile.md")
        assert result.name == "myfile.md"

    def test_nested_segments(self):
        result = safe_resolve(self.base, "a", "b", "c.txt")
        assert result.name == "c.txt"


# ── validate_filename ─────────────────────────────────────────


class TestValidateFilename:
    def test_valid_filename(self):
        assert validate_filename("test.md") == "test.md"

    def test_valid_with_dashes_underscores(self):
        assert validate_filename("my-file_v2.md") == "my-file_v2.md"

    def test_strips_whitespace(self):
        assert validate_filename("  test.md  ") == "test.md"

    def test_blocks_empty(self):
        with pytest.raises(Exception) as exc_info:
            validate_filename("")
        assert exc_info.value.status_code == 400

    def test_blocks_whitespace_only(self):
        with pytest.raises(Exception) as exc_info:
            validate_filename("   ")
        assert exc_info.value.status_code == 400

    def test_blocks_dotdot(self):
        with pytest.raises(Exception) as exc_info:
            validate_filename("../etc/passwd")
        assert exc_info.value.status_code == 400
        assert "'..' not allowed" in exc_info.value.detail

    def test_blocks_forward_slash(self):
        with pytest.raises(Exception) as exc_info:
            validate_filename("path/file.md")
        assert exc_info.value.status_code == 400
        assert "separators" in exc_info.value.detail.lower()

    def test_blocks_backslash(self):
        with pytest.raises(Exception) as exc_info:
            validate_filename("path\\file.md")
        assert exc_info.value.status_code == 400

    def test_blocks_null_bytes(self):
        with pytest.raises(Exception) as exc_info:
            validate_filename("file\x00.md")
        assert exc_info.value.status_code == 400


# ── validate_project ──────────────────────────────────────────


class TestValidateProject:
    def test_valid_encoded_path(self):
        assert validate_project("C--Users-palle-Documents-GitHub-project") == "C--Users-palle-Documents-GitHub-project"

    def test_valid_with_dots_tildes(self):
        assert validate_project("my.project~v2") == "my.project~v2"

    def test_blocks_dotdot(self):
        with pytest.raises(Exception) as exc_info:
            validate_project("../../etc")
        assert exc_info.value.status_code == 400

    def test_blocks_slashes(self):
        with pytest.raises(Exception) as exc_info:
            validate_project("path/to/project")
        assert exc_info.value.status_code == 400

    def test_blocks_spaces(self):
        with pytest.raises(Exception) as exc_info:
            validate_project("my project")
        assert exc_info.value.status_code == 400

    def test_blocks_special_chars(self):
        with pytest.raises(Exception) as exc_info:
            validate_project("project;rm -rf /")
        assert exc_info.value.status_code == 400

    def test_blocks_empty(self):
        with pytest.raises(Exception) as exc_info:
            validate_project("")
        assert exc_info.value.status_code == 400


# ── sanitize_node_id ──────────────────────────────────────────


class TestSanitizeNodeId:
    def test_simple_label(self):
        assert sanitize_node_id("My Discovery") == "my_discovery"

    def test_strips_path_separators(self):
        assert sanitize_node_id("../../etc/passwd") == "etcpasswd"

    def test_strips_special_chars(self):
        assert sanitize_node_id("hello!@#$%^&*()world") == "helloworld"

    def test_preserves_underscores(self):
        assert sanitize_node_id("my_node_id") == "my_node_id"

    def test_preserves_numbers(self):
        assert sanitize_node_id("node 42") == "node_42"

    def test_truncates_at_40(self):
        result = sanitize_node_id("a" * 100)
        assert len(result) == 40

    def test_empty_label_returns_empty(self):
        assert sanitize_node_id("!@#$%") == ""

    def test_spaces_become_underscores(self):
        assert sanitize_node_id("a b c") == "a_b_c"
