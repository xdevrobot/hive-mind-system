#!/usr/bin/env python3
"""
Issue Templates — Prompt generators for different task types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TaskType(Enum):
    SECURITY_FIX = "security-fix"
    FEATURE = "feature"
    BUGFIX = "bugfix"
    REFACTOR = "refactor"
    TEST = "test"
    DOCS = "docs"
    INFRA = "infra"


@dataclass
class TaskContext:
    task_type: TaskType
    title: str
    description: str
    issue_number: int = 0
    issue_url: str = ""
    repo_name: str = ""
    repo_description: str = ""
    parent_issue_number: int = 0
    file_hints: list[str] = field(default_factory=list)
    related_cwe: str = ""
    severity: str = ""
    dependencies: list[str] = field(default_factory=list)
    extra_context: str = ""


@dataclass
class GeneratedPrompt:
    system_prompt: str
    user_prompt: str
    task_type: TaskType
    success_criteria: list[str] = field(default_factory=list)
    files_to_check: list[str] = field(default_factory=list)


_SECURITY_FIX_SYSTEM = """You are an expert security engineer fixing a security vulnerability.

Responsibilities:
1. Understand the vulnerability (CWE, attack scenario)
2. Locate vulnerable code
3. Implement secure fix (input validation, output encoding, parameterized queries)
4. Do NOT introduce new vulnerabilities
5. Preserve functionality
6. Write tests verifying the fix
7. Document the change"""

_FEATURE_SYSTEM = """You are an expert software engineer implementing a new feature.

Responsibilities:
1. Understand requirements
2. Plan implementation
3. Follow project conventions
4. Write clean, maintainable code
5. Write comprehensive tests
6. Handle errors gracefully
7. Update documentation"""

_BUGFIX_SYSTEM = """You are an expert software engineer fixing a bug.

Responsibilities:
1. Understand the bug
2. Root cause analysis
3. Implement minimal fix
4. Write regression test
5. Verify no side effects
6. Document the fix"""

_REFACTOR_SYSTEM = """You are an expert software engineer refactoring code.
Preserve behavior, improve quality, make incremental changes."""

_TEST_SYSTEM = """You are an expert QA engineer writing tests.
Cover happy path, edge cases, error cases. Ensure deterministic, isolated tests."""

_DOCS_SYSTEM = """You are an expert technical writer.
Write clear docs following project conventions. Include examples."""

_INFRA_SYSTEM = """You are an expert DevOps engineer.
Make minimal, targeted infrastructure changes following best practices."""


def generate_prompt(ctx: TaskContext) -> GeneratedPrompt:
    system_map = {
        TaskType.SECURITY_FIX: _SECURITY_FIX_SYSTEM,
        TaskType.FEATURE: _FEATURE_SYSTEM,
        TaskType.BUGFIX: _BUGFIX_SYSTEM,
        TaskType.REFACTOR: _REFACTOR_SYSTEM,
        TaskType.TEST: _TEST_SYSTEM,
        TaskType.DOCS: _DOCS_SYSTEM,
        TaskType.INFRA: _INFRA_SYSTEM,
    }
    return GeneratedPrompt(
        system_prompt=system_map.get(ctx.task_type, _FEATURE_SYSTEM),
        user_prompt=_build_user_prompt(ctx),
        task_type=ctx.task_type,
        success_criteria=_build_success_criteria(ctx),
        files_to_check=ctx.file_hints,
    )


def _build_user_prompt(ctx: TaskContext) -> str:
    parts = [f"# Task: {ctx.title}"]
    if ctx.issue_number:
        parts.append(f"## Issue: #{ctx.issue_number}")
    parts.append(f"## Description\n{ctx.description}")
    if ctx.task_type == TaskType.SECURITY_FIX:
        if ctx.related_cwe:
            parts.append(f"**CWE:** {ctx.related_cwe}")
        if ctx.severity:
            parts.append(f"**Severity:** {ctx.severity}")
    if ctx.file_hints:
        parts.append("## Relevant Files" + "".join(f"\n- {f}" for f in ctx.file_hints))
    if ctx.dependencies:
        parts.append("## Dependencies" + "".join(f"\n- {d}" for d in ctx.dependencies))
    parts.append("## Instructions\n1. Analyze the codebase\n2. Plan your approach\n3. Implement the change\n4. Write tests\n5. Verify tests pass\n6. Commit and push")
    return "\n\n".join(parts)


def _build_success_criteria(ctx: TaskContext) -> list[str]:
    base = ["Code compiles", "All tests pass", "New tests added", "No security regressions"]
    extra = {
        TaskType.SECURITY_FIX: ["Vulnerability fixed", "CWE countermeasures in place", "Security tests added"],
        TaskType.FEATURE: ["Feature works as described", "Edge cases handled"],
        TaskType.BUGFIX: ["Bug fixed", "Regression test added", "No side effects"],
        TaskType.REFACTOR: ["All tests pass", "Code complexity reduced", "No behavior changes"],
        TaskType.TEST: ["All new tests pass", "Edge cases covered"],
    }
    return base + extra.get(ctx.task_type, [])


def detect_task_type(title: str, body: str, labels: list[str]) -> TaskType:
    text = f"{title} {body}".lower()
    labels_lower = [l.lower() for l in labels]
    if any("security" in l or "vulnerability" in l for l in labels_lower):
        return TaskType.SECURITY_FIX
    if any("bug" in l for l in labels_lower):
        return TaskType.BUGFIX
    if any("test" in l for l in labels_lower):
        return TaskType.TEST
    if any("docs" in l for l in labels_lower):
        return TaskType.DOCS
    if any("refactor" in l for l in labels_lower):
        return TaskType.REFACTOR
    if any("infra" in l or "devops" in l or "ci" in l for l in labels_lower):
        return TaskType.INFRA
    if any(kw in text for kw in ["cve", "cwe", "xss", "injection", "vulnerability", "security", "exploit"]):
        return TaskType.SECURITY_FIX
    if any(kw in text for kw in ["fix", "bug", "crash", "error", "broken", "regression"]):
        return TaskType.BUGFIX
    if any(kw in text for kw in ["test", "coverage", "spec"]):
        return TaskType.TEST
    if any(kw in text for kw in ["refactor", "restructure", "clean up"]):
        return TaskType.REFACTOR
    if any(kw in text for kw in ["document", "docs", "readme", "guide"]):
        return TaskType.DOCS
    if any(kw in text for kw in ["docker", "ci", "cd", "deploy", "pipeline"]):
        return TaskType.INFRA
    return TaskType.FEATURE


def make_security_fix_prompt(title, description, cwe="", severity="", files=None, issue_number=0):
    return generate_prompt(TaskContext(
        task_type=TaskType.SECURITY_FIX, title=title, description=description,
        issue_number=issue_number, related_cwe=cwe, severity=severity, file_hints=files or [],
    ))


def make_bugfix_prompt(title, description, files=None, issue_number=0):
    return generate_prompt(TaskContext(
        task_type=TaskType.BUGFIX, title=title, description=description,
        issue_number=issue_number, file_hints=files or [],
    ))


def make_feature_prompt(title, description, files=None, issue_number=0):
    return generate_prompt(TaskContext(
        task_type=TaskType.FEATURE, title=title, description=description,
        issue_number=issue_number, file_hints=files or [],
    ))
