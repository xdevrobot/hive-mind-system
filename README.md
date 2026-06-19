🐝 Hive Mind — Autonomous Multi-Agent Development System

Python 3.10+ | MIT License | Code style: black

Hive Mind is an autonomous development system that uses AI agents to plan, execute, review, and merge code changes based on GitHub issues. Point it at a repository and an issue, and it will:

1. Decompose the issue into parallelizable sub-tasks
2. Execute each sub-task with an isolated AI worker agent
3. Review the resulting pull requests (CI, code quality)
4. Merge approved PRs and generate a summary report

## Table of Contents

- Architecture
- How It Works
- Components
- Prerequisites
- Installation
- Quick Start
- Usage
- Configuration
- Isolation Modes
- Skills
- Development
- Project Structure
- License

## Architecture

Hive Mind consists of four main agents:

Planner → Orchestrator → Validator → Integrator

The Planner decomposes issues into sub-tasks with a dependency graph. The Orchestrator executes workers in parallel waves. The Validator reviews PRs for CI and code quality. The Integrator merges approved PRs.

Each Worker clones the repo, creates a feature branch, runs an AI agent to implement changes, commits, pushes, and creates a PR.

## How It Works

Phase 1: Plan (Planner)
- Fetches the GitHub issue
- Parses checklists (- [ ] items) and section headers (##)
- Falls back to logical phases if no structure found
- Builds a DAG of dependent tasks

Phase 2: Execute (Orchestrator + Workers)
- Wave execution: tasks at the same dependency level run in parallel
- Configurable concurrency (--max-workers)
- Fork support for safe isolation
- Each Worker: Clone → Branch → Code → Commit → Push → PR

Phase 3: Review (Validator)
- CI status checks
- Code quality scan (TODOs, debug statements, diff size)
- Auto-approve for passing PRs
- Flag for manual review when needed

Phase 4: Integrate (Integrator)
- Squash merge into base branch
- Create summary PR linking all sub-PRs
- Generate markdown report

## Components

### Core Agents

| Agent | File | Purpose |
|-------|------|---------|
| Planner | agents/architect/planner.py | Decomposes issues into sub-tasks with dependency graph |
| Orchestrator | agents/architect/orchestrator.py | Manages parallel worker execution waves |
| Validator | agents/architect/validator.py | Reviews PRs — CI, code quality, auto-approve |
| Integrator | agents/architect/integrator.py | Merges approved PRs, creates summary |
| Worker Executor | agents/worker/executor.py | Clone → branch → code → commit → push → PR |
| Worker Reporter | agents/worker/reporter.py | Reports worker status back to GitHub issue |

### Next-Gen Worker

| Component | File | Purpose |
|-----------|------|---------|
| Hive Worker | hive_worker.py | Full pipeline worker with agent-commander integration |
| Agent Commander Bridge | agent_commander_bridge.py | Python wrapper for agent-commander CLI |
| Issue Templates | issue_templates.py | Prompt generators for different task types |

### Shared Libraries

| Module | File | Purpose |
|--------|------|---------|
| GitHubClient | agents/shared/github_client.py | Python wrapper over gh CLI (issues, PRs, CI) |
| GitClient | agents/shared/git_client.py | Python wrapper over git CLI (clone, commit, push) |
| TaskGraph | agents/shared/task_graph.py | DAG for task dependency management |

### CLI Scripts

| Script | Files | Purpose |
|--------|-------|---------|
| hive-solve | scripts/hive-solve.sh / .ps1 | Solve a single issue |
| hive-batch | scripts/hive-batch.sh / .ps1 | Batch process multiple issues |
| hive-status | scripts/hive-status.sh / .ps1 | Show worker status and open PRs |
| hive-stop | scripts/hive-stop.sh / .ps1 | Stop all running workers |
| architect | scripts/architect.py | Direct Architect CLI entry point |
| worker | scripts/worker.py | Direct Worker CLI entry point |

### Skills (GitHub Workflow Guides)

| Skill | File | Purpose |
|-------|------|---------|
| Git Branch Manager | skills/git-branch-manager.md | Branch naming conventions and operations |
| Git Fork & Clone | skills/git-fork-clone.md | Fork workflow and upstream sync |
| Git Commit & Push | skills/git-commit-push.md | Conventional commits format |
| GitHub Issue Manager | skills/github-issue-manager.md | Issue CRUD operations |
| GitHub PR Creator | skills/github-pr-creator.md | PR creation with templates |
| GitHub PR Reviewer | skills/github-pr-reviewer.md | PR review checklist |
| GitHub PR Merger | skills/github-pr-merger.md | Merge strategies (squash/merge/rebase) |

## Prerequisites

### Required

- Python 3.10+ — Download
- GitHub CLI (gh) — Install guide
  - Must be authenticated: gh auth login
  - Must have repo and read:org scopes
- Git — Download

### Optional

- Docker — For Docker isolation mode
- GNU Screen — For Screen isolation mode
- AI Agent CLI — One of:
  - Claude Code (recommended)
  - OpenAI Codex
  - Gemini CLI

### Verify Prerequisites

python3 --version  # >= 3.10
gh --version
gh auth status     # Should show Logged in
git --version

## Installation

### From Source

git clone https://github.com/xdevrobot/hive-mind-system.git
cd hive-mind-system

python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or: .venv\Scripts\Activate.ps1  # Windows

pip install -e ".[dev]"

python -c "from agents.shared.github_client import GitHubClient; print('OK')"

## Quick Start

### Solve a Single Issue

./scripts/hive-solve.sh owner/repo 58

# PowerShell (Windows)
.\scripts\hive-solve.ps1 -Repo owner/repo -Issue 58

# Python directly
python hive_worker.py --task-id T1 --issue 58 --repo owner/repo

# Full pipeline
python autonomous_dev_orchestrator.py --repo owner/repo --issue 58

### Batch Process Multiple Issues

cat > issues.txt << EOF
58
59
60
EOF

./scripts/hive-batch.sh owner/repo issues.txt

# With fork
./scripts/hive-batch.sh owner/repo issues.txt --fork your-user/your-fork

### Check Status

./scripts/hive-status.sh owner/repo

### Stop All Workers

./scripts/hive-stop.sh owner/repo

## Usage

### hive-solve — Single Issue

./scripts/hive-solve.sh <repo> <issue-number>
./scripts/hive-solve.sh <repo> <issue-number> <fork>
./scripts/hive-solve.sh <repo> <issue-number> <fork> codex
./scripts/hive-solve.sh <repo> <issue-number> -- --auto-merge

### hive-batch — Multiple Issues

./scripts/hive-batch.sh <repo> <issue-list-file>
./scripts/hive-batch.sh <repo> <issue-list-file> <fork> 5

### Python API

from agents.architect.planner import Planner
from agents.architect.orchestrator import Orchestrator, OrchestratorConfig
from agents.shared.github_client import GitHubClient

gh = GitHubClient(repo="owner/repo")
planner = Planner(gh)
plan = planner.decompose(issue_number=58, subtask_count=3)
print(f"Created {len(plan.tasks)} sub-tasks")

config = OrchestratorConfig(max_parallel_workers=3, timeout=3600)
orchestrator = Orchestrator(gh, config)
result = orchestrator.run(
    task_graph=plan.task_graph,
    repo_url="https://github.com/owner/repo",
    fork_url="https://github.com/your-user/repo",
    base_branch="main",
)

print(f"Completed: {result.completed}/{result.total_tasks}")
print(f"Duration: {result.duration_seconds:.1f}s")

### Hive Worker — Direct Worker Control

python hive_worker.py \
    --task-id T1 \
    --issue 58 \
    --repo owner/repo \
    --fork your-user/repo \
    --tool claude \
    --timeout 3600 \
    --isolation direct \
    --json

### Agent Commander Bridge — Run Any AI Agent

from agent_commander_bridge import AgentCommanderBridge, AgentConfig, IsolationMode

bridge = AgentCommanderBridge()
result = bridge.start_agent(
    config=AgentConfig(
        tool="claude",
        working_dir="/path/to/repo",
        prompt="Fix the security vulnerability in issue #58",
        model="claude-opus-4-8",
        timeout=3600,
    ),
    isolation=IsolationMode.DIRECT,
)

print(f"Success: {result.success}")
print(f"Duration: {result.duration_seconds:.1f}s")
print(f"Output: {result.stdout[:500]}")

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| GITHUB_TOKEN | GitHub personal access token | Yes* |
| GH_TOKEN | Alternative GitHub token | Yes* |
| ANTHROPIC_API_KEY | Anthropic API key (for Claude) | For Claude |
| OPENAI_API_KEY | OpenAI API key (for Codex) | For Codex |

* Either set a token or authenticate via gh auth login.

### CLI Flags

#### autonomous_dev_orchestrator.py

| Flag | Default | Description |
|------|---------|-------------|
| --repo | required | Repository (owner/repo) |
| --issue | — | Single issue number |
| --issue-list | — | File with issue numbers |
| --fork | — | Fork (owner/repo) |
| --base-branch | main | Base branch |
| --max-workers | 3 | Max parallel workers |
| --tool | claude | AI tool (claude/codex/gemini) |
| --timeout | 3600 | Timeout per task (seconds) |
| --isolation | direct | Isolation mode |
| --auto-merge | false | Auto-merge after CI pass |
| --dry-run | false | Plan only, don't execute |
| --json | false | Output JSON |

#### hive_worker.py

| Flag | Default | Description |
|------|---------|-------------|
| --task-id | required | Task identifier |
| --issue | required | Issue number |
| --repo | required | Repository (owner/repo) |
| --fork | — | Fork (owner/repo) |
| --tool | claude | AI tool |
| --model | — | Model name |
| --timeout | 3600 | Timeout (seconds) |
| --isolation | direct | direct/screen/docker |
| --auto-merge | false | Auto-merge after CI |
| --draft | false | Create draft PR |
| --working-dir | — | Working directory (empty = temp) |
| --keep | false | Keep working directory |
| --json | false | Output JSON |

## Isolation Modes

Workers can run in different isolation modes depending on your needs:

### Direct Mode (--isolation direct)

The agent runs directly in the current process. Fastest, but no isolation.

python hive_worker.py --task-id T1 --issue 58 --repo owner/repo --isolation direct

Use when: Local development, trusted code, quick iterations.

### Screen Mode (--isolation screen)

The agent runs in a detached GNU Screen session. Survives terminal disconnects.

python hive_worker.py --task-id T1 --issue 58 --repo owner/repo --isolation screen

Use when: Long-running tasks, remote servers, need to disconnect.

Requirements: GNU Screen installed (apt install screen).

### Docker Mode (--isolation docker)

The agent runs in an isolated Docker container. Maximum isolation.

python hive_worker.py --task-id T1 --issue 58 --repo owner/repo --isolation docker

Use when: Production, CI/CD, untrusted code, reproducibility.

Requirements: Docker installed and running.

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
| Git Branch Manager | Branch naming conventions (hive/<issue>-<hex>), creation, deletion |
| Git Fork & Clone | Fork workflow, upstream remote, sync |
| Git Commit & Push | Conventional commits (feat:, fix:, chore:), push workflow |
| GitHub Issue Manager | Create, view, close, comment on issues |
| GitHub PR Creator | PR creation with templates, linking to issues |
| GitHub PR Reviewer | Review checklist, approve/request changes |
| GitHub PR Merger | Merge strategies, auto-merge, delete branch |

### Using Skills

Skills are automatically referenced by the AI agent based on the task type. You can also reference them manually:

cat skills/git-branch-manager.md

## Development

### Running Tests

pytest
pytest --cov=agents --cov-report=html
pytest tests/test_task_graph.py
pytest tests/test_planner.py::TestPlanner
pytest tests/test_task_graph.py::TestTaskGraph::test_add_task
pytest -v
pytest -n auto

### Code Quality

black agents/ scripts/ tests/
isort agents/ scripts/ tests/
flake8 agents/ scripts/ tests/
mypy agents/

### Adding a New Agent

1. Create the agent class in agents/<category>/
2. Add __init__.py exports
3. Create tests in tests/test_<agent>.py
4. Add CLI script in scripts/ if needed
5. Update this README

### Adding a New Skill

1. Create a markdown file in skills/
2. Follow the existing format (title, sections, code blocks, rules)
3. Reference it from the appropriate agent

## Project Structure

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
├── agents/
│   ├── __init__.py
│   ├── architect/
│   │   ├── __init__.py
│   │   ├── planner.py
│   │   ├── orchestrator.py
│   │   ├── validator.py
│   │   └── integrator.py
│   ├── worker/
│   │   ├── __init__.py
│   │   ├── executor.py
│   │   └── reporter.py
│   └── shared/
│       ├── __init__.py
│       ├── github_client.py
│       ├── git_client.py
│       └── task_graph.py
├── scripts/
│   ├── __init__.py
│   ├── architect.py
│   ├── worker.py
│   ├── hive-solve.sh / .ps1
│   ├── hive-batch.sh / .ps1
│   ├── hive-status.sh / .ps1
│   └── hive-stop.sh / .ps1
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

## License

MIT License — see LICENSE for details.

Contributing: Fork, create feature branch, make changes, run tests, open PR.

Built with 🐝 by the Hive Mind team