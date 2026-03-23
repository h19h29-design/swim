param(
    [int]$Port = 8766
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Split-Path -Parent $PSScriptRoot)).Path
$LogDir = Join-Path $RepoRoot "logs"
$StateFile = Join-Path $LogDir "pilot_server.json"
$TunnelStateFile = Join-Path $LogDir "pilot_tunnel.json"

function Remove-PilotStateFile {
    if (Test-Path $StateFile) {
        Remove-Item $StateFile -Force -ErrorAction SilentlyContinue
    }
}

function Remove-TunnelStateFile {
    if (Test-Path $TunnelStateFile) {
        Remove-Item $TunnelStateFile -Force -ErrorAction SilentlyContinue
    }
}

function Stop-ProcessAndWait {
    param([int]$ProcessId)

    Stop-Process -Id $ProcessId -Force -ErrorAction Stop

    $Deadline = (Get-Date).AddSeconds(10)
    while ((Get-Date) -lt $Deadline) {
        $Process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
        if ($null -eq $Process) {
            return
        }
        Start-Sleep -Milliseconds 250
    }

    throw "Process $ProcessId did not exit after stop request."
}

function Get-ProcessCommandLine {
    param([int]$ProcessId)

    try {
        return (Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId").CommandLine
    } catch {
        return ""
    }
}

function Get-PilotProcessOnPort {
    param([int]$TargetPort)

    $Listener = Get-NetTCPConnection -LocalPort $TargetPort -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $Listener) {
        return $null
    }

    $CommandLine = Get-ProcessCommandLine -ProcessId $Listener.OwningProcess
    $IsPilotServe = $CommandLine -match "swimdash" -and $CommandLine -match "serve" -and $CommandLine -match "--port\s+$TargetPort\b"
    $IsLegacyDocsServer = $CommandLine -match "-m\s+http\.server\s+$TargetPort\b" -and $CommandLine -match "--directory\s+docs\b"

    if ($IsPilotServe -or $IsLegacyDocsServer) {
        return [pscustomobject]@{
            ProcessId = $Listener.OwningProcess
            CommandLine = $CommandLine
        }
    }

    return [pscustomobject]@{
        ProcessId = $Listener.OwningProcess
        CommandLine = $CommandLine
        IsPilot = $false
    }
}

$Stopped = $false
$StopMessage = ""
$TunnelStopped = $false
$TunnelStopMessage = ""

if (Test-Path $StateFile) {
    try {
        $Existing = Get-Content $StateFile -Raw | ConvertFrom-Json
        $Process = Get-Process -Id $Existing.pid -ErrorAction SilentlyContinue
        if ($null -ne $Process) {
            Stop-ProcessAndWait -ProcessId $Existing.pid
            $Stopped = $true
            $StopMessage = "Stopped pilot server PID $($Existing.pid)."
        }
    } catch {
        Write-Host "Pilot state file was not usable. Falling back to port lookup."
    }
}

$PortProcess = Get-PilotProcessOnPort -TargetPort $Port
if ($null -ne $PortProcess) {
    if ($PortProcess.PSObject.Properties.Name -contains "IsPilot" -and -not $PortProcess.IsPilot) {
        Remove-PilotStateFile
        throw "Port $Port is in use by PID $($PortProcess.ProcessId), but it does not look like the pilot server. Not stopping it automatically."
    }

    Stop-ProcessAndWait -ProcessId $PortProcess.ProcessId
    $Stopped = $true
    $StopMessage = "Stopped pilot server PID $($PortProcess.ProcessId) on port $Port."
}

Remove-PilotStateFile

if (Test-Path $TunnelStateFile) {
    try {
        $Tunnel = Get-Content $TunnelStateFile -Raw | ConvertFrom-Json
        if ($Tunnel.pid) {
            $TunnelProcess = Get-Process -Id $Tunnel.pid -ErrorAction SilentlyContinue
            if ($null -ne $TunnelProcess) {
                Stop-ProcessAndWait -ProcessId $Tunnel.pid
                $TunnelStopped = $true
                $TunnelStopMessage = "Stopped external share PID $($Tunnel.pid)."
            }
        }
    } catch {
        Write-Host "Tunnel state file was not usable."
    }
}

Remove-TunnelStateFile

if ($Stopped) {
    Write-Host $StopMessage
    Write-Host "Local URL is now free: http://localhost:$Port"
} else {
    Write-Host "No pilot server was running on port $Port."
}

if ($TunnelStopped) {
    Write-Host $TunnelStopMessage
}
