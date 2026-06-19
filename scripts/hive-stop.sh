#!/usr/bin/env bash
# hive-stop.sh - Stop all Hive Mind workers for a repo
set -euo pipefail

REPO="${1:?Usage: hive-stop.sh <owner/repo>}"

echo "Hive Mind: Stopping all workers for ${REPO}"

pkill -f "hive_worker.py" 2>/dev/null || true
pkill -f "hive-solve.sh" 2>/dev/null || true
pkill -f "hive-batch.sh" 2>/dev/null || true

docker ps --filter "name=hive-agent" --format "{{.Names}}" 2>/dev/null | \
    xargs -r docker stop --time 30 2>/dev/null || true

echo "All Hive Mind workers stopped"
