# Hive Mind — Полное руководство

## Обзор архитектуры

Hive Mind — автономная мультиагентная система разработки на GitHub.
Основана на двух проектах:
- **xdevrobot/hive-mind-system** — Python-реализация (Planner, Orchestrator, Worker)
- **link-assistant/hive-mind** — JS/TS-реализация (rate-limit retry, auto-merge, task split)

### Пайплайн

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

## Компоненты

### Shared Libraries

| Модуль | Назначение |
|---|---|
| `github_client.py` | Python-обёртка над `gh` CLI (issues, PRs, CI) |
| `git_client.py` | Python-обёртка над `git` CLI (clone, commit, push) |
| `github_retry.py` | Rate-limit detection, retry with backoff, terminal state detection |
| `task_graph.py` | DAG для управления зависимостями задач |

### Architect Agents

| Агент | Назначение |
|---|---|
| **Planner** | Разбивает Issue на подзадачи (checklist → секции → фазы) |
| **TaskSplitter** | Декомпозиция issues в под-issues на GitHub |
| **Orchestrator** | Волновое параллельное исполнение воркеров |
| **Validator** | Проверяет CI, сканирует качество кода |
| **AutoMerge** | Автоматический мердж после CI с rate-limit retry |
| **Integrator** | Squash-merge, сводный PR, отчёт |

### Workers

| Воркер | Назначение |
|---|---|
| **WorkerExecutor** | Базовый: clone → branch → code → commit → push → PR |
| **EnhancedHiveWorker** | Улучшенный: + rate-limit retry, auto-merge, terminal state detection |

## Rate-Limit Retry

Автоматические повторы при 429 от GitHub API:

```python
from agents.shared.github_retry import retry_with_rate_limit

# Автоматический retry с вычислением времени ожидания
result = retry_with_rate_limit(lambda: gh.create_pr(title="...", ...))
```

Политика ожидания: `wait = (resetTimestamp - now) + 10min + random(0-5min)`

## Terminal State Detection

Обнаружение необратимых состояний (404, 410, удалённые репозитории):

```python
from agents.shared.github_retry import is_terminal_entity_error

if is_terminal_entity_error(error):
    # Не повторять — сущность удалена или недоступна
    logger.error("Terminal: %s", error)
```

## Auto-Merge

Автоматический мердж PR после прохождения CI:

```python
from agents.architect.auto_merge import AutoMerge, MergeConfig

config = MergeConfig(
    require_ci_pass=True,
    merge_method="squash",
    poll_interval=30,
    timeout=600,
)
auto = AutoMerge(gh_client, config)
auto.auto_merge(pr_number)
```

## Task Split

Разбиение issue на под-issues:

```python
from agents.architect.task_splitter import TaskSplitter

splitter = TaskSplitter(gh_client)
result = splitter.split_and_create(issue_number=58, subtask_count=5)
```

## PowerShell скрипты

```powershell
# Разработка по Issue
.\scripts\hive-dev.ps1 -Repo owner/repo -Issue 58

# Разбиение issue на под-issues
.\scripts\hive-dev.ps1 -Repo owner/repo -Issue 58 -Split 5

# Авто-мердж
.\scripts\hive-dev.ps1 -Repo owner/repo -Issue 58 -AutoMerge

# Управление Issues
.\scripts\hive-issue.ps1 -Action list
.\scripts\hive-issue.ps1 -Action create -Title "Feature" -Body "..."

# Управление PR
.\scripts\hive-pr.ps1 -Action list
.\scripts\hive-pr.ps1 -Action merge -PR 42

# Мониторинг
.\scripts\hive-dev.ps1 -Status -Repo owner/repo
.\scripts\hive-dev.ps1 -Stop -Repo owner/repo
```

## Python API

```python
from agents import (
    GitHubClient, Planner, Orchestrator, OrchestratorConfig,
    AutoMerge, MergeConfig, TaskSplitter, run_worker,
    retry_with_rate_limit,
)

# Полный пайплайн
gh = GitHubClient(repo="owner/repo")
planner = Planner(gh)
plan = planner.decompose(issue_number=58, subtask_count=3)

config = OrchestratorConfig(max_parallel_workers=3, timeout=3600)
orchestrator = Orchestrator(gh, config)
result = orchestrator.run(
    task_graph=plan.task_graph,
    repo_url="https://github.com/owner/repo",
    base_branch="main",
)

# Или напрямую через worker
result = run_worker(
    task_id="T1", issue_number=58, repo="owner/repo",
    auto_merge=True, json_output=True,
)
```
