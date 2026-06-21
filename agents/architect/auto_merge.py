"""
Auto-merge module with CI/CD status monitoring.

Adapted from link-assistant/hive-mind:
- solve.auto-merge.lib.mjs
- github-merge-ci.lib.mjs
- github-merge-ci-signals.lib.mjs
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from agents.shared.github_client import GitHubClient
from agents.shared.github_retry import (
    is_rate_limit_error,
    is_terminal_entity_error,
    retry_with_rate_limit,
)

logger = logging.getLogger(__name__)


class CIConsensusState(Enum):
    """CI/CD consensus state for a PR."""
    PASSING = "passing"
    FAILING = "failing"
    PENDING = "pending"
    MIXED = "mixed"
    UNKNOWN = "unknown"


@dataclass
class CIStatus:
    """CI/CD status for a PR."""
    pr_number: int
    state: CIConsensusState
    total_checks: int
    passed: int
    failed: int
    in_progress: int
    checks: list[dict] = field(default_factory=list)

    @property
    def all_passing(self) -> bool:
        return self.state == CIConsensusState.PASSING

    @property
    def has_failures(self) -> bool:
        return self.state == CIConsensusState.FAILING


@dataclass
class MergeConfig:
    """Configuration for auto-merge behavior."""
    require_ci_pass: bool = True
    require_no_failures: bool = True
    merge_method: str = "squash"
    delete_branch: bool = True
    poll_interval: int = 30  # seconds
    timeout: int = 600  # seconds
    require_approvals: int = 0
    protected_branch_patterns: list = field(default_factory=lambda: ["main", "master"])


class AutoMerge:
    """Auto-merge PRs after CI passes."""

    def __init__(self, gh_client: GitHubClient, config: Optional[MergeConfig] = None):
        self.gh = gh_client
        self.config = config or MergeConfig()

    def check_ci_status(self, pr_number: int) -> CIStatus:
        """Check CI/CD consensus status for a PR."""
        checks = self.gh.get_pr_checks(pr_number)

        if not checks:
            return CIStatus(
                pr_number=pr_number,
                state=CIConsensusState.UNKNOWN,
                total_checks=0, passed=0, failed=0, in_progress=0,
            )

        passed = 0
        failed = 0
        in_progress = 0
        for check in checks:
            state = check.get("state", "")
            conclusion = check.get("conclusion", "")
            if state in ("in_progress", "queued"):
                in_progress += 1
            elif conclusion == "success":
                passed += 1
            elif conclusion in ("failure", "cancelled", "timed_out"):
                failed += 1
            else:
                in_progress += 1

        total = len(checks)
        if failed > 0:
            consensus = CIConsensusState.FAILING
        elif in_progress > 0:
            consensus = CIConsensusState.PENDING
        elif passed == total:
            consensus = CIConsensusState.PASSING
        elif passed > 0 and failed > 0:
            consensus = CIConsensusState.MIXED
        else:
            consensus = CIConsensusState.UNKNOWN

        return CIStatus(
            pr_number=pr_number,
            state=consensus,
            total_checks=total,
            passed=passed,
            failed=failed,
            in_progress=in_progress,
            checks=checks,
        )

    def check_pr_mergeable(self, pr_number: int) -> bool:
        """Check if a PR is mergeable."""
        pr = self.gh.view_pr(pr_number)
        if pr.state != "OPEN":
            logger.warning("PR #%d is not open (state=%s)", pr_number, pr.state)
            return False
        if not pr.mergeable:
            logger.warning("PR #%d has merge conflicts", pr_number)
            return False
        return True

    def wait_for_ci(self, pr_number: int) -> CIStatus:
        """Wait for CI/CD to complete. Poll until all checks pass or timeout."""
        start = time.time()
        while True:
            status = self.check_ci_status(pr_number)
            logger.info(
                "PR #%d CI: %s (%d/%d passed, %d failed, %d pending)",
                pr_number, status.state.value,
                status.passed, status.total_checks, status.failed, status.in_progress,
            )

            if status.all_passing:
                logger.info("PR #%d: All CI checks passed!", pr_number)
                return status
            if status.has_failures:
                logger.warning("PR #%d: CI checks failed!", pr_number)
                return status

            elapsed = time.time() - start
            if elapsed > self.config.timeout:
                logger.warning("PR #%d: CI monitoring timeout after %.0f s", pr_number, elapsed)
                return status

            logger.info("PR #%d: Waiting %d s for CI...", pr_number, self.config.poll_interval)
            time.sleep(self.config.poll_interval)

    def merge_pr(self, pr_number: int) -> bool:
        """Merge a PR using the configured merge method."""
        try:
            self.gh.merge_pr(
                pr_number,
                method=self.config.merge_method,
                delete_branch=self.config.delete_branch,
            )
            logger.info("PR #%d merged successfully (%s)", pr_number, self.config.merge_method)
            return True
        except RuntimeError as e:
            if is_terminal_entity_error(str(e)):
                logger.error("PR #%d: terminal error during merge: %s", pr_number, e)
            elif is_rate_limit_error(str(e)):
                logger.warning("PR #%d: rate limit during merge, retrying...", pr_number)
                try:
                    retry_with_rate_limit(
                        lambda: self.gh.merge_pr(pr_number, method=self.config.merge_method, delete_branch=self.config.delete_branch)
                    )
                    return True
                except Exception as retry_e:
                    logger.error("PR #%d: merge retry failed: %s", pr_number, retry_e)
            else:
                logger.error("PR #%d: merge failed: %s", pr_number, e)
            return False

    def auto_merge(self, pr_number: int) -> bool:
        """Full auto-merge pipeline: check → wait for CI → merge."""
        logger.info("Auto-merge: PR #%d", pr_number)

        # Check mergeability
        if not self.check_pr_mergeable(pr_number):
            logger.warning("PR #%d is not mergeable", pr_number)
            return False

        # Wait for CI if required
        if self.config.require_ci_pass:
            ci_status = self.wait_for_ci(pr_number)
            if not ci_status.all_passing:
                logger.warning("PR #%d: CI did not pass, skipping merge", pr_number)
                return False

        # Merge
        return self.merge_pr(pr_number)

    def auto_merge_all(self, pr_numbers: list[int]) -> dict[int, bool]:
        """Auto-merge multiple PRs sequentially."""
        results = {}
        for pr_num in pr_numbers:
            results[pr_num] = self.auto_merge(pr_num)
        return results
