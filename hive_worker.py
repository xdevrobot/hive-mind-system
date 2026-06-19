#!/usr/bin/env python3
"""
Hive Worker — Next-generation worker agent with agent-commander integration.

Executes a single task: clone → branch → code (via agent-commander) → commit → push → PR → CI → merge.

Supports multiple isolation modes:
- direct: run agent directly in the working directory
- screen: run agent in a detached screen session
- docker: run agent in an isolated Docker container

Usage:
    python hive_worker.py --task-id T1 --issue 58 --repo labtgbot/teleton-agent --fork user/fork
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from agent_commander_bridge import (
    AgentCommanderBridge,
    AgentConfig,
    AgentResult,
    DockerConfig,
    IsolationMode,
)
from agents.shared.git_client import GitClient
from agents.shared.github_client import GitHubClient
from issue_templates import (
    GeneratedPrompt,
    TaskContext,
    TaskType,
    detect_task_type,
    generate_prompt,
)

logger = logging.getLogger("hive_worker")


@dataclass
class WorkerConfig:
    """Configuration for a worker run."""
    task_id: str = ""
    issue_number: int = 0
    repo: str = ""
    fork: str = ""
    base_branch: str = "main"
    branch_prefix: str = "hive"
    hex_length: int = 12

    # Agent settings
    tool: str = "claude"
    model: str = ""
    permission_mode: str = "plan"
    timeout: int = 3600
    isolation: str = "direct"  # direct | screen | docker

    # Docker settings
    docker_image: str = "ubuntu:22.04"
    docker_memory: str = "4g"
    docker_cpu: str = "2"

    # PR settings
    auto_merge: bool = False
    merge_strategy: str = "squash"
    require_ci_pass: bool = True
    draft_pr: bool = False

    # Working directory
    working_dir: str = ""  # empty = use temp dir
    keep_working_dir: bool = False


@dataclass
class WorkerResult:
    """Result of a worker run."""
    success: bool
    task_id: str
    branch_name: str = ""
    commit_hash: str = ""
    pr_number: Optional[int] = None
    pr_url: str = ""
    pr_merged: bool = False
    ci_passed: bool = False
    error: str = ""
    output: str = ""
    files_changed: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "task_id": self.task_id,
            "branch_name": self.branch_name,
            "commit_hash": self.commit_hash,
            "pr_number": self.pr_number,
            "pr_url": self.pr_url,
            "pr_merged": self.pr_merged,
            "ci_passed": self.ci_passed,
            "error": self.error,
            "files_changed": self.files_changed,
            "duration_seconds": round(self.duration_seconds, 1),
        }


class HiveWorker:
    """Worker that executes a single task using agent-commander."""

    def __init__(self, config: WorkerConfig):
        self.config = config
        self.gh = GitHubClient(repo=config.repo)
        self.bridge = AgentCommanderBridge()
        self._temp_dirs: list[str] = []

    def execute(self) -> WorkerResult:
        """Full execution pipeline for a single task."""
        start_time = time.time()
        task_id = self.config.task_id

        logger.info(f"Worker {task_id}: starting execution for issue #{self.config.issue_number}")

        # Step 0: Fetch issue details
        try:
            issue = self.gh.view_issue(self.config.issue_number)
            logger.info(f"Worker {task_id}: issue title: {issue.title}")
        except Exception as e:
            return self._error_result(task_id, start_time, f"Failed to fetch issue: {e}")

        # Step 1: Setup working directory
        work_dir = self._setup_work_dir(task_id)
        if not work_dir:
            return self._error_result(task_id, start_time, "Failed to setup working directory")

        try:
            # Step 2: Clone and setup repo
            branch_name = self._setup_repo(task_id, work_dir)
            if not branch_name:
                return self._error_result(task_id, start_time, "Failed to setup repository")

            # Step 3: Generate prompt
            prompt = self._generate_prompt(issue, work_dir)
            logger.info(f"Worker {task_id}: generated prompt ({len(prompt.user_prompt)} chars)")

            # Step 4: Run agent
            agent_result = self._run_agent(task_id, work_dir, prompt)
            if not agent_result.success:
                logger.warning(f"Worker {task_id}: agent returned non-zero exit code")
                # Continue anyway — agent may have done partial work

            # Step 5: Commit and push
            commit_hash = self._commit_and_push(task_id, work_dir, branch_name)
            if not commit_hash:
                return self._error_result(task_id, start_time, "Failed to commit and push changes")

            # Step 6: Create PR
            pr_number, pr_url = self._create_pr(
                task_id, branch_name, issue, prompt
            )
            if not pr_number:
                return self._error_result(task_id, start_time, "Failed to create PR")

            # Step 7: Wait for CI
            ci_passed = True
            if self.config.require_ci_pass:
                ci_passed = self._wait_for_ci(task_id, pr_number)
                if not ci_passed:
                    return WorkerResult(
                        success=False,
                        task_id=task_id,
                        branch_name=branch_name,
                        commit_hash=commit_hash,
                        pr_number=pr_number,
                        pr_url=pr_url,
                        ci_passed=False,
                        error="CI checks failed",
                        output=agent_result.output,
                        duration_seconds=time.time() - start_time,
                    )

            # Step 8: Auto-merge
            pr_merged = False
            if self.config.auto_merge and ci_passed:
                pr_merged = self._merge_pr(task_id, pr_number)

            # Step 9: Get changed files
            files_changed = self._get_changed_files(work_dir, branch_name)

            duration = time.time() - start_time
            logger.info(f"Worker {task_id}: completed in {duration:.1f}s (PR #{pr_number})")

            return WorkerResult(
                success=True,
                task_id=task_id,
                branch_name=branch_name,
                commit_hash=commit_hash,
                pr_number=pr_number,
                pr_url=pr_url,
                pr_merged=pr_merged,
                ci_passed=ci_passed,
                output=agent_result.output,
                files_changed=files_changed,
                duration_seconds=duration,
            )

        finally:
            self._cleanup(work_dir)

    def _setup_work_dir(self, task_id: str) -> Optional[str]:
        """Setup working directory for the task."""
        if self.config.working_dir:
            work_dir = self.config.working_dir
            os.makedirs(work_dir, exist_ok=True)
            return work_dir

        work_dir = tempfile.mkdtemp(prefix=f"hive-{task_id}-")
        self._temp_dirs.append(work_dir)
        logger.info(f"Worker {task_id}: working in {work_dir}")
        return work_dir

    def _setup_repo(self, task_id: str, work_dir: str) -> Optional[str]:
        """Clone repo and create feature branch."""
        try:
            git = GitClient(work_dir)

            # Determine clone URL
            if self.config.fork:
                clone_url = f"https://github.com/{self.config.fork}.git"
                upstream_url = f"https://github.com/{self.config.repo}.git"
            else:
                clone_url = f"https://github.com/{self.config.repo}.git"
                upstream_url = ""

            logger.info(f"Worker {task_id}: cloning {clone_url}")
            git.clone(clone_url, dest=work_dir)

            # Add upstream remote if forking
            if upstream_url and upstream_url != clone_url:
                git.add_remote("upstream", upstream_url)
                git.fetch("upstream", self.config.base_branch)

            # Create branch
            branch_name = git.generate_branch_name(
                self.config.issue_number,
                self.config.hex_length,
                prefix=self.config.branch_prefix,
            )
            logger.info(f"Worker {task_id}: creating branch {branch_name}")

            base = f"upstream/{self.config.base_branch}" if upstream_url else self.config.base_branch
            git.create_branch(branch_name, base)

            return branch_name

        except Exception as e:
            logger.error(f"Worker {task_id}: repo setup failed: {e}")
            return None

    def _generate_prompt(self, issue, work_dir: str) -> GeneratedPrompt:
        """Generate a prompt for the task."""
        # Detect task type
        task_type = detect_task_type(issue.title, issue.body, issue.labels)

        # Build context
        ctx = TaskContext(
            task_type=task_type,
            title=issue.title,
            description=issue.body or "",
            issue_number=issue.number,
            issue_url=issue.url,
            repo_name=self.config.repo,
            file_hints=self._extract_file_hints(issue.body or ""),
            severity=self._extract_severity(issue.labels),
            related_cwe=self._extract_cwe(issue.body or ""),
        )

        prompt = generate_prompt(ctx)

        # Add repo-specific context
        prompt.user_prompt += f"\n\n## Repository: {self.config.repo}"
        prompt.user_prompt += f"\n## Working Directory: {work_dir}"
        prompt.user_prompt += f"\n## Branch: (already checked out)"

        return prompt

    def _run_agent(self, task_id: str, work_dir: str, prompt: GeneratedPrompt) -> AgentResult:
        """Run the AI agent to implement the task."""
        logger.info(f"Worker {task_id}: running agent ({self.config.tool})")

        agent_config = AgentConfig(
            tool=self.config.tool,
            working_dir=work_dir,
            prompt=prompt.user_prompt,
            model=self.config.model,
            permission_mode=self.config.permission_mode,
            timeout=self.config.timeout,
            append_system_prompt=prompt.system_prompt,
            verbose=True,
        )

        isolation = IsolationMode(self.config.isolation)

        docker_config = None
        if isolation == IsolationMode.DOCKER:
            docker_config = DockerConfig(
                image=self.config.docker_image,
                memory_limit=self.config.docker_memory,
                cpu_limit=self.config.docker_cpu,
            )

        return self.bridge.start_agent(
            config=agent_config,
            isolation=isolation,
            docker_config=docker_config,
            session_name=f"hive-{task_id}",
        )

    def _commit_and_push(self, task_id: str, work_dir: str, branch_name: str) -> Optional[str]:
        """Commit all changes and push to remote."""
        try:
            git = GitClient(work_dir)

            # Check if there are changes
            status = git.status()
            if not status.get("files", []):
                logger.warning(f"Worker {task_id}: no changes to commit")
                return None

            # Stage all changes
            git.add_all()

            # Commit
            commit_msg = f"hive: implement task for #{self.config.issue_number} on {branch_name}"
            git.commit(commit_msg)

            # Push
            logger.info(f"Worker {task_id}: pushing branch {branch_name}")
            git.push("origin", branch_name, set_upstream=True)

            # Get commit hash
            commit_hash = git.get_current_commit()
            return commit_hash

        except Exception as e:
            logger.error(f"Worker {task_id}: commit/push failed: {e}")
            return None

    def _create_pr(
        self,
        task_id: str,
        branch_name: str,
        issue,
        prompt: GeneratedPrompt,
    ) -> tuple[Optional[int], str]:
        """Create a Pull Request."""
        try:
            head = branch_name
            if self.config.fork:
                fork_user = self.config.fork.split("/")[0]
                head = f"{fork_user}:{branch_name}"

            pr_title = f"[{self.config.task_id}] {issue.title}"
            if len(pr_title) > 256:
                pr_title = pr_title[:253] + "..."

            pr_body = self._build_pr_body(issue, prompt)

            pr = self.gh.create_pr(
                title=pr_title,
                body=pr_body,
                head=head,
                base=self.config.base_branch,
                draft=self.config.draft_pr,
            )

            logger.info(f"Worker {task_id}: created PR #{pr.number}: {pr.url}")
            return pr.number, pr.url

        except Exception as e:
            logger.error(f"Worker {task_id}: PR creation failed: {e}")
            return None, ""

    def _build_pr_body(self, issue, prompt: GeneratedPrompt) -> str:
        """Build PR body with task details."""
        parts = [
            f"## Summary\n",
            f"Closes #{issue.number}\n",
            f"## Changes\n",
            f"Implemented by Hive Worker ({self.config.tool}).\n",
            f"## Success Criteria\n",
        ]
        for criterion in prompt.success_criteria:
            parts.append(f"- [ ] {criterion}")
        parts.append("")
        parts.append("## Testing")
        parts.append("- [ ] Unit tests pass")
        parts.append("- [ ] Integration tests pass")
        parts.append("- [ ] Manual testing completed")
        parts.append("")
        parts.append(f"---\n*Generated by Hive Mind Worker — Task {self.config.task_id}*")

        return "\n".join(parts)

    def _wait_for_ci(self, task_id: str, pr_number: int, timeout: int = 600) -> bool:
        """Wait for CI checks to pass."""
        logger.info(f"Worker {task_id}: waiting for CI on PR #{pr_number}")
        start = time.time()

        while time.time() - start < timeout:
            try:
                checks = self.gh.get_pr_checks(pr_number)
                if not checks:
                    time.sleep(15)
                    continue

                all_passed = all(c["conclusion"] == "success" for c in checks)
                any_failed = any(c["conclusion"] in ("failure", "cancelled", "timed_out") for c in checks)
                all_done = all(c["status"] == "completed" for c in checks)

                if all_passed and all_done:
                    logger.info(f"Worker {task_id}: CI passed for PR #{pr_number}")
                    return True
                elif any_failed:
                    logger.warning(f"Worker {task_id}: CI failed for PR #{pr_number}")
                    return False
                else:
                    logger.info(f"Worker {task_id}: CI still running... ({int(time.time() - start)}s)")

            except Exception as e:
                logger.warning(f"Worker {task_id}: CI check error: {e}")

            time.sleep(15)

        logger.warning(f"Worker {task_id}: CI timeout after {timeout}s")
        return False

    def _merge_pr(self, task_id: str, pr_number: int) -> bool:
        """Merge a PR."""
        try:
            logger.info(f"Worker {task_id}: merging PR #{pr_number}")
            self.gh.merge_pr(pr_number, strategy=self.config.merge_strategy, delete_branch=True)
            logger.info(f"Worker {task_id}: PR #{pr_number} merged successfully")
            return True
        except Exception as e:
            logger.error(f"Worker {task_id}: merge failed: {e}")
            return False

    def _get_changed_files(self, work_dir: str, branch_name: str) -> list[str]:
        """Get list of changed files."""
        try:
            git = GitClient(work_dir)
            return git.diff_files(branch_name, self.config.base_branch)
        except Exception:
            return []

    def _cleanup(self, work_dir: str):
        """Cleanup temporary directories."""
        if not self.config.keep_working_dir and work_dir in self._temp_dirs:
            import shutil
            try:
                shutil.rmtree(work_dir, ignore_errors=True)
                self._temp_dirs.remove(work_dir)
            except Exception:
                pass

    def _error_result(self, task_id: str, start_time: float, error: str) -> WorkerResult:
        """Create an error result."""
        return WorkerResult(
            success=False,
            task_id=task_id,
            error=error,
            duration_seconds=time.time() - start_time,
        )

    @staticmethod
    def _extract_file_hints(body: str) -> list[str]:
        """Extract file paths from issue body."""
        import re
        # Match file paths like src/foo/bar.ts or path/to/file.py
        paths = re.findall(r'`([^`]+\.(?:ts|js|py|rs|go|java|yaml|yml|json|md|sh|toml))`', body)
        paths += re.findall(r'(?:File|path):\s*`?([a-zA-Z0-9_/\.-]+\.(?:ts|js|py|rs|go|java|yaml|yml|json|md|sh|toml))`?', body)
        return list(set(paths))

    @staticmethod
    def _extract_severity(labels: list[str]) -> str:
        """Extract severity from labels."""
        for label in labels:
            lower = label.lower()
            if "critical" in lower:
                return "CRITICAL"
            elif "high" in lower:
                return "HIGH"
            elif "medium" in lower:
                return "MEDIUM"
            elif "low" in lower:
                return "LOW"
        return ""

    @staticmethod
    def _extract_cwe(body: str) -> str:
        """Extract CWE identifier from issue body."""
        import re
        match = re.search(r'CWE-\d+', body)
        return match.group(0) if match else ""


# ── CLI entry point ────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Hive Worker — Execute a single task")
    parser.add_argument("--task-id", required=True, help="Task identifier")
    parser.add_argument("--issue", type=int, required=True, help="Issue number to solve")
    parser.add_argument("--repo", required=True, help="Repository (owner/repo)")
    parser.add_argument("--fork", default="", help="Fork (owner/repo)")
    parser.add_argument("--base-branch", default="main", help="Base branch")
    parser.add_argument("--branch-prefix", default="hive", help="Branch prefix")
    parser.add_argument("--tool", default="claude", help="AI tool to use")
    parser.add_argument("--model", default="", help="Model to use")
    parser.add_argument("--timeout", type=int, default=3600, help="Timeout in seconds")
    parser.add_argument("--isolation", default="direct", choices=["direct", "screen", "docker"])
    parser.add_argument("--auto-merge", action="store_true", help="Auto-merge PR after CI pass")
    parser.add_argument("--merge-strategy", default="squash", choices=["squash", "merge", "rebase"])
    parser.add_argument("--draft", action="store_true", help="Create draft PR")
    parser.add_argument("--working-dir", default="", help="Working directory (empty = temp)")
    parser.add_argument("--keep", action="store_true", help="Keep working directory after run")
    parser.add_argument("--json", action="store_true", help="Output result as JSON")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    config = WorkerConfig(
        task_id=args.task_id,
        issue_number=args.issue,
        repo=args.repo,
        fork=args.fork,
        base_branch=args.base_branch,
        branch_prefix=args.branch_prefix,
        tool=args.tool,
        model=args.model,
        timeout=args.timeout,
        isolation=args.isolation,
        auto_merge=args.auto_merge,
        merge_strategy=args.merge_strategy,
        draft_pr=args.draft,
        working_dir=args.working_dir,
        keep_working_dir=args.keep,
    )

    worker = HiveWorker(config)
    result = worker.execute()

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        if result.success:
            print(f"\u2705 Worker {result.task_id} completed in {result.duration_seconds:.1f}s")
            print(f"   Branch: {result.branch_name}")
            print(f"   PR: {result.pr_url}")
            print(f"   Merged: {result.pr_merged}")
            print(f"   CI: {'passed' if result.ci_passed else 'skipped/failed'}")
            if result.files_changed:
                print(f"   Files changed: {', '.join(result.files_changed)}")
        else:
            print(f"\u274c Worker {result.task_id} failed: {result.error}")
            sys.exit(1)


if __name__ == "__main__":
    main()
