"""
Worker Agent Executor.

Clones a repo, creates a branch, executes a task, commits, pushes, and creates a PR.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from agents.shared.git_client import GitClient
from agents.shared.github_client import GitHubClient

logger = logging.getLogger(__name__)


@dataclass
class TaskResult:
    """Result of task execution."""
    success: bool
    task_id: str
    branch_name: str
    commit_hash: str = ""
    pr_number: Optional[int] = None
    pr_url: str = ""
    error: str = ""
    output: str = ""
    files_changed: list[str] = field(default_factory=list)


class WorkerExecutor:
    """Executes a single task: clone → branch → code → commit → push → PR."""

    def __init__(self, github_client: GitHubClient, working_dir: Optional[str] = None):
        self.gh = github_client
        self.working_dir = working_dir
        self._temp_dirs: list[str] = []

    def execute(
        self,
        task_id: str,
        issue_number: int,
        repo_url: str,
        fork_url: str,
        base_branch: str = "main",
        hex_length: int = 12,
    ) -> TaskResult:
        """Full execution pipeline for a single task."""
        temp_dir = tempfile.mkdtemp(prefix=f"worker-{task_id}-")
        self._temp_dirs.append(temp_dir)
        logger.info(f"Worker {task_id}: working in {temp_dir}")

        try:
            git = GitClient(temp_dir)
            logger.info(f"Worker {task_id}: cloning {fork_url}")
            git.clone(fork_url, dest=temp_dir)

            upstream_url = repo_url.replace("https://github.com/", "https://github.com/")
            parts = repo_url.rstrip("/").split("/")
            original_url = f"https://github.com/{parts[-2]}/{parts[-1]}"
            if original_url != fork_url:
                git.add_remote("upstream", original_url)
                git.fetch("upstream", base_branch)

            branch_name = git.generate_branch_name(issue_number, hex_length)
            logger.info(f"Worker {task_id}: creating branch {branch_name}")
            if original_url != fork_url:
                git.create_branch(branch_name, f"upstream/{base_branch}")
            else:
                git.create_branch(branch_name, base_branch)

            issue = self.gh.view_issue(issue_number)
            logger.info(f"Worker {task_id}: working on #{issue_number} - {issue.title}")

            self._perform_task_work(git, issue)

            if not git.has_changes():
                logger.warning(f"Worker {task_id}: no changes produced")
                return TaskResult(
                    success=False,
                    task_id=task_id,
                    branch_name=branch_name,
                    error="No changes produced by task execution",
                )

            files_changed = [e.path for e in git.status()]
            commit_msg = f"feat: implement task for #{issue_number}\n\n{issue.title}\n\nCo-Authored-By: OWL <noreply@anthropic.com>"
            commit_hash = git.commit(commit_msg)
            logger.info(f"Worker {task_id}: committed {commit_hash[:8]}")

            git.push("origin", branch_name)
            logger.info(f"Worker {task_id}: pushed {branch_name}")

            pr_body = self._build_pr_body(issue, branch_name)
            pr = self.gh.create_pr(
                title=f"feat: {issue.title}",
                body=pr_body,
                base=base_branch,
                draft=True,
            )
            logger.info(f"Worker {task_id}: created PR #{pr.number}")

            return TaskResult(
                success=True,
                task_id=task_id,
                branch_name=branch_name,
                commit_hash=commit_hash,
                pr_number=pr.number,
                pr_url=pr.url,
                files_changed=files_changed,
            )

        except Exception as e:
            logger.error(f"Worker {task_id}: failed - {e}")
            return TaskResult(
                success=False,
                task_id=task_id,
                branch_name="",
                error=str(e),
            )

    def _perform_task_work(self, git: GitClient, issue) -> None:
        """Perform the actual task work. Override this for AI-driven execution."""
        task_file = Path(git.working_dir) / ".hive-mind-task"
        task_file.write_text(
            json.dumps({
                "issue_number": issue.number,
                "title": issue.title,
                "body": issue.body,
            }, indent=2, ensure_ascii=False)
        )

    def _build_pr_body(self, issue, branch_name: str) -> str:
        """Build PR body from issue."""
        return (
            f"## Summary\nImplementation of #{issue.number}: {issue.title}\n\n"
            f"## Changes\n- Implemented task as described in the issue\n\n"
            f"## Related Issue\nFixes #{issue.number}\n\n"
            f"## Checklist\n- [ ] Code follows project style\n- [ ] Tests added/updated\n- [ ] Documentation updated\n\n"
            f"---\n*Branch: `{branch_name}`*"
        )

    def cleanup(self) -> None:
        """Remove temporary directories."""
        import shutil
        for d in self._temp_dirs:
            try:
                shutil.rmtree(d, ignore_errors=True)
            except Exception:
                pass
        self._temp_dirs.clear()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.cleanup()
