#!/usr/bin/env python3
"""Architect CLI - Run the Hive Mind Architect agent."""

import argparse
import json
import logging
import sys

from agents.architect.orchestrator import OrchestratorConfig, AutonomousDevOrchestrator

logger = logging.getLogger("architect")


def main():
    parser = argparse.ArgumentParser(description="Hive Mind Architect")
    parser.add_argument("--repo", required=True, help="Repository (owner/repo)")
    parser.add_argument("--issue", type=int, help="Issue number to solve")
    parser.add_argument("--issue-list", help="File with issue numbers")
    parser.add_argument("--fork", default="", help="Fork (owner/repo)")
    parser.add_argument("--base-branch", default="main", help="Base branch")
    parser.add_argument("--max-workers", type=int, default=3, help="Max parallel workers")
    parser.add_argument("--tool", default="claude", help="AI tool to use")
    parser.add_argument("--timeout", type=int, default=3600, help="Timeout per task")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    config = OrchestratorConfig(
        repo=args.repo,
        issue=args.issue or 0,
        issue_list=args.issue_list or "",
        fork=args.fork,
        base_branch=args.base_branch,
        max_workers=args.max_workers,
        tool=args.tool,
        timeout=args.timeout,
    )

    orchestrator = AutonomousDevOrchestrator(config)
    result = orchestrator.run()

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        status = "SUCCESS" if result.success else "FAILED"
        print(f"Architect {status}: {result.completed}/{result.total_tasks} tasks completed")
        if result.failed:
            print(f"  Failed: {result.failed}")
        if result.report:
            print(result.report)

    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
