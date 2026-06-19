"""Tests for Planner module."""

import pytest
from unittest.mock import MagicMock, patch
from agents.architect.planner import Planner


class TestPlanner:
    def test_detect_task_type_security(self):
        from issue_templates import detect_task_type
        result = detect_task_type("Fix CVE-2024", "Security vulnerability", [])
        assert result.value == "security-fix"

    def test_detect_task_type_bug(self):
        from issue_templates import detect_task_type
        result = detect_task_type("Fix crash", "Bug report", [])
        assert result.value == "bugfix"

    def test_detect_task_type_feature(self):
        from issue_templates import detect_task_type
        result = detect_task_type("Add new feature", "Feature request", [])
        assert result.value == "feature"

    def test_generate_prompt_security(self):
        from issue_templates import make_security_fix_prompt
        prompt = make_security_fix_prompt(
            "Fix XSS",
            "Cross-site scripting vulnerability",
            cwe="CWE-79",
            severity="HIGH",
        )
        assert "security" in prompt.system_prompt.lower()
        assert "CWE-79" in prompt.user_prompt

    def test_generate_prompt_bugfix(self):
        from issue_templates import make_bugfix_prompt
        prompt = make_bugfix_prompt("Fix crash", "Application crashes on startup")
        assert "bug" in prompt.system_prompt.lower() or "fix" in prompt.system_prompt.lower()
