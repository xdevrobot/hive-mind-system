#!/usr/bin/env bash
# hive-solve.sh - Solve a single issue using Hive Mind
set -euo pipefail

REPO="${1:?Usage: hive-solve.sh <owner/repo> <issue-number>}"
ISSUE="${2:?Usage: hive-solve.sh <owner/repo> <issue-number>}"
FORK="${3:-}"
TOOL="${4:-claude}"

echo "Hive Mind: Solving issue #${ISSUE} in ${REPO}"

python -m scripts.worker \
    --task-id "solve-${ISSUE}" \
    --issue "${ISSUE}" \
    --repo "${REPO}" \
    --tool "${TOOL}" \
    ${FORK:+--fork "${FORK}"} \
    --json

echo "Done!"
