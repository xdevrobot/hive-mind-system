# hive-stop.ps1 - Stop all Hive Mind workers
param(
    [Parameter(Mandatory=$true)][string]$Repo
)

Write-Host "Hive Mind: Stopping all workers for ${Repo}"

Get-Process -Name "python" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match "hive_worker|architect" } |
    Stop-Process -Force -ErrorAction SilentlyContinue

docker ps --filter "name=hive-agent" --format "{{.Names}}" 2>$null |
    ForEach-Object { docker stop --time 30 $_ 2>$null }

Write-Host "All Hive Mind workers stopped"
