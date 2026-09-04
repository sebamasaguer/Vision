param(
    [Parameter(Mandatory = $true)][string]$ProjectPath
)
$ErrorActionPreference = 'Stop'
$ProjectPath = (Resolve-Path $ProjectPath).Path
Set-Location $ProjectPath
Write-Host '=== BLOQUE 10 - ACTIVAR DEMO EPP REAL EN CAMARAS ===' -ForegroundColor Cyan

$video = Join-Path $ProjectPath 'demo\intel_worker_safety_test.avi'
if (-not (Test-Path $video)) {
    throw 'Falta demo\intel_worker_safety_test.avi. Ejecute scripts\instalar_bootstrap_intel_bloque9.ps1 primero.'
}

$envPath = Join-Path $ProjectPath '.env'
$text = Get-Content $envPath -Raw
if ($text -match '(?m)^DEMO_VIDEO_PATH=') {
    $text = [regex]::Replace($text, '(?m)^DEMO_VIDEO_PATH=.*$', 'DEMO_VIDEO_PATH=/demo/intel_worker_safety_test.avi')
} else {
    $text += "`nDEMO_VIDEO_PATH=/demo/intel_worker_safety_test.avi"
}
$text | Set-Content $envPath -Encoding UTF8

function Wait-Healthy([string]$service, [int]$attempts = 100) {
    for ($i = 1; $i -le $attempts; $i++) {
        $id = docker compose ps -q $service
        if ($id) {
            $status = docker inspect -f '{{.State.Status}}' $id
            $health = docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}n/a{{end}}' $id
            if ($status -eq 'running' -and ($health -eq 'healthy' -or $health -eq 'n/a')) {
                Write-Host "[OK] $service status=$status health=$health" -ForegroundColor Green
                return
            }
        }
        Start-Sleep -Seconds 2
    }
    throw "$service no alcanzo healthy"
}

& docker compose up -d --force-recreate backend
if ($LASTEXITCODE -ne 0) { throw 'No se pudo recrear backend.' }
Wait-Healthy 'backend'

& docker compose exec -T backend python -m app.block10_demo_setup
if ($LASTEXITCODE -ne 0) { throw 'No se pudo preparar DEMO01 para SHADOW visual.' }

& cmd.exe /d /c "docker compose up -d --force-recreate camera-worker vision-engine >nul 2>&1"
if ($LASTEXITCODE -ne 0) { throw 'No se pudieron recrear camera-worker/vision-engine.' }
Wait-Healthy 'camera-worker'
Wait-Healthy 'vision-engine'
Write-Host '[PASS] DEMO01 usa video EPP real + overlay IA SHADOW; compliance permanece desactivado.' -ForegroundColor Green
