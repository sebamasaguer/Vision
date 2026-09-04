$ErrorActionPreference = "Stop"
$ProjectPath = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectPath
Write-Host "=== VALIDACION HYS VISION IA - BLOQUE 1 v0.2.0 ===" -ForegroundColor Cyan

function Wait-Healthy([string]$service, [int]$attempts = 30) {
    for ($i = 1; $i -le $attempts; $i++) {
        $id = docker compose ps -q $service
        if ($id) {
            $status = docker inspect -f '{{.State.Status}}' $id
            $health = docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}n/a{{end}}' $id
            if ($status -eq "running" -and ($health -eq "healthy" -or $health -eq "n/a")) {
                Write-Host "[OK] $service status=$status health=$health" -ForegroundColor Green
                return
            }
            Write-Host "[WAIT] $service status=$status health=$health" -ForegroundColor DarkGray
        }
        Start-Sleep -Seconds 2
    }
    throw "[FAIL] $service no alcanzo estado healthy."
}

@("postgres","redis","minio","backend","camera-worker","frontend") | ForEach-Object { Wait-Healthy $_ }

$health = Invoke-RestMethod "http://localhost:8160/health"
if ($health.status -ne "ok" -or $health.version -ne "0.2.0") { throw "[FAIL] Backend /health version/status inesperado" }
Write-Host "[OK] Backend /health: status=$($health.status) version=$($health.version)" -ForegroundColor Green

$ready = Invoke-RestMethod "http://localhost:8160/ready"
if ($ready.status -notin @("ready","degraded")) { throw "[FAIL] Backend /ready" }
Write-Host "[OK] Backend /ready: $($ready.status)" -ForegroundColor Green

$frontend = Invoke-WebRequest "http://localhost:5200" -UseBasicParsing
if ($frontend.StatusCode -ne 200) { throw "[FAIL] Frontend HTTP $($frontend.StatusCode)" }
Write-Host "[OK] Frontend HTTP 200" -ForegroundColor Green

Write-Host "Verificando migracion Alembic..." -ForegroundColor Cyan
$current = docker compose exec -T backend alembic current
if (($current -join "`n") -notmatch "0002_block1") { throw "[FAIL] Alembic no esta en 0002_block1" }
Write-Host "[OK] Alembic 0002_block1" -ForegroundColor Green

Write-Host "Verificando Demo Camera MP4..." -ForegroundColor Cyan
docker compose exec -T camera-worker ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,width,height,r_frame_rate -of default=nw=1 /demo/demo_camera.mp4
if ($LASTEXITCODE -ne 0) { throw "[FAIL] Demo Camera MP4 no es decodificable" }
Write-Host "[OK] Demo Camera MP4 decodificable" -ForegroundColor Green

docker compose exec -T camera-worker python -m app.worker_health
if ($LASTEXITCODE -ne 0) { throw "[FAIL] camera-worker heartbeat" }
Write-Host "[OK] camera-worker heartbeat" -ForegroundColor Green

Write-Host "Ejecutando tests backend..." -ForegroundColor Cyan
docker compose exec -T backend sh -lc "PYTHONPATH=/app pytest -q"
if ($LASTEXITCODE -ne 0) { throw "[FAIL] Tests backend" }

Write-Host "[PASS] BLOQUE 1 v0.2.0 CAMARAS + RTSP + DEMO CAMERA VALIDADO" -ForegroundColor Green
