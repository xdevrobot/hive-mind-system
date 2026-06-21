# 🐝 Hive Mind — Autonomous Multi-Agent Development System

**Python 3.10+ | MIT License**

Hive Mind is an autonomous development system that uses AI agents to plan, execute, review, and merge code changes based on GitHub issues. Point it at a repository and an issue, and it will:

1. **Decompose** the issue into parallelizable sub-tasks
2. **Execute** each sub-task with an isolated AI worker agent
3. **Review** the resulting pull requests (CI, code quality)
4. **Merge** approved PRs and generate a summary report

## Table of Contents

- [Architecture](#architecture)
- [How It Works](#how-it-works)
- [Components](#components)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Isolation Modes](#isolation-modes)
- [Skills](#skills)
- [Development](#development)
- [Project Structure](#project-structure)
- [Credits](#credits)
- [License](#license)

## Architecture

Hive Mind consists of four main agents:

| Agent | Role |
|-------|------|
| **Planner** | Decomposes issues into sub-tasks with a dependency graph (DAG) |
| **Orchestrator** | Executes workers in parallel waves with configurable concurrency |
| **Validator** | Reviews PRs for CI status and code quality |
| **Integrator** | Squash-merges approved PRs and generates summary reports |

Each **Worker** clones the repo, creates a feature branch, runs an AI agent to implement changes, commits, pushes, and creates a PR.

Enhanced components add production-grade reliability:

| Component | Role |
|-----------|------|
| **AutoMerge** | Monitors CI/CD consensus and auto-merges passing PRs |
| **TaskSplitter** | Decomposes large issues into smaller, independently actionable sub-issues |
| **GitHubRetry** | Rate-limit detection with exponential backoff and terminal state handling |
| **EnhancedWorker** | Full pipeline worker with retry logic and auto-merge integration |

## How It Works

### Phase 1: Plan (Planner)

- Fetches the GitHub issue
- Parses checklists (`- [ ]` items) and section headers (`##`)
- Falls back to logical phases if no structure found
- Builds a DAG of dependent tasks

### Phase 2: Execute (Orchestrator + Workers)

- Wave execution: tasks at the same dependency level run in parallel
- Configurable concurrency (`--max-workers`)
- Fork support for safe isolation
- Each Worker: Clone → Branch → Code → Commit → Push → PR

### Phase 3: Review (Validator)

- CI status checks
- Code quality scan (TODOs, debug statements, diff size)
- Auto-approve for passing PRs
- Flag for manual review when needed

### Phase 4: Integrate (Integrator)

- Squash merge into base branch
- Create summary PR linking all sub-PRs
- Generate markdown report

### Phase 5: Auto-Merge (AutoMerge) — Optional

- Monitors CI/CD consensus (PASSING, FAILING, PENDING, MIXED)
- Automatically merges PRs after all checks pass
- Handles GitHub rate limits with intelligent backoff

## Components

### Core Agents

| Agent | File | Purpose |
|-------|------|---------|
| Planner | `agents/architect/planner.py` | Decomposes issues into sub-tasks with dependency graph |
| Orchestrator | `agents/architect/orchestrator.py` | Manages parallel worker execution waves |
| Validator | `agents/architect/validator.py` | Reviews PRs — CI, code quality, auto-approve |
| Integrator | `agents/architect/integrator.py` | Merges approved PRs, creates summary |
| Worker Executor | `agents/worker/executor.py` | Clone → branch → code → commit → push → PR |

### Enhanced Components

| Component | File | Purpose |
|-----------|------|---------|
| AutoMerge | `agents/architect/auto_merge.py` | CI/CD consensus monitoring, auto-merge with rate-limit retry |
| TaskSplitter | `agents/architect/task_splitter.py` | Decomposes issues into sub-issues (checklist → sections → phases) |
| EnhancedWorker | `agents/worker/enhanced_worker.py` | Full pipeline worker with rate-limit retry and auto-merge |

### Next-Gen Worker

| Component | File | Purpose |
|-----------|------|---------|
| Hive Worker | `hive_worker.py` | Full pipeline worker with agent-commander integration |
| Agent Commander Bridge | `agent_commander_bridge.py` | Python wrapper for agent-commander CLI |
| Issue Templates | `issue_templates.py` | Prompt generators for different task types |

### Shared Libraries

| Module | File | Purpose |
|--------|------|---------|
| GitHubClient | `agents/shared/github_client.py` | Python wrapper over `gh` CLI (issues, PRs, CI) |
| GitClient | `agents/shared/git_client.py` | Python wrapper over `git` CLI (clone, commit, push) |
| TaskGraph | `agents/shared/task_graph.py` | DAG for task dependency management |
| GitHubRetry | `agents/shared/github_retry.py` | Rate-limit detection, retry with backoff, terminal state handling |

### CLI Scripts

| Script | Files | Purpose |
|--------|-------|---------|
| hive-solve | `scripts/hive-solve.sh` / `.ps1` | Solve a single issue |
| hive-batch | `scripts/hive-batch.sh` / `.ps1` | Batch process multiple issues |
| hive-status | `scripts/hive-status.sh` / `.ps1` | Show worker status and open PRs |
| hive-stop | `scripts/hive-stop.sh` / `.ps1` | Stop all running workers |
| hive-dev | `scripts/hive-dev.ps1` | Main development workflow (solve, status, stop, split) |
| hive-issue | `scripts/hive-issue.ps1` | Issue CRUD operations (list, create, view, close, comment) |
| hive-pr | `scripts/hive-pr.ps1` | PR management (list, view, checks, merge, approve) |
| architect | `scripts/architect.py` | Direct Architect CLI entry point |
| worker | `scripts/worker.py` | Direct Worker CLI entry point |

### Skills (GitHub Workflow Guides)

| Skill | File | Purpose |
|-------|------|---------|
| Git Branch Manager | `skills/git-branch-manager.md` | Branch naming conventions and operations |
| Git Fork & Clone | `skills/git-fork-clone.md` | Fork workflow and upstream sync |
| Git Commit & Push | `skills/git-commit-push.md` | Conventional commits format |
| GitHub Issue Manager | `skills/github-issue-manager.md` | Issue CRUD operations |
| GitHub PR Creator | `skills/github-pr-creator.md` | PR creation with templates |
| GitHub PR Reviewer | `skills/github-pr-reviewer.md` | PR review checklist |
| GitHub PR Merger | `skills/github-pr-merger.md` | Merge strategies (squash/merge/rebase) |

## Prerequisites

### Required

- **Python 3.10+** — [Download](https://www.python.org/downloads/)
- **GitHub CLI (`gh`)** — [Install guide](https://github.com/cli/cli#installation)
  - Must be authenticated: `gh auth login`
  - Must have `repo` and `read:org` scopes
- **Git** — [Download](https://git-scm.com/downloads)

### Optional

- **Docker** — For Docker isolation mode
- **GNU Screen** — For Screen isolation mode
- **AI Agent CLI** — One of:
  - Claude Code (recommended)
  - OpenAI Codex
  - Gemini CLI

### Verify Prerequisites

```bash
python3 --version  # >= 3.10
gh --version
gh auth status     # Should show "Logged in"
git --version
```

## Installation

### From Source

```bash
git clone https://github.com/xdevrobot/hive-mind-system.git
cd hive-mind-system

python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or: .venv\Scripts\Activate.ps1  # Windows

pip install -e ".[dev]"

python -c "from agents.shared.github_client import GitHubClient; print('OK')"
```

## Quick Start

### Solve a Single Issue

```bash
# Bash
./scripts/hive-solve.sh owner/repo 58

# PowerShell (Windows)
.\scripts\hive-solve.ps1 -Repo owner/repo -Issue 58

# Python directly
python hive_worker.py --task-id T1 --issue 58 --repo owner/repo

# Full pipeline
python autonomous_dev_orchestrator.py --repo owner/repo --issue 58
```

### Batch Process Multiple Issues

```bash
cat > issues.txt << EOF
58
59
60
EOF

./scripts/hive-batch.sh owner/repo issues.txt

# With fork
./scripts/hive-batch.sh owner/repo issues.txt --fork your-user/your-fork
```

### Split an Issue into Sub-Issues

```powershell
# Decompose issue #58 into 5 sub-issues on GitHub
.\scripts\hive-dev.ps1 -Repo owner/repo -Issue 58 -Split 5
```

### Check Status

```bash
./scripts/hive-status.sh owner/repo
.\scripts\hive-dev.ps1 -Repo owner/repo -Status
```

### Stop All Workers

```bash
./scripts/hive-stop.sh owner/repo
.\scripts\hive-dev.ps1 -Repo owner/repo -Stop
```

## Usage

### hive-solve — Single Issue

```bash
./scripts/hive-solve.sh <repo> <issue-number>
./scripts/hive-solve.sh <repo> <issue-number> <fork>
./scripts/hive-solve.sh <repo> <issue-number> <fork> codex
./scripts/hive-solve.sh <repo> <issue-number> -- --auto-merge
```

### hive-batch — Multiple Issues

```bash
./scripts/hive-batch.sh <repo> <issue-list-file>
./scripts/hive-batch.sh <repo> <issue-list-file> <fork> 5
```

### hive-dev — Main Development Workflow

```powershell
# Solve an issue
.\scripts\hive-dev.ps1 -Repo owner/repo -Issue 58

# Split and solve
.\scripts\hive-dev.ps1 -Repo owner/repo -Issue 58 -Split 5 -AutoMerge

# Dry run (plan only)
.\scripts\hive-dev.ps1 -Repo owner/repo -Issue 58 -DryRun

# Check status
.\scripts\hive-dev.ps1 -Repo owner/repo -Status

# Stop all workers
.\scripts\hive-dev.ps1 -Repo owner/repo -Stop
```

### hive-issue — Issue Management

```powershell
.\scripts\hive-issue.ps1 -Action list
.\scripts\hive-issue.ps1 -Action create -Title "New feature" -Body "Description"
.\scripts\hive-issue.ps1 -Action view -Issue 58
.\scripts\hive-issue.ps1 -Action close -Issue 58
.\scripts\hive-issue.ps1 -Action comment -Issue 58 -Comment "Done!"
```

### hive-pr — PR Management

```powershell
.\scripts\hive-pr.ps1 -Action list
.\scripts\hive-pr.ps1 -Action view -PR 42
.\scripts\hive-pr.ps1 -Action checks -PR 42
.\scripts\hive-pr.ps1 -Action merge -PR 42
.\scripts\hive-pr.ps1 -Action approve -PR 42 -Comment "LGTM!"
```

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GITHUB_TOKEN` | GitHub personal access token | Yes* |
| `GH_TOKEN` | Alternative GitHub token | Yes* |
| `ANTHROPIC_API_KEY` | Anthropic API key (for Claude) | For Claude |
| `OPENAI_API_KEY` | OpenAI API key (for Codex) | For Codex |

*Either set a token or authenticate via `gh auth login`.

### CLI Flags

#### autonomous_dev_orchestrator.py

| Flag | Default | Description |
|------|---------|-------------|
| `--repo` | required | Repository (owner/repo) |
| `--issue` | — | Single issue number |
| `--issue-list` | — | File with issue numbers |
| `--fork` | — | Fork (owner/repo) |
| `--base-branch` | main | Base branch |
| `--max-workers` | 3 | Max parallel workers |
| `--tool` | claude | AI tool (claude/codex/gemini) |
| `--timeout` | 3600 | Timeout per task (seconds) |
| `--isolation` | direct | Isolation mode |
| `--auto-merge` | false | Auto-merge after CI pass |
| `--dry-run` | false | Plan only, don't execute |
| `--json` | false | Output JSON |

#### hive_worker.py

| Flag | Default | Description |
|------|---------|-------------|
| `--task-id` | required | Task identifier |
| `--issue` | required | Issue number |
| `--repo` | required | Repository (owner/repo) |
| `--fork` | — | Fork (owner/repo) |
| `--tool` | claude | AI tool |
| `--model` | — | Model name |
| `--timeout` | 3600 | Timeout (seconds) |
| `--isolation` | direct | direct/screen/docker |
| `--auto-merge` | false | Auto-merge after CI |
| `--draft` | false | Create draft PR |
| `--working-dir` | — | Working directory (empty = temp) |
| `--keep` | false | Keep working directory |
| `--json` | false | Output JSON |

## API Reference

### GitHubClient — GitHub Operations

```python
from agents.shared.github_client import GitHubClient

gh = GitHubClient(repo="owner/repo")

# Issues
issues = gh.list_issues(state="open", labels=["bug"])
issue = gh.view_issue(58)
new_issue = gh.create_issue(title="Bug fix", body="...", labels=["bug"])
gh.close_issue(58)

# PRs
prs = gh.list_prs(state="open")
pr = gh.create_pr(title="Fix", body="...", head="feature-branch")
gh.merge_pr(pr.number, method="squash")
checks = gh.get_pr_checks(pr.number)
```

### GitHubRetry — Rate-Limit Resilient Operations

```python
from agents.shared.github_retry import retry_with_rate_limit, is_rate_limit_error

# Automatic retry with rate-limit awareness
# Wait policy: (resetTimestamp - now) + 10min buffer + random(0-5min) jitter
result = retry_with_rate_limit(lambda: gh.create_pr(title="...", ...))

# Check if an error is a rate-limit response
if is_rate_limit_error(error):
    # Handle rate limit
    pass
```

### Planner — Issue Decomposition

```python
from agents.architect.planner import Planner

planner = Planner(gh)
plan = planner.decompose(issue_number=58, subtask_count=3)
print(f"Created {len(plan.tasks)} sub-tasks")
```

### TaskSplitter — Create Sub-Issues on GitHub

```python
from agents.architect.task_splitter import TaskSplitter

splitter = TaskSplitter(gh)
result = splitter.split_and_create(issue_number=58, subtask_count=5)
# Creates 5 sub-issues linked to the parent
for task in result.subtasks:
    print(f"  #{task.issue_number}: {task.title}")
```

### Orchestrator — Parallel Execution

```python
from agents.architect.orchestrator import Orchestrator, OrchestratorConfig

config = OrchestratorConfig(max_parallel_workers=3, timeout=3600)
orchestrator = Orchestrator(gh, config)
result = orchestrator.run(
    task_graph=plan.task_graph,
    repo_url="https://github.com/owner/repo",
    base_branch="main",
)
print(f"Completed: {result.completed}/{result.total_tasks}")
print(f"Duration: {result.duration_seconds:.1f}s")
```

### AutoMerge — CI/CD Auto-Merge

```python
from agents.architect.auto_merge import AutoMerge, MergeConfig

config = MergeConfig(
    require_ci_pass=True,
    merge_method="squash",
    poll_interval=30,
    timeout=600,
)
auto = AutoMerge(gh, config)

# Auto-merge a single PR
auto.auto_merge(pr_number=42)

# Auto-merge multiple PRs sequentially
results = auto.auto_merge_all([42, 43, 44])
```

### EnhancedWorker — Full Pipeline

```python
from agents.worker.enhanced_worker import run_worker

result = run_worker(
    task_id="T1",
    issue_number=58,
    repo="owner/repo",
    fork="user/fork",
    auto_merge=True,
    json_output=True,
)
```

## Isolation Modes

Workers can run in different isolation modes depending on your needs:

### Direct Mode (`--isolation direct`)

The agent runs directly in the current process. Fastest, but no isolation.

```bash
python hive_worker.py --task-id T1 --issue 58 --repo owner/repo --isolation direct
```

**Use when:** Local development, trusted code, quick iterations.

### Screen Mode (`--isolation screen`)

The agent runs in a detached GNU Screen session. Survives terminal disconnects.

```bash
python hive_worker.py --task-id T1 --issue 58 --repo owner/repo --isolation screen
```

**Use when:** Long-running tasks, remote servers, need to disconnect.

**Requirements:** GNU Screen installed (`apt install screen`).

### Docker Mode (`--isolation docker`)

The agent runs in an isolated Docker container. Maximum isolation.

```bash
python hive_worker.py --task-id T1 --issue 58 --repo owner/repo --isolation docker
```

**Use when:** Production, CI/CD, untrusted code, reproducibility.

**Requirements:** Docker installed and running.

### Comparison

| Feature | Direct | Screen | Docker |
|---------|--------|--------|--------|
| Speed | ★★★★★ | ★★★★ | ★★★ |
| Isolation | ★ | ★★ | ★★★★★ |
| Persistence | ★★ | ★★★★ | ★★★ |
| Reproducibility | ★★ | ★★ | ★★★★★ |
| Setup complexity | ★ | ★★ | ★★★★ |

## Skills

Hive Mind includes a library of skills — markdown guides for common GitHub workflows. These are used by the AI agents as context for how to perform operations correctly.

### Available Skills

| Skill | Description |
|-------|-------------|
| Git Branch Manager | Branch naming conventions (`hive/<issue>-<hex>`), creation, deletion |
| Git Fork & Clone | Fork workflow, upstream remote, sync |
| Git Commit & Push | Conventional commits (`feat:`, `fix:`, `chore:`), push workflow |
| GitHub Issue Manager | Create, view, close, comment on issues |
| GitHub PR Creator | PR creation with templates, linking to issues |
| GitHub PR Reviewer | Review checklist, approve/request changes |
| GitHub PR Merger | Merge strategies, auto-merge, delete branch |

### Using Skills

Skills are automatically referenced by the AI agent based on the task type. You can also reference them manually:

```bash
cat skills/git-branch-manager.md
```

## Development

### Running Tests

```bash
pytest
pytest --cov=agents --cov-report=html
pytest tests/test_task_graph.py
pytest tests/test_planner.py::TestPlanner
pytest -v
```

### Code Quality

```bash
black agents/ scripts/ tests/
isort agents/ scripts/ tests/
flake8 agents/ scripts/ tests/
mypy agents/
```

### Adding a New Agent

1. Create the agent class in `agents/<category>/`
2. Add `__init__.py` exports
3. Add type hints and docstrings
4. Add retry logic for GitHub API calls using `retry_with_rate_limit`
5. Create tests in `tests/test_<agent>.py`
6. Add CLI script in `scripts/` if needed
7. Update this README

### Adding a New Skill

1. Create a markdown file in `skills/`
2. Follow the existing format (title, sections, code blocks, rules)
3. Reference it from the appropriate agent

## Project Structure

```
hive-mind-system/
├── README.md
├── pyproject.toml
├── setup.py
├── conftest.py
├── __main__.py
├── autonomous_dev_orchestrator.py
├── hive_worker.py
├── agent_commander_bridge.py
├── issue_templates.py
├── docs/
│   └── guides/
│       └── hive-mind.md          # Comprehensive Python API guide
├── agents/
│   ├── __init__.py
│   ├── architect/
│   │   ├── __init__.py
│   │   ├── planner.py            # Issue decomposition
│   │   ├── orchestrator.py       # Parallel wave execution
│   │   ├── validator.py          # PR review, CI checks
│   │   ├── integrator.py         # Merge, summary
│   │   ├── auto_merge.py         # CI/CD auto-merge
│   │   └── task_splitter.py      # Issue → sub-issues
│   ├── worker/
│   │   ├── __init__.py
│   │   ├── executor.py           # Base worker pipeline
│   │   └── enhanced_worker.py    # Worker with retry + auto-merge
│   └── shared/
│       ├── __init__.py
│       ├── github_client.py      # gh CLI wrapper
│       ├── git_client.py         # git CLI wrapper
│       ├── github_retry.py       # Rate-limit retry, terminal state
│       └── task_graph.py         # DAG for task dependencies
├── scripts/
│   ├── __init__.py
│   ├── architect.py
│   ├── worker.py
│   ├── hive-solve.sh / .ps1
│   ├── hive-batch.sh / .ps1
│   ├── hive-status.sh / .ps1
│   ├── hive-stop.sh / .ps1
│   ├── hive-dev.ps1              # Main dev workflow
│   ├── hive-issue.ps1            # Issue CRUD
│   └── hive-pr.ps1               # PR management
├── skills/
│   ├── git-branch-manager.md
│   ├── git-fork-clone.md
│   ├── git-commit-push.md
│   ├── github-issue-manager.md
│   ├── github-pr-creator.md
│   ├── github-pr-reviewer.md
│   └── github-pr-merger.md
└── tests/
    ├── __init__.py
    ├── test_task_graph.py
    ├── test_planner.py
    ├── test_git_client.py
    ├── test_orchestrator.py
    ├── test_validator.py
    └── test_integrator.py
```

## Credits

This system combines concepts from two excellent projects:

- [xdevrobot/hive-mind-system](https://github.com/xdevrobot/hive-mind-system) — Python multi-agent orchestration framework
- [link-assistant/hive-mind](https://github.com/link-assistant/hive-mind) — Rate-limit retry patterns, auto-merge with CI/CD consensus, task splitting, terminal state detection

## License

MIT License

Contributing: Fork, create a feature branch, make changes, run tests, and open a PR.
