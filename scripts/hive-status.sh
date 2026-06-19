#!/usr/bin/env bash
# hive-status.sh - Check status of Hive Mind workers
set -euo pipefail

REPO="${1:?Usage: hive-status.sh <owner/repo>}"

echo "Hive Mind: Status for ${REPO}"
echo "---"

echo "Open Hive PRs:"
gh pr list --repo "${REPO}" --label "hive" --state open --json number,title,url \
    --jq '.[] | "  #\(.number): \(.title) (\(.url))"' 2>/dev/null || echo "  (none)"

echo ""
echo "Recent Hive commits:"
gh api "repos/${REPO}/commits?per_page=5" \
    --jq '.[] | "  \(.sha[:7]): \(.commit.message | split("\n")[0])"' 2>/dev/null || echo "  (none)"
