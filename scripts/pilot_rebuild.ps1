param(
    [switch]$SkipIncrementalSync,
    [switch]$FromDashboardFloor,
    [string]$PythonExe = "D:\gpt\01project\.venv311\Scripts\python.exe"
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Split-Path -Parent $PSScriptRoot)).Path
$RecordsFile = Join-Path $RepoRoot "docs\data\records.json"
$SummaryFile = Join-Path $RepoRoot "docs\data\summary.json"
$ReviewQueueFile = Join-Path $RepoRoot "docs\data\review_queue.json"
$ManualOverrideFile = Join-Path $RepoRoot "data\manual_review_overrides.csv"
$StateFile = Join-Path $RepoRoot "logs\pilot_server.json"

function Assert-PathExists {
    param(
        [string]$Path,
        [string]$Label
    )

    if (-not (Test-Path $Path)) {
        throw "$Label file was not found after rebuild: $Path"
    }
}

function Get-RunningPilotUrl {
    if (-not (Test-Path $StateFile)) {
        return $null
    }

    try {
        $State = Get-Content $StateFile -Raw | ConvertFrom-Json
        $Process = Get-Process -Id $State.pid -ErrorAction SilentlyContinue
        if ($null -ne $Process) {
            return $State.url
        }
    } catch {
    }

    return $null
}

if (-not (Test-Path $PythonExe)) {
    throw "Python executable not found: $PythonExe"
}

Push-Location $RepoRoot
try {
    if ($SkipIncrementalSync) {
        Write-Host "Step 1/1: rebuild dashboard data only..."
        if ($FromDashboardFloor) {
            & $PythonExe -m swimdash refresh-from-floor --skip-incremental
        } else {
            & $PythonExe -m swimdash refresh --skip-incremental
        }
    } else {
        if ($FromDashboardFloor) {
            Write-Host "Step 1/1: refresh posts from dashboard floor (2026-03-01) and rebuild dashboard data..."
            & $PythonExe -m swimdash refresh-from-floor
        } else {
            Write-Host "Step 1/1: refresh editable posts window and rebuild dashboard data..."
            & $PythonExe -m swimdash refresh
        }
    }
    if ($LASTEXITCODE -ne 0) {
        throw "refresh failed with exit code $LASTEXITCODE"
    }
} finally {
    Pop-Location
}

Assert-PathExists -Path $RecordsFile -Label "Records"
Assert-PathExists -Path $SummaryFile -Label "Summary"
Assert-PathExists -Path $ReviewQueueFile -Label "Review queue"

$RunningPilotUrl = Get-RunningPilotUrl

Write-Host ""
Write-Host "Pilot rebuild completed."
Write-Host "Records: $RecordsFile"
Write-Host "Summary: $SummaryFile"
Write-Host "Review queue: $ReviewQueueFile"
Write-Host "Manual override file: $ManualOverrideFile"
if ($SkipIncrementalSync) {
    Write-Host "Incremental sync was skipped for this run."
} elseif ($FromDashboardFloor) {
    Write-Host "Refresh used the dashboard floor window from 2026-03-01 through today before rebuild."
} else {
    Write-Host "Refresh used the current editable-post policy before rebuild."
}
Write-Host "Current sync policy:"
Write-Host "- Through Sunday, March 15, 2026: posts dated from March 1, 2026 onward are re-collected for corrections."
Write-Host "- After Monday, March 16, 2026: only the latest 3 days are re-collected."
if (-not $RunningPilotUrl) {
    Write-Host "Daily flow: run pilot_rebuild first, then open http://localhost:8766"
}
if ($RunningPilotUrl) {
    Write-Host "Pilot server is already running at $RunningPilotUrl"
    Write-Host "Refresh the browser to see the rebuilt data."
} else {
    Write-Host "Next command: powershell -ExecutionPolicy Bypass -File .\scripts\pilot_start.ps1"
}
