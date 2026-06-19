"""Tests for GitClient module."""

import os
import tempfile
import pytest
from agents.shared.git_client import GitClient


class TestGitClient:
    def test_init(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            client = GitClient(tmpdir)
            assert client.work_dir == tmpdir

    def test_generate_branch_name(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            client = GitClient(tmpdir)
            name = client.generate_branch_name(42, 8)
            assert "42" in name
            assert "hive" in name.lower() or len(name) > 0

    def test_generate_branch_name_with_prefix(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            client = GitClient(tmpdir)
            name = client.generate_branch_name(100, 12, prefix="feature")
            assert "feature" in name.lower() or "100" in name
