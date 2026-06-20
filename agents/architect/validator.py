from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

from agents.shared.github_client import GitHubClient, PullRequest

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    pr_number: int
    approved: bool
    ci_passed: bool
    has_review: bool
    mergeable: bool
    comments: list[str]
    verdict: str = ""

    def __post_init__(self):
        if not self.verdict:
            if not self.ci_passed:
                self.verdict = "wait"
            elif not self.mergeable:
                self.verdict = "wait"
            elif self.approved:
                self.verdict = "approve"
            elif self.has_review:
                self.verdict = "request_changes"
            else:
                self.verdict = "wait"

    def to_dict(self) -> dict:
        return {
            "pr_number": self.pr_number, "approved": self.approved,
            "ci_passed": self.ci_passed, "has_review": self.has_review,
            "mergeable": self.mergeable, "verdict": self.verdict,
            "comments": self.comments,
        }


class Validator:
    def __init__(self, gh_client: GitHubClient, auto_review: bool = True):
        self.gh = gh_client
        self.auto_review = auto_review

    def validate_pr(self, pr_number: int, wait_for_ci: bool = True, ci_timeout: int = 600) -> ValidationResult:
        pr = self.gh.view_pr(pr_number)
        logger.info(f"Validating PR {pr_number}: {pr.title}")
        if wait_for_ci:
            ci_passed = self._wait_for_ci(pr_number, timeout=ci_timeout)
        else:
            checks = self.gh.get_pr_checks(pr_number)
            ci_passed = all(c.get("conclusion") == "success" for c in checks if c.get("conclusion"))
        approved = False
        has_review = False
        has_changes_requested = False
        comments = []
        if self.auto_review and not has_review and ci_passed:
            issues = self._check_pr_quality(pr)
            if issues:
                self.gh.add_pr_comment(pr_number, "\n".join(issues))
                has_review = True
                has_changes_requested = True
                comments.append(f"[AUTO] Validation issues found: {', '.join(issues)}")
            else:
                self.gh.add_pr_comment(pr_number, "Auto-approved: CI passing, basic checks passed.")
                approved = True
                has_review = True
                comments.append("[AUTO] Approved.")
        result = ValidationResult(
            pr_number=pr_number,
            approved=approved and not has_changes_requested,
            ci_passed=ci_passed, has_review=has_review,
            mergeable=pr.mergeable, comments=comments,
        )
        logger.info(f"PR {pr_number} verdict: {result.verdict}")
        return result

    def validate_all(self, pr_numbers: list[int], wait_for_ci: bool = True) -> list[ValidationResult]:
        return [self.validate_pr(pr_num, wait_for_ci=wait_for_ci) for pr_num in pr_numbers]

    def _wait_for_ci(self, pr_number: int, timeout: int = 600) -> bool:
        start = time.time()
        while time.time() - start < timeout:
            checks = self.gh.get_pr_checks(pr_number)
            if not checks:
                return True
            states = [c.get("state", "") for c in checks]
            if any(s in ("in_progress", "queued", "pending") for s in states):
                time.sleep(30)
                continue
            conclusions = [c.get("conclusion", "") for c in checks]
            return all(c == "success" for c in conclusions if c)
        return False

    def _check_pr_quality(self, pr: PullRequest) -> list[str]:
        issues = []
        if not pr.body or len(pr.body.strip()) < 20:
            issues.append("PR body is too short. Please describe the changes.")
        if pr.is_draft:
            issues.append("PR is still in draft. Mark as ready for review first.")
        return issues
