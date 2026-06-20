from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from agents.shared.github_client import GitHubClient
from agents.shared.task_graph import TaskGraph, TaskState
from agents.worker.executor import TaskResult, WorkerExecutor

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorConfig:
    max_parallel_workers: int = 3
    poll_interval: int = 30
    timeout: int = 3600
    retry_failed: bool = False
    max_retries: int = 1


@dataclass
class OrchestratorResult:
    success: bool
    total_tasks: int
    completed: int
    failed: int
    task_results: dict[str, TaskResult] = field(default_factory=dict)
    duration_seconds: float = 0.0
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "success": self.success, "total_tasks": self.total_tasks,
            "completed": self.completed, "failed": self.failed,
            "duration_seconds": self.duration_seconds, "error": self.error,
            "tasks": {
                tid: {"success": r.success, "pr_number": r.pr_number, "pr_url": r.pr_url, "error": r.error}
                for tid, r in self.task_results.items()
            },
        }


class Orchestrator:
    def __init__(self, gh_client: GitHubClient, config: Optional[OrchestratorConfig] = None):
        self.gh = gh_client
        self.config = config or OrchestratorConfig()

    def run(self, task_graph: TaskGraph, repo_url: str, fork_url: str,
            base_branch: str = "main", state_file: Optional[str] = None) -> OrchestratorResult:
        start_time = time.time()
        results: dict[str, TaskResult] = {}
        logger.info(f"Starting orchestration: {task_graph}")
        try:
            waves = task_graph.get_execution_waves()
        except ValueError as e:
            return OrchestratorResult(
                success=False, total_tasks=len(task_graph), completed=0, failed=0,
                error=f"Task graph error: {e}",
            )
        logger.info(f"Execution plan: {len(waves)} waves")
        for wave_num, wave in enumerate(waves, 1):
            logger.info(f"Wave {wave_num}/{len(waves)}: {len(wave)} task(s)")
            wave_results = self._execute_wave(wave, repo_url, fork_url, base_branch)
            for task_id, result in wave_results.items():
                results[task_id] = result
                state = TaskState.COMPLETED if result.success else TaskState.FAILED
                task_graph.update_state(task_id, state)
            if state_file:
                self._save_state(task_graph, results, state_file)
            failed_wave = [r for r in wave_results.values() if not r.success]
            if failed_wave and not self.config.retry_failed:
                logger.error(f"Wave {wave_num} had {len(failed_wave)} failure(s), stopping")
                break
        duration = time.time() - start_time
        completed = sum(1 for r in results.values() if r.success)
        failed_count = sum(1 for r in results.values() if not r.success)
        return OrchestratorResult(
            success=failed_count == 0, total_tasks=len(task_graph),
            completed=completed, failed=failed_count, task_results=results,
            duration_seconds=round(duration, 2),
        )

    def _execute_wave(self, tasks: list, repo_url: str, fork_url: str, base_branch: str) -> dict[str, TaskResult]:
        results = {}
        with ThreadPoolExecutor(max_workers=self.config.max_parallel_workers) as pool:
            futures = {}
            for task in tasks:
                future = pool.submit(self._run_worker, task, repo_url, fork_url, base_branch)
                futures[future] = task
            for future in as_completed(futures):
                task = futures[future]
                try:
                    result = future.result(timeout=self.config.timeout)
                    results[task.id] = result
                    status = "SUCCESS" if result.success else "FAILED"
                    logger.info(f"Task {task.id}: {status}")
                except Exception as e:
                    logger.error(f"Task {task.id}: exception - {e}")
                    results[task.id] = TaskResult(
                        success=False, task_id=task.id, branch_name="", error=str(e)
                    )
        return results

    def _run_worker(self, task, repo_url: str, fork_url: str, base_branch: str) -> TaskResult:
        with WorkerExecutor(self.gh) as executor:
            result = executor.execute(
                task_id=task.id, issue_number=task.issue_number or 0,
                repo_url=repo_url, fork_url=fork_url, base_branch=base_branch,
            )
        return result

    def monitor(self, pr_numbers: list[int], timeout: int = 600, interval: int = 30) -> dict[int, bool]:
        results = {}
        start = time.time()
        while len(results) < len(pr_numbers):
            if time.time() - start > timeout:
                logger.warning("Monitor timeout reached")
                break
            for pr_num in pr_numbers:
                if pr_num in results:
                    continue
                checks = self.gh.get_pr_checks(pr_num)
                if not checks:
                    results[pr_num] = True
                    continue
                states = [c.get("state", "") for c in checks]
                conclusions = [c.get("conclusion", "") for c in checks]
                if any(s in ("in_progress", "queued") for s in states):
                    continue
                results[pr_num] = all(c == "success" for c in conclusions if c)
            if len(results) < len(pr_numbers):
                time.sleep(interval)
        return results

    def _save_state(self, graph: TaskGraph, results: dict[str, TaskResult], state_file: str) -> None:
        state = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "graph": graph.to_dict(),
            "results": {
                tid: {"success": r.success, "pr_number": r.pr_number, "error": r.error}
                for tid, r in results.items()
            },
        }
        Path(state_file).write_text(json.dumps(state, indent=2, ensure_ascii=False))
