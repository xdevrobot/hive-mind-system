#!/usr/bin/env python3
"""
Autonomous Development Orchestrator — Main entry point for Hive Mind.

Coordinates: Plan -> Execute -> Review -> Merge -> Close -> Report
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from agents.architect.planner import Planner
from agents.architect.validator import Validator
from agents.architect.integrator import Integrator
from agents.shared.github_client import GitHubClient
from agents.shared.task_graph import TaskGraph, TaskState
from hive_worker import HiveWorker, WorkerConfig, WorkerResult

logger = logging.getLogger("orchestrator")


@dataclass
class OrchestratorConfig:
    repo: str = ""
    issue: int = 0
    issue_list: str = ""
    fork: str = ""
    base_branch: str = "main"
    branch_prefix: str = "hive"
    max_workers: int = 3
    tool: str = "claude"
    model: str = ""
    timeout: int = 3600
    isolation: str = "direct"
    auto_merge: bool = False
    merge_strategy: str = "squash"
    require_ci_pass: bool = True
    create_sub_issues: bool = True
    dry_run: bool = False
    config_file: str = ""


@dataclass
class OrchestratorResult:
    success: bool
    total_tasks: int = 0
    completed: int = 0
    failed: int = 0
    merged: int = 0
    task_results: dict = field(default_factory=dict)
    duration_seconds: float = 0.0
    error: str = ""
    report: str = ""

    def to_dict(self) -> dict:
        return {
            "success": self.success, "total_tasks": self.total_tasks,
            "completed": self.completed, "failed": self.failed,
            "merged": self.merged, "duration_seconds": round(self.duration_seconds, 1),
            "error": self.error,
            "tasks": {tid: r.to_dict() for tid, r in self.task_results.items()},
        }


class AutonomousDevOrchestrator:
    def __init__(self, config: OrchestratorConfig):
        self.config = config
        self.gh = GitHubClient(repo=config.repo)
        self.planner = Planner(self.gh)
        self.validator = Validator(self.gh)
        self.integrator = Integrator(self.gh)

    def run(self) -> OrchestratorResult:
        start_time = time.time()
        try:
            issues = self._collect_issues()
            if not issues:
                return OrchestratorResult(success=False, error="No issues", duration_seconds=time.time() - start_time)

            all_tasks = []
            for issue_num in issues:
                try:
                    plan = self.planner.decompose(issue_number=issue_num, subtask_count=3)
                    all_tasks.extend(plan.tasks)
                except Exception as e:
                    logger.error(f"Failed to decompose #{issue_num}: {e}")

            if not all_tasks:
                return OrchestratorResult(success=False, error="No tasks", duration_seconds=time.time() - start_time)

            if self.config.dry_run:
                return self._dry_run_result(all_tasks, start_time)

            task_results = self._execute_tasks(all_tasks)
            completed = {tid: r for tid, r in task_results.items() if r.success}
            failed = {tid: r for tid, r in task_results.items() if not r.success}
            report = self._generate_report(completed, failed, issues)
            self._update_parent_issues(issues, task_results)

            return OrchestratorResult(
                success=len(failed) == 0, total_tasks=len(all_tasks),
                completed=len(completed), failed=len(failed),
                merged=sum(1 for r in task_results.values() if r.pr_merged),
                task_results=task_results, duration_seconds=time.time() - start_time, report=report,
            )
        except Exception as e:
            return OrchestratorResult(success=False, error=str(e), duration_seconds=time.time() - start_time)

    def _collect_issues(self) -> list[int]:
        if self.config.issue_list:
            path = Path(self.config.issue_list)
            if path.exists():
                return [int(line.strip()) for line in path.read_text().splitlines() if line.strip().isdigit()]
            return []
        return [self.config.issue] if self.config.issue else []

    def _execute_tasks(self, tasks: list) -> dict:
        results = {}
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            futures = {}
            for task in tasks:
                config = WorkerConfig(
                    task_id=task.id, issue_number=task.issue_number or self.config.issue,
                    repo=self.config.repo, fork=self.config.fork, base_branch=self.config.base_branch,
                    branch_prefix=self.config.branch_prefix, tool=self.config.tool, model=self.config.model,
                    timeout=self.config.timeout, isolation=self.config.isolation,
                    auto_merge=self.config.auto_merge, merge_strategy=self.config.merge_strategy,
                    require_ci_pass=self.config.require_ci_pass,
                )
                futures[executor.submit(HiveWorker(config).execute)] = task.id
            for future in as_completed(futures):
                task_id = futures[future]
                try:
                    results[task_id] = future.result()
                except Exception as e:
                    results[task_id] = WorkerResult(success=False, task_id=task_id, error=str(e))
        return results

    def _dry_run_result(self, tasks, start_time):
        return OrchestratorResult(success=True, total_tasks=len(tasks), duration_seconds=time.time() - start_time,
                                  report=f"Dry run: {len(tasks)} tasks would be executed")

    def _generate_report(self, completed, failed, issues):
        lines = ["# Hive Mind Report", f"**Repo:** {self.config.repo}",
                 f"**Completed:** {len(completed)}/{len(completed) + len(failed)} tasks"]
        if completed:
            lines.append("## Completed")
            for tid, r in completed.items():
                lines.append(f"- **{tid}**: PR #{r.pr_number}" if r.pr_number else f"- **{tid}**: No PR")
        if failed:
            lines.append("## Failed")
            for tid, r in failed.items():
                lines.append(f"- **{tid}**: {r.error}")
        return "\n".join(lines)

    def _update_parent_issues(self, issues, results):
        for issue_num in issues:
            try:
                completed = sum(1 for r in results.values() if r.success)
                self.gh.add_issue_comment(issue_num, f"Progress: {completed}/{len(results)} tasks completed")
            except Exception:
                pass


def main():
    parser = argparse.ArgumentParser(description="Autonomous Development Orchestrator")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--issue", type=int)
    parser.add_argument("--issue-list")
    parser.add_argument("--fork", default="")
    parser.add_argument("--base-branch", default="main")
    parser.add_argument("--max-workers", type=int, default=3)
    parser.add_argument("--tool", default="claude")
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument("--isolation", default="direct", choices=["direct", "screen", "docker"])
    parser.add_argument("--auto-merge", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not args.issue and not args.issue_list:
        parser.error("Either --issue or --issue-list is required")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    config = OrchestratorConfig(
        repo=args.repo, issue=args.issue or 0, issue_list=args.issue_list or "",
        fork=args.fork, base_branch=args.base_branch, max_workers=args.max_workers,
        tool=args.tool, timeout=args.timeout, isolation=args.isolation,
        auto_merge=args.auto_merge, dry_run=args.dry_run,
    )
    result = AutonomousDevOrchestrator(config).run()

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(f"Tasks: {result.total_tasks}, Completed: {result.completed}, Failed: {result.failed}")
    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
