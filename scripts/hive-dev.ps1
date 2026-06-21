# Hive Mind — Главный скрипт разработки на GitHub (PowerShell)
#
# Использование:
#   .\scripts\hive-dev.ps1 -Repo owner/repo -Issue 58
#   .\scripts\hive-dev.ps1 -Repo owner/repo -Issue 58 -Fork myuser/repo
#   .\scripts\hive-dev.ps1 -Repo owner/repo -Issue 58 -DryRun
#   .\scripts\hive-dev.ps1 -Repo owner/repo -Issue 58 -AutoMerge
#   .\scripts\hive-dev.ps1 -Repo owner/repo -Issue 58 -Split 5
#   .\scripts\hive-dev.ps1 -Repo owner/repo -IssueList issues.txt
#   .\scripts\hive-dev.ps1 -Status -Repo owner/repo
#   .\scripts\hive-dev.ps1 -Stop -Repo owner/repo

param(
    [string]$Repo = "",
    [int]$Issue = 0,
    [string]$IssueList = "",
    [string]$Fork = "",
    [string]$Tool = "claude",
    [int]$MaxWorkers = 3,
    [string]$BaseBranch = "main",
    [switch]$DryRun,
    [switch]$AutoMerge,
    [int]$Split = 0,
    [switch]$Status,
    [switch]$Stop,
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Загрузка .env
$envFile = Join-Path (Split-Path $PSScriptRoot -Parent) "configs\.env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)\s*=\s*(.+)\s*$') {
            $key = $Matches[1].Trim()
            $val = $Matches[2].Trim()
            [Environment]::SetEnvironmentVariable($key, $val, "Process")
        }
    }
}

if ($Repo) { $env:HIVE_TARGET_REPO = $Repo }
if ($Tool) { $env:HIVE_TOOL = $Tool }
if ($MaxWorkers -gt 0) { $env:HIVE_MAX_WORKERS = $MaxWorkers.ToString() }
if ($BaseBranch) { $env:HIVE_BASE_BRANCH = $BaseBranch }

$targetRepo = $env:HIVE_TARGET_REPO
if (-not $targetRepo -and -not $Status) {
    Write-Error "Укажите -Repo или задайте HIVE_TARGET_REPO в configs/.env"
    exit 1
}

Write-Host "=== Hive Mind Development System ===" -ForegroundColor Cyan
if ($targetRepo) { Write-Host "Repo: $targetRepo" -ForegroundColor White }
Write-Host "Tool: $($env:HIVE_TOOL)" -ForegroundColor White
Write-Host "Workers: $($env:HIVE_MAX_WORKERS)" -ForegroundColor White

# === Status ===
if ($Status) {
    Write-Host "`n--- Open Issues ---" -ForegroundColor Yellow
    gh issue list --repo $targetRepo --state open --limit 20
    Write-Host "`n--- Open PRs ---" -ForegroundColor Yellow
    gh pr list --repo $targetRepo --state open --limit 20
    Write-Host "`n--- Recent CI ---" -ForegroundColor Yellow
    gh run list --repo $targetRepo --limit 10
    exit 0
}

# === Stop ===
if ($Stop) {
    Write-Host "Stopping all Hive Mind workers..." -ForegroundColor Yellow
    Get-Process -Name "python" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match "hive_worker|autonomous_dev|enhanced_worker" } |
        Stop-Process -Force
    Write-Host "Stopped." -ForegroundColor Green
    exit 0
}

# === Split Issue ===
if ($Split -gt 0) {
    if ($Issue -eq 0) { Write-Error "Укажите -Issue для разбиения"; exit 1 }
    Write-Host "Splitting issue #$Issue into $Split sub-issues..." -ForegroundColor Yellow
    python -c "
import sys, json
sys.path.insert(0, '.')
from agents.architect.task_splitter import TaskSplitter
from agents.shared.github_client import GitHubClient
gh = GitHubClient(repo='$targetRepo')
splitter = TaskSplitter(gh)
result = splitter.split_and_create($Issue, $Split, link_to_parent=True)
print(f'Created {result.task_count} sub-issues:')
for t in result.subtasks:
    print(f'  #{t.issue_number}: {t.issue_url}')
"
    exit $LASTEXITCODE
}

# === Запуск разработки ===
$orchestratorArgs = @(
    "-m", "autonomous_dev_orchestrator",
    "--repo", $targetRepo,
    "--base-branch", $env:HIVE_BASE_BRANCH,
    "--max-workers", $env:HIVE_MAX_WORKERS,
    "--tool", $env:HIVE_TOOL,
    "--timeout", $env:HIVE_TIMEOUT,
    "--isolation", $env:HIVE_ISOLATION,
    "--merge-strategy", $env:HIVE_MERGE_STRATEGY,
)

if ($Issue -gt 0) {
    $orchestratorArgs += @("--issue", $Issue.ToString())
    Write-Host "Issue: #$Issue" -ForegroundColor White
}
elseif ($IssueList) {
    $orchestratorArgs += @("--issue-list", $IssueList)
    Write-Host "Issue list: $IssueList" -ForegroundColor White
}
else {
    Write-Error "Укажите -Issue <number> или -IssueList <file>"
    exit 1
}

if ($Fork) {
    $orchestratorArgs += @("--fork", $Fork)
    Write-Host "Fork: $Fork" -ForegroundColor White
}
if ($DryRun) {
    $orchestratorArgs += "--dry-run"
    Write-Host "Mode: DRY RUN" -ForegroundColor Yellow
}
if ($AutoMerge) {
    $orchestratorArgs += "--auto-merge"
    Write-Host "Auto-merge: ON" -ForegroundColor Yellow
}
if ($Json) {
    $orchestratorArgs += "--json"
}

Write-Host "`nStarting orchestration..." -ForegroundColor Cyan
& python @orchestratorArgs

if ($LASTEXITCODE -ne 0) {
    Write-Host "`nOrchestration FAILED (exit code $LASTEXITCODE)" -ForegroundColor Red
    exit $LASTEXITCODE
}
Write-Host "`nOrchestration COMPLETE" -ForegroundColor Green
