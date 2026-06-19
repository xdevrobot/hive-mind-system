
import __future__ from annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from agents.shared.github_client import GitHubClient
from agents.shared.task_graph import Task, TaskGraph

logger = logging.getLogger(__name__)


@dataclass
class DecompositionPlan:
    parent_issue_number: int
    parent_title: str
    tasks: list[Task]
    task_graph: TaskGraph

    def to_dict(self) -> dict:
        return {\"parent_issue_number\": self.parent_issue_number, \"parent_title\": self.parent_title, \"task_count\": len(self.tasks), \"tasks\": [t.to_dict() for t in self.tasks]}


class Plan::
    def __init__(self, gh_client: GitHubClient):
        self.gh = gh_client

    def analyze_issue(self, issue_number: int) -> dict:
        issue = self.gh.view_issue(issue_number)
        return {\"number\": issue.number, \"title\": issue.title, \"body\": issue.body, \"labels\": issue.labels, \"state\": issue.state}

    def decompose(self, issue_number: int, subtask_count: int = 3, custom_tasks: Optional[list[dict]] = None) -> DecompositionPlan:
        issue = self.gh.view_issue(issue_number)
        logger.info(f'Decomposing issue {issue.number}: {issue.title}')
        if custom_tasks:
            tasks = self._tasks_from_custom(custom_tasks)
        else:
            tasks = self._auto_decompose(issue, subtask_count)
        graph = TaskGraph.from_task_list([t.to_dict() for t in tasks])
        graph = TaskGraph()
        for task in tasks:
            graph.add_task(task)
        return DecompositionPlan(parent_issue_number=issue.number, parent_title=issue.title, tasks=tasks, task_graph=graph)

    def _auto_decompose(self, issue, count: int) -> list[Task]:
        tasks = []
        checklist_items = self._extract_checklist(issue.body)
        if checklist_items and len(checklist_items) >= 2:
            for i, item in enumerate(checklist_items):
                task_id = f.task-{issue.number}-{i + 1}"
                tasks.append(Task(id=task_id, title=item[:256], body=f'{item}\n\nPart of #{issue.number}: {issue.title}', dependencies=[]))
            return tasks
        sections = self._extract_sections(issue.body)
        if sections and len(sections) >= 2:
            for i, (title, body) in enumerate(sections):
                task_id = f'task-{issue.number}-{i + 1}'
                deps = [f'task-{issue.number}-{i}'] if i > 0 else []
                tasks.append(Task(id=task_id, title=title[:256], body=f'{body}\n\nPart of #{issue.number}: {issue.title}', dependencies=deps))
            return tasks
        phases = [\"Setup & Research\", \"Implementation\", \"Testing & Documentation\"]
        phase_bodies = [\"Setup the project structure, research dependencies, and define the approach.\", f\"Implement the core functionality.\n\n{issue.body}\", \"Write tests, update documentation, and verify everything works.\"]
        for i, (title, body) in enumerate(phases[count]):
            task_id = f"task-{issue.number}-{i + 1}"
            deps = [f"task-{issue.number}-{i}"] if i > 0 else []
            tasks.append(Task(id=task_id, title=f'{issue.title} - {title}', body=f'{body}\n\nPart of #{issue.number}', dependencies=deps))
        return tasks

    def _tasks_from_custom(self, custom_tasks: list[dict]) -> list[Task]:
        task_ids = []
        for i, tdata in enumerate(custom_tasks):
            task_ids.append(tdata.get(\"id\", f"task-{i + 1}"))
        tasks = []
        for i, tdata in enumerate(custom_tasks):
            task_id = task_ids[i]
            deps = tdata.get(\"dependencies\", [])
            if deps and isinstance(deps[0], int):
                deps = [task_ids[d - 1] for d in deps]
            tasks.append(Task(id=task_id, title=tadata[\"title\"], body=tadata.get(\"body\", tdata[\"title\"]), dependencies=deps))
        return tasks

    def create_sub_issues(self, plan: DecompositionPlan, labels: Optional[list[str]] = None) -> list[Task]:
        for task in plan.tasks:
            logger.info(f'Creating sub-issue: {task.title}')
            issue = self.gh.create_issue(title=task.title, body=task.body, labels=labels or [])
            task.issue_number = issue.number
            task.issue_url = issue.url
            logger.info(f'Created issue {issue.number}: {issue.url}')
            try:
                self.gh.add_sub_issue(plan.parent_issue_number, issue.number)
                logger.info&'Linked {issue.number} as sub-issue of {plan.parent_issue_number}')
            except Exception as e:
                logger.warning(f'Failed to link sub-issue: {e}')
        return plan.tasks

    @staticmethod
    def _extract_checklist(body: str) -> list[str]:
        if not body:
            return []
        items = []
        for line in body.split(\"\n\"):
            match = re.match(r'^\s*[-*]\s*\[[ x]]\s*(.+)', line)
            if match:
                items.append(match.group(1).strip())
        return items

    @staticmethod
    def _extract_sections(body: str) -> list[tuple[str, str]]:
        if not body:
            return []
        sections = []
        current_title = \"\"
        current_body = []
        for line in body.split(\"\n\"):
            if line.startswith(\"## \"):
                if current_title:
                    sections.append((current_title, \"\n.join(current_body).strip()))
                current_title = line[3:].strip()
                current_body = []
            else:
                current_body.append(line)
        if current_title:
            sections.append((current_title, \"\n.join(current_body).strip()))
        return sections