"""Tests for TaskGraph module."""

import pytest
from agents.shared.task_graph import TaskGraph, TaskState, TaskNode


class TestTaskNode:
    def test_create_task(self):
        node = TaskNode(id="T1", title="Test task")
        assert node.id == "T1"
        assert node.title == "Test task"
        assert node.state == TaskState.PENDING

    def test_to_dict(self):
        node = TaskNode(id="T1", title="Test")
        d = node.to_dict()
        assert d["id"] == "T1"
        assert d["state"] == "pending"


class TestTaskGraph:
    def test_add_task(self):
        g = TaskGraph()
        g.add_task("T1", "Test")
        assert "T1" in g.tasks

    def test_add_dependency(self):
        g = TaskGraph()
        g.add_task("T1", "First")
        g.add_task("T2", "Second")
        g.add_dependency("T2", "T1")
        assert "T1" in g.tasks["T2"].dependencies

    def test_get_ready_tasks(self):
        g = TaskGraph()
        g.add_task("T1", "First")
        g.add_task("T2", "Second")
        g.add_dependency("T2", "T1")
        ready = g.get_ready_tasks()
        assert len(ready) == 1
        assert ready[0].id == "T1"

    def test_update_state(self):
        g = TaskGraph()
        g.add_task("T1", "Test")
        g.update_state("T1", TaskState.COMPLETED)
        assert g.tasks["T1"].state == TaskState.COMPLETED

    def test_is_complete(self):
        g = TaskGraph()
        g.add_task("T1", "Test")
        assert not g.is_complete()
        g.update_state("T1", TaskState.COMPLETED)
        assert g.is_complete()
