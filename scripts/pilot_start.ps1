param(
    [int]$Port = 8766,
    [string]$PythonExe = "D:\gpt\01project\.venv311\Scripts\python.exe",
    [int]$StartupTimeoutSec = 15
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Split-Path -Parent $PSScriptRoot)).Path
$LogDir = Join-Path $RepoRoot "logs"
$StateFile = Join-Path $LogDir "pilot_server.json"
$StdOutLog = Join-Path $LogDir "pilot_server_stdout.log"
$StdErrLog = Join-Path $LogDir "pilot_server_stderr.log"
$DisplayUrl = "http://localhost`:$Port"
$HealthUrl = "$DisplayUrl/"

New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

function Remove-PilotStateFile {
    if (Test-Path $StateFile) {
        Remove-Item $StateFile -Force -ErrorAction SilentlyContinue
    }
}

function Get-PilotState {
    if (-not (Test-Path $StateFile)) {
        return $null
    }

    try {
        return Get-Content $StateFile -Raw | ConvertFrom-Json
    } catch {
        Remove-PilotStateFile
        return $null
    }
}

function Test-PilotUrl {
    try {
        $Response = Invoke-WebRequest -Uri $HealthUrl -TimeoutSec 2 -UseBasicParsing
        return ($Response.StatusCode -ge 200 -and $Response.StatusCode -lt 400)
    } catch {
        return $false
    }
}

function Get-ProcessCommandLine {
    param([int]$ProcessId)

    try {
        return (Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId").CommandLine
    } catch {
        return ""
    }
}

function Get-PortListenerInfo {
    param([int]$TargetPort)

    $Listener = Get-NetTCPConnection -LocalPort $TargetPort -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $Listener) {
        return $null
    }

    $CommandLine = Get-ProcessCommandLine -ProcessId $Listener.OwningProcess
    $IsPilotServe = $CommandLine -match "swimdash" -and $CommandLine -match "serve" -and $CommandLine -match "--port\s+$TargetPort\b"
    $IsLegacyDocsServer = $CommandLine -match "-m\s+http\.server\s+$TargetPort\b" -and $CommandLine -match "--directory\s+docs\b"

    return [pscustomobject]@{
        ProcessId = $Listener.OwningProcess
        CommandLine = $CommandLine
        IsPilot = ($IsPilotServe -or $IsLegacyDocsServer)
    }
}

function Get-ProcessSummary {
    param([int]$ProcessId)

    try {
        $ProcessInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId"
        if ($null -ne $ProcessInfo) {
            return "$($ProcessInfo.Name) (PID $ProcessId)"
        }
    } catch {
    }

    $CommandLine = Get-ProcessCommandLine -ProcessId $ProcessId
    if ($CommandLine) {
        return "$CommandLine (PID $ProcessId)"
    }

    return "PID $ProcessId"
}

if (-not (Test-Path $PythonExe)) {
    throw "Python executable not found: $PythonExe"
}

$ExistingState = Get-PilotState
if ($null -ne $ExistingState -and $ExistingState.pid) {
    $ExistingProcess = Get-Process -Id $ExistingState.pid -ErrorAction SilentlyContinue
    if ($null -ne $ExistingProcess) {
        if (Test-PilotUrl) {
            Write-Host ""
            Write-Host "Pilot server is already running."
            Write-Host "Local URL: $DisplayUrl"
            Write-Host "PID: $($ExistingState.pid)"
            Write-Host "Stop command: powershell -ExecutionPolicy Bypass -File .\scripts\pilot_stop.ps1"
            exit 0
        }

        Stop-Process -Id $ExistingState.pid -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
    }

    Remove-PilotStateFile
}

$PortListener = Get-PortListenerInfo -TargetPort $Port
if ($null -ne $PortListener) {
    if ($PortListener.IsPilot) {
        [pscustomobject]@{
            pid = $PortListener.ProcessId
            port = $Port
            url = $DisplayUrl
            repo_root = $RepoRoot
            python_exe = $PythonExe
            stdout_log = $StdOutLog
            stderr_log = $StdErrLog
            started_at = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
        } | ConvertTo-Json | Set-Content -Path $StateFile -Encoding UTF8

        Write-Host ""
        Write-Host "Pilot server is already running."
        Write-Host "Local URL: $DisplayUrl"
        Write-Host "PID: $($PortListener.ProcessId)"
        Write-Host "Stop command: powershell -ExecutionPolicy Bypass -File .\scripts\pilot_stop.ps1"
        exit 0
    }

    $Summary = Get-ProcessSummary -ProcessId $PortListener.ProcessId
    throw "Port $Port is already in use by $Summary. Free the port, then run .\scripts\pilot_start.ps1 again."
}

Set-Content -Path $StdOutLog -Value "" -Encoding UTF8
Set-Content -Path $StdErrLog -Value "" -Encoding UTF8

$Process = Start-Process `
    -FilePath $PythonExe `
    -ArgumentList "-m", "swimdash", "serve", "--port", "$Port" `
    -WorkingDirectory $RepoRoot `
    -RedirectStandardOutput $StdOutLog `
    -RedirectStandardError $StdErrLog `
    -WindowStyle Hidden `
    -PassThru

$Ready = $false
$Deadline = (Get-Date).AddSeconds($StartupTimeoutSec)
while ((Get-Date) -lt $Deadline) {
    $Process.Refresh()
    if ($Process.HasExited) {
        break
    }

    if (Test-PilotUrl) {
        $Ready = $true
        break
    }

    Start-Sleep -Milliseconds 500
}

if (-not $Ready) {
    $Process.Refresh()
    if (-not $Process.HasExited) {
        Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
    }

    $ErrorTail = ""
    if (Test-Path $StdErrLog) {
        $ErrorTail = ((Get-Content $StdErrLog -Tail 20 -ErrorAction SilentlyContinue) -join [Environment]::NewLine).Trim()
    }

    if ($ErrorTail) {
        throw "Pilot server did not become ready at $DisplayUrl. Check $StdErrLog`n$ErrorTail"
    }

    throw "Pilot server did not become ready at $DisplayUrl. Check $StdErrLog"
}

$ActiveListener = Get-PortListenerInfo -TargetPort $Port
$ActiveProcessId = if ($null -ne $ActiveListener) { $ActiveListener.ProcessId } else { $Process.Id }

[pscustomobject]@{
    pid = $ActiveProcessId
    port = $Port
    url = $DisplayUrl
    repo_root = $RepoRoot
    python_exe = $PythonExe
    stdout_log = $StdOutLog
    stderr_log = $StdErrLog
    started_at = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
} | ConvertTo-Json | Set-Content -Path $StateFile -Encoding UTF8

Write-Host ""
Write-Host "Pilot server started."
Write-Host "Local URL: $DisplayUrl"
Write-Host "PID: $ActiveProcessId"
Write-Host "State file: $StateFile"
Write-Host "Stdout log: $StdOutLog"
Write-Host "Stderr log: $StdErrLog"
Write-Host "Stop command: powershell -ExecutionPolicy Bypass -File .\scripts\pilot_stop.ps1"
