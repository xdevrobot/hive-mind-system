"""Tests for Orchestrator module."""

import pytest
from unittest.mock import MagicMock, patch
from agents.architect.orchestrator import OrchestratorConfig, OrchestratorResult


class TestOrchestratorConfig:
    def test_default_config(self):
        config = OrchestratorConfig()
        assert config.max_workers == 3
        assert config.base_branch == "main"
        assert config.auto_merge is False

    def test_custom_config(self):
        config = OrchestratorConfig(
            repo="owner/repo",
            issue=42,
            max_workers=5,
            auto_merge=True,
        )
        assert config.repo == "owner/repo"
        assert config.issue == 42
        assert config.max_workers == 5
        assert config.auto_merge is True


class TestOrchestratorResult:
    def test_to_dict(self):
        result = OrchestratorResult(
            success=True,
            total_tasks=5,
            completed=4,
            failed=1,
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["total_tasks"] == 5
        assert d["completed"] == 4
        assert d["failed"] == 1
