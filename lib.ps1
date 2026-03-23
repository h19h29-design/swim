Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Section {
    param([string]$Message)
    Write-Host "`n==== $Message ====" -ForegroundColor Cyan
}

function Get-DefaultConfigObject {
    return [ordered]@{
        project_root = 'AUTO'
        venv_candidates = @('..\\.venv311', '.\\.venv311', '..\\.venv', '.\\.venv')
        server_port = 8765
        scheduler_times = @('00:10', '06:10', '12:10', '18:10')
        mode = 'march_pilot'
        march_pilot_start_date = '2026-03-01'
        production_lookback_days = 3
        crawl_command = ''
        rebuild_command = 'python -m swimdash rebuild'
        serve_command = 'python -m swimdash serve --port {port}'
        task_prefix = 'SwimmingDash'
        skip_scheduler = $false
    }
}

function Ensure-ConfigFile {
    param([string]$ProjectRoot)
    $configPath = Join-Path $ProjectRoot 'pilot_config.json'
    if (-not (Test-Path $configPath)) {
        $default = Get-DefaultConfigObject | ConvertTo-Json -Depth 6
        Set-Content -Path $configPath -Value ($default + "`n") -Encoding UTF8
        Write-Host "pilot_config.json 새로 생성: $configPath" -ForegroundColor Yellow
    }
    return $configPath
}

function Load-Config {
    param([string]$ProjectRoot)
    $configPath = Ensure-ConfigFile -ProjectRoot $ProjectRoot
    $json = Get-Content -Path $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
    return $json
}

function Get-ProjectRoot {
    param([string]$ScriptRoot)
    $candidates = @($ScriptRoot, (Get-Location).Path) | Select-Object -Unique
    foreach ($candidate in $candidates) {
        if (Test-Path (Join-Path $candidate 'requirements.txt')) {
            return (Resolve-Path $candidate).Path
        }
    }
    return (Resolve-Path $ScriptRoot).Path
}

function Find-BasePython {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        try {
            & py -3.11 -c "import sys; print(sys.executable)" 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) { return @('py', '-3.11') }
        } catch {}
        try {
            & py -3 -c "import sys; print(sys.executable)" 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) { return @('py', '-3') }
        } catch {}
    }
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) { return @($python.Source) }
    throw 'Python 3 실행 파일을 찾지 못했습니다. Python 3.11 설치 후 다시 실행하세요.'
}

function Resolve-VenvPath {
    param(
        [string]$ProjectRoot,
        $Config
    )
    foreach ($candidate in $Config.venv_candidates) {
        $full = Join-Path $ProjectRoot $candidate
        $py = Join-Path $full 'Scripts\python.exe'
        if (Test-Path $py) {
            return (Resolve-Path $full).Path
        }
    }
    return (Join-Path $ProjectRoot '.venv311')
}

function Ensure-Venv {
    param(
        [string]$ProjectRoot,
        $Config
    )
    $venvPath = Resolve-VenvPath -ProjectRoot $ProjectRoot -Config $Config
    $pythonExe = Join-Path $venvPath 'Scripts\python.exe'
    if (-not (Test-Path $pythonExe)) {
        Write-Section "가상환경 생성"
        $basePython = Find-BasePython
        Write-Host "사용할 Python: $($basePython -join ' ')"
        if ($basePython.Count -gt 1) {
            & $basePython[0] @($basePython[1..($basePython.Count-1)]) -m venv $venvPath
        } else {
            & $basePython[0] -m venv $venvPath
        }
        if ($LASTEXITCODE -ne 0) {
            throw "가상환경 생성 실패: $venvPath"
        }
    }
    return (Resolve-Path $pythonExe).Path
}

function Convert-CommandTemplate {
    param(
        [string]$Template,
        [string]$PythonExe,
        [int]$Port
    )
    $command = $Template.Replace('{port}', [string]$Port)
    if ($command -match '^\s*python(\.exe)?\b') {
        $command = $command -replace '^\s*python(\.exe)?', ('"' + $PythonExe + '"')
    }
    return $command
}

function Convert-ToCmdArgument {
    param([string]$CommandLine)
    if ($CommandLine.TrimStart().StartsWith('"')) {
        return '"' + $CommandLine + '"'
    }
    return $CommandLine
}

function Invoke-CommandTemplate {
    param(
        [string]$Template,
        [string]$PythonExe,
        [int]$Port,
        [string]$WorkingDirectory,
        [string]$LogPrefix = ''
    )
    $command = Convert-CommandTemplate -Template $Template -PythonExe $PythonExe -Port $Port
    if ($LogPrefix) {
        Write-Host "[$LogPrefix] $command" -ForegroundColor DarkGray
    } else {
        Write-Host $command -ForegroundColor DarkGray
    }
    $cmdArgument = Convert-ToCmdArgument -CommandLine $command
    Push-Location $WorkingDirectory
    try {
        & cmd.exe /d /s /c $cmdArgument
        return $LASTEXITCODE
    } finally {
        Pop-Location
    }
}

function Invoke-CommandCapture {
    param(
        [string]$CommandLine,
        [string]$WorkingDirectory
    )
    $cmdArgument = Convert-ToCmdArgument -CommandLine $CommandLine
    Push-Location $WorkingDirectory
    try {
        $output = & cmd.exe /d /s /c $cmdArgument 2>&1 | Out-String
        return @{ exit_code = $LASTEXITCODE; output = $output }
    } finally {
        Pop-Location
    }
}

function Can-RunSwimdash {
    param(
        [string]$PythonExe,
        [string]$WorkingDirectory
    )
    $probe = Invoke-CommandCapture -CommandLine ('"' + $PythonExe + '" -m swimdash --help') -WorkingDirectory $WorkingDirectory
    return ($probe.exit_code -eq 0)
}

function Get-LookbackDaysFromStartDate {
    param([string]$StartDate)
    $start = [datetime]::Parse($StartDate).Date
    $today = [datetime]::Now.Date
    $diff = [int]([math]::Floor(($today - $start).TotalDays)) + 1
    if ($diff -lt 1) { return 1 }
    return $diff
}

function Get-AutoDetectedCrawlCommand {
    param(
        [string]$PythonExe,
        [string]$ProjectRoot,
        $Config
    )
    if ($Config.crawl_command -and $Config.crawl_command.ToString().Trim()) {
        return $Config.crawl_command.ToString().Trim()
    }

    $subcommands = @('crawl', 'sync', 'fetch', 'update', 'collect')
    $dateOptions = @('--start-date', '--since', '--from-date', '--from', '--date-from')
    $lookbackOptions = @('--lookback-days', '--days', '--lookback', '--recent-days')

    foreach ($subcmd in $subcommands) {
        $helpCommand = '"' + $PythonExe + '" -m swimdash ' + $subcmd + ' --help'
        $probe = Invoke-CommandCapture -CommandLine $helpCommand -WorkingDirectory $ProjectRoot
        $text = ($probe.output | Out-String)
        if (($probe.exit_code -eq 0) -or ($text -match [regex]::Escape($subcmd))) {
            $base = 'python -m swimdash ' + $subcmd
            if ($Config.mode -eq 'march_pilot') {
                foreach ($opt in $dateOptions) {
                    if ($text -match [regex]::Escape($opt)) {
                        return "$base $opt $($Config.march_pilot_start_date)"
                    }
                }
                foreach ($opt in $lookbackOptions) {
                    if ($text -match [regex]::Escape($opt)) {
                        $days = Get-LookbackDaysFromStartDate -StartDate $Config.march_pilot_start_date
                        return "$base $opt $days"
                    }
                }
                return $base
            }

            foreach ($opt in $lookbackOptions) {
                if ($text -match [regex]::Escape($opt)) {
                    return "$base $opt $($Config.production_lookback_days)"
                }
            }
            foreach ($opt in $dateOptions) {
                if ($text -match [regex]::Escape($opt)) {
                    $since = ([datetime]::Now.Date.AddDays(-1 * [int]$Config.production_lookback_days)).ToString('yyyy-MM-dd')
                    return "$base $opt $since"
                }
            }
            return $base
        }
    }

    return ''
}

function Ensure-LogsDir {
    param([string]$ProjectRoot)
    $logsDir = Join-Path $ProjectRoot 'logs'
    if (-not (Test-Path $logsDir)) {
        New-Item -ItemType Directory -Path $logsDir | Out-Null
    }
    return $logsDir
}

function Get-PortInUse {
    param([int]$Port)
    try {
        $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop | Select-Object -First 1
        return $null -ne $conn
    } catch {
        return $false
    }
}
