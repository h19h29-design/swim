$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $ScriptRoot 'lib.ps1')

$projectRoot = Get-ProjectRoot -ScriptRoot $ScriptRoot
$config = Load-Config -ProjectRoot $projectRoot
$pythonExe = Ensure-Venv -ProjectRoot $projectRoot -Config $config
$logsDir = Ensure-LogsDir -ProjectRoot $projectRoot
$port = [int]$config.server_port

if (Get-PortInUse -Port $port) {
    Write-Host "포트 $port 에 이미 서버가 떠 있습니다. 새로 시작하지 않습니다." -ForegroundColor Yellow
    exit 0
}

$stdout = Join-Path $logsDir 'server.stdout.log'
$stderr = Join-Path $logsDir 'server.stderr.log'
$pidFile = Join-Path $logsDir 'server.pid'

$serveTemplate = $config.serve_command
$serveLine = Convert-CommandTemplate -Template $serveTemplate -PythonExe $pythonExe -Port $port
$arguments = '/d', '/s', '/c', (Convert-ToCmdArgument -CommandLine $serveLine)

Write-Host "서버 시작: $serveLine" -ForegroundColor Cyan
$proc = Start-Process -FilePath 'cmd.exe' -ArgumentList $arguments -WorkingDirectory $projectRoot -RedirectStandardOutput $stdout -RedirectStandardError $stderr -WindowStyle Hidden -PassThru
Set-Content -Path $pidFile -Value ($proc.Id.ToString() + "`n") -Encoding ASCII
Write-Host "서버 PID: $($proc.Id)"
Write-Host "대시보드 주소: http://127.0.0.1:$port/"
