from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from agents.shared.github_client import GitHubClient
from agents.architect.validator import ValidationResult

logger = logging.getLogger(__name__)


@dataclass
class IntegrationResult:
    success: bool
    summary_pr_number: Optional[int] = None
    summary_pr_url: str = ""
    merged_prs: list[int] = field(default_factory=list)
    failed_prs: list[int] = field(default_factory=list)
    report: str = ""
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "success": self.success, "summary_pr_number": self.summary_pr_number,
            "summary_pr_url": self.summary_pr_url, "merged_prs": self.merged_prs,
            "failed_prs": self.failed_prs, "error": self.error,
        }


class Integrator:
    def __init__(self, gh_client: GitHubClient):
        self.gh = gh_client

    def integrate(self, validation_results: list[ValidationResult],
                  parent_issue_number: int, feature_branch: str = "integration",
                  base_branch: str = "main", merge_strategy: str = "squash") -> IntegrationResult:
        approved = [r for r in validation_results if r.approved]
        rejected = [r for r in validation_results if not r.approved]
        logger.info(f"Integration: {len(approved)} approved, {len(rejected)} rejected")
        if not approved:
            return IntegrationResult(success=False, error="No PRs approved for merging")
        if rejected:
            logger.warning(f"Skipping {len(rejected)} rejected PRs: {[r.pr_number for r in rejected]}")
        merged = []
        failed = []
        for result in approved:
            try:
                self.gh.merge_pr(result.pr_number, method=merge_strategy, delete_branch=True)
                merged.append(result.pr_number)
                logger.info(f"Merged PR {result.pr_number}")
            except Exception as e:
                failed.append(result.pr_number)
                logger.error(f"Failed to merge PR {result.pr_number}: {e}")
        summary_pr = None
        try:
            parent_issue = self.gh.view_issue(parent_issue_number)
            pr_body = self._build_summary_body(parent_issue_number, parent_issue.title, merged, rejected)
            summary_pr = self.gh.create_pr(
                title=f"feat: {parent_issue.title} [Integration]",
                body=pr_body, base=base_branch, draft=False,
            )
            logger.info(f"Created summary PR {summary_pr.number}")
        except Exception as e:
            logger.error(f"Failed to create summary PR: {e}")
        report = self._generate_report(parent_issue_number, merged, rejected, failed, summary_pr)
        return IntegrationResult(
            success=len(merged) > 0,
            summary_pr_number=summary_pr.number if summary_pr else None,
            summary_pr_url=summary_pr.url if summary_pr else "",
            merged_prs=merged,
            failed_prs=failed + [r.pr_number for r in rejected],
            report=report,
        )

    def _build_summary_body(self, issue_number: int, issue_title: str,
                            merged: list[int], rejected: list[ValidationResult]) -> str:
        lines = [
            "## Summary",
            f"Integration PR for #{issue_number}: {issue_title}",
            "", "## Merged Pull Requests",
        ]
        for pr_num in merged:
            lines.append(f"- #{pr_num}")
        if rejected:
            lines += ["", "## Not Merged"]
            for r in rejected:
                comment_summary = "; ".join(r.comments[:2])
                lines.append(f"- #{r.pr_number} - {r.verdict}: {comment_summary}")
        lines += [
            "", "## Testing",
            "- [ ] All sub-PRs passed CI",
            "- [ ] Integration tests pass",
            "- [ ] Manual verification completed",
            "", f"Closes #{issue_number}",
        ]
        return "\n".join(lines)

    def _generate_report(self, issue_number: int, merged: list[int],
                         rejected: list[ValidationResult], failed: list[int],
                         summary_pr) -> str:
        lines = [
            "# Integration Report", "",
            f"**Issue:** #{issue_number}",
            f"**Date:** {datetime.now(timezone.utc).isoformat()}",
            "", "## Results", "",
            "| Metric | Value |", "| ------- | ----- |",
            f"| Merged | {len(merged)} |",
            f"| Rejected | {len(rejected)} |",
            f"| Failed to merge | {len(failed)} |",
            f"| Summary PR | #{summary_pr.number if summary_pr else 'N/A'} |", "",
        ]
        if merged:
            lines += ["## Merged PRs"] + [f"- #{pr_num}" for pr_num in merged] + [""]
        if rejected:
            lines += ["## Rejected PRs"] + [f"- #{r.pr_number} ({r.verdict})" for r in rejected] + [""]
        if failed:
            lines += ["## Failed to Merge"] + [f"- #{pr_num}" for pr_num in failed] + [""]
        return "\n".join(lines)
