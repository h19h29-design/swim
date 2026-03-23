$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = if (Test-Path (Join-Path $ScriptRoot 'pilot_config.json')) { $ScriptRoot } else { (Get-Location).Path }
$configPath = Join-Path $projectRoot 'pilot_config.json'
if (-not (Test-Path $configPath)) {
    throw "pilot_config.json 을 찾지 못했습니다: $configPath"
}
$config = Get-Content -Path $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
$config.mode = 'rolling_3d'
$config.production_lookback_days = 3
$config | ConvertTo-Json -Depth 6 | Set-Content -Path $configPath -Encoding UTF8
Write-Host 'pilot_config.json 을 rolling_3d 모드로 변경했습니다.' -ForegroundColor Green
