$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $ScriptRoot 'lib.ps1')

$projectRoot = Get-ProjectRoot -ScriptRoot $ScriptRoot
$config = Load-Config -ProjectRoot $projectRoot
$port = [int]$config.server_port

$urls = @(
    "http://127.0.0.1:$port/",
    "http://127.0.0.1:$port/data/records.json",
    "http://127.0.0.1:$port/data/summary.json",
    "http://127.0.0.1:$port/data/review_queue.json"
)

foreach ($url in $urls) {
    try {
        $code = (Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 10).StatusCode
        Write-Host "$url -> $code" -ForegroundColor Green
    } catch {
        Write-Host "$url -> FAIL ($($_.Exception.Message))" -ForegroundColor Red
    }
}
