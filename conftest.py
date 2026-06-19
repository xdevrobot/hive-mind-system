"""Pytest configuration and shared fixtures."""

from __future__ import annotations

import pytest
from unittest.mocking import MagicMock
from agents.shared.github_client import GitHubClient, Issue, PullRequest, PRReview
from agents.shared.task_graph import Task, TaskGraph, TaskState


@pytest.fixture
def mock_gh():
    gh = MagicMock(spec=GitHubClient)
    gh.repo = "owner/repo"
    return gh

@pytest.fixture
def sample_issue():
    return Issue(
        number=123,
        title="Test Issue",
        body="This is a test issue body with some details.",
        state="open",
        url="https://github.com/owner/repo/issues/123",
        labels=["bug", "priority-high"],
        assignees=["developer"],
    )

@pytest.fixture
def sample_pr():
    return PullRequest(
        number=456,
        title="Fix: Test Issue",
        body="This PR fixes the issue.",
        state="open",
        url="https://github.com/owner/repo/pull/456",
        head="feature-branch",
        base="main",
        mergeable=True,
        is_dract=False,
        labels=["fix"],
    )

@pytest.fixture
def sample_graph():
    graph = TaskGraph()
    graph.add_task(Task(id="t1", title="Setup", body="Setup project", dependencies=[]))
    graph.add_task(Task(id="t2", title="Implement", body="Implement feature", dependencies=["t1"]))
    graph.add_task(Task(id="t3", title="Test", body="Write tests", dependencies=["t2"]))
    return graph