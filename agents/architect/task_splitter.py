"""
Task Split module — decompose a GitHub issue into smaller sub-issues.

Adapted from link-assistant/hive-mind:
- task.split.lib.mjs
- task.issue-creation.lib.mjs

Supports three decomposition strategies:
1. Checklist-based: split by - [ ] items
2. Section-based: split by ## headers
3. Logical phases: Setup → Implementation → Testing
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from agents.shared.github_client import GitHubClient

logger = logging.getLogger(__name__)

TASK_SPLIT_MARKER_START = "<!-- hive-mind-task-split:start -->"
TASK_SPLIT_MARKER_END = "<!-- hive-mind-task-split:end -->"


@dataclass
class SubTask:
    """A decomposed sub-task ready to become a GitHub issue."""
    title: str
    body: str
    dependencies: list[int] = field(default_factory=list)
    issue_number: Optional[int] = None
    issue_url: Optional[str] = None


@dataclass
class SplitResult:
    """Result of decomposing an issue."""
    parent_issue_number: int
    parent_title: str
    subtasks: list[SubTask]

    @property
    def task_count(self) -> int:
        return len(self.subtasks)

    def to_dict(self) -> dict:
        return {
            "parent_issue_number": self.parent_issue_number,
            "parent_title": self.parent_title,
            "task_count": self.task_count,
            "tasks": [
                {
                    "title": t.title,
                    "body": t.body,
                    "dependencies": t.dependencies,
                    "issue_number": t.issue_number,
                    "issue_url": t.issue_url,
                }
                for t in self.subtasks
            ],
        }


class TaskSplitter:
    """Decompose GitHub issues into smaller, independently actionable sub-issues."""

    def __init__(self, gh_client: GitHubClient):
        self.gh = gh_client

    def split(self, issue_number: int, subtask_count: int = 3,
              custom_tasks: Optional[list[dict]] = None) -> SplitResult:
        """Decompose an issue into sub-tasks.

        Strategy priority:
        1. Custom tasks (if provided)
        2. Checklist items from issue body
        3. Section headers from issue body
        4. Logical phases (fallback)
        """
        issue = self.gh.view_issue(issue_number)
        logger.info("Splitting issue %d: %s", issue.number, issue.title)

        if custom_tasks:
            subtasks = self._from_custom(custom_tasks, issue)
        else:
            subtasks = self._auto_split(issue, subtask_count)

        return SplitResult(
            parent_issue_number=issue.number,
            parent_title=issue.title,
            subtasks=subtasks,
        )

    def split_and_create(self, issue_number: int, subtask_count: int = 3,
                         labels: Optional[list[str]] = None,
                         link_to_parent: bool = True) -> SplitResult:
        """Split an issue and create sub-issues on GitHub."""
        result = self.split(issue_number, subtask_count)

        for task in result.subtasks:
            body = task.body
            if link_to_parent:
                body += f"\n\n---\nPart of #{result.parent_issue_number}: {result.parent_title}"

            logger.info("Creating sub-issue: %s", task.title)
            issue = self.gh.create_issue(
                title=task.title,
                body=body,
                labels=labels or [],
            )
            task.issue_number = issue.number
            task.issue_url = issue.url
            logger.info("Created sub-issue %d: %s", issue.number, issue.url)

        return result

    def _auto_split(self, issue, count: int) -> list[SubTask]:
        """Auto-decompose using checklist → sections → phases."""
        body = issue.body or ""

        # 1. Checklist items
        checklist = self._extract_checklist(body)
        if checklist and len(checklist) >= 2:
            return [
                SubTask(
                    title=item[:256],
                    body=f"{item}\n\nPart of #{issue.number}: {issue.title}",
                    dependencies=[],
                )
                for item in checklist
            ]

        # 2. Section headers
        sections = self._extract_sections(body)
        if sections and len(sections) >= 2:
            tasks = []
            for i, (title, section_body) in enumerate(sections):
                deps = [i] if i > 0 else []  # 1-based dependency indices
                tasks.append(SubTask(
                    title=title[:256],
                    body=f"{section_body}\n\nPart of #{issue.number}: {issue.title}",
                    dependencies=deps,
                ))
            return tasks

        # 3. Logical phases fallback
        return self._split_by_phases(issue, count)

    def _split_by_phases(self, issue, count: int) -> list[SubTask]:
        """Split by logical development phases."""
        phases = [
            ("Setup & Research",
             "Setup the project structure, research dependencies, and define the approach."),
            ("Implementation",
             f"Implement the core functionality.\n\n{issue.body or ''}"),
            ("Testing & Documentation",
             "Write tests, update documentation, and verify everything works."),
        ]

        tasks = []
        for i in range(min(count, len(phases))):
            title, phase_body = phases[i]
            deps = [i] if i > 0 else []  # 1-based
            tasks.append(SubTask(
                title=f"{issue.title} — {title}"[:256],
                body=f"{phase_body}\n\nPart of #{issue.number}",
                dependencies=deps,
            ))
        return tasks

    def _from_custom(self, custom_tasks: list[dict], issue) -> list[SubTask]:
        """Create sub-tasks from a custom specification."""
        tasks = []
        for i, data in enumerate(custom_tasks):
            deps = data.get("dependencies", [])
            if deps and isinstance(deps[0], int):
                deps = [d for d in deps if d > 0]
            tasks.append(SubTask(
                title=data["title"][:256],
                body=data.get("body", data["title"]),
                dependencies=deps,
            ))
        return tasks

    @staticmethod
    def _extract_checklist(body: str) -> list[str]:
        """Extract checklist items from markdown body."""
        items = []
        for line in body.split("\n"):
            match = re.match(r"^\s*[-*]\s*\[[ x]]\s*(.+)", line)
            if match:
                items.append(match.group(1).strip())
        return items

    @staticmethod
    def _extract_sections(body: str) -> list[tuple[str, str]]:
        """Extract ## sections from markdown body."""
        sections = []
        current_title = ""
        current_lines: list[str] = []
        for line in body.split("\n"):
            if line.startswith("## "):
                if current_title:
                    sections.append((current_title, "\n".join(current_lines).strip()))
                current_title = line[3:].strip()
                current_lines = []
            else:
                current_lines.append(line)
        if current_title:
            sections.append((current_title, "\n".join(current_lines).strip()))
        return sections

    @staticmethod
    def build_split_prompt(issue_data: dict, split_count: int) -> str:
        """Build an AI prompt for intelligent task splitting."""
        body = issue_data.get("body", "") or "(empty)"
        return (
            f"Split this GitHub issue into exactly {split_count} smaller GitHub issues.\n\n"
            f"Source issue:\n"
            f"- Title: {issue_data.get('title', '')}\n"
            f"- Body:\n{body}\n\n"
            f"Return only this JSON shape:\n"
            f"{{\n"
            f'  "tasks": [\n'
            f"    {{\n"
            f'      "title": "short issue title",\n'
            f'      "body": "complete issue body with objective, scope, deliverables",\n'
            f'      "dependencies": [1]\n'
            f"    }}\n"
            f"  ]\n"
            f"}}\n\n"
            f"Rules:\n"
            f"- The tasks array must contain exactly {split_count} items.\n"
            f"- Each task must be independently actionable.\n"
            f"- Together the tasks must cover the full source issue.\n"
            f"- Dependencies must be 1-based task numbers (empty if none).\n"
            f"- Do not include Markdown fences, prose, or extra keys."
        )
