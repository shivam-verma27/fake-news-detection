param(
    [int]$ApiPort = 8000,
    [int]$FrontendPort = 5173,
    [string]$BindHost = "127.0.0.1",
    [bool]$DisableUrlSslVerification = $true
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$runDir = Join-Path $root ".run"
$backendPidFile = Join-Path $runDir "backend.pid"
$frontendPidFile = Join-Path $runDir "frontend.pid"
$runMetaFile = Join-Path $runDir "run-meta.json"
$backendOutLog = Join-Path $runDir "backend.out.log"
$backendErrLog = Join-Path $runDir "backend.err.log"
$frontendOutLog = Join-Path $runDir "frontend.out.log"
$frontendErrLog = Join-Path $runDir "frontend.err.log"

function Test-PortListening {
    param([int]$Port)
    return $null -ne (netstat -ano | Select-String ":$Port\s+.*LISTENING")
}

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

function Wait-Http {
    param(
        [string]$Url,
        [int]$TimeoutSeconds = 20
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $res = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 2
            if ($res.StatusCode -ge 200 -and $res.StatusCode -lt 500) {
                return $true
            }
        }
        catch {
            Start-Sleep -Milliseconds 600
        }
    }

    return $false
}

$pythonExe = Join-Path $root "venv\\Scripts\\python.exe"
$viteJs = Join-Path $root "frontend\\node_modules\\vite\\bin\\vite.js"
$nodeCmd = Get-Command node -ErrorAction SilentlyContinue

if (-not (Test-Path $pythonExe)) {
    throw "Python venv not found at '$pythonExe'. Create it first: python -m venv venv"
}
if (-not (Test-Path $viteJs)) {
    throw "Vite CLI not found at '$viteJs'. Run npm install in frontend first."
}
if ($null -eq $nodeCmd) {
    throw "Node.js was not found in PATH. Install Node.js and reopen your terminal."
}

if (Test-PortListening -Port $ApiPort) {
    throw "Port $ApiPort is already in use. Free the port or run .\\stop-dev.ps1 first."
}
if (Test-PortListening -Port $FrontendPort) {
    throw "Port $FrontendPort is already in use. Free the port or run .\\stop-dev.ps1 first."
}

New-Item -ItemType Directory -Force -Path $runDir | Out-Null
Remove-Item -Path $backendOutLog,$backendErrLog,$frontendOutLog,$frontendErrLog -Force -ErrorAction SilentlyContinue

$backendVerifySsl = if ($DisableUrlSslVerification) { "false" } else { "true" }
$backendCommand = "`$env:URL_FETCH_VERIFY_SSL='$backendVerifySsl'; & '$pythonExe' -m uvicorn src.api_server:app --host $BindHost --port $ApiPort"
$backendLauncher = Start-Process -FilePath "powershell.exe" -ArgumentList @(
    "-NoProfile", "-Command", $backendCommand
) -WorkingDirectory $root -RedirectStandardOutput $backendOutLog -RedirectStandardError $backendErrLog -PassThru

$frontendLauncher = Start-Process -FilePath $nodeCmd.Source -ArgumentList @(
    $viteJs, "--configLoader", "runner", "--host", $BindHost, "--port", "$FrontendPort"
) -WorkingDirectory (Join-Path $root "frontend") -RedirectStandardOutput $frontendOutLog -RedirectStandardError $frontendErrLog -PassThru

$apiUrl = "http://${BindHost}:$ApiPort/health"
$uiUrl = "http://${BindHost}:$FrontendPort"

$apiReady = Wait-Http -Url $apiUrl -TimeoutSeconds 20
$uiReady = Wait-Http -Url $uiUrl -TimeoutSeconds 20

$backendPid = Get-ListeningPid -Port $ApiPort
$frontendPid = Get-ListeningPid -Port $FrontendPort

if ($null -ne $backendPid) {
    Set-Content -Path $backendPidFile -Value $backendPid -Encoding ascii
}
if ($null -ne $frontendPid) {
    Set-Content -Path $frontendPidFile -Value $frontendPid -Encoding ascii
}

$meta = [ordered]@{
    host = $BindHost
    api_port = $ApiPort
    frontend_port = $FrontendPort
    backend_pid = $backendPid
    frontend_pid = $frontendPid
    backend_launcher_pid = $backendLauncher.Id
    frontend_launcher_pid = $frontendLauncher.Id
    started_at = (Get-Date).ToString("o")
}
$meta | ConvertTo-Json | Set-Content -Path $runMetaFile -Encoding ascii

Write-Host "Backend PID : $backendPid"
Write-Host "Frontend PID: $frontendPid"
Write-Host "API URL     : http://${BindHost}:$ApiPort"
Write-Host "UI URL      : http://${BindHost}:$FrontendPort"
Write-Host "URL SSL verify: $(-not $DisableUrlSslVerification)"
Write-Host "Backend logs: $backendOutLog, $backendErrLog"
Write-Host "Frontend logs: $frontendOutLog, $frontendErrLog"

if (-not $apiReady -or -not $uiReady -or $null -eq $backendPid -or $null -eq $frontendPid) {
    Write-Warning "One or both services failed to stay up. Check logs in .run/*.log"
    if (Test-Path $backendErrLog) {
        Write-Host "`n=== backend.err.log (tail) ==="
        Get-Content $backendErrLog -Tail 30
    }
    if (Test-Path $frontendErrLog) {
        Write-Host "`n=== frontend.err.log (tail) ==="
        Get-Content $frontendErrLog -Tail 30
    }
    exit 1
}

Write-Host "Both services are up."
