# Hive Mind — Comprehensive Guide

## Architecture Overview

Hive Mind is an autonomous multi-agent development system for GitHub. It combines:

- **xdevrobot/hive-mind-system** — Python multi-agent orchestration (Planner, Orchestrator, Worker)
- **link-assistant/hive-mind** — Rate-limit retry, auto-merge, task splitting patterns (adapted from JS/TS)

### Pipeline

```
┌──────────┐    ┌─────────────┐    ┌──────────┐    ┌────────────┐
│  Planner  │───▶│ Orchestrator │───▶│ Validator │───▶│ Integrator │
│ (split)   │    │ (parallel)   │    │ (CI/quality)│   │ (merge)    │
└──────────┘    └──────┬──────┘    └──────────┘    └────────────┘
                       │
                  ┌────┴────┐
                  │ Workers  │ × N (parallel)
                  └────┬────┘
                       │
            Clone → Branch → Code → Commit → Push → PR → Auto-merge
```

## Components

### Shared Libraries

| Module | Purpose |
|--------|---------|
| `github_client.py` | Python wrapper over `gh` CLI (issues, PRs, CI) |
| `git_client.py` | Python wrapper over `git` CLI (clone, commit, push) |
| `github_retry.py` | Rate-limit detection, retry with backoff, terminal state handling |
| `task_graph.py` | DAG for task dependency management |

### Architect Agents

| Agent | Purpose |
|-------|---------|
| **Planner** | Decomposes issues into sub-tasks (checklist → sections → phases) |
| **TaskSplitter** | Decomposes issues into sub-issues on GitHub |
| **Orchestrator** | Parallel wave execution with configurable concurrency |
| **Validator** | PR review — CI checks, code quality scan |
| **AutoMerge** | CI/CD consensus monitoring, auto-merge with rate-limit retry |
| **Integrator** | Squash-merge, summary PR, markdown report |

### Workers

| Worker | Purpose |
|--------|---------|
| **WorkerExecutor** | Base pipeline: clone → branch → code → commit → push → PR |
| **EnhancedHiveWorker** | Enhanced pipeline with rate-limit retry and auto-merge |

## Rate-Limit Retry

Automatic retries with intelligent backoff when hitting GitHub API rate limits:

```python
from agents.shared.github_retry import retry_with_rate_limit

result = retry_with_rate_limit(lambda: gh.create_pr(title="...", ...))
```

**Wait policy:** `wait = (resetTimestamp - now) + 10min buffer + random(0-5min) jitter`

The system recognizes both primary (5000/hr) and secondary (abuse-detection) rate limits.

## Terminal State Detection

Detects non-retryable states (404, 410, deleted entities):

```python
from agents.shared.github_retry import is_terminal_entity_error

if is_terminal_entity_error(error):
    # Entity is deleted or inaccessible — do not retry
    logger.error("Terminal: %s", error)
```

## Auto-Merge

Automatically merge PRs after CI/CD checks pass:

```python
from agents.architect.auto_merge import AutoMerge, MergeConfig

config = MergeConfig(
    require_ci_pass=True,
    merge_method="squash",
    poll_interval=30,
    timeout=600,
)
auto = AutoMerge(gh, config)
auto.auto_merge(pr_number=42)
```

### CI/CD Consensus States

| State | Description |
|-------|-------------|
| `PASSING` | All checks passed |
| `FAILING` | One or more checks failed |
| `PENDING` | Checks still running |
| `MIXED` | Some passed, some failed |
| `UNKNOWN` | No checks found |

## Task Splitting

Decompose large issues into smaller, independently actionable sub-issues:

```python
from agents.architect.task_splitter import TaskSplitter

splitter = TaskSplitter(gh)
result = splitter.split_and_create(issue_number=58, subtask_count=5)
```

### Decomposition Strategies

1. **Checklist-based** — splits by `- [ ]` items in the issue body
2. **Section-based** — splits by `##` headers
3. **Phase-based** — fallback: Setup → Implementation → Testing

## PowerShell Scripts

### hive-dev.ps1 — Main Development Workflow

```powershell
# Solve an issue
.\scripts\hive-dev.ps1 -Repo owner/repo -Issue 58

# Split and solve
.\scripts\hive-dev.ps1 -Repo owner/repo -Issue 58 -Split 5

# Auto-merge after CI
.\scripts\hive-dev.ps1 -Repo owner/repo -Issue 58 -AutoMerge

# Dry run (plan only)
.\scripts\hive-dev.ps1 -Repo owner/repo -Issue 58 -DryRun

# Check status
.\scripts\hive-dev.ps1 -Repo owner/repo -Status

# Stop all workers
.\scripts\hive-dev.ps1 -Repo owner/repo -Stop
```

### hive-issue.ps1 — Issue Management

```powershell
.\scripts\hive-issue.ps1 -Action list
.\scripts\hive-issue.ps1 -Action create -Title "Feature" -Body "Description"
.\scripts\hive-issue.ps1 -Action view -Issue 58
.\scripts\hive-issue.ps1 -Action close -Issue 58
.\scripts\hive-issue.ps1 -Action comment -Issue 58 -Comment "Done!"
```

### hive-pr.ps1 — PR Management

```powershell
.\scripts\hive-pr.ps1 -Action list
.\scripts\hive-pr.ps1 -Action view -PR 42
.\scripts\hive-pr.ps1 -Action checks -PR 42
.\scripts\hive-pr.ps1 -Action merge -PR 42
.\scripts\hive-pr.ps1 -Action approve -PR 42 -Comment "LGTM!"
```

## Python API

### Full Orchestration Pipeline

```python
from agents import (
    GitHubClient, Planner, Orchestrator, OrchestratorConfig,
    AutoMerge, MergeConfig, TaskSplitter, run_worker,
)

# Initialize
gh = GitHubClient(repo="owner/repo")

# Plan
planner = Planner(gh)
plan = planner.decompose(issue_number=58, subtask_count=3)

# Execute
config = OrchestratorConfig(max_parallel_workers=3, timeout=3600)
orchestrator = Orchestrator(gh, config)
result = orchestrator.run(
    task_graph=plan.task_graph,
    repo_url="https://github.com/owner/repo",
    base_branch="main",
)

# Auto-merge
merge_config = MergeConfig(require_ci_pass=True, merge_method="squash")
auto = AutoMerge(gh, merge_config)
for task_id, task_result in result.task_results.items():
    if task_result.pr_number:
        auto.auto_merge(task_result.pr_number)
```

### Direct Worker

```python
from agents.worker.enhanced_worker import run_worker

result = run_worker(
    task_id="T1",
    issue_number=58,
    repo="owner/repo",
    auto_merge=True,
    json_output=True,
)
```

## Skills

Hive Mind includes skills — markdown guides for common GitHub workflows:

| Skill | Description |
|-------|-------------|
| Git Branch Manager | Branch naming conventions (`hive/<issue>-<hex>`) |
| Git Fork & Clone | Fork workflow, upstream sync |
| Git Commit & Push | Conventional commits |
| GitHub Issue Manager | Issue CRUD operations |
| GitHub PR Creator | PR creation with templates |
| GitHub PR Reviewer | Review checklist |
| GitHub PR Merger | Merge strategies |

## Requirements

- Python 3.10+
- GitHub CLI (`gh`) — authenticated
- AI Agent CLI (Claude Code / OpenAI Codex / Gemini CLI)
- (optional) Docker — for Docker isolation mode
- (optional) GNU Screen — for Screen isolation mode
