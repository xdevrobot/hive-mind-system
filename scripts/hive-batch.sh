#!/usr/bin/env bash
# hive-batch.sh - Solve multiple issues using Hive Mind
set -euo pipefail

REPO="${1:?Usage: hive-batch.sh <owner/repo> <issue-list-file>}"
ISSUE_LIST="${2:?Usage: hive-batch.sh <owner/repo> <issue-list-file>}"
FORK="${3:-}"
MAX_WORKERS="${4:-3}"

echo "Hive Mind: Batch solving issues from ${ISSUE_LIST} in ${REPO}"

python -m scripts.architect \
    --repo "${REPO}" \
    --issue-list "${ISSUE_LIST}" \
    --max-workers "${MAX_WORKERS}" \
    ${FORK:+--fork "${FORK}"} \
    --json

echo "Batch complete!"
