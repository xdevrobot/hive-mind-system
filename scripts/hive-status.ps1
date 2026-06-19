# hive-status.ps1 - Check status of Hive Mind workers
param(
    [Parameter(Mandatory=$true)][string]$Repo
)

Write-Host "Hive Mind: Status for ${Repo}"
Write-Host "---"

Write-Host "Open Hive PRs:"
gh pr list --repo $Repo --label "hive" --state open --json number,title,url `
    --jq '.[] | "  #\(.number): \(.title) (\(.url))"' 2>$null
if ($LASTEXITCODE -ne 0) { Write-Host "  (none)" }

Write-Host ""
Write-Host "Recent Hive commits:"
gh api "repos/$Repo/commits?per_page=5" `
    --jq '.[] | "  \(.sha[:7]): \(.commit.message | split("\n")[0])"' 2>$null
if ($LASTEXITCODE -ne 0) { Write-Host "  (none)" }
