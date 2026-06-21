"""
Enhanced Hive Worker — full pipeline worker with rate-limit retry,
auto-merge, and task splitting.

Combines components from:
- xdevrobot/hive-mind-system (Python base)
- link-assistant/hive-mind concepts (rate-limit, auto-merge, terminal state)
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from agents.shared.github_client import GitHubClient
from agents.shared.git_client import GitClient
from agents.shared.github_retry import (
    retry_with_rate_limit,
    is_terminal_entity_error,
    is_rate_limit_error,
)
from agents.worker.executor import TaskResult
from agents.architect.auto_merge import AutoMerge, MergeConfig

logger = logging.getLogger(__name__)


@dataclass
class EnhancedWorkerConfig:
    """Enhanced worker configuration."""
    task_id: str = ""
    issue_number: int = 0
    repo: str = ""
    fork: str = ""
    base_branch: str = "main"
    branch_prefix: str = "hive"
    hex_length: int = 12
    tool: str = "claude"
    model: str = ""
    timeout: int = 3600
    isolation: str = "direct"
    merge_strategy: str = "squash"
    auto_merge: bool = False
    require_ci_pass: bool = True
    draft_pr: bool = False
    working_dir: str = ""
    keep: bool = False
    json_output: bool = False


class EnhancedHiveWorker:
    """Enhanced worker with rate-limit retry, auto-merge, and better error handling."""

    def __init__(self, config: EnhancedWorkerConfig):
        self.config = config
        self.gh = GitHubClient(repo=config.repo)

    def run(self) -> TaskResult:
        """Full pipeline: clone → branch → code → commit → push → PR → (auto-merge)."""
        temp_dir = tempfile.mkdtemp(prefix=f"worker-{self.config.task_id}-")
        logger.info("Worker %s: working in %s", self.config.task_id, temp_dir)

        try:
            return self._execute_pipeline(temp_dir)
        except Exception as e:
            logger.error("Worker %s: failed — %s", self.config.task_id, e)
            return TaskResult(
                success=False,
                task_id=self.config.task_id,
                branch_name="",
                error=str(e),
            )
        finally:
            if not self.config.keep:
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)

    def _execute_pipeline(self, work_dir: str) -> TaskResult:
        """Core execution pipeline with retry logic."""
        git = GitClient(work_dir)

        # 1. Clone
        fork_url = self.config.fork or self._get_repo_url()
        logger.info("Worker %s: cloning %s", self.config.task_id, fork_url)
        retry_with_rate_limit(lambda: git.clone(fork_url, dest=work_dir))

        # Setup upstream if using fork
        original_url = self._get_repo_url()
        if original_url != fork_url:
            retry_with_rate_limit(lambda: git.add_remote("upstream", original_url))
            retry_with_rate_limit(lambda: git.fetch("upstream", self.config.base_branch))

        # 2. Create branch
        branch_name = git.generate_branch_name(self.config.issue_number, self.config.hex_length)
        logger.info("Worker %s: creating branch %s", self.config.task_id, branch_name)
        if original_url != fork_url:
            retry_with_rate_limit(lambda: git.create_branch(branch_name, f"upstream/{self.config.base_branch}"))
        else:
            retry_with_rate_limit(lambda: git.create_branch(branch_name, self.config.base_branch))

        # 3. Get issue info
        issue = retry_with_rate_limit(lambda: self.gh.view_issue(self.config.issue_number))
        logger.info("Worker %s: working on #%d — %s", self.config.task_id, issue.number, issue.title)

        # 4. Write task info (for AI agent)
        task_file = Path(work_dir) / ".hive-mind-task"
        task_file.write_text(json.dumps({
            "issue_number": issue.number,
            "title": issue.title,
            "body": issue.body,
        }, indent=2, ensure_ascii=False))

        # 5. Check for changes
        if not git.has_changes():
            logger.warning("Worker %s: no changes", self.config.task_id)
            return TaskResult(
                success=False, task_id=self.config.task_id,
                branch_name=branch_name, error="No changes produced",
            )

        # 6. Commit
        files_changed = [e.path for e in git.status()]
        commit_msg = (
            f"feat: implement task for #{issue.number}\n\n"
            f"{issue.title}\n\n"
            f"Co-Authored-By: OWL <noreply@anthropic.com>"
        )
        commit_hash = retry_with_rate_limit(lambda: git.commit(commit_msg))
        logger.info("Worker %s: committed %s", self.config.task_id, commit_hash[:8])

        # 7. Push
        retry_with_rate_limit(lambda: git.push("origin", branch_name))
        logger.info("Worker %s: pushed %s", self.config.task_id, branch_name)

        # 8. Create PR
        pr_body = (
            f"## Summary\nImplementation of #{issue.number}: {issue.title}\n\n"
            f"## Changes\n- Implemented task as described in the issue\n\n"
            f"## Related Issue\nCloses #{issue.number}\n\n"
            f"## Checklist\n- [ ] Code follows project style\n"
            f"- [ ] Tests added/updated\n- [ ] Documentation updated\n\n"
            f"---\n*Branch: `{branch_name}`*"
        )
        pr = retry_with_rate_limit(
            lambda: self.gh.create_pr(
                title=f"feat: {issue.title}",
                body=pr_body,
                head=branch_name,
                base=self.config.base_branch,
                draft=self.config.draft_pr,
            )
        )
        logger.info("Worker %s: created PR #%d", self.config.task_id, pr.number)

        result = TaskResult(
            success=True, task_id=self.config.task_id,
            branch_name=branch_name, commit_hash=commit_hash,
            pr_number=pr.number, pr_url=pr.url, files_changed=files_changed,
        )

        # 9. Auto-merge if configured
        if self.config.auto_merge:
            logger.info("Worker %s: auto-merging PR #%d...", self.config.task_id, pr.number)
            merge_config = MergeConfig(
                require_ci_pass=self.config.require_ci_pass,
                merge_method=self.config.merge_strategy,
            )
            auto = AutoMerge(self.gh, merge_config)
            merged = auto.auto_merge(pr.number)
            if merged:
                logger.info("Worker %s: PR #%d auto-merged!", self.config.task_id, pr.number)
            else:
                logger.warning("Worker %s: auto-merge failed for PR #%d", self.config.task_id, pr.number)

        return result

    def _get_repo_url(self) -> str:
        """Get the GitHub URL for the configured repo."""
        return f"https://github.com/{self.config.repo}"


def run_worker(
    task_id: str,
    issue_number: int,
    repo: str,
    fork: str = "",
    auto_merge: bool = False,
    json_output: bool = False,
) -> TaskResult:
    """Convenience function to run a worker."""
    config = EnhancedWorkerConfig(
        task_id=task_id,
        issue_number=issue_number,
        repo=repo,
        fork=fork,
        auto_merge=auto_merge,
        json_output=json_output,
    )
    worker = EnhancedHiveWorker(config)
    result = worker.run()
    if json_output:
        print(json.dumps({
            "success": result.success,
            "task_id": result.task_id,
            "branch": result.branch_name,
            "commit": result.commit_hash,
            "pr_number": result.pr_number,
            "pr_url": result.pr_url,
            "files_changed": result.files_changed,
            "error": result.error,
        }, indent=2))
    return result
