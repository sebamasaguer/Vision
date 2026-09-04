$ErrorActionPreference = "Stop"
$ProjectPath = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectPath
Write-Host "=== HYS VISION IA - BLOQUE 1 v0.2.0 CAMARAS + RTSP + DEMO CAMERA ===" -ForegroundColor Cyan
if (-not (Test-Path ".env")) { throw "Este Bloque 1 se instala sobre un Bloque 0 existente. Falta .env." }
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw "Docker no esta disponible en PATH." }

function New-FernetKey {
    $b = New-Object byte[] 32
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
    return [Convert]::ToBase64String($b).Replace('+','-').Replace('/','_')
}
$envText = Get-Content .env -Raw
$envText = [regex]::Replace($envText, '(?m)^APP_VERSION=.*$', 'APP_VERSION=0.2.0')
if ($envText -notmatch '(?m)^CAMERA_CREDENTIAL_KEY=') { $envText += "`nCAMERA_CREDENTIAL_KEY=$(New-FernetKey)" }
if ($envText -notmatch '(?m)^CAMERA_POLL_INTERVAL_SECONDS=') { $envText += "`nCAMERA_POLL_INTERVAL_SECONDS=3" }
if ($envText -notmatch '(?m)^CAMERA_FRAME_TTL_SECONDS=') { $envText += "`nCAMERA_FRAME_TTL_SECONDS=10" }
if ($envText -notmatch '(?m)^DEMO_VIDEO_PATH=') { $envText += "`nDEMO_VIDEO_PATH=/demo/demo_camera.mp4" }
$envText | Set-Content .env -Encoding UTF8

Write-Host "Construyendo backend, camera-worker y frontend..." -ForegroundColor Cyan
docker compose up -d --build
if ($LASTEXITCODE -ne 0) { throw "docker compose up fallo" }
& "$PSScriptRoot\validar_bloque1.ps1"
