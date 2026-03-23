$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $ScriptRoot 'lib.ps1')

$projectRoot = Get-ProjectRoot -ScriptRoot $ScriptRoot
$logsDir = Ensure-LogsDir -ProjectRoot $projectRoot
$pidFile = Join-Path $logsDir 'server.pid'

if (Test-Path $pidFile) {
    $pid = (Get-Content $pidFile -Raw).Trim()
    if ($pid) {
        try {
            Stop-Process -Id ([int]$pid) -Force -ErrorAction Stop
            Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
            Write-Host "서버 종료 완료(PID=$pid)"
            exit 0
        } catch {
            Write-Warning "PID 파일은 있었지만 종료하지 못했습니다: $pid"
        }
    }
}

Write-Warning 'PID 파일 기준 서버를 찾지 못했습니다. 직접 실행한 창이 있으면 닫아 주세요.'
