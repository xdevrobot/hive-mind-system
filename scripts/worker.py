#!/usr/bin/env python3
"""Worker CLI - Run a single Hive Mind Worker agent."""

import argparse
import json
import logging
import sys

from hive_worker import HiveWorker, WorkerConfig


def main():
    parser = argparse.ArgumentParser(description="Hive Mind Worker")
    parser.add_argument("--task-id", required=True, help="Task identifier")
    parser.add_argument("--issue", type=int, required=True, help="Issue number")
    parser.add_argument("--repo", required=True, help="Repository (owner/repo)")
    parser.add_argument("--fork", default="", help="Fork (owner/repo)")
    parser.add_argument("--tool", default="claude", help="AI tool")
    parser.add_argument("--timeout", type=int, default=3600, help="Timeout")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    config = WorkerConfig(
        task_id=args.task_id,
        issue_number=args.issue,
        repo=args.repo,
        fork=args.fork,
        tool=args.tool,
        timeout=args.timeout,
    )

    worker = HiveWorker(config)
    result = worker.execute()

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        if result.success:
            print(f"Worker {result.task_id} completed: PR {result.pr_url}")
        else:
            print(f"Worker {result.task_id} failed: {result.error}")
            sys.exit(1)


if __name__ == "__main__":
    main()
