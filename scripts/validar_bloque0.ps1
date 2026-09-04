$ErrorActionPreference = "Stop"
$ProjectPath = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectPath
Write-Host "=== VALIDACION HYS VISION IA - BLOQUE 0 v0.2.0 ===" -ForegroundColor Cyan

$services = @("postgres","redis","minio","backend","frontend")
foreach ($service in $services) {
    $id = docker compose ps -q $service
    if (-not $id) { throw "[FAIL] $service no existe." }
    $status = docker inspect -f '{{.State.Status}}' $id
    $health = docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}n/a{{end}}' $id
    if ($status -ne "running") { throw "[FAIL] $service status=$status" }
    if ($health -ne "healthy" -and $health -ne "n/a") { throw "[FAIL] $service health=$health" }
    Write-Host "[OK] $service status=$status health=$health" -ForegroundColor Green
}

$health = Invoke-RestMethod "http://localhost:8160/health"
if ($health.status -ne "ok") { throw "[FAIL] /health" }
Write-Host "[OK] Backend /health: $($health.status)" -ForegroundColor Green

$ready = Invoke-RestMethod "http://localhost:8160/ready"
if ($ready.status -notin @("ready","degraded")) { throw "[FAIL] /ready" }
Write-Host "[OK] Backend /ready: $($ready.status)" -ForegroundColor Green

$frontend = Invoke-WebRequest "http://localhost:5200" -UseBasicParsing
if ($frontend.StatusCode -ne 200) { throw "[FAIL] Frontend HTTP $($frontend.StatusCode)" }
Write-Host "[OK] Frontend HTTP 200" -ForegroundColor Green

Write-Host "Ejecutando tests backend..." -ForegroundColor Cyan
docker compose exec -T backend sh -lc "PYTHONPATH=/app pytest -q"
if ($LASTEXITCODE -ne 0) { throw "[FAIL] Tests backend" }

Write-Host "[PASS] BASELINE BLOQUE 0 COMPATIBLE EN v0.2.0" -ForegroundColor Green
