# hive-batch.ps1 - Solve multiple issues using Hive Mind
param(
    [Parameter(Mandatory=$true)][string]$Repo,
    [Parameter(Mandatory=$true)][string]$IssueList,
    [string]$Fork = "",
    [int]$MaxWorkers = 3
)

Write-Host "Hive Mind: Batch solving issues from ${IssueList} in ${Repo}"

$args = @(
    "-m", "scripts.architect",
    "--repo", $Repo,
    "--issue-list", $IssueList,
    "--max-workers", $MaxWorkers,
    "--json"
)

if ($Fork) { $args += @("--fork", $Fork) }

python @args

Write-Host "Batch complete!"
