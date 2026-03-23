$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $ScriptRoot 'lib.ps1')

$projectRoot = Get-ProjectRoot -ScriptRoot $ScriptRoot
$config = Load-Config -ProjectRoot $projectRoot
$pythonExe = Ensure-Venv -ProjectRoot $projectRoot -Config $config
$logsDir = Ensure-LogsDir -ProjectRoot $projectRoot
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$logPath = Join-Path $logsDir ("pilot_cycle_$stamp.log")

Start-Transcript -Path $logPath -Append | Out-Null
try {
    Write-Section '자동 수집/리빌드 시작'
    Write-Host "프로젝트: $projectRoot"
    Write-Host "Python: $pythonExe"
    Write-Host "모드: $($config.mode)"

    $crawlCommand = Get-AutoDetectedCrawlCommand -PythonExe $pythonExe -ProjectRoot $projectRoot -Config $config
    if ($crawlCommand) {
        Write-Section '크롤링 실행'
        $crawlExit = Invoke-CommandTemplate -Template $crawlCommand -PythonExe $pythonExe -Port ([int]$config.server_port) -WorkingDirectory $projectRoot -LogPrefix 'crawl'
        if ($crawlExit -ne 0) {
            throw "크롤링 실패(exit=$crawlExit). pilot_config.json 에 crawl_command 를 직접 넣어 주세요."
        }
    } else {
        Write-Warning '크롤링 명령을 자동 탐지하지 못했습니다. 이번 실행은 rebuild 만 수행합니다. 필요하면 pilot_config.json 의 crawl_command 를 채워 주세요.'
    }

    Write-Section '데이터 rebuild'
    $rebuildExit = Invoke-CommandTemplate -Template $config.rebuild_command -PythonExe $pythonExe -Port ([int]$config.server_port) -WorkingDirectory $projectRoot -LogPrefix 'rebuild'
    if ($rebuildExit -ne 0) {
        throw "rebuild 실패(exit=$rebuildExit)"
    }

    $status = [ordered]@{
        timestamp = (Get-Date).ToString('s')
        mode = $config.mode
        crawl_command = $crawlCommand
        rebuild_command = $config.rebuild_command
        ok = $true
    } | ConvertTo-Json -Depth 6
    Set-Content -Path (Join-Path $logsDir 'last_cycle_status.json') -Value ($status + "`n") -Encoding UTF8
    Write-Section '완료'
} catch {
    $status = [ordered]@{
        timestamp = (Get-Date).ToString('s')
        mode = $config.mode
        ok = $false
        error = $_.Exception.Message
    } | ConvertTo-Json -Depth 6
    Set-Content -Path (Join-Path $logsDir 'last_cycle_status.json') -Value ($status + "`n") -Encoding UTF8
    Write-Error $_.Exception.Message
    exit 1
} finally {
    Stop-Transcript | Out-Null
}
