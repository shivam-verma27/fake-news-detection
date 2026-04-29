$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$runDir = Join-Path $root ".run"
$backendPidFile = Join-Path $runDir "backend.pid"
$frontendPidFile = Join-Path $runDir "frontend.pid"
$runMetaFile = Join-Path $runDir "run-meta.json"

function Get-ListeningPid {
    param([int]$Port)
    $line = netstat -ano | Select-String ":$Port\s+.*LISTENING" | Select-Object -First 1
    if ($null -eq $line) {
        return $null
    }

    $parts = ($line.ToString().Trim() -split "\s+")
    if ($parts.Length -lt 1) {
        return $null
    }

    return [int]$parts[$parts.Length - 1]
}

function Stop-ProcessIfRunning {
    param(
        [int]$ProcId,
        [string]$Name
    )

    $proc = Get-Process -Id $ProcId -ErrorAction SilentlyContinue
    if ($null -eq $proc) {
        return $false
    }

    Stop-Process -Id $ProcId -Force
    Write-Host "Stopped $Name (PID $ProcId)."
    return $true
}

function Read-PidFile {
    param([string]$Path)

    if (-not (Test-Path $Path)) {
        return $null
    }

    $text = (Get-Content -Path $Path -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
    if (-not $text) {
        return $null
    }

    return [int]$text
}

$apiPort = 8000
$frontendPort = 5173
if (Test-Path $runMetaFile) {
    try {
        $meta = Get-Content $runMetaFile -Raw | ConvertFrom-Json
        if ($meta.api_port) { $apiPort = [int]$meta.api_port }
        if ($meta.frontend_port) { $frontendPort = [int]$meta.frontend_port }
    }
    catch {
        # Ignore malformed metadata and fall back to defaults.
    }
}

$backendStopped = $false
$backendPid = Read-PidFile -Path $backendPidFile
if ($null -ne $backendPid) {
    $backendStopped = Stop-ProcessIfRunning -ProcId $backendPid -Name "Backend"
}
if (-not $backendStopped) {
    $backendByPort = Get-ListeningPid -Port $apiPort
    if ($null -ne $backendByPort) {
        $backendStopped = Stop-ProcessIfRunning -ProcId $backendByPort -Name "Backend"
    }
}
if (-not $backendStopped) {
    Write-Host "Backend not running."
}

$frontendStopped = $false
$frontendPid = Read-PidFile -Path $frontendPidFile
if ($null -ne $frontendPid) {
    $frontendStopped = Stop-ProcessIfRunning -ProcId $frontendPid -Name "Frontend"
}
if (-not $frontendStopped) {
    $frontendByPort = Get-ListeningPid -Port $frontendPort
    if ($null -ne $frontendByPort) {
        $frontendStopped = Stop-ProcessIfRunning -ProcId $frontendByPort -Name "Frontend"
    }
}
if (-not $frontendStopped) {
    Write-Host "Frontend not running."
}

Remove-Item -Path $backendPidFile,$frontendPidFile,$runMetaFile -Force -ErrorAction SilentlyContinue
