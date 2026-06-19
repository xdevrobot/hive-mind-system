# hive-solve.ps1 - Solve a single issue using Hive Mind
param(
    [Parameter(Mandatory=$true)][string]$Repo,
    [Parameter(Mandatory=$true)][int]$Issue,
    [string]$Fork = "",
    [string]$Tool = "claude"
)

Write-Host "Hive Mind: Solving issue #${Issue} in ${Repo}"

$args = @(
    "-m", "scripts.worker",
    "--task-id", "solve-${Issue}",
    "--issue", $Issue,
    "--repo", $Repo,
    "--tool", $Tool,
    "--json"
)

if ($Fork) { $args += @("--fork", $Fork) }

python @args

Write-Host "Done!"
