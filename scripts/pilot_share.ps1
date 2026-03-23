param(
    [int]$Port = 8766,
    [string]$CloudflaredExe = "C:\Users\user\AppData\Local\Microsoft\WinGet\Packages\Cloudflare.cloudflared_Microsoft.Winget.Source_8wekyb3d8bbwe\cloudflared.exe",
    [int]$StartupTimeoutSec = 30
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Split-Path -Parent $PSScriptRoot)).Path
$LogDir = Join-Path $RepoRoot "logs"
$TunnelStateFile = Join-Path $LogDir "pilot_tunnel.json"
$StdOutLog = Join-Path $LogDir "pilot_tunnel_stdout.log"
$StdErrLog = Join-Path $LogDir "pilot_tunnel_stderr.log"
$LocalUrl = "http://localhost`:$Port"

New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

function Remove-TunnelStateFile {
    if (Test-Path $TunnelStateFile) {
        Remove-Item $TunnelStateFile -Force -ErrorAction SilentlyContinue
    }
}

function Get-TunnelState {
    if (-not (Test-Path $TunnelStateFile)) {
        return $null
    }

    try {
        return Get-Content $TunnelStateFile -Raw | ConvertFrom-Json
    } catch {
        Remove-TunnelStateFile
        return $null
    }
}

function Test-Url {
    param([string]$Url)

    try {
        $Response = Invoke-WebRequest -Uri $Url -TimeoutSec 3 -UseBasicParsing
        return ($Response.StatusCode -ge 200 -and $Response.StatusCode -lt 400)
    } catch {
        return $false
    }
}

function Extract-TunnelUrl {
    param([string]$Text)

    if (-not $Text) {
        return ""
    }

    $Match = [regex]::Match($Text, 'https://[a-zA-Z0-9.-]+\.trycloudflare\.com')
    if ($Match.Success) {
        return $Match.Value
    }

    return ""
}

if (-not (Test-Path $CloudflaredExe)) {
    throw "cloudflared executable not found: $CloudflaredExe"
}

if (-not (Test-Url -Url "$LocalUrl/")) {
    Write-Host "Local pilot server is not running yet. Starting it first..."
    powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "pilot_start.ps1") -Port $Port
    Start-Sleep -Seconds 2
}

if (-not (Test-Url -Url "$LocalUrl/")) {
    throw "Local pilot server is still not reachable at $LocalUrl"
}

$ExistingState = Get-TunnelState
if ($null -ne $ExistingState -and $ExistingState.pid) {
    $ExistingProcess = Get-Process -Id $ExistingState.pid -ErrorAction SilentlyContinue
    if ($null -ne $ExistingProcess -and (Test-Url -Url $ExistingState.url)) {
        Write-Host ""
        Write-Host "Pilot share is already running."
        Write-Host "External URL: $($ExistingState.url)"
        Write-Host "Stop command: powershell -ExecutionPolicy Bypass -File .\scripts\pilot_stop.ps1"
        exit 0
    }

    if ($null -ne $ExistingProcess) {
        Stop-Process -Id $ExistingState.pid -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
    }
    Remove-TunnelStateFile
}

Set-Content -Path $StdOutLog -Value "" -Encoding UTF8
Set-Content -Path $StdErrLog -Value "" -Encoding UTF8

$Process = Start-Process `
    -FilePath $CloudflaredExe `
    -ArgumentList "tunnel", "--url", $LocalUrl, "--no-autoupdate" `
    -WorkingDirectory $RepoRoot `
    -RedirectStandardOutput $StdOutLog `
    -RedirectStandardError $StdErrLog `
    -WindowStyle Hidden `
    -PassThru

$ReadyUrl = ""
$Deadline = (Get-Date).AddSeconds($StartupTimeoutSec)
while ((Get-Date) -lt $Deadline) {
    $Process.Refresh()
    if ($Process.HasExited) {
        break
    }

    $LogText = ""
    if (Test-Path $StdErrLog) {
        $LogText += Get-Content $StdErrLog -Raw -ErrorAction SilentlyContinue
    }
    if (Test-Path $StdOutLog) {
        $LogText += "`n" + (Get-Content $StdOutLog -Raw -ErrorAction SilentlyContinue)
    }

    $ReadyUrl = Extract-TunnelUrl -Text $LogText
    if ($ReadyUrl -and (Test-Url -Url $ReadyUrl)) {
        break
    }

    Start-Sleep -Milliseconds 500
}

if (-not $ReadyUrl) {
    $Process.Refresh()
    if (-not $Process.HasExited) {
        Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
    }

    $ErrorTail = ""
    if (Test-Path $StdErrLog) {
        $ErrorTail = ((Get-Content $StdErrLog -Tail 40 -ErrorAction SilentlyContinue) -join [Environment]::NewLine).Trim()
    }
    if ($ErrorTail) {
        throw "External share URL was not created in time.`n$ErrorTail"
    }
    throw "External share URL was not created in time."
}

[pscustomobject]@{
    pid = $Process.Id
    port = $Port
    local_url = $LocalUrl
    url = $ReadyUrl
    stdout_log = $StdOutLog
    stderr_log = $StdErrLog
    started_at = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
} | ConvertTo-Json | Set-Content -Path $TunnelStateFile -Encoding UTF8

Write-Host ""
Write-Host "Pilot share started."
Write-Host "Local URL: $LocalUrl"
Write-Host "External URL: $ReadyUrl"
Write-Host "Tunnel state file: $TunnelStateFile"
Write-Host "Stop command: powershell -ExecutionPolicy Bypass -File .\scripts\pilot_stop.ps1"
