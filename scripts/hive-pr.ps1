# Hive Mind — Управление Pull Request'ами
#
# Использование:
#   .\scripts\hive-pr.ps1 -Repo owner/repo -Action list
#   .\scripts\hive-pr.ps1 -Repo owner/repo -Action view -PR 42
#   .\scripts\hive-pr.ps1 -Repo owner/repo -Action checks -PR 42
#   .\scripts\hive-pr.ps1 -Repo owner/repo -Action merge -PR 42
#   .\scripts\hive-pr.ps1 -Repo owner/repo -Action approve -PR 42 -Comment "LGTM"

param(
    [string]$Repo = "",
    [ValidateSet("list", "view", "checks", "merge", "approve", "close")]
    [string]$Action = "list",
    [int]$PR = 0,
    [string]$Comment = "",
    [ValidateSet("squash", "merge", "rebase")]
    [string]$Strategy = "squash"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$envFile = Join-Path (Split-Path $PSScriptRoot -Parent) "configs\.env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)\s*=\s*(.+)\s*$') {
            [Environment]::SetEnvironmentVariable($Matches[1].Trim(), $Matches[2].Trim(), "Process")
        }
    }
}
if (-not $Repo) { $Repo = $env:HIVE_TARGET_REPO }
if (-not $Repo) { Write-Error "Укажите -Repo"; exit 1 }

switch ($Action) {
    "list" {
        gh pr list --repo $Repo --state open --limit 30
    }
    "view" {
        if ($PR -eq 0) { Write-Error "Укажите -PR"; exit 1 }
        gh pr view $PR --repo $Repo
    }
    "checks" {
        if ($PR -eq 0) { Write-Error "Укажите -PR"; exit 1 }
        gh pr checks $PR --repo $Repo
    }
    "merge" {
        if ($PR -eq 0) { Write-Error "Укажите -PR"; exit 1 }
        gh pr merge $PR --repo $Repo --$Strategy --delete-branch
    }
    "approve" {
        if ($PR -eq 0) { Write-Error "Укажите -PR"; exit 1 }
        $body = if ($Comment) { $Comment } else { "Approved by Hive Mind" }
        gh pr review $PR --repo $Repo --approve --body $body
    }
    "close" {
        if ($PR -eq 0) { Write-Error "Укажите -PR"; exit 1 }
        gh pr close $PR --repo $Repo
    }
}
