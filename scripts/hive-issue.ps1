# Hive Mind — Создание и управление Issues на GitHub
#
# Использование:
#   .\scripts\hive-issue.ps1 -Repo owner/repo -Action list
#   .\scripts\hive-issue.ps1 -Repo owner/repo -Action create -Title "New feature" -Body "Description"
#   .\scripts\hive-issue.ps1 -Repo owner/repo -Action view -Issue 58
#   .\scripts\hive-issue.ps1 -Repo owner/repo -Action close -Issue 58
#   .\scripts\hive-issue.ps1 -Repo owner/repo -Action comment -Issue 58 -Comment "Done!"

param(
    [string]$Repo = "",
    [ValidateSet("list", "create", "view", "close", "comment", "label")]
    [string]$Action = "list",
    [int]$Issue = 0,
    [string]$Title = "",
    [string]$Body = "",
    [string]$Comment = "",
    [string[]]$Labels = @()
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Загрузка .env
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
        gh issue list --repo $Repo --state open --limit 30
    }
    "create" {
        if (-not $Title) { Write-Error "Укажите -Title"; exit 1 }
        $args = @("issue", "create", "--repo", $Repo, "--title", $Title, "--body", $Body)
        if ($Labels) { $args += @("--label", ($Labels -join ",")) }
        & gh @args
    }
    "view" {
        if ($Issue -eq 0) { Write-Error "Укажите -Issue"; exit 1 }
        gh issue view $Issue --repo $Repo
    }
    "close" {
        if ($Issue -eq 0) { Write-Error "Укажите -Issue"; exit 1 }
        gh issue close $Issue --repo $Repo
    }
    "comment" {
        if ($Issue -eq 0) { Write-Error "Укажите -Issue"; exit 1 }
        gh issue comment $Issue --repo $Repo --body $Comment
    }
    "label" {
        gh label list --repo $Repo
    }
}
