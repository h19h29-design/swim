$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $ScriptRoot 'lib.ps1')

$projectRoot = Get-ProjectRoot -ScriptRoot $ScriptRoot
$config = Load-Config -ProjectRoot $projectRoot
$taskPrefix = $config.task_prefix
$runCycle = Join-Path $projectRoot 'run_cycle.ps1'
$startServer = Join-Path $projectRoot 'start_server.ps1'

$runCmd = 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "' + $runCycle + '"'
$serverCmd = 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "' + $startServer + '"'

foreach ($time in $config.scheduler_times) {
    $safe = $time.Replace(':','')
    $taskName = "$taskPrefix`_Cycle_$safe"
    schtasks /Create /F /SC DAILY /ST $time /TN $taskName /TR $runCmd | Out-Host
}

$serverTask = "$taskPrefix`_Server_OnLogon"
schtasks /Create /F /SC ONLOGON /TN $serverTask /TR $serverCmd | Out-Host

Write-Host '작업 스케줄러 등록 완료' -ForegroundColor Green
